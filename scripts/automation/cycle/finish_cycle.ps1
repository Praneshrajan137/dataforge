<#
.SYNOPSIS
    Collects a completed four-day cycle: gates its patch and opens a pull request.

.DESCRIPTION
    Run this in the EVENING after Day 4 (Thursday), while the machine is demonstrably awake.

    It is a thin wrapper. All the real work is in scripts/automation/apply_and_pr.ps1, invoked with
    -Cycle so it reads cycle/CYCLE.json and cycle/changes.patch. That file is not forked, because
    every control in it was established by a specific failure - the origin/main ancestor check, the
    LF worktree assertion, comparing failure COUNTS rather than exit codes, protected paths enforced
    in the script rather than requested in the prompt, timestamped branch names, and the assertion
    that the commit contains exactly the gated file list. A forked collector would inherit the
    comments describing those fixes without inheriting the fixes.

    What this wrapper adds is the LOCK. On 2026-09-10 the scheduled `publish` (00:00) and `pickup`
    (03:00) were both deferred by a sleeping laptop onto the same wake instant, 09:18:47, and ran
    concurrently: publish deleted handoff artifacts while pickup fetched them, and both were killed
    nine seconds later. The lock makes that specific race impossible regardless of how either is
    launched.

.PARAMETER DryRun
    Do everything except push the branch and open the pull request.

.PARAMETER SkipTests
    Skip the two full-suite passes. Fast plumbing check only; never for a real collection, since the
    test gate is the one that matters most.

.PARAMETER Connection
    Snowflake connection profile used to retrieve artifacts.

.EXAMPLE
    powershell -NoProfile -File scripts\automation\cycle\finish_cycle.ps1
    powershell -NoProfile -File scripts\automation\cycle\finish_cycle.ps1 -DryRun -SkipTests

.NOTES
    Windows PowerShell 5.1. Exit codes are passed through from apply_and_pr.ps1:
      0 PR opened, or nothing to collect
      1 BLOCKED: patch did not apply, touched a protected path, or regressed a gate
      2 RETRIEVAL FAILED: workspace unreachable, state unknown
      3 REFUSED: no state file, cycle not certified, or a previous cycle's artifacts
      4 lock held by another cycle operation
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipTests,
    [string]$Connection = 'dataforge_automation'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Collector = (Resolve-Path (Join-Path $PSScriptRoot '..\apply_and_pr.ps1')).Path
$LockPath  = Join-Path $env:LOCALAPPDATA 'dataforge-automation\cycle.lock'

function Write-Note { param([string]$m) Write-Host "    $m" -ForegroundColor DarkGray }
function Write-Fail { param([string]$m) Write-Host "!!! $m" -ForegroundColor Yellow }

Write-Host "`n==> Collecting the cycle" -ForegroundColor Cyan
Write-Note "collector = $Collector"

# Exclusive lock, released when this process exits even if it is killed, because opening with
# FileShare::None means no second process can open the file at all.
$dir = Split-Path $LockPath -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

$lock = $null
try {
    $lock = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes("finish_cycle pid=$PID at=$(Get-Date -Format o)`n")
    $lock.SetLength(0)
    $lock.Write($bytes, 0, $bytes.Length)
    $lock.Flush()
}
catch {
    Write-Fail 'REFUSING: another cycle operation holds the lock.'
    Write-Note "lock = $LockPath"
    Write-Note 'start_cycle.ps1 is probably running. Wait for it and re-run.'
    exit 4
}

try {
    $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Collector,
              '-Cycle', '-Connection', $Connection)
    if ($DryRun) { $args += '-DryRun' }
    if ($SkipTests) { $args += '-SkipTests' }

    # Run the collector as a child process rather than dot-sourcing it: it calls `exit` with
    # meaningful codes throughout, and dot-sourcing would terminate this wrapper before the lock
    # was released.
    & powershell.exe @args
    $code = $LASTEXITCODE

    $meaning = switch ($code) {
        0       { 'OK (PR opened, or nothing to collect)' }
        1       { 'BLOCKED (patch did not apply, touched a protected path, or regressed a gate)' }
        2       { 'RETRIEVAL FAILED (workspace unreachable) - state UNKNOWN, investigate' }
        3       { 'REFUSED (not certified, missing state, or a previous cycle) - a normal outcome' }
        default { 'UNEXPECTED' }
    }
    Write-Host "`n==> finish_cycle EXIT=$code : $meaning" -ForegroundColor Cyan
    exit $code
}
finally {
    if ($lock) { $lock.Dispose() }
}
