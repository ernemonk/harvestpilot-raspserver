# HarvestPilot Pi Diagnostics - Quick Setup Guide

## Problem
Your SSH connection requires a password, but PowerShell SSH doesn't easily support automatic password entry on Windows.

## Solution: Use SSH Keys (Recommended)

### Step 1: Generate SSH Key
Run this **ONCE** in PowerShell:
```powershell
ssh-keygen -t rsa -b 4096 -f "$HOME\.ssh\id_rsa" -N ""
```

### Step 2: Copy Key to Pi
SSH into your Pi and manually add your public key:

```bash
# On your Pi (via SSH or direct connection):
mkdir -p ~/.ssh
# Then paste the contents of your public key when prompted
nano ~/.ssh/authorized_keys

# Set correct permissions
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

Or use this one-liner from WSL (if you have WSL installed):
```bash
wsl ssh-copy-id -i ~/.ssh/id_rsa.pub pi@192.168.1.233
```

### Step 3: Test It
```powershell
ssh pi@192.168.1.233 "echo OK"
# Should NOT prompt for password
```

### Step 4: Run Diagnostics
Once keys are set up, this works without passwords:
```powershell
.\check-pi-status.ps1
```

---

## Alternative: Use WSL SSH

If you have Windows Subsystem for Linux (WSL), you can use the Linux SSH with sshpass:

```bash
# In WSL terminal
wsl
sudo apt-get install sshpass
sshpass -p 149246116 ssh pi@192.168.1.233 "sudo journalctl -u harvestpilot-autodeploy.service -n 50"
```

---

## My Pi Credentials
- **Host:** 192.168.1.233
- **User:** pi
- **Password:** 149246116

## To Get Heartbeat Status Manually

```bash
ssh pi@192.168.1.233 "sudo journalctl -u harvestpilot-autodeploy.service | grep -i heartbeat | tail -10"
```

Should show output like:
```
💓 Heartbeat #1 sent successfully
💓 Heartbeat #2 sent successfully
```

## Current Heartbeat Issue

Your Firebase shows `lastHeartbeat` is stale (from yesterday). This means:

1. **Service might not be running**
   ```bash
   ssh pi@192.168.1.233 "sudo systemctl status harvestpilot-autodeploy.service"
   ```

2. **Check the logs**
   ```bash
   ssh pi@192.168.1.233 "sudo journalctl -u harvestpilot-autodeploy.service -f"
   ```

3. **Restart if needed**
   ```bash
   ssh pi@192.168.1.233 "sudo systemctl restart harvestpilot-autodeploy.service"
   ```

---

## Next Steps

1. **Setup SSH keys** (Step 1-3 above)
2. **Run diagnostics** once keys work
3. **Check heartbeat status** in the logs
4. **Fix any issues** found

Need help? Check [HEARTBEAT_TROUBLESHOOTING.md](./HEARTBEAT_TROUBLESHOOTING.md)
