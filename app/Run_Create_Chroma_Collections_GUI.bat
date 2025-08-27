@echo off
setlocal EnableExtensions

REM === Discover repo root (this .bat is in ...\app, so parent is the repo) ===
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..") do set "REPO=%%~fI"

REM === Path to your external RAG folder (edit if different) ===
set "RAG_HOME=C:\Users\gmoores\Desktop\AI\RAG"

set "LOG=%REPO%\run_embed_gui_last.log"
echo [%DATE% %TIME%] Starting Create_Chroma_Collections_GUI.bat > "%LOG%"
echo Repo: %REPO% >> "%LOG%"
echo RAG_HOME: %RAG_HOME% >> "%LOG%"
echo Script: %~f0 >> "%LOG%"

REM === Sanity: required script path ===
set "GUI_PY=%REPO%\app\graphagent\create_chroma_collections_gui.py"
if not exist "%GUI_PY%" (
  echo [ERROR] File not found: %GUI_PY%
  echo Make sure you saved the GUI as: app\graphagent\create_chroma_collections_gui.py
  echo See log: %LOG%
  pause
  exit /b 1
)

REM === Ensure packages (so module imports work) ===
if not exist "%REPO%\app\__init__.py" type nul > "%REPO%\app\__init__.py"
if not exist "%REPO%\app\graphagent\__init__.py" type nul > "%REPO%\app\graphagent\__init__.py"
if not exist "%RAG_HOME%\rag_core\__init__.py" (
  if exist "%RAG_HOME%\rag_core" type nul > "%RAG_HOME%\rag_core\__init__.py"
)

REM === Activate venv ===
if not exist "%REPO%\venv\Scripts\activate.bat" (
  echo [ERROR] venv not found at "%REPO%\venv"
  echo Create one and install deps:
  echo   python -m venv "%REPO%\venv"
  echo   "%REPO%\venv\Scripts\pip.exe" install -U gradio chromadb sentence-transformers pyyaml nltk
  echo   "%REPO%\venv\Scripts\python.exe" -c "import nltk; nltk.download('punkt')"
  echo See log: %LOG%
  pause
  exit /b 2
)
call "%REPO%\venv\Scripts\activate.bat" 1>>"%LOG%" 2>&1

REM === Print interpreter for sanity ===
where python 1>>"%LOG%" 2>&1
python -c "import sys; print('PY:', sys.executable)" 1>>"%LOG%" 2>&1

REM === Make rag_core importable ===
set "PYTHONPATH=%REPO%;%RAG_HOME%"

REM === Launch GUI as a module first (preferred) ===
echo Starting Embedding GUI... (see %LOG% for details)
python -m app.graphagent.create_chroma_collections_gui 1>>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

REM === Fallback: run by path if module launch failed ===
if not "%RC%"=="0" (
  echo [WARN] Module launch failed (code %RC%). Trying path-based launch...
  python "%GUI_PY" 1>>"%LOG%" 2>&1
  set "RC=%ERRORLEVEL%"
)

echo.
if "%RC%"=="0" (
  echo [DONE] GUI exited normally.
) else (
  echo [ERROR] GUI exited with code %RC%.
  echo Check log for details: %LOG%
)

echo.
pause
endlocal
