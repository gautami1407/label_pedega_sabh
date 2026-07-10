#!/usr/bin/env python3
"""
Unified server entry point for Label Padegha Sabh.

Set LPS_SERVER=fastapi to start the FastAPI gateway (port 8000).
Set LPS_SERVER=flask (default) to start the legacy Flask app (port 5000).

Usage:
    python run.py

PowerShell:
    $env:LPS_SERVER='fastapi'; python run.py

Command Prompt:
    set LPS_SERVER=fastapi
    python run.py

Git Bash:
    LPS_SERVER=fastapi python run.py
"""
from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

SERVER = os.getenv("LPS_SERVER", "fastapi").lower()
HOST = os.getenv("LPS_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("LPS_PORT", "5000"))
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")


def run_flask() -> None:
    from api import app

    print(f"Starting LPS Flask server on http://{HOST}:{FLASK_PORT} (debug={DEBUG})")
    app.run(debug=DEBUG, port=FLASK_PORT, host=HOST)


def run_fastapi() -> None:
    import uvicorn

    print(f"Starting LPS FastAPI gateway on http://{HOST}:{FASTAPI_PORT} (reload={DEBUG})")
    uvicorn.run(
        "lps.gateway.main:app",
        host=HOST,
        port=FASTAPI_PORT,
        reload=DEBUG,
    )


if __name__ == "__main__":
    if SERVER == "fastapi":
        run_fastapi()
    elif SERVER == "flask":
        run_flask()
    else:
        print(f"ERROR: Unknown LPS_SERVER='{SERVER}'. Use 'flask' or 'fastapi'.")
        sys.exit(1)
