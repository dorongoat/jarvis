@echo off
REM Start JARVIS (HUD). Use "run_jarvis.bat --cli" for the console interface.
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m jarvis %*
    goto :eof
)

where pythonw.exe >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pythonw.exe -m jarvis %*
    goto :eof
)

where py.exe >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" py.exe -3 -m jarvis %*
    goto :eof
)

echo Python was not found. Install Python 3.10+ or run install_windows.ps1 first.
pause
exit /b 1
