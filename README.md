# HarvestPilot RaspServer

**Raspberry Pi Controller for HarvestPilot Farm Intelligence Platform**

![Status](https://img.shields.io/badge/Status-Active-green)
![Auto Deploy](https://img.shields.io/badge/Auto_Deploy-GitHub_Actions-blue)
![Hardware](https://img.shields.io/badge/Hardware-Raspberry_Pi_4-red)

## Overview
HarvestPilot RaspServer runs on a Raspberry Pi and handles:
- GPIO control (lights, pumps, sensors)
- Firebase real-time database sync
- MQTT communication
- System monitoring and logging

## ⚡ Quick Start

### Hardware Requirements
- Raspberry Pi 4 (ARM64)
- Python 3.9+
- SSH access (192.168.1.233)
- User: `monkphx`

### Installation
```bash
# Clone repository
git clone https://github.com/ernemonk/harvestpilot-raspserver.git
cd harvestpilot-raspserver

# Install dependencies
pip3 install -r requirements.txt

# Configure Firebase
bash setup-firebase.sh

# Start service
sudo systemctl start harvestpilot-raspserver
```

## 🚀 Auto-Deployment
This repo uses **GitHub Actions** for automatic deployment to Raspberry Pi.

### How It Works
1. Push code to `main` branch
2. GitHub Actions triggers on Raspberry Pi
3. Code automatically updates and service restarts
4. No manual intervention needed!

**Read**: [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md) for full details

## 📂 Project Structure
```
harvestpilot-raspserver/
├── main.py                 # Entry point
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── controllers/           # GPIO controllers
├── mqtt/                  # MQTT communication
├── utils/                 # Helper functions
├── firebase_client.py     # Firebase integration
└── .github/workflows/     # GitHub Actions CI/CD
```

## 🔧 Commands

### Check Status
```bash
sudo systemctl status harvestpilot-raspserver
```

### View Logs
```bash
sudo journalctl -u harvestpilot-raspserver -f
```

### Restart Service
```bash
sudo systemctl restart harvestpilot-raspserver
```

### Manual Deployment
```bash
git pull origin main
pip3 install -r requirements.txt
sudo systemctl restart harvestpilot-raspserver
```

## 📡 Integration Points

### Firebase
- Real-time sensor data sync
- Configuration management
- Cloud command execution

### MQTT (Optional)
- Pi ↔ Agent communication
- Sensor stream publishing
- Command subscription

### API
- RESTful endpoints for status
- Configuration updates
- Emergency controls

## 🔐 Security
- GitHub Actions secrets for sensitive data
- SSH key authentication (no passwords)
- Firewall rules for local network only
- Firebase security rules enforced

## 📊 Monitoring

### GitHub Actions
View all deployments: https://github.com/ernemonk/harvestpilot-raspserver/actions

### Pi Status
```bash
ssh monkphx@192.168.1.233 'systemctl status harvestpilot-raspserver'
```

## 🐛 Troubleshooting

**Service won't start?**
```bash
sudo systemctl status harvestpilot-raspserver
sudo journalctl -u harvestpilot-raspserver -n 50
```

**Deployment failed?**
- Check GitHub Actions logs: https://github.com/ernemonk/harvestpilot-raspserver/actions
- SSH into Pi and verify pip3 installation
- Ensure Firebase credentials are loaded

**Network issues?**
```bash
ping 192.168.1.233
ssh -v monkphx@192.168.1.233
```

## 📚 Documentation
- [Deployment Guide](DEPLOYMENT_SETUP.md)
- [Firebase Setup](setup-firebase.sh)
- [Commands Reference](COMMANDS.md)

## 🎯 Current Features
✅ GPIO Control (lights, pumps)
✅ Sensor Reading
✅ Firebase Sync
✅ MQTT Communication
✅ Auto-restart on failure
✅ Automated GitHub Actions deployment

## 📝 License
Private - HarvestPilot Team

## 👥 Contributors
- ernemonk (owner)
- Automated deployment via GitHub Actions
