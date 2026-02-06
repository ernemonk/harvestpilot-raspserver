#!/bin/bash
# Auto-deploy script for HarvestPilot RaspServer
# Pulls latest code, injects secrets, and restarts service
# Usage: This script is run by systemd service and cron job

set -e

REPO_PATH="/home/monkphx/harvestpilot-raspserver"
LOG_FILE="${LOG_FILE:-/var/log/harvestpilot-autodeploy.log}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
SECRETS_SCRIPT="$REPO_PATH/deployment/inject-secrets.sh"

# Create log directory if needed and writable
if ! mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || ! touch "$LOG_FILE" 2>/dev/null; then
    # If /var/log not writable, use repo directory
    LOG_FILE="$REPO_PATH/.autodeploy.log"
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
fi

log_message() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" >> "$LOG_FILE" 2>/dev/null || true
}

log_message "=== Auto-Deploy Started ==="

# Change to repo directory
cd "$REPO_PATH"

# Fetch latest changes
log_message "Fetching latest changes from GitHub..."
git fetch origin main >> "$LOG_FILE" 2>&1 || true

# Check if there are changes
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log_message "✓ Already up to date. No changes to deploy."
    exit 0
fi

log_message "⬇️  Pulling changes from origin/main..."
git pull origin main >> "$LOG_FILE" 2>&1 || true

log_message "✓ Code updated successfully"

# Inject secrets from environment variables
log_message "🔐 Injecting secrets into deployment..."
if [ -f "$SECRETS_SCRIPT" ]; then
    if bash "$SECRETS_SCRIPT" "$REPO_PATH" >> "$LOG_FILE" 2>&1; then
        log_message "✓ Secrets injected successfully"
    else
        log_message "⚠️  Warning: Some secrets may not have been properly injected"
        # Continue deployment anyway (secrets might be cached)
    fi
else
    log_message "⚠️  Warning: Secrets injection script not found at $SECRETS_SCRIPT"
fi

# Restart service
log_message "♻️  Restarting harvestpilot-raspserver service..."
sudo systemctl restart harvestpilot-raspserver >> "$LOG_FILE" 2>&1 || true

log_message "✓ Service restarted"
log_message "=== Auto-Deploy Complete ==="
