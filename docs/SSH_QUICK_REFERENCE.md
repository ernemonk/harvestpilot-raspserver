# SSH Quick Reference - Your Raspberry Pi

**Your Pi:** `monkphx@192.168.1.233`

---

## 🔐 SSH Login

### Fastest Way (with saved key)
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233
```

### With Password
```bash
ssh monkphx@192.168.1.233
```

### Using Hostname (same network)
```bash
ssh monkphx@raspberrypi.local
```

---

## 📍 File Locations on Pi

```
Repository:     /home/monkphx/harvestpilot-raspserver
Config file:    /home/monkphx/harvestpilot-raspserver/src/config.py
.env file:      /home/monkphx/harvestpilot-raspserver/.env
Logs:           /home/monkphx/harvestpilot-raspserver/logs/raspserver.log
Firebase key:   /home/monkphx/harvestpilot-raspserver/firebase-key.json
Service file:   /etc/systemd/system/harvestpilot-raspserver.service
```

---

## 🚀 Service Commands

```bash
# Check status
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo systemctl status harvestpilot-raspserver"

# Start service
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo systemctl start harvestpilot-raspserver"

# Stop service
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo systemctl stop harvestpilot-raspserver"

# Restart service
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo systemctl restart harvestpilot-raspserver"

# View logs (last 50 lines)
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver -n 50"

# Follow logs (live)
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver -f"
```

---

## 📂 File Operations

### View .env
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "cat /home/monkphx/harvestpilot-raspserver/.env"
```

### View config.py (first 50 lines)
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "head -50 /home/monkphx/harvestpilot-raspserver/src/config.py"
```

### View logs
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "tail -50 /home/monkphx/harvestpilot-raspserver/logs/raspserver.log"
```

---

## 🔍 Hardware Serial Verification

### Check Detection
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
python3 << 'PYTHON'
import sys
sys.path.insert(0, '/home/monkphx/harvestpilot-raspserver')
from src import config
print(f'HARDWARE_SERIAL: {config.HARDWARE_SERIAL}')
print(f'DEVICE_ID: {config.DEVICE_ID}')
PYTHON
EOF
```

### Check Pi Serial (from /proc/cpuinfo)
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "cat /proc/cpuinfo | grep Serial"
```

### Check Init Logs for Hardware Serial
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver | grep -i hardware_serial"
```

---

## 🔄 Code Deployment

### Push code (triggers auto-deploy)
```bash
cd /Users/user/Projects/HarvestPilot/Repos/harvestpilot-raspserver
git add -A
git commit -m "your message"
git push origin main
```

### Check if Pi has latest code
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "cd /home/monkphx/harvestpilot-raspserver && git log -1 --oneline"
```

### Manual update (if auto-deploy fails)
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
cd /home/monkphx/harvestpilot-raspserver
git pull origin main
pip3 install -r requirements.txt
sudo systemctl restart harvestpilot-raspserver
EOF
```

---

## 🔧 Quick Diagnostics

### Full System Check
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
echo "=== System Info ==="
uname -a

echo -e "\n=== Python Version ==="
python3 --version

echo -e "\n=== Service Status ==="
sudo systemctl status harvestpilot-raspserver --no-pager

echo -e "\n=== Recent Logs ==="
sudo journalctl -u harvestpilot-raspserver -n 10

echo -e "\n=== Hardware Serial ==="
cat /proc/cpuinfo | grep Serial
EOF
```

### Firebase Connection Check
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver -n 30 | grep -i firebase"
```

---

## 📋 Copy-Paste Commands

**SSH into Pi (one-liner):**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233
```

**View last 100 log lines:**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver -n 100 --no-pager"
```

**Restart service and show status:**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo systemctl restart harvestpilot-raspserver && sleep 2 && sudo systemctl status harvestpilot-raspserver"
```

**Check hardware serial in running app:**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "python3 -c 'import sys; sys.path.insert(0, \"/home/monkphx/harvestpilot-raspserver\"); from src import config; print(f\"Hardware Serial: {config.HARDWARE_SERIAL}\")\nDevice ID: {config.DEVICE_ID}\"'"
```

---

## 🚨 Common Issues

**Can't SSH?**
```bash
ping 192.168.1.233
# If no response, check WiFi on Pi
```

**Service won't start?**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver -p err -n 20"
```

**Hardware serial wrong?**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 "cat /home/monkphx/harvestpilot-raspserver/.env | grep HARDWARE"
```

---

## 📞 Key Contact Info

- **Pi IP:** 192.168.1.233
- **Pi User:** monkphx
- **Pi Hostname:** raspberrypi
- **SSH Key:** ~/.ssh/harvestpilot_pi
- **GitHub Repo:** https://github.com/ernemonk/harvestpilot-raspserver
- **Service Name:** harvestpilot-raspserver
