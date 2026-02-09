@echo off
REM HarvestPilot Pi Status Check - Using Plink with automatic password
REM This is the ONLY way to get password automation on Windows without prompts

set PI_HOST=192.168.1.233
set PI_USER=pi
set PI_PASSWORD=149246116

echo ======================================================================
echo HarvestPilot Pi Status Check - Automated Password
echo ======================================================================
echo.

REM Check if plink.exe exists
where plink.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo [-] plink.exe not found. Installing from PuTTY...
    powershell -Command "Invoke-WebRequest -Uri 'https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe' -OutFile 'C:\Windows\System32\plink.exe'" 2>nul
    if %errorlevel% neq 0 (
        echo [!] Failed to install plink. Please install PuTTY manually.
        exit /b 1
    )
    echo [+] plink installed
)

echo [*] Connecting to pi@%PI_HOST%...
echo.

REM Test connection first
.\plink.exe -pw %PI_PASSWORD% -o "StrictHostKeyChecking=no" %PI_USER%@%PI_HOST% "echo OK" 2>nul
if %errorlevel% neq 0 (
    echo [!] Connection failed
    exit /b 1
)

echo [+] Connected! Running diagnostics...
echo.

REM SERVICE STATUS
echo [*] SERVICE STATUS
echo ======================================================================
.\plink.exe -pw %PI_PASSWORD% -o "StrictHostKeyChecking=no" %PI_USER%@%PI_HOST% "sudo systemctl status harvestpilot-autodeploy.service --no-pager" 2>nul
echo.

REM PROCESS CHECK
echo [*] PROCESS CHECK
echo ======================================================================
.\plink.exe -pw %PI_PASSWORD% -o "StrictHostKeyChecking=no" %PI_USER%@%PI_HOST% "ps aux | grep -E 'python.*main' | grep -v grep" 2>nul
echo.

REM RECENT LOGS
echo [*] RECENT LOGS (Last 50 lines)
echo ======================================================================
.\plink.exe -pw %PI_PASSWORD% -o "StrictHostKeyChecking=no" %PI_USER%@%PI_HOST% "sudo journalctl -u harvestpilot-autodeploy.service -n 50 --no-pager" 2>nul
echo.

REM HEARTBEAT STATUS
echo [*] HEARTBEAT/SYNC STATUS (Last 20 lines)
echo ======================================================================
.\plink.exe -pw %PI_PASSWORD% -o "StrictHostKeyChecking=no" %PI_USER%@%PI_HOST% "sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -iE 'heartbeat|sync' | tail -20" 2>nul
echo.

REM SERVICE ACTIVE CHECK
echo [*] SERVICE ACTIVE CHECK
echo ======================================================================
.\plink.exe -pw %PI_PASSWORD% -o "StrictHostKeyChecking=no" %PI_USER%@%PI_HOST% "sudo systemctl is-active harvestpilot-autodeploy.service" 2>nul
echo.

echo ======================================================================
echo [+] Diagnostics complete - ZERO PASSWORD PROMPTS
echo ======================================================================
