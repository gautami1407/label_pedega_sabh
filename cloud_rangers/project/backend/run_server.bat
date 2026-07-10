@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls\cloud_rangers\project\backend"
echo Starting server...
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 2> crash_log.txt
echo Server exited with code: %errorlevel%
echo.
echo === CRASH LOG ===
type crash_log.txt
pause
