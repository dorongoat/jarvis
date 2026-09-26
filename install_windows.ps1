<#
  JARVIS - Windows installer
  התקנה לווינדוס. הרץ ב-PowerShell:  powershell -ExecutionPolicy Bypass -File install_windows.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "== JARVIS setup ==" -ForegroundColor Cyan

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Error "Python 3.10+ is required. Install it from https://www.python.org/downloads/windows/ and tick 'Add python.exe to PATH'."
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .

if (-not (Test-Path "config.yaml")) {
    Copy-Item "config.example.yaml" "config.yaml"
    Write-Host "Created config.yaml - edit it to change voices, apps and the language model." -ForegroundColor Yellow
}

$ollama = (Get-Command ollama -ErrorAction SilentlyContinue)
if ($ollama) {
    Write-Host "Ollama found. Pulling the default model (this can take a few minutes)..." -ForegroundColor Cyan
    ollama pull llama3.1:8b
} else {
    Write-Host "Ollama is not installed. JARVIS will still obey voice commands, but conversation needs a model." -ForegroundColor Yellow
    Write-Host "Install it from https://ollama.com/download then run: ollama pull llama3.1:8b" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Start JARVIS with run_jarvis.bat" -ForegroundColor Green
