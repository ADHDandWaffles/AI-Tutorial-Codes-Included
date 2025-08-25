@echo off
setlocal
echo ============================
echo GraphAgent Flow GUI (Windows)
echo ============================

set ROOT=%~dp0\..
set PY=%ROOT%\venv\Scripts\python.exe

if not exist "%PY%" (
  echo [ERROR] venv Python not found at "%PY%"
  pause
  exit /b 1
)

pushd "%ROOT%"
set PYTHONPATH=%ROOT%
"%PY%" -m app.graphagent.flow_gui %*
popd
endlocal
