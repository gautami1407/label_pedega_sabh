@echo off
title Label Padegha Sabh — Backend Server
echo ================================================
echo   Label Padegha Sabh — Starting Backend Server
echo ================================================
echo.

set VENV=c:\Users\kalal\Desktop\labelpadega\.venv\Scripts

echo [1/2] Installing / verifying dependencies...
%VENV%\pip.exe install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check your Python/venv setup.
    pause
    exit /b 1
)
echo Dependencies OK.
echo.

echo [2/2] Starting FastAPI server...
echo.
echo   App URL  : http://127.0.0.1:8000
echo   Scanner  : http://127.0.0.1:8000/scanner.html
echo   Dashboard: http://127.0.0.1:8000/dashboard.html
echo.
echo   Press Ctrl+C to stop the server.
echo.

%VENV%\uvicorn.exe app:app --host 127.0.0.1 --port 8000 --reload

pause
