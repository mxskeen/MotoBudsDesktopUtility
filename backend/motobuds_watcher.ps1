# Moto Buds Auto-Connect Background Watcher for Windows
# Monitors Bluetooth PnP status and automatically starts / reconnects Moto Buds Utility in tray

$DeviceNamePattern = "moto buds"
$CheckIntervalSeconds = 2
$WasConnected = $false

function Find-AppExecutable {
    $candidates = @(
        "$PSScriptRoot\..\builds\win-unpacked\Moto Buds Utility.exe",
        "$PSScriptRoot\..\builds\win-unpacked\motobudsdesktoputility.exe",
        "$env:LOCALAPPDATA\Programs\motobudsdesktoputility\Moto Buds Utility.exe",
        "$env:LOCALAPPDATA\Programs\Moto Buds Utility\Moto Buds Utility.exe",
        "$env:ProgramFiles\Moto Buds Utility\Moto Buds Utility.exe",
        "$env:ProgramFiles(x86)\Moto Buds Utility\Moto Buds Utility.exe",
        "$PSScriptRoot\..\Moto Buds Utility.exe"
    )

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return (Resolve-Path $path).Path
        }
    }
    return $null
}

Write-Host "[Moto Buds Watcher] Service started. Monitoring for Bluetooth connections..."

while ($true) {
    try {
        # Check if Moto Buds device is currently connected and active
        $devices = Get-PnpDevice -Class "Bluetooth", "AudioEndpoint" -ErrorAction SilentlyContinue |
            Where-Object { 
                ($_.FriendlyName -match $DeviceNamePattern -or $_.Name -match $DeviceNamePattern) -and 
                ($_.Status -eq "OK") 
            }

        $isConnected = ($devices -ne $null -and $devices.Count -gt 0)

        if ($isConnected -and -not $WasConnected) {
            Write-Host "[Moto Buds Watcher] Moto Buds connected! Launching application..."
            $WasConnected = $true

            # Brief delay for Windows Bluetooth RFCOMM driver and audio endpoints to be ready
            Start-Sleep -Seconds 2

            $exe = Find-AppExecutable
            if ($exe) {
                Write-Host "[Moto Buds Watcher] Executing: $exe --hidden --connect"
                Start-Process -FilePath $exe -ArgumentList "--hidden", "--connect" -WindowStyle Hidden
            } else {
                Write-Warning "[Moto Buds Watcher] Could not find Moto Buds Utility executable."
            }
        }
        elseif (-not $isConnected -and $WasConnected) {
            Write-Host "[Moto Buds Watcher] Moto Buds disconnected."
            $WasConnected = $false
        }
    } catch {
        # Silently ignore transient PnP query errors
    }

    Start-Sleep -Seconds $CheckIntervalSeconds
}
