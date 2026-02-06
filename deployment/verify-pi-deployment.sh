#!/bin/bash
# HarvestPilot Pi Deployment Verification Script
# Run this on your Raspberry Pi to verify latest code and secrets injection

set -e

REPO_PATH="/home/monkphx/harvestpilot-raspserver"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  HarvestPilot Raspberry Pi Deployment Verification             ║"
echo "║  $TIMESTAMP"
echo "╚════════════════════════════════════════════════════════════════╝"

echo ""
echo "📍 Checking Repository Status..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$REPO_PATH"

# Check latest commits
echo "✓ Latest commits:"
git log --oneline -3

echo ""
echo "✓ Current branch:"
git rev-parse --abbrev-ref HEAD

echo ""
echo "✓ Git remote:"
git remote -v | head -2

echo ""
echo "📄 Checking Configuration Files..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check .env file
if [ -f ".env" ]; then
    echo "✓ .env file exists (size: $(wc -c < .env) bytes)"
    echo "  Contains:"
    grep -E "FIREBASE|PUMP|LIGHT|DHT|WATER" .env | sed 's/=.*/=***HIDDEN***/g' || echo "  (no expected vars found)"
else
    echo "✗ .env file NOT FOUND"
fi

echo ""

# Check firebase credentials
if [ -f "firebase-key.json" ]; then
    echo "✓ firebase-key.json exists (size: $(wc -c < firebase-key.json) bytes)"
    # Verify it's valid JSON
    if python3 -c "import json; json.load(open('firebase-key.json'))" 2>/dev/null; then
        echo "  ✓ Valid JSON format"
        # Extract project ID
        PROJECT_ID=$(python3 -c "import json; print(json.load(open('firebase-key.json')).get('project_id', 'unknown'))" 2>/dev/null)
        echo "  Project ID: $PROJECT_ID"
    else
        echo "  ✗ Invalid JSON format!"
    fi
else
    echo "✗ firebase-key.json NOT FOUND"
fi

echo ""
echo "🔐 Checking File Permissions..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check .env permissions
if [ -f ".env" ]; then
    ENV_PERMS=$(stat -c "%a" .env)
    if [ "$ENV_PERMS" = "600" ]; then
        echo "✓ .env has restrictive permissions (600)"
    else
        echo "⚠ .env permissions are $ENV_PERMS (should be 600)"
    fi
else
    echo "- .env not found"
fi

# Check firebase-key permissions
if [ -f "firebase-key.json" ]; then
    KEY_PERMS=$(stat -c "%a" firebase-key.json)
    if [ "$KEY_PERMS" = "600" ]; then
        echo "✓ firebase-key.json has restrictive permissions (600)"
    else
        echo "⚠ firebase-key.json permissions are $KEY_PERMS (should be 600)"
    fi
else
    echo "- firebase-key.json not found"
fi

echo ""
echo "🚀 Checking Service Status..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if sudo systemctl is-active --quiet harvestpilot-raspserver; then
    echo "✓ Service is RUNNING"
    
    # Get service uptime
    UPTIME=$(sudo systemctl status harvestpilot-raspserver --no-pager | grep "Active:" | sed 's/.*Active: //' | cut -d';' -f1)
    echo "  Status: $UPTIME"
else
    echo "✗ Service is NOT RUNNING"
    echo ""
    echo "Last 20 lines of service logs:"
    sudo journalctl -u harvestpilot-raspserver -n 20 --no-pager || echo "(Could not retrieve logs)"
fi

echo ""
echo "📊 Checking Deployment Report..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f ".deployment-secrets-report.json" ]; then
    echo "✓ Deployment report found:"
    python3 -m json.tool .deployment-secrets-report.json 2>/dev/null || cat .deployment-secrets-report.json
else
    echo "- No deployment report yet (will be created on next deployment)"
fi

echo ""
echo "✅ Verification Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "📋 Checklist Summary:"
echo "  ✓ Git repository up to date: $(cd $REPO_PATH && [ "$(git rev-parse @)" = "$(git rev-parse origin/main)" ] && echo 'YES' || echo 'NO - needs pull')"
echo "  ✓ Configuration files present: $([ -f .env ] && echo 'YES' || echo 'NO')"
echo "  ✓ Credentials present: $([ -f firebase-key.json ] && echo 'YES' || echo 'NO')"
echo "  ✓ Service running: $(sudo systemctl is-active --quiet harvestpilot-raspserver && echo 'YES' || echo 'NO')"

echo ""
echo "🔄 To update with latest code and reinject secrets:"
echo "  git fetch origin main"
echo "  git pull origin main"
echo "  sudo systemctl restart harvestpilot-raspserver"

echo ""
echo "📚 Logs location: /var/log/harvestpilot-autodeploy.log"
echo "                 /var/log/harvestpilot-secrets-inject.log"
echo ""
