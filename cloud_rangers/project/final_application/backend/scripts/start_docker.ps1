param()

# Start Docker Compose for local development with helpful checks
$scriptDir = Split-Path -Parent $PSCommandPath
Set-Location $scriptDir

# Ensure docker CLI and daemon are available
& ..\scripts\check_docker.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Cannot start compose because Docker is unavailable." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Starting Docker Compose (backend/docker-compose.yml)..." -ForegroundColor Cyan
docker compose up --build
