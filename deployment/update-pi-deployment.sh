#!/bin/bash
# HarvestPilot Pi Manual Deployment & Secrets Injection
# Run this on your Raspberry Pi to update to latest code and reinject secrets

set -euo pipefail

REPO_PATH="/home/monkphx/harvestpilot-raspserver"
DEPLOY_SCRIPT="$REPO_PATH/deployment/auto-deploy.sh"
VERIFY_SCRIPT="$REPO_PATH/deployment/verify-pi-deployment.sh"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  HarvestPilot Pi Deployment & Secrets Injection                ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')"
echo "╚════════════════════════════════════════════════════════════════╝"

echo ""
echo "Step 1: Checking repository status..."
cd "$REPO_PATH"

# Show current state
echo "Current commit:"
git log --oneline -1

echo ""
echo "Step 2: Fetching latest changes..."
git fetch origin main

# Check if there are updates
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "✓ Already up to date with origin/main"
else
    echo "⬇️  Updates available, pulling..."
    git pull origin main
fi

echo ""
echo "Step 3: Running deployment (auto-deploy.sh)..."
echo "This will:"
echo "  - Inject secrets from environment or existing configuration"
echo "  - Validate all credentials"
echo "  - Restart the service"
echo ""

if [ -f "$DEPLOY_SCRIPT" ]; then
    bash "$DEPLOY_SCRIPT"
else
    echo "Error: auto-deploy.sh not found at $DEPLOY_SCRIPT"
    exit 1
fi

echo ""
echo "Step 4: Verifying deployment..."
if [ -f "$VERIFY_SCRIPT" ]; then
    bash "$VERIFY_SCRIPT"
else
    echo "Verification script not found, running basic checks..."
    echo "Service status:"
    sudo systemctl status harvestpilot-raspserver --no-pager | grep -E "Active|running"
    echo ""
    echo "✓ Deployment update complete!"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT & SECRETS INJECTION COMPLETE"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "1. Monitor service: sudo journalctl -u harvestpilot-raspserver -f"
echo "2. Check Firebase connectivity: Look for successful sync in logs"
echo "3. Verify heartbeat: Check device status in Firebase Console"
echo ""
