<#
.SYNOPSIS
    Starts a four-day, twenty-session automation cycle by freezing and publishing its inputs.

.DESCRIPTION
    Run this in the EVENING before Day 1 (Monday), while the machine is demonstrably awake.

    It is deliberately NOT a scheduled task. On 2026-09-10 the previous design had `publish` at
    00:00 and `pickup` at 03:00; the laptop was asleep for both, Task Scheduler's
    StartWhenAvailable deferred them, and they collapsed onto the SAME wake instant (09:18:47).
    They then ran concurrently - publish deleting handoff artifacts while pickup fetched them -
    and both were killed nine seconds later (0xC000013A). A cycle whose sessions run 00:30-03:30
    makes that worse, not better. A command a human runs at a time the machine is on removes the
    whole class. The lock file below removes the concurrency half of it regardless.

    What it does:
      1. Takes an exclusive lock, so this can never overlap finish_cycle.ps1.
      2. Builds a source snapshot from `git archive HEAD` with LF line endings, and ASSERTS LF.
      3. Clears the previous cycle's artifacts from the stage.
      4. Uploads the snapshot, TASK.md, RESEARCH_BRIEF.md, ASSIGNMENTS.md and a fresh CYCLE.json.

    THE SNAPSHOT IS FROZEN FOR THE WHOLE CYCLE, deliberately. Its md5 is the lineage key every one
    of the twenty sessions validates, so refreshing it on Day 2 would invalidate Day 1's findings.
    Do not run this again mid-cycle; that is what -Force exists to make you think about.

.PARAMETER TaskFile
    The standing directive for this cycle. Defaults to scripts/automation/cycle/TASK.md.

.PARAMETER CycleId
    Defaults to ISO year and week, e.g. 2026-W38.

.PARAMETER Connection
    Snowflake connection profile. Defaults to the headless key-pair profile.

.PARAMETER Force
    Start a new cycle even though the staged one is unfinished or uncollected. This DISCARDS the
    current cycle's artifacts, including any patch that was never turned into a pull request.

.EXAMPLE
    powershell -NoProfile -File scripts\automation\cycle\start_cycle.ps1

.NOTES
    Windows PowerShell 5.1. `pwsh` is not installed on this machine.
    Exit codes: 0 published; 1 refused (bad input, or an unfinished cycle without -Force);
                2 Snowflake failure; 4 lock held by another process.
#>
[CmdletBinding()]
param(
    [string]$TaskFile,
    [string]$CycleId,
    [string]$Connection = 'dataforge_automation',
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot  = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Workspace = 'USER$PRANESH07.PUBLIC.DEFAULT$'
$StagePath = "snow://workspace/$Workspace/versions/live"
$WorkDir   = Join-Path $env:TEMP 'dataforge-automation'
$Snow      = Join-Path $env:LOCALAPPDATA 'dataforge-automation\venv\Scripts\snow.exe'
$LockPath  = Join-Path $env:LOCALAPPDATA 'dataforge-automation\cycle.lock'

if (-not $TaskFile) { $TaskFile = Join-Path $PSScriptRoot 'TASK.md' }
if (-not $CycleId) {
    # The cycle is identified by the DATE OF ITS MONDAY, which is when Day 1 fires.
    #
    # An earlier version used an ISO week label via [System.Globalization.ISOWeek]. That type does
    # not exist in .NET Framework, only in .NET Core, so it threw TypeNotFound under Windows
    # PowerShell 5.1 - and `pwsh` is not installed on this machine. A date also avoids ISO week's
    # year-boundary edge cases entirely, sorts correctly as a string, and tells a human reading a
    # log exactly which week's work they are looking at.
    $d = Get-Date
    $daysUntilMonday = ([int][System.DayOfWeek]::Monday - [int]$d.DayOfWeek + 7) % 7
    $CycleId = $d.Date.AddDays($daysUntilMonday).ToString('yyyy-MM-dd')
}

function Write-Step { param([string]$m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host "    $m" -ForegroundColor DarkGray }
function Write-Fail { param([string]$m) Write-Host "!!! $m" -ForegroundColor Yellow }

# Native tools write progress to stderr on success, which $ErrorActionPreference='Stop' turns into
# a terminating NativeCommandError. Judge by exit code only, never by whether stderr had content.
function Invoke-Native {
    param([Parameter(Mandatory)][string]$File, [string[]]$Arguments = @())
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $File @Arguments 2>&1 | Out-String
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $out }
    }
    finally { $ErrorActionPreference = $prev }
}

