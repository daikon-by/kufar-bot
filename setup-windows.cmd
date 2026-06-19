@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem ============================================================
rem  Kufar Bot — клонирование, venv, запуск
rem  setup-windows.cmd [C:\kufar-bot]
rem  Лог: data\setup.log
rem ============================================================

set "REPO=https://github.com/daikon-by/kufar-bot.git"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=C:\kufar-bot"

if exist "%~dp0.git" (
  set "ROOT=%~dp0"
  goto :main
)

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git не найден: https://git-scm.com/download/win
  pause
  exit /b 1
)

if not exist "%TARGET%\.git" (
  echo ==^> git clone %REPO%
  echo     -^> %TARGET%
  git clone "%REPO%" "%TARGET%"
  if errorlevel 1 (
    echo [ERROR] git clone failed
    pause
    exit /b 1
  )
) else (
  echo ==^> git pull %TARGET%
  pushd "%TARGET%"
  git pull --ff-only
  popd
)

set "ROOT=%TARGET%\"

:main
cd /d "%ROOT%"
if not exist "data" mkdir "data"
set "SETUP_LOG=%CD%\data\setup.log"

call :log "======== setup started ========"
call :log "folder: %CD%"

set "PY=%CD%\.venv\Scripts\python.exe"
set "PIP=%CD%\.venv\Scripts\pip.exe"

if not exist "%PY%" (
  call :log "creating .venv"
  echo ==^> Creating .venv...
  python -m venv .venv >> "%SETUP_LOG%" 2>&1
  if errorlevel 1 (
    call :log "ERROR: python -m venv failed"
    echo [ERROR] Не удалось создать .venv. Python в PATH?
    pause
    exit /b 1
  )
)

call :log "pip install -e ."
echo ==^> Installing dependencies...
"%PIP%" install -e . >> "%SETUP_LOG%" 2>&1
if errorlevel 1 (
  call :log "ERROR: pip install failed"
  echo [ERROR] pip install failed. See data\setup.log
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" copy /Y ".env.example" ".env" >nul
  call :log "created .env from .env.example"
)

"%PY%" -c "from kufar_bot.config import settings; import sys; sys.exit(0 if settings.is_configured else 1)" 2>nul
if errorlevel 1 (
  echo.
  echo Fill .env: BOT_TOKEN and ADMIN_IDS
  echo Log: data\setup.log
  notepad ".env"
  pause
  "%PY%" -c "from kufar_bot.config import settings; import sys; sys.exit(0 if settings.is_configured else 1)" 2>nul
  if errorlevel 1 (
    call :log "ERROR: .env not configured"
    pause
    exit /b 1
  )
)

call :log "starting bot"
echo.
echo ==^> Starting bot...
echo     App log:    data\kufar_bot.log
echo     Console:    data\console.log
echo     Setup log:  data\setup.log
echo.

call "%CD%\run-bot.cmd" _run
set "RC=%ERRORLEVEL%"
call :log "bot exited code %RC%"
exit /b %RC%

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1>> "%SETUP_LOG%"
exit /b 0
