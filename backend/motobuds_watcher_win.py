import os
import sys
import time
import subprocess
import re

DEVICE_PATTERN = re.compile(r"moto\s*buds", re.IGNORECASE)
CHECK_INTERVAL = 2

CANDIDATE_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "builds", "win-unpacked", "Moto Buds Utility.exe"),
    os.path.join(os.path.dirname(__file__), "..", "builds", "win-unpacked", "motobudsdesktoputility.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\motobudsdesktoputility\Moto Buds Utility.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Moto Buds Utility\Moto Buds Utility.exe"),
    os.path.expandvars(r"%ProgramFiles%\Moto Buds Utility\Moto Buds Utility.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Moto Buds Utility\Moto Buds Utility.exe"),
]

def find_app_binary():
    for p in CANDIDATE_PATHS:
        normalized = os.path.normpath(p)
        if os.path.isfile(normalized):
            return normalized
    return None

def is_device_connected():
    try:
        cmd = 'Get-PnpDevice -Class "Bluetooth", "AudioEndpoint" -ErrorAction SilentlyContinue | Where-Object { ($_.FriendlyName -match "moto buds" -or $_.Name -match "moto buds") -and ($_.Status -eq "OK") }'
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd], text=True, timeout=5, creationflags=0x08000000) # CREATE_NO_WINDOW
        return bool(out.strip())
    except Exception:
        return False

def trigger_app():
    time.sleep(2)
    exe = find_app_binary()
    if exe:
        try:
            subprocess.Popen([exe, "--hidden", "--connect"], creationflags=0x08000000) # CREATE_NO_WINDOW
        except Exception:
            pass

def main():
    was_connected = False
    while True:
        connected = is_device_connected()
        if connected and not was_connected:
            was_connected = True
            trigger_app()
        elif not connected and was_connected:
            was_connected = False
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
