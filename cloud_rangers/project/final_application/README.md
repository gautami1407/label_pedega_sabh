# Label Padegha Sabh — final_application Startup Guide

## Correct Folder Structure

Root path for this app:
- `cloud_rangers/cloud_rangers/project/final_application`

Backend folder:
- `cloud_rangers/cloud_rangers/project/final_application/backend`

Frontend folder:
- `cloud_rangers/cloud_rangers/project/final_application/frontend`

## Python Environments

There are two separate virtual environments in this project:
- `cloud_rangers/cloud_rangers/project/final_application/.venv` — workspace root Python 3.14 environment
- `cloud_rangers/cloud_rangers/project/final_application/backend/venv` — backend environment using Python 3.11.9

### Recommended runtime
- Use `backend/venv` for backend development and runtime.
- The backend code is validated against Python 3.11 and the backend virtualenv is already created.

## Backend Startup

### Activate backend venv

PowerShell:
```powershell
cd "cloud_rangers\cloud_rangers\project\final_application\backend"
.\venv\Scripts\Activate.ps1
```

Command Prompt:
```cmd
cd /d "cloud_rangers\cloud_rangers\project\final_application\backend"
venv\Scripts\activate.bat
```

Git Bash:
```bash
cd "cloud_rangers/cloud_rangers/project/final_application/backend"
source venv/Scripts/activate
```

### Install requirements

PowerShell / CMD / Git Bash:
```bash
python -m pip install -r requirements.txt
```

### Start backend

PowerShell:
```powershell
$env:LPS_SERVER = 'fastapi'
$env:LPS_HOST = '0.0.0.0'
$env:FASTAPI_PORT = '8000'
python run.py
```

Command Prompt:
```cmd
set LPS_SERVER=fastapi
set LPS_HOST=0.0.0.0
set FASTAPI_PORT=8000
python run.py
```

Git Bash:
```bash
LPS_SERVER=fastapi LPS_HOST=0.0.0.0 FASTAPI_PORT=8000 python run.py
```

### Backend server endpoints

- FastAPI gateway: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Frontend Startup

This app is a static frontend located in `frontend/`.
You can open `frontend/index.html` directly in a browser, or serve it with the backend via the FastAPI static route.

## Docker Startup

Docker Compose is available at `backend/docker-compose.yml`.

### Run Docker Compose

PowerShell / CMD:
```powershell
cd "cloud_rangers\cloud_rangers\project\final_application\backend"
docker compose up --build
```

Git Bash:
```bash
cd "cloud_rangers/cloud_rangers/project/final_application/backend"
docker compose up --build
```

### Required services
- `postgres` on port `5432`
- `mongodb` on port `27017`
- `redis` on port `6379`
- `backend` on port `8000`

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in values.

Minimum required values for local development:
- `LPS_SERVER=fastapi`
- `LPS_HOST=0.0.0.0`
- `FASTAPI_PORT=8000`
- `DATABASE_URL=postgresql://lps:lps_dev_password@localhost:5432/lps`
- `MONGODB_URL=mongodb://localhost:27017/lps`
- `REDIS_URL=redis://localhost:6379/0`

## Common Troubleshooting

- If `docker compose` fails with a pipe error, start Docker Desktop and ensure the Docker engine is running.
- On Windows, do not use `&&` in PowerShell commands; use separate lines or `;`.
- If the backend cannot import `lps`, make sure you are inside `backend/` and using `venv`.
- If PostgreSQL, Redis, or MongoDB are unavailable, start Docker Compose first.

### Docker helper scripts

- `backend\scripts\check_docker.ps1` — verifies the Docker CLI is installed and the daemon is reachable.
- `backend\scripts\start_docker.ps1` — runs the check then starts `docker compose up --build` for the backend stack.

PowerShell example to run the helper:
```powershell
cd "cloud_rangers\cloud_rangers\project\final_application\backend\scripts"
.\check_docker.ps1
.\start_docker.ps1
```

## Verification Checklist

- [ ] `backend/venv` is activated
- [ ] `python -m pip install -r backend/requirements.txt` succeeds
- [ ] `docker compose up --build` starts `postgres`, `mongodb`, `redis`, and `backend`
- [ ] `http://localhost:8000/health` returns status OK
- [ ] `frontend/index.html` loads successfully from browser
