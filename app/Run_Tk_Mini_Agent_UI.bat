@echo off
setlocal
set REPO=C:\Users\gmoores\AI-Tutorial-Codes-Included
set VENV=%REPO%\venv\Scripts\python.exe
set LOG=%REPO%\run_tk_agent_ui_last.log

echo [%DATE% %TIME%] Starting Tk Mini Agent UI > "%LOG%"
echo Repo: %REPO% >> "%LOG%"
echo Script: app\graphagent\tk_mini_agent_ui.py >> "%LOG%"
echo Using Python: %VENV% >> "%LOG%"

cd /d %REPO%
"%VENV%" -m app.graphagent.tk_mini_agent_ui >> "%LOG%" 2>&1

echo ===================================================
echo Tk Mini Agent UI exited. Check log:
echo   %LOG%
echo ===================================================
pause
