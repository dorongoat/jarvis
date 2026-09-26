<#
  Build a standalone Jarvis.exe into .\dist  (no Python needed on the target machine).
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

.\.venv\Scripts\python.exe -m pip install --upgrade pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean --windowed --name Jarvis `
    --paths src `
    --collect-all edge_tts `
    --collect-all speech_recognition `
    --add-data "config.example.yaml;." `
    jarvis_launcher.py

Write-Host "Built dist\Jarvis\Jarvis.exe" -ForegroundColor Green
