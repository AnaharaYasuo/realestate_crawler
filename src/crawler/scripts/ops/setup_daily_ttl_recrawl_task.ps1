# PowerShell script to install Daily TTL-Expired Direct-URL Recrawl as a headless Windows Scheduled Task
# Follows AGENTS.md Principle 1 (Strictly Headless) & Principle 1.1 (Local Production Execution)
param(
    [string]$TriggerTime = "08:30"
)

$TaskName = "RealEstateCrawler_DailyTtlRecrawl"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$ScriptPath = Join-Path $RepoRoot "src\crawler\scripts\ops\run_ttl_expired_recrawl.py"
$PythonExe = if ($env:PYTHON_PATH -and (Test-Path $env:PYTHON_PATH)) {
    $env:PYTHON_PATH
} else {
    (Get-Command python).Source
}
$PythonwExe = Join-Path (Split-Path $PythonExe -Parent) "pythonw.exe"
$RunnerExe = if (Test-Path $PythonwExe) { $PythonwExe } else { $PythonExe }

$Action = New-ScheduledTaskAction `
    -Execute $RunnerExe `
    -Argument "`"$ScriptPath`" --ensure-local-prod-infra --ttl-days 14" `
    -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
$Settings = New-ScheduledTaskSettingsSet `
    -Hidden `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily 14-day TTL-expired direct-URL crawl & delisted flagging (Local Production Execution)"

Write-Host "SUCCESS: Registered headless daily task '$TaskName' at $TriggerTime JST."
