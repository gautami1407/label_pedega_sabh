@echo off
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\pip.exe install -r requirements.txt 2>&1 > install_log.txt
echo Exit code: %errorlevel% >> install_log.txt
