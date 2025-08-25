@echo off
setlocal

REM Absolute path to your repo venv python:
set "PY=C:\Users\gmoores\AI-Tutorial-Codes-Included\venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Venv python not found at "%PY%"
  echo Repair it:
  echo   cd C:\Users\gmoores\AI-Tutorial-Codes-Included
  echo   py -3.13 -m venv venv
  echo   .\venv\Scripts\python.exe -m pip install --upgrade pip
  pause
  exit /b 1
)

cd /d "%~dp0"
echo ============================
echo GraphAgent Launcher (Windows)
echo ============================
echo [INFO] Repo root: "%CD%\.."
echo [INFO] Using:
echo        LLM_ENDPOINT=%LLM_ENDPOINT%
echo        LLM_MODEL=%LLM_MODEL%

REM If no arguments, run interactive mode
if "%~1"=="" (
  "%PY%" -m app.cli --interactive
) else (
  "%PY%" -m app.cli %*
)

echo.
pause
endlocal
