@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo ============================
echo GraphAgent Launcher (Windows)
echo ============================

rem This .bat lives in ...\app\
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

set "VENV_PY=%REPO_ROOT%\venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  set "PYEXE=%VENV_PY%"
) else (
  set "PYEXE=python"
)

if "%LLM_ENDPOINT%"=="" set "LLM_ENDPOINT=http://127.0.0.1:1234/v1"
if "%LLM_MODEL%"=="" set "LLM_MODEL=qwen/qwen2.5-vl-7b"

echo [INFO] Repo root: "%REPO_ROOT%"
echo [INFO] Using:
echo        LLM_ENDPOINT=%LLM_ENDPOINT%
echo        LLM_MODEL=%LLM_MODEL%

rem >>> IMPORTANT: run from the repo root so 'app' is importable
pushd "%REPO_ROOT%"

set "USER_TASK="
if "%~1"=="" (
  set /p USER_TASK=Enter your task: 
)

if not "%USER_TASK%"=="" (
  "%PYEXE%" -m app.graphagent.cli --task "%USER_TASK%"
) else (
  "%PYEXE%" -m app.graphagent.cli %*
)

set "EC=%ERRORLEVEL%"
popd

echo.
echo [INFO] Exit code: %EC%
echo.
pause
endlocal
