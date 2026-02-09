#!/bin/bash

# Heartbeat Test Diagnostic Script
# Run this on your Raspberry Pi to check if heartbeats are actually happening

echo "=========================================="
echo "HarvestPilot Heartbeat Diagnostic Test"
echo "=========================================="
echo ""

# Test 1: Check if service is running
echo "📋 TEST 1: Service Status"
echo "---"
sudo systemctl is-active harvestpilot-autodeploy.service
if [ $? -eq 0 ]; then
    echo "✅ Service is running"
else
    echo "❌ Service is NOT running"
    echo "Start it with: sudo systemctl start harvestpilot-autodeploy.service"
    exit 1
fi
echo ""

# Test 2: Check recent logs for heartbeats
echo "📋 TEST 2: Recent Heartbeat Log Messages (last 30 seconds)"
echo "---"
journalctl -u harvestpilot-autodeploy.service --since "30 seconds ago" | grep -i heartbeat
if [ $? -ne 0 ]; then
    echo "❌ No heartbeat messages found in last 30 seconds!"
    echo ""
    echo "Checking for ANY recent activity..."
    journalctl -u harvestpilot-autodeploy.service -n 20
fi
echo ""

# Test 3: Monitor heartbeats in real-time (10 seconds)
echo "📋 TEST 3: Real-time Heartbeat Monitoring (10 seconds)"
echo "---"
echo "Watching for heartbeat messages..."
timeout 10 journalctl -u harvestpilot-autodeploy.service -f | grep -i heartbeat &
sleep 10
wait
echo ""

# Test 4: Count heartbeats in last 2 minutes
echo "📋 TEST 4: Heartbeat Frequency Check (2-minute window)"
echo "---"
HEARTBEAT_COUNT=$(journalctl -u harvestpilot-autodeploy.service --since "2 minutes ago" | grep "Heartbeat #" | wc -l)
echo "Heartbeats in last 2 minutes: $HEARTBEAT_COUNT"
if [ "$HEARTBEAT_COUNT" -ge 3 ]; then
    echo "✅ Heartbeats are working! (~$((HEARTBEAT_COUNT/2))/minute = ~$((HEARTBEAT_COUNT*30)) per 30 seconds)"
elif [ "$HEARTBEAT_COUNT" -gt 0 ]; then
    echo "⚠️  Some heartbeats found, but fewer than expected"
else
    echo "❌ No heartbeats found in last 2 minutes!"
fi
echo ""

# Test 5: Check Firebase connection
echo "📋 TEST 5: Firebase Connection Status"
echo "---"
journalctl -u harvestpilot-autodeploy.service --since "5 minutes ago" | grep -i "firebase\|connected"
echo ""

# Test 6: Check for errors
echo "📋 TEST 6: Error Messages (last 5 minutes)"
echo "---"
ERROR_COUNT=$(journalctl -u harvestpilot-autodeploy.service --since "5 minutes ago" | grep -i "error\|failed" | wc -l)
echo "Error count: $ERROR_COUNT"
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo ""
    echo "Recent errors:"
    journalctl -u harvestpilot-autodeploy.service --since "5 minutes ago" | grep -i "error\|failed"
fi
echo ""

# Test 7: System status summary
echo "📋 TEST 7: System Summary"
echo "---"
echo "Service status:"
sudo systemctl status harvestpilot-autodeploy.service --no-pager | head -10
echo ""
echo "Last 5 log lines:"
journalctl -u harvestpilot-autodeploy.service -n 5 --no-pager
echo ""

echo "=========================================="
echo "Diagnostic Complete"
echo "=========================================="
echo ""
echo "Interpretation Guide:"
echo "  ✅ Heartbeats = Service is working correctly"
echo "  ❌ No heartbeats = Service stopped or heartbeat failing"
echo "  ⚠️  Errors = Check error messages above"
echo ""
echo "If no heartbeats found:"
echo "  1. Restart service: sudo systemctl restart harvestpilot-autodeploy.service"
echo "  2. Check logs: journalctl -u harvestpilot-autodeploy.service -f"
echo "  3. Verify Firebase credentials exist"
echo ""
