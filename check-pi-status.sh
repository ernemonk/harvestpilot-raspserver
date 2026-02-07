#!/bin/bash
# HarvestPilot Diagnostic Check - Run this ON your Raspberry Pi
# Usage: bash <(curl -s https://your-repo/check-pi-status.sh)
# Or: chmod +x check-pi-status.sh && ./check-pi-status.sh

echo "========================================"
echo "HarvestPilot Pi Diagnostics"
echo "========================================"
echo ""

# Service Status
echo "[*] SERVICE STATUS"
echo "----------------------------------------"
sudo systemctl status harvestpilot-autodeploy.service --no-pager
echo ""

# Process Check
echo "[*] PROCESS CHECK"
echo "----------------------------------------"
ps aux | grep -E 'python.*main|harvestpilot' | grep -v grep || echo "No process found"
echo ""

# Recent Logs
echo "[*] RECENT LOGS (Last 50 lines)"
echo "----------------------------------------"
sudo journalctl -u harvestpilot-autodeploy.service -n 50 --no-pager
echo ""

# Recent Errors
echo "[!] RECENT ERRORS"
echo "----------------------------------------"
sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -i error | tail -20 || echo "No errors found"
echo ""

# Heartbeat Check
echo "[*] HEARTBEAT/SYNC STATUS"
echo "----------------------------------------"
sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -iE 'heartbeat|sync' | tail -15 || echo "No heartbeat entries found"
echo ""

# Summary
echo "========================================"
echo "[+] Diagnostics complete"
echo "========================================"
echo ""

# Check if service is active
if sudo systemctl is-active --quiet harvestpilot-autodeploy.service; then
    echo "[+] Service is RUNNING"
else
    echo "[!] Service is STOPPED"
    echo "    To restart: sudo systemctl restart harvestpilot-autodeploy.service"
fi

echo ""
echo "[*] For live logs:"
echo "    sudo journalctl -u harvestpilot-autodeploy.service -f"
echo ""
