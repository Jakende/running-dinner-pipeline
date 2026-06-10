@echo off
setlocal
cd /d "%~dp0"

if "%PORT%"=="" set PORT=8765
if "%OPEN_BROWSER%"=="" set OPEN_BROWSER=1

set VENV_PYTHON=.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
  python -m venv .venv
)

"%VENV_PYTHON%" -m pip install -r requirements.txt

set URL=http://127.0.0.1:%PORT%
echo Starting Running Dinner Web App at %URL%
if not "%OPEN_BROWSER%"=="0" start "" "%URL%"
"%VENV_PYTHON%" -m uvicorn web_app:app --host 127.0.0.1 --port %PORT%
