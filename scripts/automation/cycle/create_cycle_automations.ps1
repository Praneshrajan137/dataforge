<#
.SYNOPSIS
    Creates the twenty AGENT TASKs of the four-day cycle: five sessions on each of four days.

.DESCRIPTION
    Twenty tasks, but only FIVE prompt files. Each day's five sessions share one phase prompt,
    assembled at create time from prompts/_preamble.md plus prompts/day<N>-*.md. The
    session-specific brief is NOT in the prompt: it lives in ASSIGNMENTS.md, which ships inside the
    snapshot, so a session reads its own objective and - importantly - its boundaries from there.

    WHY NOT TWENTY PROMPTS
    Twenty copies of the environment facts drift, and a drifted copy in an unattended prompt is
    invisible until a fire misbehaves. Prompts are baked into the task definition at create time, so
    a drifted copy also cannot be fixed by editing a file. One preamble, four phase bodies, and one
    assignments file is the smallest structure that keeps each session's brief specific while
    keeping the shared facts in one place.

    WHY THE BRIEFS MUST BE SPECIFIC
    Anthropic measured their own subagents duplicating work and leaving gaps when briefs were
    vague - one explored the 2021 automotive chip crisis while two others duplicated 2025
    supply-chain work - and their fix was an objective, an output format, and explicit boundaries.
    ASSIGNMENTS.md carries all three for each of the twenty.

    SCHEDULE
    Five slots 45 minutes apart: 00:30, 01:15, 02:00, 02:45, 03:30 Asia/Kolkata. Each fire has a
    ~15 minute wall plus 30 minutes of slack, so no two sessions of a day can overlap. Day gating
    is by cron day-of-week: Mon explore, Tue plan, Wed code, Thu verify.

    MODEL
    All twenty run claude-opus-5 explicitly rather than "auto", so the cycle's reasoning quality is
    a property of the configuration and not of whatever the orchestrator ranks highest that week.
    The id is confirmed valid: the retired COCO_ROUTINE_PROJECT payload carried
    "model":"claude-opus-5" verbatim.

    ACCESS MODE
    Created --without-read-only --force, i.e. fully READ-WRITE, at the owner's explicit
    instruction. Recorded plainly: no session needs SQL DML - all twenty work on the sandbox
    filesystem, which succeeds under the read-only default - so the flag grants twenty unattended
    fires per week the ability to run DML on any database with an ACCOUNTADMIN token and no human
    present. To tighten it, drop the two flags below and re-run with -Recreate.

.PARAMETER DryRun
    Print the generated task metadata and SQL for each task without creating anything.

.PARAMETER Recreate
    Drop each task before creating it. Required after editing any prompt file, because prompts are
    baked in at create time and editing the .md on disk does NOT change a live automation.

.PARAMETER OnlyDay
    Create just one day's five sessions. For iterating on a single phase prompt.

.PARAMETER Connection
    Connection the tasks are created on. Must be the account that owns the workspace stage,
    otherwise the CLI refuses: CREATE AGENT TASK runs on the SQL connection while a fire's thread
    is only visible through the agent connection's account.

.EXAMPLE
    powershell -NoProfile -File scripts\automation\cycle\create_cycle_automations.ps1 -DryRun
    powershell -NoProfile -File scripts\automation\cycle\create_cycle_automations.ps1 -Recreate

.NOTES
    Windows PowerShell 5.1. Requires the `cortex` CLI on PATH and signed in.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Recreate,
    [ValidateRange(1, 4)][int]$OnlyDay,
    [string]$Connection = 'AEGIS15',
    [string]$Model = 'claude-opus-5'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$PromptDir = Join-Path $PSScriptRoot 'prompts'
$Workspace = 'USER$PRANESH07.PUBLIC.DEFAULT$'
$Timezone  = 'Asia/Calcutta'   # this machine is UTC+05:30; the CLI default is UTC
$BuildDir  = Join-Path $env:TEMP 'dataforge-automation\cycle-prompts'

