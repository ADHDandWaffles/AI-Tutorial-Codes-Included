@echo off
setlocal
echo ============================
echo GraphAgent Flow Diagram
echo ============================
set ROOT=%~dp0..
set PY=%ROOT%\venv\Scripts\python.exe

echo [INFO] Using Python: "%PY%"
echo [INFO] Module: app.graphagent.core

pushd "%ROOT%"
"%PY%" -m app.graphagent.diagram
set RC=%ERRORLEVEL%
popd

if %RC%==0 (
  echo.
  echo [OK] Done.
) else (
  echo.
  echo [ERROR] Exit code: %RC%
)
pause
endlocal
