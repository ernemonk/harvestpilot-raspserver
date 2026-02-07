#!/bin/bash
# HarvestPilot Pi - Code & Secrets Injection Test Suite
# Run this on your Raspberry Pi to verify:
# 1. Latest code is deployed
# 2. Secrets are properly injected
# 3. Service is running with correct configuration
# 4. Firebase connectivity is working

set -euo pipefail

REPO_PATH="/home/monkphx/harvestpilot-raspserver"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
TEST_LOG="/tmp/harvestpilot-test-$(date +%s).log"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNING=0

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  HarvestPilot Raspberry Pi - CODE & SECRETS INJECTION TEST SUITE   ║"
echo "║  $TIMESTAMP"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    ((TESTS_WARNING++))
}

info() {
    echo -e "${BLUE}ℹ INFO${NC}: $1"
}

section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "TEST: $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: Git Repository Status
# ═══════════════════════════════════════════════════════════════════════════

section "Git Repository & Latest Code"

cd "$REPO_PATH"

# Check if git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    pass "Git repository detected"
else
    fail "Not a git repository"
    exit 1
fi

# Check branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "main" ]; then
    pass "On main branch"
else
    warn "On branch '$CURRENT_BRANCH' (expected 'main')"
fi

# Check remote
if git remote | grep -q origin; then
    pass "Origin remote configured"
else
    fail "No origin remote"
fi

# Check if up to date
LOCAL_COMMIT=$(git rev-parse @)
REMOTE_COMMIT=$(git rev-parse origin/main 2>/dev/null || echo "unknown")

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    pass "Code is up to date with origin/main"
    info "Latest commit: $(git log -1 --oneline)"
else
    warn "Local commit differs from remote"
    info "Local:  $LOCAL_COMMIT"
    info "Remote: $REMOTE_COMMIT"
fi

# Show latest commits
info "Latest 3 commits:"
git log --oneline -3 | sed 's/^/  /'

# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: Secrets Files & Format
# ═══════════════════════════════════════════════════════════════════════════

section "Secrets Files & Configuration"

# Check .env file
if [ -f ".env" ]; then
    pass ".env file exists"
    
    ENV_SIZE=$(wc -c < .env)
    info ".env size: $ENV_SIZE bytes"
    
    # Check for required variables
    REQUIRED_VARS=("FIREBASE_CREDENTIALS_PATH" "PI_MODEL" "MODULE_ID" "PUMP_GPIO" "LIGHT_GPIO")
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^$var=" .env; then
            pass "Variable $var found in .env"
        else
            fail "Variable $var NOT found in .env"
        fi
    done
else
    fail ".env file NOT found"
fi

echo ""

# Check firebase-key.json
if [ -f "firebase-key.json" ]; then
    pass "firebase-key.json exists"
    
    KEY_SIZE=$(wc -c < firebase-key.json)
    info "firebase-key.json size: $KEY_SIZE bytes"
    
    # Validate JSON
    if python3 -c "import json; json.load(open('firebase-key.json'))" 2>/dev/null; then
        pass "firebase-key.json is valid JSON"
        
        # Extract and display key info
        PROJECT_ID=$(python3 -c "import json; print(json.load(open('firebase-key.json')).get('project_id', 'unknown'))" 2>/dev/null)
        CLIENT_EMAIL=$(python3 -c "import json; print(json.load(open('firebase-key.json')).get('client_email', 'unknown'))" 2>/dev/null)
        
        info "Project ID: $PROJECT_ID"
        info "Service Account: $CLIENT_EMAIL"
    else
        fail "firebase-key.json is INVALID JSON"
    fi
else
    fail "firebase-key.json NOT found"
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: File Permissions
# ═══════════════════════════════════════════════════════════════════════════

section "File Permissions (Security Check)"

