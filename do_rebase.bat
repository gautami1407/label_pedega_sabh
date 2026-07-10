@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls"

echo === Checking conflict markers === > rebase_out.txt 2>&1
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\backend\app.py" >> rebase_out.txt 2>&1 && echo CONFLICT: app.py >> rebase_out.txt
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\backend\requirements.txt" >> rebase_out.txt 2>&1 && echo CONFLICT: requirements.txt >> rebase_out.txt
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\assets\js\app.js" >> rebase_out.txt 2>&1 && echo CONFLICT: app.js >> rebase_out.txt
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\assets\js\scanner.js" >> rebase_out.txt 2>&1 && echo CONFLICT: scanner.js >> rebase_out.txt
findstr /c:"<<<<<<< HEAD" "cloud_rangers\project\scanner.html" >> rebase_out.txt 2>&1 && echo CONFLICT: scanner.html >> rebase_out.txt

echo === Staging files === >> rebase_out.txt
git add cloud_rangers/project/backend/app.py >> rebase_out.txt 2>&1
git add cloud_rangers/project/backend/requirements.txt >> rebase_out.txt 2>&1
git add cloud_rangers/project/assets/js/app.js >> rebase_out.txt 2>&1
git add cloud_rangers/project/assets/js/scanner.js >> rebase_out.txt 2>&1
git add cloud_rangers/project/scanner.html >> rebase_out.txt 2>&1
git add . >> rebase_out.txt 2>&1

echo === Git status before continue === >> rebase_out.txt
git status >> rebase_out.txt 2>&1

echo === Rebase continue === >> rebase_out.txt
set GIT_EDITOR=true
git rebase --continue >> rebase_out.txt 2>&1

echo === Final status === >> rebase_out.txt
git status >> rebase_out.txt 2>&1

type rebase_out.txt
