#!/bin/bash
# Quick Start: Test Server Initialization

echo "🚀 HarvestPilot Server Initialization - Quick Start"
echo "=================================================="
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📍 Working directory: $SCRIPT_DIR"
echo ""

# Check if server_init.py exists
if [ ! -f "$SCRIPT_DIR/scripts/server_init.py" ]; then
    echo "❌ Error: server_init.py not found"
    echo "   Expected: $SCRIPT_DIR/scripts/server_init.py"
    exit 1
fi

echo "✅ Found server_init.py"
echo ""

# Make executable
chmod +x "$SCRIPT_DIR/scripts/server_init.py"
echo "✅ Made executable: scripts/server_init.py"
echo ""

# Test imports
echo "🔧 Checking Python environment..."
python3 -c "import subprocess; import pathlib; import json; import firebase_admin" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ All required imports available"
else
    echo "⚠️  Some imports may be missing, but script will try anyway"
fi
echo ""

# Run initialization
echo "🎯 Running initialization script..."
echo "=================================================="
echo ""

cd "$SCRIPT_DIR"
python3 scripts/server_init.py

RESULT=$?
echo ""
echo "=================================================="

if [ $RESULT -eq 0 ]; then
    echo "✅ Initialization completed successfully!"
    echo ""
    echo "📊 Device Info Summary:"
    if [ -f .device_info.json ]; then
        cat .device_info.json | python3 -m json.tool
    fi
else
    echo "❌ Initialization had issues (exit code: $RESULT)"
    echo ""
    echo "💡 Troubleshooting:"
    echo "   1. Check /proc/cpuinfo exists: cat /proc/cpuinfo | grep Serial"
    echo "   2. Check Firebase credentials: ls -la firebase-key.json"
    echo "   3. Check network: ping 8.8.8.8"
fi

echo ""
echo "📚 Next steps:"
echo "   - View local device info: cat .device_info.json"
echo "   - Check Firestore: Firebase Console → Harvest-hub → Firestore → devices"
echo "   - View service logs: sudo journalctl -u harvestpilot-raspserver -n 50"
echo "   - Start service: sudo systemctl start harvestpilot-raspserver"
echo ""

exit $RESULT
