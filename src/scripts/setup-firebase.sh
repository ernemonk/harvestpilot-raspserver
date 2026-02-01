#!/bin/bash
# Setup script for HarvestPilot RaspServer with Firestore

set -e

echo "Setting up HarvestPilot RaspServer with Firestore..."

# Install system dependencies
sudo apt-get update
sudo apt-get install -y libgpiod2 libgpiod-dev

# Install Python dependencies
pip3 install -r requirements.txt

# Get Firestore credentials (user must provide this manually)
echo ""
echo "================================================================"
echo "IMPORTANT: Firestore Credentials Setup"
echo "================================================================"
echo ""
echo "You need to set up Firebase Admin SDK credentials:"
echo "1. Go to your Firebase console"
echo "2. Project Settings > Service Accounts"
echo "3. Generate a new private key (JSON)"
echo "4. Save it as 'firebase-key.json' in the config/ directory"
echo ""
echo "Then set environment variables in .env:"
echo "  DEVICE_ID=raspserver-001"
echo "  FIREBASE_PROJECT_ID=your-project-id"
echo "  FIREBASE_CREDENTIALS_PATH=config/firebase-key.json"
echo ""
echo "================================================================"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
  cat > .env << 'EOF'
# Hardware Configuration
HARDWARE_PLATFORM=raspberry_pi
SIMULATE_HARDWARE=false

# Firestore Configuration
DEVICE_ID=raspserver-001
FIREBASE_CREDENTIALS_PATH=config/firebase-key.json
FIREBASE_PROJECT_ID=harvest-hub

# Automation Settings
AUTO_IRRIGATION_ENABLED=true
AUTO_LIGHTING_ENABLED=true

# Logging
LOG_LEVEL=INFO
DEBUG=false
EOF
  echo "Created .env file - please update with your Firebase settings"
fi

# Create systemd service
echo "Creating systemd service..."
sudo python3 << 'EOFPYTHON'
import subprocess

service_content = '''[Unit]
Description=HarvestPilot RaspServer with Firebase
After=network.target

[Service]
Type=simple
User=monkphx
WorkingDirectory=/home/monkphx/harvestpilot-raspserver
EnvironmentFile=/home/monkphx/harvestpilot-raspserver/.env
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''

with open('/etc/systemd/system/harvestpilot-raspserver.service', 'w') as f:
    f.write(service_content)

subprocess.run(['systemctl', 'daemon-reload'])
subprocess.run(['systemctl', 'enable', 'harvestpilot-raspserver'])
print("✓ Systemd service created and enabled")

EOFPYTHON

echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Add your Firebase credentials (firebase-key.json)"
echo "2. Update .env with your Firebase project details"
echo "3. Run: sudo systemctl start harvestpilot-raspserver"
echo "4. Check status: sudo systemctl status harvestpilot-raspserver"
