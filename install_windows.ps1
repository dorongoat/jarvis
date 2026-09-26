<#
  JARVIS - Windows installer
  התקנה לווינדוס. הרץ ב-PowerShell:  powershell -ExecutionPolicy Bypass -File install_windows.ps1
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "== JARVIS setup ==" -ForegroundColor Cyan

function Resolve-Python {
    $probe = "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')"
    foreach ($candidate in @("py -3", "python", "python3")) {
        $parts = $candidate.Split(" ")
        $name = $parts[0]
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
        try {
            if ($parts.Count -gt 1) {
                $exe = & $name $parts[1] "-c" $probe 2>$null
            } else {
                $exe = & $name "-c" $probe 2>$null
            }
        } catch {
            continue
        }
        if ($exe) { $exe = ($exe | Select-Object -Last 1).Trim() }
        if ($exe -and (Test-Path $exe) -and $exe -notlike "*WindowsApps*") {
            return $exe
        }
    }
    return $null
}

$python = Resolve-Python
if (-not $python) {
    Write-Host "Python 3.10+ was not found (the Microsoft Store stub does not count)." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/windows/ and tick 'Add python.exe to PATH'," -ForegroundColor Yellow
    Write-Host "then open a NEW PowerShell window and run this script again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Using Python: $python" -ForegroundColor DarkCyan

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    try { & $python -m venv .venv } catch { }
}

if (Test-Path $venvPython) {
    $target = $venvPython
} else {
    $target = $python
    Write-Host "Could not create a virtual environment here (Windows often blocks writes inside" -ForegroundColor Yellow
    Write-Host "Documents/OneDrive - see 'Controlled folder access'). Installing into $python instead." -ForegroundColor Yellow
    Write-Host "If that also fails, copy this folder to a plain path such as C:\jarvis and rerun." -ForegroundColor Yellow
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $target -m pip install --upgrade pip
& $target -m pip install -r requirements.txt
try {
    & $target -m pip install -e .
} catch {
    Write-Host "Editable install failed; run_jarvis.bat falls back to src/ on PYTHONPATH." -ForegroundColor Yellow
}

if (-not (Test-Path "config.yaml")) {
    try {
        Copy-Item "config.example.yaml" "config.yaml"
        Write-Host "Created config.yaml - edit it to change voices, apps and the language model." -ForegroundColor Yellow
    } catch {
        Write-Host "Could not write config.yaml here; JARVIS will run with built-in defaults." -ForegroundColor Yellow
    }
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
