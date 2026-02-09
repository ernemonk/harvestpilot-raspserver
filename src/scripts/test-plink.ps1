#!/usr/bin/env pwsh
# Test plink with the password interactively

$PiHost = "192.168.1.233"
$PiUser = "pi"  
$PiPassword = "149246116"
$plinkExe = "C:\Users\User\plink.exe"

Write-Host "Testing plink SSH connection..." -ForegroundColor Cyan
Write-Host "Host: $PiHost" -ForegroundColor Yellow
Write-Host "User: $PiUser" -ForegroundColor Yellow
Write-Host "Password: (hidden)" -ForegroundColor Yellow
Write-Host ""

# Test 1: Try with password
Write-Host "[*] Attempt 1: Using password..." -ForegroundColor Cyan
$output = & $plinkExe -pw $PiPassword -l $PiUser $PiHost "whoami" 2>&1
Write-Host "Output: $output" -ForegroundColor Yellow

if ($output -like "*pi*") {
    Write-Host "[+] Password auth successful!" -ForegroundColor Green
}
elseif ($output -like "*denied*" -or $output -like "*Access*") {
    Write-Host "[!] Password incorrect or access denied" -ForegroundColor Red
    Write-Host ""
    Write-Host "Trying interactive auth..." -ForegroundColor Yellow
    Write-Host "(You will be prompted for password - enter: 149246116)" -ForegroundColor Yellow
    Write-Host ""
    & $plinkExe -l $PiUser $PiHost "whoami" 2>&1
}
else {
    Write-Host "[!] Unexpected output:" -ForegroundColor Red
    Write-Host $output -ForegroundColor Yellow
}
