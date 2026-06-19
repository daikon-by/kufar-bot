# Install kufar-bot on Windows (no Docker)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "==> Project: $Root"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.11+ from https://www.python.org/downloads/"
    Write-Host "Check 'Add python.exe to PATH' during install."
    exit 1
}

$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "==> Python $pyVersion"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Created .env - set BOT_TOKEN and ADMIN_IDS"
}

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating venv..."
    python -m venv .venv
}

Write-Host "==> Installing dependencies..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\pip.exe" install -e .

New-Item -ItemType Directory -Force -Path "data" | Out-Null

Write-Host ""
Write-Host "Done."
Write-Host "  1. Edit .env:  notepad .env"
Write-Host "  2. Test run:   .\run-bot.cmd"
Write-Host "  3. Autostart:  .\register-task.ps1"
