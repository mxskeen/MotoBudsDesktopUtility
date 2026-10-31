@echo off
setlocal
echo =====================================================
echo   Uninstalling Moto Buds Auto-Connect Watcher (Windows)
echo =====================================================
echo.

schtasks /Delete /TN "MotoBudsWatcher" /F >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq *motobuds_watcher*" >nul 2>&1

echo [SUCCESS] Moto Buds Watcher scheduled task removed.
pause
