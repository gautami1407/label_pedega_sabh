@echo off
cd /d %~dp0
call venv\Scripts\activate.bat
set LPS_SERVER=fastapi
set LPS_HOST=0.0.0.0
set FASTAPI_PORT=8000
python run.py
