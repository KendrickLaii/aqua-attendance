# Starts the isolated inventory test environment (DB: attendance_inventory, API: 8010, Web: 5173).
# Does not touch apps/api/.env or the main `attendance` database.
# Usage (repo root):  powershell -ExecutionPolicy Bypass -File .\start-inventory.ps1 [-Seed]
param([switch]$Seed)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"
$py = Join-Path $api ".venv\Scripts\python.exe"
$dbName = "attendance_inventory"
$apiPort = 8010

$dbUrl = "postgresql+asyncpg://attendance:attendance@localhost:5432/$dbName"
$dbUrlSync = "postgresql+psycopg://attendance:attendance@localhost:5432/$dbName"

Push-Location $root
docker compose up -d db
Pop-Location

Write-Host "Waiting for Postgres..."
for ($i = 0; $i -lt 30; $i++) {
    docker exec aqua-attendance-db-1 pg_isready -U attendance 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}

$exists = docker exec aqua-attendance-db-1 psql -U attendance -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$dbName'"
if (-not $exists) {
    Write-Host "Creating database $dbName"
    docker exec aqua-attendance-db-1 psql -U attendance -d postgres -c "CREATE DATABASE $dbName"
    $Seed = $true
}

$apiEnv = "`$env:PYTHONUTF8='1'; `$env:APP_DISABLE_BACKGROUND_TASKS='1'; `$env:DATABASE_URL='$dbUrl'; `$env:DATABASE_URL_SYNC='$dbUrlSync'; `$env:CORS_ORIGINS='http://localhost:5173,http://localhost:5174'"

Push-Location $api
$env:PYTHONUTF8 = "1"; $env:DATABASE_URL = $dbUrl; $env:DATABASE_URL_SYNC = $dbUrlSync
& $py -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed" }
if ($Seed) { & $py seed.py | Out-Null }
Pop-Location

Start-Process powershell -ArgumentList "-NoExit", "-Command", "$apiEnv; cd '$api'; & '$py' -m uvicorn app.main:app --reload --port $apiPort"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:VITE_ATTENDANCE_API_URL='http://localhost:$apiPort/api'; cd '$web'; npm run dev"

if ($Seed) {
    Write-Host "Waiting for API to seed demo data..."
    for ($i = 0; $i -lt 30; $i++) {
        try { Invoke-RestMethod "http://localhost:$apiPort/api/health" | Out-Null; break } catch { Start-Sleep -Seconds 2 }
    }
    Push-Location $api
    & $py seed_inventory.py | Select-Object -Last 15
    Pop-Location
}

Write-Host ""
Write-Host "Web: http://localhost:5173/attendance/login   API docs: http://localhost:$apiPort/docs"
Write-Host "Login: demo_admin / Demo1234!   (admin / admin123)"
