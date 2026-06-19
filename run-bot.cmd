@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist ".env" (
  echo [.env missing] Copy .env.example to .env and set BOT_TOKEN, ADMIN_IDS
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [not installed] Run install-windows.ps1 first
  exit /b 1
)

".venv\Scripts\python.exe" -m kufar_bot.main
