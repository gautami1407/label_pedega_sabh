@echo off
cd /d "c:\Users\kalal\Desktop\labelpadega\404-girls\cloud_rangers\project\backend"
c:\Users\kalal\Desktop\labelpadega\.venv\Scripts\python.exe -X utf8 list_models.py > list_models_out.txt 2>&1
type list_models_out.txt
