<#
.SYNOPSIS
  Starts the Re:Learn backend (FastAPI, :8000) and frontend (Vite, :5173) together. Windows PowerShell 5.1+.

.DESCRIPTION
  First run does the setup for you: creates ml\.venv, installs pinned Python deps, trains the model if
  ml\artifacts\diagnoser.joblib is missing, and runs `npm install` in client\. Ctrl+C stops both servers.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\run.ps1
  powershell -ExecutionPolicy Bypass -File .\run.ps1 -NoBrowser -ApiPort 8000 -WebPort 5173
#>
param(
  [int]$ApiPort = 8000,
  [int]$WebPort = 5173,
  [switch]$NoBrowser,
  [switch]$Retrain   # force re-training the model
)
$ErrorActionPreference = 'Stop'
$Root   = $PSScriptRoot
$Venv   = Join-Path $Root 'ml\.venv'
$VPy    = Join-Path $Venv 'Scripts\python.exe'
$Model  = Join-Path $Root 'ml\artifacts\diagnoser.joblib'
$Client = Join-Path $Root 'client'
$RunDir = Join-Path $Root '.run'
New-Item -ItemType Directory -Force $RunDir | Out-Null

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "ERROR: $m" -ForegroundColor Red; exit 1 }
function Test-Port($p) { [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }

# ---- prerequisites -------------------------------------------------------
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail 'Node.js not found. Install Node 20+ from https://nodejs.org (or: winget install OpenJS.NodeJS.LTS) and re-open PowerShell.' }
foreach ($p in @($ApiPort, $WebPort)) { if (Test-Port $p) { Fail "Port $p is already in use. Stop that program or pass -ApiPort / -WebPort." } }

# ---- python venv + deps --------------------------------------------------
if (-not (Test-Path $VPy)) {
  Step 'Creating Python virtual environment (ml\.venv)'
  $cands = @(
    @{ exe = 'py';      args = @('-3.12') },
    @{ exe = 'python';  args = @() },
    @{ exe = (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'); args = @() }
  )
  $made = $false
  foreach ($c in $cands) {
    $found = Get-Command $c.exe -ErrorAction SilentlyContinue
    if (-not $found -or $found.Source -like '*WindowsApps*') { continue }   # skip the Microsoft Store stub
    & $c.exe @($c.args) -m venv $Venv 2>$null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $VPy)) { $made = $true; break }
  }
  if (-not $made) { Fail 'Python 3.12 not found. Install it (winget install Python.Python.3.12) and re-open PowerShell.' }
  Step 'Installing Python dependencies (first run takes a few minutes)'
  & $VPy -m pip install --quiet --upgrade pip
  & $VPy -m pip install --quiet -r (Join-Path $Root 'server\requirements-dev.txt')
  if ($LASTEXITCODE -ne 0) { Fail 'pip install failed.' }
}

# ---- model ---------------------------------------------------------------
if ($Retrain -or -not (Test-Path $Model)) {
  Step 'Training the diagnoser (about a minute)'
  & $VPy (Join-Path $Root 'ml\train.py')
  if ($LASTEXITCODE -ne 0) { Fail 'Training failed.' }
}

# ---- frontend deps -------------------------------------------------------
if (-not (Test-Path (Join-Path $Client 'node_modules'))) {
  Step 'Installing frontend dependencies (npm install)'
  Push-Location $Client; npm install --no-audit --no-fund; $code = $LASTEXITCODE; Pop-Location
  if ($code -ne 0) { Fail 'npm install failed.' }
}

# ---- start both servers --------------------------------------------------
$procs = @()
function Stop-All {
  foreach ($p in $procs) { if ($p -and -not $p.HasExited) { & taskkill /PID $p.Id /T /F 2>&1 | Out-Null } }
}
try {
  Step "Starting backend on http://localhost:$ApiPort"
  $env:RELEARN_DB = Join-Path $RunDir 'relearn.db'
  $env:CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort"
  $api = Start-Process -FilePath $VPy -WorkingDirectory (Join-Path $Root 'server') -PassThru -WindowStyle Hidden `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") `
    -RedirectStandardOutput (Join-Path $RunDir 'backend.out.log') -RedirectStandardError (Join-Path $RunDir 'backend.err.log')
  $procs += $api

  Step "Starting frontend on http://localhost:$WebPort"
  $env:VITE_API_URL = "http://localhost:$ApiPort"
  $web = Start-Process -FilePath 'cmd.exe' -WorkingDirectory $Client -PassThru -WindowStyle Hidden `
    -ArgumentList @('/c', 'npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', "$WebPort", '--strictPort') `
    -RedirectStandardOutput (Join-Path $RunDir 'frontend.out.log') -RedirectStandardError (Join-Path $RunDir 'frontend.err.log')
  $procs += $web

  # wait until both answer (probe 127.0.0.1 explicitly: Windows PowerShell tries IPv6 for 'localhost' first and times out)
  $deadline = (Get-Date).AddSeconds(90)
  $apiUp = $false; $webUp = $false
  while ((Get-Date) -lt $deadline -and -not ($apiUp -and $webUp)) {
    if ($api.HasExited) { Fail "Backend exited early. See .run\backend.err.log`n$(Get-Content (Join-Path $RunDir 'backend.err.log') -Tail 15 -ErrorAction SilentlyContinue | Out-String)" }
    if ($web.HasExited) { Fail "Frontend exited early. See .run\frontend.err.log`n$(Get-Content (Join-Path $RunDir 'frontend.out.log') -Tail 15 -ErrorAction SilentlyContinue | Out-String)" }
    try { if ((Invoke-RestMethod "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2).model_loaded) { $apiUp = $true } } catch {}
    try { if ((Invoke-WebRequest "http://127.0.0.1:$WebPort/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $webUp = $true } } catch {}
    Start-Sleep -Milliseconds 700
  }
  if (-not ($apiUp -and $webUp)) { Fail 'Servers did not become ready within 90 s. Check the logs in .run\' }

  Write-Host ''
  Write-Host "  Re:Learn is running" -ForegroundColor Green
  Write-Host "    App      http://localhost:$WebPort"
  Write-Host "    API docs http://localhost:$ApiPort/docs"
  Write-Host "    Logs     .run\*.log      (Ctrl+C stops everything)"
  Write-Host ''
  if (-not $NoBrowser) { Start-Process "http://localhost:$WebPort" }

  while ($true) {
    Start-Sleep -Seconds 1
    if ($api.HasExited) { Fail 'Backend stopped unexpectedly. See .run\backend.err.log' }
    if ($web.HasExited) { Fail 'Frontend stopped unexpectedly. See .run\frontend.out.log' }
  }
}
finally {
  Stop-All
  Write-Host 'Stopped.' -ForegroundColor Yellow
}
