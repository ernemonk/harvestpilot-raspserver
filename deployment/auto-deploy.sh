#!/bin/bash
# Auto-deploy script for HarvestPilot RaspServer
# Pulls latest code and restarts service
# Usage: This script is run by systemd service and cron job

set -e

REPO_PATH="/home/monkphx/harvestpilot-raspserver"
LOG_FILE="/var/log/harvestpilot-autodeploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Create log directory if needed
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log_message() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log_message "=== Auto-Deploy Started ==="

# Change to repo directory
cd "$REPO_PATH"

# Fetch latest changes
log_message "Fetching latest changes from GitHub..."
git fetch origin main 2>&1 | tee -a "$LOG_FILE"

# Check if there are changes
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log_message "✓ Already up to date. No changes to deploy."
    exit 0
fi

log_message "⬇️  Pulling changes from origin/main..."
git pull origin main 2>&1 | tee -a "$LOG_FILE"

log_message "✓ Code updated successfully"

# Restart service
log_message "♻️  Restarting harvestpilot-raspserver service..."
sudo systemctl restart harvestpilot-raspserver 2>&1 | tee -a "$LOG_FILE"

log_message "✓ Service restarted"
log_message "=== Auto-Deploy Complete ==="
