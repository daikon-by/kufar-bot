@echo off
rem Запуск из любой папки: клонирует в C:\kufar-bot и вызывает setup-windows.cmd
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=C:\kufar-bot"
set "REPO=https://github.com/daikon-by/kufar-bot.git"

if exist "%~dp0setup-windows.cmd" (
  call "%~dp0setup-windows.cmd" "%TARGET%"
  exit /b %ERRORLEVEL%
)

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git not found
  pause
  exit /b 1
)

if not exist "%TARGET%\.git" (
  git clone "%REPO%" "%TARGET%"
  if errorlevel 1 exit /b 1
)

call "%TARGET%\setup-windows.cmd"
exit /b %ERRORLEVEL%
