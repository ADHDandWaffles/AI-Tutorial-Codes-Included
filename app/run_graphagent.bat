@echo off
setlocal ENABLEEXTENSIONS
chcp 65001 >nul

echo ============================
echo GraphAgent Launcher (Windows)
echo ============================

REM --- Compute repo root = parent of this script's folder ---
set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
echo [INFO] Repo root: "%REPO_ROOT%"

REM --- Paths ---
set "VENV_DIR=%REPO_ROOT%\venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "ACTIVATE=%VENV_DIR%\Scripts\activate.bat"

REM --- Verify venv ---
if not exist "%PYTHON_EXE%" (
  echo [ERROR] venv Python not found at "%PYTHON_EXE%"
  echo        Create/repair the venv:
  echo        python -m venv "%VENV_DIR%"
  echo        "%VENV_DIR%\Scripts\activate.bat"
  echo        pip install -U pip openai
  goto :PAUSE_AND_EXIT
)

REM --- Activate venv ---
call "%ACTIVATE%"
if errorlevel 1 (
  echo [ERROR] Failed to activate venv at "%VENV_DIR%"
  goto :PAUSE_AND_EXIT
)

REM --- Default env for local LLM (only set if not already set) ---
if not defined LLM_ENDPOINT set "LLM_ENDPOINT=http://127.0.0.1:1234/v1"
if not defined LLM_API_KEY  set "LLM_API_KEY=sk-local"
if not defined LLM_MODEL    set "LLM_MODEL=qwen/qwen2.5-vl-7b"

echo [INFO] Using:
echo        LLM_ENDPOINT=%LLM_ENDPOINT%
echo        LLM_MODEL=%LLM_MODEL%

REM --- Change to repo root BEFORE running modules so "app" is importable ---
pushd "%REPO_ROOT%"

REM --- Quick import self-test (Windows-friendly) ---
"%PYTHON_EXE%" -c "import sys; print('Python:', sys.version); import app, openai; print('Import check: OK')"
if errorlevel 1 goto :PAUSE_AND_EXIT

REM --- Mode selection: no args or --gui -> GUI; else -> CLI with args forwarded ---
if "%~1"=="" goto RUN_GUI
if /I "%~1"=="--gui" (shift & goto RUN_GUI) else goto RUN_CLI

:RUN_CLI
echo [INFO] Launching CLI: python -m app.cli %*
"%PYTHON_EXE%" -m app.cli %*
set "RC=%ERRORLEVEL%"
goto :DONE

:RUN_GUI
echo [INFO] Launching GUI: python -m app.gui
"%PYTHON_EXE%" -m app.gui
set "RC=%ERRORLEVEL%"
goto :DONE

:DONE
popd
echo [INFO] Exit code: %RC%
if "%~1"=="" (
  echo.
  pause
)
endlocal
exit /b %RC%

:PAUSE_AND_EXIT
echo.
pause
endlocal
exit /b 1
