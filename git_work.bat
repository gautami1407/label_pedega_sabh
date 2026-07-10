@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls"
git status > git_status.txt 2>&1
echo --- git log (last 5) >> git_status.txt
git log --oneline -5 >> git_status.txt 2>&1
echo --- diff HEAD >> git_status.txt
git diff --name-only >> git_status.txt 2>&1
