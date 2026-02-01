# Deployment Scripts

This directory contains setup and deployment automation scripts for Raspberry Pi.

## 📁 Scripts

### `setup-firebase.sh`
Configures Firebase credentials on the Raspberry Pi.

```bash
bash deployment/setup-firebase.sh
```

**What it does:**
- Validates Firebase credential file exists
- Tests Firebase connection
- Sets up environment variables
- Configures systemd service

### `setup-gpio-automated.sh`
Initializes GPIO pins and verifies hardware connections.

```bash
bash deployment/setup-gpio-automated.sh
```

**What it does:**
- Enables SPI and I2C
- Tests GPIO pin access
- Validates sensor connections
- Configures pin permissions

### `setup-init.sh`
Initial system setup and bootstrap.

```bash
bash deployment/setup-init.sh
```

**What it does:**
- Checks system requirements
- Installs system dependencies
- Creates service user (if needed)
- Initializes directories

## 🚀 Full Deployment

Run these scripts in order:

```bash
# 1. Initial setup
bash deployment/setup-init.sh

# 2. Configure GPIO
bash deployment/setup-gpio-automated.sh

# 3. Configure Firebase
bash deployment/setup-firebase.sh

# 4. Start service
sudo systemctl start harvestpilot-raspserver
```

## 📋 Requirements

- Raspberry Pi 4 with Raspberry Pi OS
- SSH access
- `sudo` privileges for GPIO and systemd
- Bash 4.0+

## 🔒 Security

These scripts handle sensitive operations:
- They require `sudo` for GPIO configuration
- Firebase credentials are validated but not logged
- Use in trusted environments only

## 📖 Documentation

See [../REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) for project layout.  
See [../docs/DEPLOYMENT_SETUP.md](../docs/DEPLOYMENT_SETUP.md) for detailed deployment guide.
