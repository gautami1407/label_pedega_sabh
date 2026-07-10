#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/Scripts/activate
export LPS_SERVER=fastapi
export LPS_HOST=0.0.0.0
export FASTAPI_PORT=8000
python run.py
