# Register Windows Task Scheduler job (run at startup)
# Run as Administrator
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
$RunScript = Join-Path $Root "run-bot.cmd"
$TaskName = "KufarBot"

if (-not (Test-Path $RunScript)) {
    Write-Host "Missing: $RunScript"
    exit 1
}

if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
    Write-Host "Run install-windows.ps1 first"
    exit 1
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed old task"
}

$action = New-ScheduledTaskAction `
    -Execute $RunScript `
    -WorkingDirectory $Root

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Description "Kufar Telegram bot"

Write-Host ""
Write-Host "Task '$TaskName' created."
Write-Host "Start now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Stop:       Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "Logs:       $Root\data\kufar_bot.log"