# Check .env permissions
if [ -f ".env" ]; then
    ENV_PERMS=$(stat -c "%a" .env)
    if [ "$ENV_PERMS" = "600" ]; then
        pass ".env has restrictive permissions (600)"
    else
        fail ".env permissions are $ENV_PERMS (should be 600)"
    fi
fi

# Check firebase-key.json permissions
if [ -f "firebase-key.json" ]; then
    KEY_PERMS=$(stat -c "%a" firebase-key.json)
    if [ "$KEY_PERMS" = "600" ]; then
        pass "firebase-key.json has restrictive permissions (600)"
    else
        fail "firebase-key.json permissions are $KEY_PERMS (should be 600)"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: Service Running & Status
# ═══════════════════════════════════════════════════════════════════════════

section "Service Status & Execution"

if sudo systemctl is-active --quiet harvestpilot-raspserver; then
    pass "Service is RUNNING"
    
    # Get uptime
    UPTIME=$(systemctl show -p ActiveEnterTimestamp --value harvestpilot-raspserver)
    info "Service started at: $UPTIME"
    
    # Get PID
    PID=$(systemctl show -p MainPID --value harvestpilot-raspserver)
    if [ "$PID" != "0" ]; then
        pass "Service has active process (PID: $PID)"
        
        # Check memory usage
        if [ -f "/proc/$PID/status" ]; then
            MEMORY=$(grep "VmRSS:" "/proc/$PID/status" | awk '{print $2}' | numfmt --to=iec 2>/dev/null || echo $2)
            info "Service memory usage: $MEMORY"
        fi
    fi
else
    fail "Service is NOT RUNNING"
    info "Try: sudo systemctl restart harvestpilot-raspserver"
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: Service Logs & Firebase Connection
# ═══════════════════════════════════════════════════════════════════════════

section "Service Logs & Firebase Connectivity"

info "Checking recent service logs..."

# Check for successful Firebase initialization
if sudo journalctl -u harvestpilot-raspserver -n 100 --no-pager | grep -q "Firebase\|Firestore\|Connected"; then
    pass "Firebase connection detected in logs"
else
    warn "No Firebase connection messages in recent logs"
fi

