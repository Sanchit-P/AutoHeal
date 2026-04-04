param(
    [ValidateSet("ddos", "leak")]
    [string]$Scenario = "ddos"
)

$ErrorActionPreference = "Stop"

function Ensure-Venv {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Requirements
    )
    if (-not (Test-Path $Path)) {
        Write-Host "Creating venv at $Path"
        python -m venv $Path
    }
    $pip = Join-Path $Path "Scripts\pip.exe"
    if (-not (Test-Path $pip)) {
        throw "pip not found at $pip"
    }
    if (Test-Path $Requirements) {
        Write-Host "Installing requirements from $Requirements"
        & $pip install -r $Requirements --disable-pip-version-check
    }
}

# Backend setup
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$backendVenv = Join-Path $backendDir "venv"
$backendReq = Join-Path $backendDir "requirements.txt"

Ensure-Venv -Path $backendVenv -Requirements $backendReq

$uvicorn = Join-Path $backendVenv "Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) {
    throw "uvicorn not found at $uvicorn"
}

Write-Host "Starting backend (FastAPI) on http://127.0.0.1:8000 ..."
Start-Process -FilePath $uvicorn -ArgumentList "main:app","--host","127.0.0.1","--port","8000","--reload" -WorkingDirectory $backendDir

Start-Sleep -Seconds 2

# Simulation setup
$simDir = Join-Path $repoRoot "SIMULATION"
$simVenv = Join-Path $simDir ".venv"
$simReq = Join-Path $simDir "requirements.txt"

Ensure-Venv -Path $simVenv -Requirements $simReq

$py = Join-Path $simVenv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "python not found at $py"
}

switch ($Scenario) {
    "ddos" { $script = Join-Path $simDir "simulate_ddos.py" }
    "leak" { $script = Join-Path $simDir "simulate_leak.py" }
}

Write-Host "Starting simulation: $Scenario"
Start-Process -FilePath $py -ArgumentList $script -WorkingDirectory $simDir

Write-Host "Both backend and simulation started. Check console windows for logs."
