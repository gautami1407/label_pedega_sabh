@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls\cloud_rangers\project\backend"
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -X utf8 gemini_test.py > gemini_test_out.txt 2>&1
type gemini_test_out.txt
