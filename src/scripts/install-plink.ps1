#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Install plink.exe (PuTTY SSH client) for password-based SSH automation
    Run this ONCE to set up passwordless diagnostics
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installing plink.exe (PuTTY SSH Client)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$programFiles = "C:\Program Files"
$plinkPath = "$programFiles\PuTTY\plink.exe"

# Check if plink already exists
if (Test-Path $plinkPath) {
    Write-Host "[+] plink.exe already installed at: $plinkPath" -ForegroundColor Green
    exit 0
}

Write-Host "[*] Downloading PuTTY installer..." -ForegroundColor Cyan

# Download PuTTY portable executable
$tempDir = [System.IO.Path]::GetTempPath()
$plinkUrl = "https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe"
$downloadPath = Join-Path $tempDir "plink.exe"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $plinkUrl -OutFile $downloadPath -UseBasicParsing
    Write-Host "[+] Downloaded plink.exe to temp" -ForegroundColor Green
}
catch {
    Write-Host "[!] Failed to download plink.exe" -ForegroundColor Red
    Write-Host "    Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual install:" -ForegroundColor Yellow
    Write-Host "  1. Go to: https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html" -ForegroundColor Yellow
    Write-Host "  2. Download: plink.exe" -ForegroundColor Yellow
    Write-Host "  3. Save to: C:\Program Files\PuTTY\plink.exe" -ForegroundColor Yellow
    exit 1
}

# Create PuTTY directory if needed
$puttyDir = "$programFiles\PuTTY"
if (-not (Test-Path $puttyDir)) {
    New-Item -ItemType Directory -Path $puttyDir -Force | Out-Null
    Write-Host "[+] Created directory: $puttyDir" -ForegroundColor Green
}

# Copy plink to Program Files
try {
    Copy-Item -Path $downloadPath -Destination $plinkPath -Force
    Write-Host "[+] Installed plink.exe to: $plinkPath" -ForegroundColor Green
}
catch {
    Write-Host "[!] Failed to copy plink.exe to Program Files" -ForegroundColor Red
    Write-Host "    Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Trying to copy to user directory instead..." -ForegroundColor Yellow
    
    $userPath = Join-Path $HOME "plink.exe"
    Copy-Item -Path $downloadPath -Destination $userPath -Force
    Write-Host "[+] Installed plink.exe to: $userPath" -ForegroundColor Green
    Write-Host "[*] Add this to your PATH or use: $userPath" -ForegroundColor Yellow
    exit 0
}

# Add to PATH if not already there
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*PuTTY*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$puttyDir", "User")
    Write-Host "[+] Added PuTTY to user PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS! plink.exe installed" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Now you can run diagnostics without password prompts:" -ForegroundColor Green
Write-Host "  .\check-pi-status.ps1" -ForegroundColor Cyan
Write-Host ""
