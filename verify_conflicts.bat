@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls"
echo === Checking for conflict markers ===
set FOUND=0

findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\backend\app.py" >nul 2>&1 && echo CONFLICT in app.py && set FOUND=1
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\backend\requirements.txt" >nul 2>&1 && echo CONFLICT in requirements.txt && set FOUND=1
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\assets\js\app.js" >nul 2>&1 && echo CONFLICT in app.js && set FOUND=1
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\assets\js\scanner.js" >nul 2>&1 && echo CONFLICT in scanner.js && set FOUND=1
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\scanner.html" >nul 2>&1 && echo CONFLICT in scanner.html && set FOUND=1

if %FOUND%==0 echo ALL CLEAR - no conflict markers found

echo.
echo === Git status ===
git status

echo.
echo === Staging all files ===
git add cloud_rangers/project/backend/app.py
git add cloud_rangers/project/backend/requirements.txt
git add cloud_rangers/project/assets/js/app.js
git add cloud_rangers/project/assets/js/scanner.js
git add cloud_rangers/project/scanner.html
git add .

echo.
echo === Continuing rebase ===
git rebase --continue

echo.
echo === Final status ===
git status
