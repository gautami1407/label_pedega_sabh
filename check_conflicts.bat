@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls"

echo === Checking for leftover conflict markers ===
echo.

findstr /r /s "^<<<<<<< " cloud_rangers\project\assets\js\app.js > conflict_check.txt 2>&1
findstr /r /s "^<<<<<<< " cloud_rangers\project\assets\js\scanner.js >> conflict_check.txt 2>&1
findstr /r /s "^<<<<<<< " cloud_rangers\project\backend\app.py >> conflict_check.txt 2>&1
findstr /r /s "^<<<<<<< " cloud_rangers\project\backend\requirements.txt >> conflict_check.txt 2>&1
findstr /r /s "^<<<<<<< " cloud_rangers\project\scanner.html >> conflict_check.txt 2>&1

echo Conflict marker check done. >> conflict_check.txt
type conflict_check.txt
