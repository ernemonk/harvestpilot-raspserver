#!/bin/bash
# Setup script to configure server initialization

echo "🔧 Setting up HarvestPilot server initialization..."

# Get the repository directory
REPO_DIR="/home/monkphx/harvestpilot-raspserver"
SCRIPT_DIR="$REPO_DIR/scripts"
INIT_SCRIPT="$SCRIPT_DIR/server_init.py"

# Make init script executable
chmod +x "$INIT_SCRIPT"
echo "✅ Made init script executable"

# Create systemd service wrapper (optional - for non-GitHub Actions runs)
# This ensures initialization runs before the main service starts

echo "✅ Server initialization setup complete"
echo "   Init script: $INIT_SCRIPT"
echo "   Usage:"
echo "     python3 $INIT_SCRIPT       # Run manually"
echo "     From systemd: ExecStartPre=$INIT_SCRIPT"