function Invoke-Sql {
    param([Parameter(Mandatory)][string]$Query)
    return Invoke-Native -File $Snow -Arguments @('sql', '-c', $Connection, '--format', 'json', '-q', $Query)
}

# Exclusive lock held for the life of this process. Opening with no sharing means a second process
# cannot open it at all, so the lock is released even if we are killed - which matters here, since
# being killed mid-run is exactly what happened to the design this replaces.
$LockStream = $null
function Enter-CycleLock {
    $dir = Split-Path $LockPath -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    try {
        $script:LockStream = [System.IO.File]::Open(
            $LockPath, [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $bytes = [System.Text.Encoding]::UTF8.GetBytes("start_cycle pid=$PID at=$(Get-Date -Format o)`n")
        $script:LockStream.SetLength(0)
        $script:LockStream.Write($bytes, 0, $bytes.Length)
        $script:LockStream.Flush()
        return $true
    }
    catch {
        Write-Fail 'REFUSING: another cycle operation holds the lock.'
        Write-Note "lock = $LockPath"
        Write-Note 'This is the guard against publish and collect running at the same time.'
        return $false
    }
}
function Exit-CycleLock {
    if ($script:LockStream) { $script:LockStream.Dispose(); $script:LockStream = $null }
}

Write-Step "Starting cycle $CycleId"
Write-Note "repo       = $RepoRoot"
Write-Note "task       = $TaskFile"
Write-Note "connection = $Connection"

if (-not (Enter-CycleLock)) { exit 4 }

try {
    if (-not (Test-Path $Snow)) { Write-Fail "Snowflake CLI not found at $Snow"; exit 2 }
    if (-not (Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir | Out-Null }

    # --- 1. Inputs ---------------------------------------------------------------------
    if (-not (Test-Path $TaskFile)) {
        Write-Fail "No task file at $TaskFile"
        exit 1
    }
    $taskText = Get-Content $TaskFile -Raw
    if (-not $taskText -or $taskText.Trim().Length -lt 200) {
        # A standing directive for twenty sessions is not a one-liner. Refusing here is cheaper
        # than twenty sessions refusing individually at 00:30.
        Write-Fail 'Task file is shorter than 200 characters. Refusing to start a cycle on it.'
        exit 1
    }

    $briefFile = Join-Path $PSScriptRoot 'RESEARCH_BRIEF.md'
    $assignFile = Join-Path $PSScriptRoot 'ASSIGNMENTS.md'
    foreach ($f in @($briefFile, $assignFile)) {
        if (-not (Test-Path $f)) { Write-Fail "Missing required cycle input: $f"; exit 1 }
    }

    # --- 2. Refuse to clobber an unfinished cycle --------------------------------------
    $ls = Invoke-Sql -Query "LS '$StagePath/'"
    if ($ls.ExitCode -ne 0) {
        Write-Fail 'Could not list the workspace stage; state unknown.'
        Write-Note $ls.Output
        exit 2
    }
    $staged = @([regex]::Matches($ls.Output, '"name"\s*:\s*"([^"]+)"') |
                ForEach-Object { $_.Groups[1].Value })
    $hasPatch = @($staged | Where-Object { $_ -match 'changes\.patch$' }).Count -gt 0
    if ($hasPatch -and -not $Force) {
        Write-Fail 'REFUSING: the stage still holds a changes.patch from the previous cycle.'
        Write-Note 'That work was never collected into a pull request. Either run'
        Write-Note 'finish_cycle.ps1 first, or re-run with -Force to discard it deliberately.'
        exit 1
    }
    if ($hasPatch) { Write-Note 'Discarding the previous cycle patch (-Force)' }

    # --- 3. Snapshot, LF, from HEAD ----------------------------------------------------
    Write-Step 'Building the frozen source snapshot from HEAD'

    # HEAD, never the working tree, so another session's uncommitted work never ships into an
    # unattended cycle. `training/` was moved to `archive/`; git archive FAILS OUTRIGHT on a
    # pathspec matching nothing, so this list must stay in step with the tree.
    $paths = @(
        'dataforge', 'docs', 'tests', 'scripts', 'specs', 'packages', 'dataforge-mcp',
        'playground', 'archive', 'constitutions', 'requirements', 'fixtures',
        'benchmark_results', 'eval/thresholds', 'eval/preregistration', 'eval/results',
        '.github', 'pyproject.toml', 'Makefile', 'uv.lock', 'test_map.json', '*.md'
    )

    $snapshot = Join-Path $WorkDir 'dataforge-snapshot.tar.gz'
    if (Test-Path $snapshot) { Remove-Item $snapshot -Force }

    # -c core.autocrlf=false is LOAD-BEARING. git archive applies the same eol conversion as a
    # checkout, so without it the snapshot is CRLF while the gating worktree is LF, and every
    # patch that MODIFIES an existing file is rejected with a misleading "patch does not apply".
    # Patches that only ADD files still work, so the pipeline looks healthy while being unable to
    # deliver a modification. Measured 2026-09-09: test_map.json carried 868 CRLF.
    $archiveArgs = @('-c', 'core.autocrlf=false', '-C', $RepoRoot, 'archive',
                     '--format=tar.gz', '-o', $snapshot, 'HEAD') + $paths
    $res = Invoke-Native -File 'git' -Arguments $archiveArgs
    if ($res.ExitCode -ne 0 -or -not (Test-Path $snapshot)) {
        Write-Fail "git archive failed (exit $($res.ExitCode))"
        Write-Note $res.Output
        exit 1
    }

    $entries = @((Invoke-Native -File 'tar' -Arguments @('-tzf', $snapshot)).Output -split "`r?`n" |
                 Where-Object { $_.Trim() })
    Write-Note "snapshot = $((Get-Item $snapshot).Length) bytes, $($entries.Count) entries"

    if (@($entries | Where-Object { $_ -match '^data/' }).Count -gt 0) {
        Write-Fail 'Snapshot contains entries under data/. Refusing to publish.'
        exit 1
    }

    # Verify the property, do not trust the flag: this failure is invisible at publish time and
    # only surfaces days later, at the gate, as a misleading corrupt-patch error.
    $probeDir = Join-Path $WorkDir 'eolprobe'
    Remove-Item $probeDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $probeDir -Force | Out-Null
    $null = Invoke-Native -File 'tar' -Arguments @('-xzf', $snapshot, '-C', $probeDir, 'PRODUCT.md', 'test_map.json')
    $eolBad = @()
    foreach ($pf in @('PRODUCT.md', 'test_map.json')) {
        $pp = Join-Path $probeDir $pf
        if (-not (Test-Path $pp)) { continue }
        $pb = [System.IO.File]::ReadAllBytes($pp)
        $crlf = 0
        for ($i = 1; $i -lt $pb.Length; $i++) { if ($pb[$i] -eq 10 -and $pb[$i - 1] -eq 13) { $crlf++ } }
        if ($crlf -gt 0) { $eolBad += "$pf ($crlf CRLF)" }
    }
    Remove-Item $probeDir -Recurse -Force -ErrorAction SilentlyContinue
    if ($eolBad.Count -gt 0) {
        Write-Fail "Snapshot has CRLF line endings: $($eolBad -join ', '). Refusing."
        Write-Note 'Check that git archive is invoked with -c core.autocrlf=false.'
        exit 1
    }
    Write-Note 'snapshot line endings = LF (matches the gating worktree)'

    $snapMd5 = (Get-FileHash -Path $snapshot -Algorithm MD5).Hash.ToLower()
    $taskSha = (Get-FileHash -Path $TaskFile -Algorithm SHA256).Hash.ToLower()
    $briefSha = (Get-FileHash -Path $briefFile -Algorithm SHA256).Hash.ToLower()
    Write-Note "snapshot md5 = $snapMd5"
    Write-Note "task sha256  = $taskSha"

    # --- 4. Clear the previous cycle ---------------------------------------------------
    Write-Step "Clearing the previous cycle from the stage"

    # Both the flat legacy artifacts and the cycle/ subtree. Clearing matters as much as
    # publishing: without it, a day whose sessions all die leaves the previous cycle's artifacts
    # in place for the next day to read as current, and the manifest check is the only thing
    # standing between that and confidently wrong work.
    $prefixes = @(
        'cycle/', '01-explore.md', '02-plan.md', '03-code.md', '04-verify.md',
        'changes.patch', 'COMMIT_MSG.txt', 'daily-review.md', 'MANIFEST.json',
        '.mypy_cache/', '.ruff_cache/', '.pytest_cache/', '.benchmarks/', '.hypothesis/'
    )
    foreach ($p in $prefixes) {
        $r = Invoke-Sql -Query "REMOVE '$StagePath/$p'"
        # REMOVE exits 0 whether or not anything was there, so this cannot honestly report which
        # files existed. Say what was attempted.
        if ($r.ExitCode -ne 0) { Write-Note "  $p : REMOVE failed (exit $($r.ExitCode))" }
        else { Write-Note "  $p : cleared" }
    }

    # --- 5. CYCLE.json -----------------------------------------------------------------
    Write-Step 'Writing CYCLE.json'
    $cycle = [ordered]@{
        cycle_id       = $CycleId
        started_utc    = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        task_sha256    = $taskSha
        brief_sha256   = $briefSha
        snapshot_md5   = $snapMd5
        snapshot_bytes = (Get-Item $snapshot).Length
        head_sha       = (Invoke-Native -File 'git' -Arguments @('-C', $RepoRoot, 'rev-parse', 'HEAD')).Output.Trim()
        published_from = $RepoRoot
        schedule       = [ordered]@{
            timezone = 'Asia/Kolkata'
            slots    = @('00:30', '01:15', '02:00', '02:45', '03:30')
            days     = [ordered]@{ '1' = 'explore (Mon)'; '2' = 'plan (Tue)'; '3' = 'code (Wed)'; '4' = 'verify (Thu)' }
        }
        sessions       = @()
        certified      = $false
    }
    $cyclePath = Join-Path $WorkDir 'CYCLE.json'
    # ASCII-safe UTF-8 with NO BOM: a BOM makes json.load() in the sandbox fail with
    # "Expecting value: line 1 column 1", which reads as malformed JSON rather than an encoding
    # problem, and every session would then refuse for the wrong reason.
    [System.IO.File]::WriteAllText($cyclePath, ($cycle | ConvertTo-Json -Depth 6),
        (New-Object System.Text.UTF8Encoding($false)))
    Write-Note "head_sha = $($cycle.head_sha)"

    # --- 6. Upload ---------------------------------------------------------------------
    Write-Step 'Uploading the frozen cycle inputs'
    # AUTO_COMPRESS=FALSE throughout: the tarball is already gzipped, and gzipping the text files
    # would make sessions fetch <name>.gz and find nothing at the name they expect.
    $uploads = @(
        @{ Local = $snapshot;   Dest = "$StagePath/";       Name = 'dataforge-snapshot.tar.gz' },
        @{ Local = $TaskFile;   Dest = "$StagePath/";       Name = 'TASK.md' },
        @{ Local = $briefFile;  Dest = "$StagePath/";       Name = 'RESEARCH_BRIEF.md' },
        @{ Local = $assignFile; Dest = "$StagePath/cycle/"; Name = 'ASSIGNMENTS.md' },
        @{ Local = $cyclePath;  Dest = "$StagePath/cycle/"; Name = 'CYCLE.json' }
    )
    foreach ($u in $uploads) {
        $src = ((Resolve-Path $u.Local).Path -replace '\\', '/')
        $r = Invoke-Sql -Query "PUT 'file://$src' '$($u.Dest)' AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        if ($r.ExitCode -ne 0) {
            Write-Fail "PUT failed for $($u.Name) (exit $($r.ExitCode))"
            Write-Note $r.Output
            exit 2
        }
        Write-Note "uploaded $($u.Name)"
    }

    # --- 7. Confirm --------------------------------------------------------------------
    Write-Step 'Confirming the stage'
    $ls2 = Invoke-Sql -Query "LS '$StagePath/'"
    if ($ls2.ExitCode -ne 0) { Write-Fail 'Uploads reported success but the stage cannot be listed.'; exit 2 }
    $names = @([regex]::Matches($ls2.Output, '"name"\s*:\s*"([^"]+)"') |
               ForEach-Object { ($_.Groups[1].Value -split '/')[-1] })
    Write-Note "stage contains: $($names -join ', ')"

    $missing = @($uploads | Where-Object { $names -notcontains $_.Name } | ForEach-Object { $_.Name })
    if ($missing.Count -gt 0) { Write-Fail "Missing after upload: $($missing -join ', ')"; exit 2 }

    Write-Step "Cycle $CycleId is published"
    Write-Note 'Day 1 EXPLORE fires Monday at 00:30, 01:15, 02:00, 02:45 and 03:30 Asia/Kolkata.'
    Write-Note 'Do NOT run this again mid-cycle: the snapshot md5 is the lineage key all 20 sessions check.'
    Write-Note 'After Thursday, collect with: scripts\automation\cycle\finish_cycle.ps1'
    exit 0
}
finally {
    Exit-CycleLock
}
