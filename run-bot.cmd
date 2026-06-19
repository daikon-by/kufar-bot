@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>&1
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

if not exist ".env" call :fail ".env missing - run setup-windows.cmd"
if not exist "%PY%" call :fail "no venv - run setup-windows.cmd"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

"%PY%" -c "from kufar_bot.config import settings; import sys; sys.exit(0 if settings.is_configured else 1)" 2>nul
if errorlevel 1 call :fail "Set BOT_TOKEN and ADMIN_IDS in .env"

"%PY%" -c "import PIL" 2>nul
if errorlevel 1 call :fail "Run setup-windows.cmd or pip install -e ."

echo Starting kufar-bot. Logs: data\kufar_bot.log data\console.log
echo Press Ctrl+C to stop.
echo.

echo ===== %date% %time% start =====>> "%CONSOLE_LOG%"
"%PY%" -m kufar_bot.main 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%CONSOLE_LOG%' -Append"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo [ERROR] exit code %RC%
  echo [%date% %time%] exit %RC%>> "%ERR_LOG%"
)

if /i "%~1"=="_run" pause
exit /b %RC%

:fail
echo [ERROR] %~1
echo [%date% %time%] %~1>> "%ERR_LOG%"
pause
exit /b 1
