param()

# Check if Docker is reachable and provide guidance
try {
    $info = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker CLI executed but daemon may be unreachable." -ForegroundColor Yellow
        Write-Host $info
        Write-Host "Start Docker Desktop (or the Docker daemon) and re-run this script." -ForegroundColor Yellow
        exit 2
    }
    Write-Host "Docker is reachable." -ForegroundColor Green
    docker version --format '{{.Server.Version}}' 2>$null | Out-Null
} catch {
    Write-Host "Docker CLI not found. Install Docker Desktop or ensure 'docker' is on PATH." -ForegroundColor Red
    exit 1
}
