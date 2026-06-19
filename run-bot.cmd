@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if /i not "%~1"=="_service" if /i not "%~1"=="_run" (
  start "Kufar Bot" cmd /k "%~f0" _run
  exit /b 0
)

set "PY=%CD%\.venv\Scripts\python.exe"
set "LOG_DIR=%CD%\data"
set "CONSOLE_LOG=%LOG_DIR%\console.log"
set "ERR_LOG=%LOG_DIR%\startup-error.log"

if not exist ".env" (
  call :fail "[.env missing] Run setup-windows.cmd or copy .env.example to .env"
)

if not exist "%PY%" (
  call :fail "[no venv] Run setup-windows.cmd"
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

"%PY%" -c "from kufar_bot.config import settings; import sys; sys.exit(0 if settings.is_configured else 1)" 2>nul
if errorlevel 1 (
  call :fail "[config] Set BOT_TOKEN and ADMIN_IDS in .env"
)

"%PY%" -c "import PIL" 2>nul
if errorlevel 1 (
  call :fail "[deps] Run setup-windows.cmd or: .venv\Scripts\pip.exe install -e ."
)

echo Starting kufar-bot...
echo   data\kufar_bot.log  - bot events
echo   data\console.log    - console output (send for debug)
echo   data\setup.log      - install log
echo Press Ctrl+C to stop.
echo.

echo ===== %date% %time% run-bot start =====>> "%CONSOLE_LOG%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "& { $py = '%PY%'; $log = '%CONSOLE_LOG%'; " ^
  "& $py -m kufar_bot.main 2>&1 | Tee-Object -FilePath $log -Append }"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [ERROR] exit code %RC%
  echo [%date% %time%] exit code %RC%>> "%ERR_LOG%"
  echo Send for debug: data\console.log and data\kufar_bot.log
)

if /i "%~1"=="_run" pause
exit /b %RC%

:fail
echo.
echo %~1
echo.
echo [%date% %time%] %~1>> "%ERR_LOG%"
pause
exit /b 1