# Check for errors
ERROR_COUNT=$(sudo journalctl -u harvestpilot-raspserver -n 100 --no-pager | grep -i "error\|failed" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    pass "No errors in recent logs"
else
    warn "Found $ERROR_COUNT error/failed messages in logs"
fi

# Show last 10 log lines
info "Last 10 service log lines:"
sudo journalctl -u harvestpilot-raspserver -n 10 --no-pager | sed 's/^/  /'

# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: Deployment Report
# ═══════════════════════════════════════════════════════════════════════════

section "Deployment & Secrets Injection Report"

if [ -f ".deployment-secrets-report.json" ]; then
    pass "Deployment report exists"
    
    info "Report contents:"
    python3 -m json.tool .deployment-secrets-report.json 2>/dev/null | sed 's/^/  /' || cat .deployment-secrets-report.json | sed 's/^/  /'
else
    warn "No deployment report (will be created on next deployment)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 7: Configuration Environment Variables
# ═══════════════════════════════════════════════════════════════════════════

section "Environment Configuration"

if [ -f ".env" ]; then
    info "Environment variables from .env:"
    
    # Display key variables (hide sensitive values)
    while IFS='=' read -r key value; do
        if [[ $key =~ ^[A-Z_]+$ ]]; then
            if [[ $key == *"SECRET"* ]] || [[ $key == *"KEY"* ]] || [[ $key == *"TOKEN"* ]] || [[ $key == *"PASSWORD"* ]]; then
                echo "  $key=***HIDDEN***"
            else
                echo "  $key=$value"
            fi
        fi
    done < .env
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 8: GPIO Configuration
# ═══════════════════════════════════════════════════════════════════════════

section "GPIO Configuration"

if [ -f ".env" ]; then
    GPIO_VARS=("PUMP_GPIO" "LIGHT_GPIO" "DHT_GPIO" "WATER_GPIO")
    for gpio_var in "${GPIO_VARS[@]}"; do
        if grep -q "^$gpio_var=" .env; then
            GPIO_PIN=$(grep "^$gpio_var=" .env | cut -d'=' -f2)
            if [ -n "$GPIO_PIN" ]; then
                pass "$gpio_var is configured to pin $GPIO_PIN"
            fi
        fi
    done
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 9: Network & Connectivity
# ═══════════════════════════════════════════════════════════════════════════

section "Network & Connectivity"

# Check IP address
IP=$(hostname -I | awk '{print $1}')
if [ -n "$IP" ]; then
    pass "IP address: $IP"
else
    warn "Could not determine IP address"
fi

# Check internet connectivity
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    pass "Internet connectivity confirmed"
else
    warn "No internet connectivity"
fi

# Check Firebase domain
if ping -c 1 firebaseio.com >/dev/null 2>&1; then
    pass "Firebase domain reachable"
else
    warn "Firebase domain not reachable"
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST 10: Secrets Injection Verification
# ═══════════════════════════════════════════════════════════════════════════

section "Secrets Injection - Direct Verification"

if [ -f ".env" ] && [ -f "firebase-key.json" ]; then
    pass "Both .env and firebase-key.json files present"
    
    # Check if files are readable
    if [ -r ".env" ] && [ -r "firebase-key.json" ]; then
        pass "Secrets files are readable"
    else
        fail "Secrets files are not readable"
    fi
    
    # Check file timestamps (recently modified?)
    ENV_AGE=$(find .env -mtime +7 2>/dev/null && echo "old" || echo "recent")
    KEY_AGE=$(find firebase-key.json -mtime +7 2>/dev/null && echo "old" || echo "recent")
    
    if [ "$ENV_AGE" = "recent" ]; then
        pass ".env file modified recently"
    else
        warn ".env file not modified in 7+ days"
    fi
    
    if [ "$KEY_AGE" = "recent" ]; then
        pass "firebase-key.json modified recently"
    else
        warn "firebase-key.json not modified in 7+ days"
    fi
else
    fail "Missing secrets files"
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY & RESULTS
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  TEST RESULTS SUMMARY                                             ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

echo ""
echo -e "${GREEN}✓ PASSED: $TESTS_PASSED${NC}"
echo -e "${YELLOW}⚠ WARNINGS: $TESTS_WARNING${NC}"
echo -e "${RED}✗ FAILED: $TESTS_FAILED${NC}"

TOTAL=$((TESTS_PASSED + TESTS_WARNING + TESTS_FAILED))
echo ""
echo "Total tests: $TOTAL"

# Overall status
echo ""
if [ $TESTS_FAILED -eq 0 ]; then
    if [ $TESTS_WARNING -eq 0 ]; then
        echo -e "${GREEN}════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ ALL SYSTEMS OPERATIONAL${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo "✓ Latest code is deployed"
        echo "✓ Secrets are properly injected"
        echo "✓ Service is running"
        echo "✓ Firebase is configured and reachable"
        echo ""
        EXIT_CODE=0
    else
        echo -e "${YELLOW}════════════════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}⚠️  OPERATIONAL WITH WARNINGS${NC}"
        echo -e "${YELLOW}════════════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo "Review warnings above for details"
        echo ""
        EXIT_CODE=0
    fi
else
    echo -e "${RED}════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}❌ TESTS FAILED - ACTION REQUIRED${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Review failures above and troubleshoot"
    echo ""
    EXIT_CODE=1
fi

# Recommendations
echo "📋 Next Steps:"
echo "  1. Review any warnings or failures above"
echo "  2. Monitor service: sudo journalctl -u harvestpilot-raspserver -f"
echo "  3. Check Firebase Console for device heartbeat"
echo "  4. Re-run this test after fixes: $0"

echo ""
echo "Test completed: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Log saved to: $TEST_LOG"

exit $EXIT_CODE
