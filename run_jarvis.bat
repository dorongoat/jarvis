@echo off
REM Start JARVIS (HUD). Use "run_jarvis.bat --cli" for the console interface.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment missing. Run install_windows.ps1 first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m jarvis %*
endlocal
