@echo off
REM === Setup Python Virtual Environment ===

:: Go to your project folder
cd /d C:\Users\gmoores\AI-Tutorial-Codes-Included

:: Create the virtual environment (only runs if venv doesn’t exist yet)
if not exist venv (
    python -m venv venv
)

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Upgrade pip (recommended)
python -m pip install --upgrade pip

:: Install Jupyter (so you can run notebooks)
pip install jupyter

echo.
echo ✅ Environment ready! Launching Jupyter...
call venv\Scripts\activate.bat
.\venv\Scripts\jupyter.exe notebook


