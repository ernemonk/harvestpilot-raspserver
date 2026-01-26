# 🌱 HarvestPilot Setup - Your Pi (192.168.1.233)

## Your System Info

| Component | Value |
|-----------|-------|
| **Pi Username** | `monkphx` |
| **Pi IP Address** | `192.168.1.233` |
| **Network** | WiFi (wlan0) |
| **Hostname** | `raspberrypi` |

---

## 🚀 Quick Setup (5 minutes)

### Step 1: SSH Into Your Pi

```bash
ssh monkphx@192.168.1.233
```

Password: (whatever you set)

### Step 2: Run Auto-Setup

```bash
# One command setup
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/harvestpilot/main/scripts/setup-raspserver.sh | bash
```

Or manually:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3-pip python3-rpi.gpio git mosquitto mosquitto-clients

# Add GPIO permissions
sudo usermod -a -G gpio monkphx
sudo usermod -a -G spi monkphx
sudo usermod -a -G i2c monkphx

# Reboot
sudo reboot
```

### Step 3: Clone Repository (After Reboot)

```bash
ssh monkphx@192.168.1.233

cd ~
git clone https://github.com/YOUR_USERNAME/harvestpilot.git
cd harvestpilot/harvestpilot-raspserver
```

### Step 4: Install Python Packages

```bash
pip3 install -r requirements.txt
```

### Step 5: Configure MQTT

```bash
nano config.py
```

Edit this line (around line 8):
```python
# Change this:
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")

# To your cloud agent IP:
MQTT_BROKER = os.getenv("MQTT_BROKER", "YOUR_AGENT_SERVER_IP")
```

Save: `Ctrl+X`, `Y`, `Enter`

### Step 6: Test

```bash
python3 main.py
```

You should see:
```
INFO - Starting HarvestPilot RaspServer...
INFO - Connected to MQTT broker successfully
INFO - Subscribed to harvestpilot/commands/#
```

Press `Ctrl+C` to stop.

### Step 7: Set Up as Service

```bash
# Create service file
sudo nano /etc/systemd/system/harvestpilot-raspserver.service
```

Paste:
```ini
[Unit]
Description=HarvestPilot RaspServer
After=network.target

[Service]
Type=simple
User=monkphx
WorkingDirectory=/home/monkphx/harvestpilot/harvestpilot-raspserver
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable harvestpilot-raspserver
sudo systemctl start harvestpilot-raspserver
sudo systemctl status harvestpilot-raspserver
```

---

## ✅ Verify It's Working

```bash
# Check service
sudo systemctl status harvestpilot-raspserver

# View logs
tail -f ~/harvestpilot/harvestpilot-raspserver/logs/raspserver.log

# Watch MQTT
mosquitto_sub -h localhost -t "harvestpilot/#" -v
```

Expected output:
```
harvestpilot/sensors/reading {"temperature": 72.5, "humidity": 65, ...}
```

---

## 📡 GitHub Actions Auto-Deploy

Once you push to GitHub, add these secrets:

**GitHub → Settings → Secrets → New secret**

| Name | Value |
|------|-------|
| `PI_HOST` | `monkphx@192.168.1.233` |
| `PI_USER` | `monkphx` |
| `PI_SSH_KEY` | Your private SSH key |

Then every `git push main` auto-deploys! 🎉

---

## 🎮 Quick Commands

```bash
# Connect to Pi
ssh monkphx@192.168.1.233

# Start service
sudo systemctl start harvestpilot-raspserver

# Stop service
sudo systemctl stop harvestpilot-raspserver

# View logs
tail -f ~/harvestpilot/harvestpilot-raspserver/logs/raspserver.log

# Deploy updates
bash ~/harvestpilot/scripts/deploy-raspserver.sh

# Check MQTT
mosquitto_sub -h localhost -t "harvestpilot/#" -v

# View IP
hostname -I
```

---

## 🔗 Next: Deploy Agent to Cloud

You need:
1. Cloud server IP/domain (AWS, Railway, DigitalOcean)
2. Update `config.py` line: `MQTT_BROKER = "YOUR_CLOUD_IP"`
3. Set up GitHub Secrets
4. Push and auto-deploy!

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Can't SSH | Check IP: `ip a` on Pi |
| Permission denied | Run permission script again |
| MQTT not connecting | Check `config.py` MQTT_BROKER IP |
| Service won't start | `sudo systemctl status harvestpilot-raspserver` |

---

See [harvestpilot-raspserver/COMMANDS.md](../../harvestpilot-raspserver/COMMANDS.md) for all commands.
