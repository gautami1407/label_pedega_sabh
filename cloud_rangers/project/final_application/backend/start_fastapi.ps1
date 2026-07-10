$scriptDir = Split-Path -Parent $PSCommandPath
Set-Location $scriptDir
$python = Join-Path $scriptDir 'venv\Scripts\python.exe'
$env:LPS_SERVER = 'fastapi'
$env:LPS_HOST = '0.0.0.0'
$env:FASTAPI_PORT = '8000'
& $python run.py
