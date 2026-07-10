@echo off
echo ============================================
echo  Label Padegha Sabh - Backend Installer
echo ============================================

set VENV=c:\Users\kalal\Desktop\labelpadega\.venv\Scripts
set PIP=%VENV%\pip.exe
set PYTHON=%VENV%\python.exe
set UVICORN=%VENV%\uvicorn.exe

echo.
echo [1/2] Installing dependencies...
%PIP% install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo FAILED to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed OK.

echo.
echo [2/2] Starting FastAPI server on http://127.0.0.1:8000
echo       Open: http://127.0.0.1:8000 in your browser
echo       Press Ctrl+C to stop.
echo.
%UVICORN% app:app --host 127.0.0.1 --port 8000 --reload
