# Обновление бота на Windows (git pull + переустановка)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$taskName = "KufarBot"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "==> Останавливаю задачу $taskName..."
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

if (Test-Path ".git") {
    Write-Host "==> git pull..."
    git pull --ff-only
}

Write-Host "==> Обновляю зависимости..."
& ".\.venv\Scripts\pip.exe" install -e .

if ($task) {
    Write-Host "==> Запускаю задачу $taskName..."
    Start-ScheduledTask -TaskName $taskName
}

Write-Host "Готово."
