@echo off
setlocal
REM Launch GraphAgent GUI

set APPDIR=%~dp0
set ROOT=%APPDIR%\..
echo ============================
echo GraphAgent GUI (Windows)
echo ============================
echo [INFO] Repo root: "%ROOT%"

set PY=%ROOT%\venv\Scripts\python.exe
if not exist "%PY%" (
  echo [ERROR] venv Python not found at "%PY%"
  echo        Activate or create the venv first.
  pause
  exit /b 1
)

REM Ensure the package root is on sys.path and run from there
pushd "%ROOT%"
set PYTHONPATH=%ROOT%

"%PY%" -m app.graphagent.gui %*
set EC=%ERRORLEVEL%

popd

if %EC% neq 0 (
  echo [INFO] GUI exited with an error code %EC%.
  pause
)
endlocal
