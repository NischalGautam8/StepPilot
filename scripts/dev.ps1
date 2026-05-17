# StepPilot (Cursor-King) Launcher Script
# Starts both the FastAPI backend and the Tauri dev frontend, with automatic dependency checking and cleanup.

$ErrorActionPreference = "Stop"

# Get root directory of the repository
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
$BackendDir = Join-Path $RootDir "backend"
$VenvDir = Join-Path $BackendDir "venv"
$PythonPath = Join-Path $VenvDir "Scripts\python.exe"
$PipPath = Join-Path $VenvDir "Scripts\pip.exe"

Write-Host "👑 Starting StepPilot (Cursor-King) Dev Launcher" -ForegroundColor Magenta
Write-Host "==============================================" -ForegroundColor Magenta

# 1. Ensure Python environment is ready
Write-Host "`n=== [1/4] Checking Python Backend Environment ===" -ForegroundColor Cyan
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating python virtual environment in: $VenvDir..." -ForegroundColor Yellow
    Start-Process -FilePath "python" -ArgumentList "-m venv venv" -WorkingDirectory $BackendDir -Wait -NoNewWindow
}

if (-not (Test-Path $PythonPath)) {
    Write-Error "Could not find Python executable at $PythonPath. Please ensure Python is installed and in your environment PATH."
}

Write-Host "Installing Python dependencies (this might take a few moments on first run)..." -ForegroundColor Yellow
Start-Process -FilePath $PipPath -ArgumentList "install --upgrade pip" -WorkingDirectory $BackendDir -Wait -NoNewWindow
Start-Process -FilePath $PipPath -ArgumentList "install -r requirements.txt" -WorkingDirectory $BackendDir -Wait -NoNewWindow

# 2. Ensure Node dependencies are installed
Write-Host "`n=== [2/4] Checking Frontend Dependencies ===" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $RootDir "node_modules"))) {
    Write-Host "Installing Node.js packages..." -ForegroundColor Yellow
    Start-Process -FilePath "npm" -ArgumentList "install" -WorkingDirectory $RootDir -Wait -NoNewWindow
}

# 3. Start the Python FastAPI backend
Write-Host "`n=== [3/4] Starting FastAPI Backend (Port 8765) ===" -ForegroundColor Cyan
Write-Host "Starting sidecar server at ws://127.0.0.1:8765..." -ForegroundColor Yellow
$BackendProcess = Start-Process -FilePath $PythonPath -ArgumentList "main.py" -WorkingDirectory $BackendDir -PassThru -NoNewWindow

# Process cleanup handler
$Cleanup = {
    Write-Host "`n🧹 Cleaning up dev processes..." -ForegroundColor Yellow
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Write-Host "Stopping FastAPI backend process (ID: $($BackendProcess.Id))..." -ForegroundColor DarkYellow
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✨ Dev environment cleanly shut down." -ForegroundColor Green
}

# 4. Start Tauri Development server inside try-finally block to ensure cleanup
try {
    Write-Host "`n=== [4/4] Starting Tauri Desktop Application ===" -ForegroundColor Cyan
    Set-Location $RootDir
    npm run tauri dev
}
catch {
    Write-Host "`nAn error occurred while launching or running the application: $_" -ForegroundColor Red
}
finally {
    & $Cleanup
}
