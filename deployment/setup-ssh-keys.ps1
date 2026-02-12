#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Setup SSH key-based authentication to Raspberry Pi
    Run this ONCE, then check-pi-status.ps1 will work without passwords
#>

param(
    [string]$PiHost = "192.168.1.233",
    [string]$PiUser = "pi",
    [string]$PiPassword = $env:PI_PASSWORD  # Set PI_PASSWORD env var or pass -PiPassword
)

if (-not $PiPassword) {
    Write-Host "ERROR: Set the PI_PASSWORD environment variable or pass -PiPassword." -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SSH Keys Setup for Raspberry Pi" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$sshDir = Join-Path $HOME ".ssh"
$keyPath = Join-Path $sshDir "id_rsa"

# Step 1: Create .ssh directory if needed
Write-Host "[*] Setting up SSH directory..." -ForegroundColor Cyan
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
    Write-Host "[+] Created $sshDir" -ForegroundColor Green
}
else {
    Write-Host "[+] $sshDir already exists" -ForegroundColor Green
}

# Step 2: Check if key already exists
if (Test-Path $keyPath) {
    Write-Host "[!] SSH key already exists at $keyPath" -ForegroundColor Yellow
    $useExisting = Read-Host "Use existing key? (y/n)"
    if ($useExisting -ne "y") {
        Write-Host "[*] Generating new key..." -ForegroundColor Cyan
        Remove-Item $keyPath -Force
        Remove-Item "$keyPath.pub" -Force
        ssh-keygen -t rsa -b 4096 -f $keyPath -N "" | Out-Null
        Write-Host "[+] New key generated" -ForegroundColor Green
    }
}
else {
    Write-Host "[*] Generating new SSH key..." -ForegroundColor Cyan
    ssh-keygen -t rsa -b 4096 -f $keyPath -N "" | Out-Null
    Write-Host "[+] SSH key generated at $keyPath" -ForegroundColor Green
}

# Step 3: Copy public key to Pi
Write-Host ""
Write-Host "[*] Copying public key to Pi..." -ForegroundColor Cyan
Write-Host "    Host: $PiUser@$PiHost" -ForegroundColor Yellow
Write-Host ""

$pubKeyContent = Get-Content "$keyPath.pub"

# Use expect-like approach with PowerShell
$sshCmd = @"
mkdir -p ~/.ssh && echo "$pubKeyContent" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo "Key installed successfully"
"@

# Try using ssh-copy-id first (if available)
$sshCopyId = Get-Command ssh-copy-id -ErrorAction SilentlyContinue
if ($sshCopyId) {
    Write-Host "[*] Using ssh-copy-id..." -ForegroundColor Cyan
    # This will prompt for password
    & ssh-copy-id -i "$keyPath.pub" -p 22 "$PiUser@$PiHost"
}
else {
    # Fallback: manual install
    Write-Host "[*] Manual key installation (will prompt for password)..." -ForegroundColor Yellow
    Write-Host "    When prompted, enter your Pi password: $PiPassword" -ForegroundColor Yellow
    Write-Host ""
    
    ssh "$PiUser@$PiHost" $sshCmd
}

Write-Host ""
Write-Host "[*] Testing new SSH connection..." -ForegroundColor Cyan
$testCmd = ssh "$PiUser@$PiHost" "echo 'SSH key auth works!'"

if ($testCmd -like "*works*") {
    Write-Host "[+] SSH key authentication verified!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "SUCCESS!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now run diagnostics without password prompts:" -ForegroundColor Green
    Write-Host "  .\check-pi-status.ps1" -ForegroundColor Cyan
    Write-Host ""
}
else {
    Write-Host "[!] SSH key auth test failed. You may still need to enter password." -ForegroundColor Yellow
}

Write-Host "[*] Your public key is stored at: $keyPath.pub" -ForegroundColor Cyan
Write-Host "[*] Your private key is stored at: $keyPath" -ForegroundColor Cyan
Write-Host ""
