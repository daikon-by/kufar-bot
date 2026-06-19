@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "OUT=%CD%\data\support-bundle.txt"
if not exist "data" (
  echo No data folder. Run setup-windows.cmd first.
  pause
  exit /b 1
)

echo Collecting logs to data\support-bundle.txt ...

(
  echo ===== KUFAR BOT SUPPORT BUNDLE =====
  echo Time: %date% %time%
  echo Folder: %CD%
  echo.

  if exist "data\setup.log" (
    echo ===== setup.log =====
    type "data\setup.log"
    echo.
  )

  if exist "data\startup-error.log" (
    echo ===== startup-error.log =====
    type "data\startup-error.log"
    echo.
  )

  if exist "data\console.log" (
    echo ===== console.log =====
    type "data\console.log"
    echo.
  )

  if exist "data\kufar_bot.log" (
    echo ===== kufar_bot.log last 500 lines =====
    powershell -NoProfile -Command "Get-Content -Path 'data\kufar_bot.log' -Tail 500 -Encoding UTF8"
    echo.
  )
) > "%OUT%" 2>&1

echo Done: %OUT%
pause
