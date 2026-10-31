@echo off
setlocal
echo ===================================================
echo   Installing Moto Buds Auto-Connect Watcher (Windows)
echo ===================================================
echo.

set SCRIPT_PATH=%~dp0motobuds_watcher.ps1

echo Registering Windows Task Scheduler logon task...
schtasks /Create /SC ONLOGON /TN "MotoBudsWatcher" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%SCRIPT_PATH%\"" /RL LIMITED /F

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Moto Buds Watcher has been installed and scheduled!
    echo Starting the watcher service for this session...
    start "" /B powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT_PATH%"
    echo.
    echo Moto Buds will now automatically connect in the background whenever turned on.
) else (
    echo.
    echo [ERROR] Failed to register Task Scheduler task. Please run as Administrator if required.
)

pause
