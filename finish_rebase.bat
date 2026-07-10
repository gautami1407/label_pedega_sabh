@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls"
echo Current dir: %CD%

echo Staging files...
git add cloud_rangers/project/backend/app.py
git add cloud_rangers/project/backend/requirements.txt
git add cloud_rangers/project/assets/js/app.js
git add cloud_rangers/project/assets/js/scanner.js
git add cloud_rangers/project/scanner.html
git add .
echo Stage done.

echo Git status:
git status

echo.
echo Continuing rebase...
set GIT_EDITOR=true
git -c core.editor=true rebase --continue
echo Rebase exit code: %errorlevel%

echo.
echo Final git status:
git status
