# HarvestPilot RaspServer - Quick Start

## One-Command Setup (Raspberry Pi)

```bash
# Copy this entire command and paste on your Pi:
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/harvestpilot/main/scripts/setup-raspserver.sh | bash
```

Then reboot and configure:
```bash
sudo reboot
```

After reboot:
```bash
nano ~/harvestpilot/harvestpilot-raspserver/config.py
# Edit line 8: MQTT_BROKER = "YOUR_AGENT_SERVER_IP"
```

---

## Manual Setup (Step-by-Step)

### 1. SSH into Pi
```bash
ssh monkphx@192.168.1.233
```

### 2. Run Setup Script
```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/harvestpilot/main/scripts/setup-raspserver.sh | bash

# Or manually:
sudo apt update && sudo apt upgrade -y
sudo apt install python3.11 python3-pip python3-rpi.gpio git -y
sudo usermod -a -G gpio pi
sudo reboot
```

### 3. Clone Repository
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/harvestpilot.git
cd harvestpilot/harvestpilot-raspserver
```

### 4. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 5. Configure
```bash
nano config.py
# Edit: MQTT_BROKER = "YOUR_AGENT_SERVER_IP"
```

### 6. Test
```bash
python3 main.py
# Should show: "Connected to MQTT broker successfully"
# Ctrl+C to stop
```

### 7. Set Up as Service
```bash
sudo nano /etc/systemd/system/harvestpilot-raspserver.service
```

Paste:
```ini
[Unit]
Description=HarvestPilot RaspServer
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/harvestpilot/harvestpilot-raspserver
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable harvestpilot-raspserver
sudo systemctl start harvestpilot-raspserver
sudo systemctl status harvestpilot-raspserver
```

---

## Verify It's Working

```bash
# Check service status
sudo systemctl status harvestpilot-raspserver

# View live logs
tail -f ~/harvestpilot/harvestpilot-raspserver/logs/raspserver.log

# Check MQTT connection
mosquitto_sub -h localhost -t "harvestpilot/#" -v
```

Expected output:
```
harvestpilot/sensors/reading {"temperature": 72.5, "humidity": 65, ...}
harvestpilot/status/irrigation {"running": false}
```

---

## Common Commands

```bash
# Start service
sudo systemctl start harvestpilot-raspserver

# Stop service
sudo systemctl stop harvestpilot-raspserver

# Restart service
sudo systemctl restart harvestpilot-raspserver

# View logs
tail -f logs/raspserver.log

# View status
sudo systemctl status harvestpilot-raspserver

# Disable auto-start
sudo systemctl disable harvestpilot-raspserver

# Manual run (for debugging)
python3 main.py
```

---

## GitHub Actions Auto-Deploy

Once you set up GitHub Secrets:
- `PI_HOST` = `pi@192.168.1.100`
- `PI_USER` = `pi`
- `PI_SSH_KEY` = your private SSH key

Every push to `main` automatically:
```
Git push → GitHub Actions → SSH to Pi → git pull → pip install → systemctl restart
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: RPi.GPIO` | `pip3 install RPi.GPIO` |
| `Permission denied GPIO` | `sudo usermod -a -G gpio pi && sudo reboot` |
| `MQTT connection refused` | Check `MQTT_BROKER` IP in config.py |
| `Service won't start` | `sudo systemctl status harvestpilot-raspserver` |

---

## What's Next?

1. ✅ RaspServer running on Pi
2. ⏭️  Deploy Agent to cloud
3. ⏭️  Connect via MQTT
4. ⏭️  Access via REST API
5. ⏭️  Use web dashboard

See: [DEPLOYMENT_ARCHITECTURE.md](../harvestpilot-agent/docs/DEPLOYMENT_ARCHITECTURE.md)