function Write-Step { param([string]$m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host "    $m" -ForegroundColor DarkGray }
function Write-Fail { param([string]$m) Write-Host "!!! $m" -ForegroundColor Yellow }

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

# Slot minute-of-day, expressed as cron minute and hour. Kept as data so the five slots are stated
# exactly once and cannot drift between this script, ASSIGNMENTS.md and the preamble.
$slots = @(
    [pscustomobject]@{ N = 1; Min = 30; Hour = 0; At = '00:30' }
    [pscustomobject]@{ N = 2; Min = 15; Hour = 1; At = '01:15' }
    [pscustomobject]@{ N = 3; Min = 0;  Hour = 2; At = '02:00' }
    [pscustomobject]@{ N = 4; Min = 45; Hour = 2; At = '02:45' }
    [pscustomobject]@{ N = 5; Min = 30; Hour = 3; At = '03:30' }
)

$days = @(
    [pscustomobject]@{ N = 1; Phase = 'EXPLORE'; Dow = 1; DayName = 'Mon'; File = 'day1-explore.md' }
    [pscustomobject]@{ N = 2; Phase = 'PLAN';    Dow = 2; DayName = 'Tue'; File = 'day2-plan.md' }
    [pscustomobject]@{ N = 3; Phase = 'CODE';    Dow = 3; DayName = 'Wed'; File = 'day3-code.md' }
    [pscustomobject]@{ N = 4; Phase = 'VERIFY';  Dow = 4; DayName = 'Thu'; File = 'day4-verify.md' }
)

if ($OnlyDay) { $days = @($days | Where-Object { $_.N -eq $OnlyDay }) }

# --- Assemble one prompt per phase -----------------------------------------------------
Write-Step 'Assembling phase prompts'

$preamblePath = Join-Path $PromptDir '_preamble.md'
if (-not (Test-Path $preamblePath)) { throw "Missing preamble at $preamblePath" }
$preamble = (Get-Content $preamblePath -Raw).TrimEnd()

if (-not (Test-Path $BuildDir)) { New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null }

foreach ($d in $days) {
    $bodyPath = Join-Path $PromptDir $d.File
    if (-not (Test-Path $bodyPath)) { throw "Missing phase prompt at $bodyPath" }
    $combined = $preamble + "`n`n" + (Get-Content $bodyPath -Raw)

    # A prompt containing '$$' collides with the SQL body delimiter in the generated
    # CREATE AGENT TASK. Fail here with a clear message rather than at Snowflake with a syntax
    # error that gives no hint which prompt is at fault.
    if ($combined -match '\$\$') {
        throw "Prompt for day $($d.N) contains '`$`$', which collides with the SQL body delimiter."
    }

    $out = Join-Path $BuildDir ("day{0}.md" -f $d.N)
    [System.IO.File]::WriteAllText($out, $combined, (New-Object System.Text.UTF8Encoding($false)))
    $d | Add-Member -NotePropertyName PromptPath -NotePropertyValue $out
    Write-Note ("day {0} {1,-8} {2,6} chars  {3}" -f $d.N, $d.Phase, $combined.Length, $d.DayName)
}

# --- Create ----------------------------------------------------------------------------
Write-Step ("Creating {0} tasks on model {1}" -f ($days.Count * $slots.Count), $Model)

$failed = New-Object System.Collections.Generic.List[string]
$created = 0

foreach ($d in $days) {
    foreach ($s in $slots) {
        $name = 'DF_D{0}_{1}_S{2}' -f $d.N, $d.Phase, $s.N
        $cron = '{0} {1} * * {2}' -f $s.Min, $s.Hour, $d.Dow

        if ($Recreate -and -not $DryRun) {
            $drop = Invoke-Native -File 'cortex' -Arguments @('automation', 'drop', $name, '--connection', $Connection)
            if ($drop.ExitCode -eq 0) { Write-Note "$name : dropped before recreate" }
        }

        $args = @(
            'automation', 'create',
            '--connection', $Connection,
            '--name', $name,
            '--prompt-file', $d.PromptPath,
            '--schedule', $cron,
            '--timezone', $Timezone,
            '--workspace', $Workspace,
            # Persisting /workspace across fires IS the handoff mechanism. With --no-workspace the
            # mount is ephemeral per fire and every session would find its inputs missing.
            '--model', $Model,
            '--without-read-only', '--force'
        )
        if ($DryRun) { $args += '--dry-run' }

        $r = Invoke-Native -File 'cortex' -Arguments $args
        if ($r.ExitCode -ne 0) {
            Write-Fail "$name : create failed (exit $($r.ExitCode))"
            Write-Note $r.Output
            $failed.Add($name)
        }
        else {
            $created++
            Write-Note ("{0,-24} {1,-12} {2}" -f $name, $cron, $s.At)
            if ($DryRun -and $s.N -eq 1) {
                # Print one payload per day so the model id and mount can be eyeballed without
                # drowning in twenty near-identical blobs. Note the JSON is ESCAPED inside the
                # generated SQL body, so the pattern must tolerate backslashes - an unescaped
                # pattern silently reports NOT FOUND for a payload that is perfectly correct.
                $modelSeen = if ($r.Output -match 'model\\?":\\?"([a-z0-9\-\.]+)') { $Matches[1] } else { 'NOT FOUND' }
                $rssSeen = if ($r.Output -match 'restricted_session_scope\\?":\\?"([a-z_$A-Z]+)') { $Matches[1] } else { 'NOT FOUND' }
                $mountSeen = if ($r.Output -match 'mount_path\\?":\\?"([^\\"]+)') { $Matches[1] } else { 'NOT FOUND' }
                Write-Note "  payload: model=$modelSeen rss=$rssSeen mount=$mountSeen"
            }
        }
    }
}

if ($failed.Count -gt 0) {
    Write-Fail "Failed: $($failed -join ', ')"
    exit 1
}

Write-Step "Done - $created task(s)"
if (-not $DryRun) {
    Write-Note 'Verify with: cortex automation list --connection AEGIS15'
    Write-Note 'Inspect one with: cortex automation doctor DF_D1_EXPLORE_S1 --connection AEGIS15'
    Write-Note 'Inputs must be published BEFORE Monday 00:30 by start_cycle.ps1.'
}
exit 0
