@echo off
setlocal EnableDelayedExpansion

REM -------- CONFIG --------
set "REPO=C:\Users\gmoores\AI-Tutorial-Codes-Included"
set "RAG_HOME=C:\Users\gmoores\Desktop\AI\RAG"
set "VENV=%REPO%\venv"
set "LOG=%REPO%\run_tk_ui_last.log"
REM ------------------------

echo [%%DATE%% %%TIME%%] Starting Run_Tk_UI.bat  > "%LOG%"
echo Repo: %REPO%                                   >> "%LOG%"
echo RAG_HOME: %RAG_HOME%                           >> "%LOG%"
echo Log: %LOG%                                     >> "%LOG%"

cd /d "%REPO%"
if errorlevel 1 (
  echo Failed to cd into %REPO% >> "%LOG%"
  echo Failed to cd into %REPO%
  pause
  exit /b 1
)

REM Prefer venv python
set "PYTHON=%VENV%\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo venv python not found, falling back to system python >> "%LOG%"
  for %%P in (python.exe) do set "PYTHON=%%~$PATH:P"
)

echo Using PYTHON: %PYTHON% >> "%LOG%"
echo %PYTHON%

REM Make sure env is set for imports
set "RAG_HOME=%RAG_HOME%"
set "PYTHONPATH=%REPO%;%RAG_HOME%"

REM Run module with full stdout/stderr captured
echo Launching Tk UI... >> "%LOG%"
"%PYTHON%" -X faulthandler -u -m app.graphagent.tk_mini_ui >> "%LOG%" 2>&1

set "EC=%ERRORLEVEL%"
echo ExitCode=%EC% >> "%LOG%"
echo.
echo Starting Local RAG Tk UI... (see %LOG% for details)
echo ExitCode=%EC%
echo.
pause
