#!/bin/bash

##############################################################################
# HarvestPilot Hardware Serial Deployment Verification Script
# 
# Usage: ./verify_hardware_serial_deployment.sh
# 
# This script verifies that the hardware_serial fallback implementation
# is correctly deployed and running on your Raspberry Pi.
##############################################################################

set -e

# Configuration
PI_USER="${PI_USER:-monkphx}"
PI_HOST="${PI_HOST:-192.168.1.233}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/harvestpilot_pi}"
REPO_PATH="/home/$PI_USER/harvestpilot-raspserver"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} $1"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

print_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Main verification function
main() {
    print_header "HarvestPilot Hardware Serial Verification"
    print_info "Pi: $PI_USER@$PI_HOST"
    print_info "SSH Key: $SSH_KEY"
    print_info "Repository: $REPO_PATH\n"

    # Check SSH connectivity
    print_check "SSH Connectivity"
    if ssh -i "$SSH_KEY" -q "$PI_USER@$PI_HOST" exit 2>/dev/null; then
        print_pass "SSH connection successful"
    else
        print_fail "SSH connection failed - check Pi IP and SSH key"
        exit 1
    fi

    # Part A: Code Deployment Verification
    print_header "Part A: Code Deployment"

    # Check 1: Latest code deployed
    print_check "Latest code deployment"
    COMMIT=$(ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "cd $REPO_PATH && git log -1 --format='%h %s'" 2>/dev/null)
    if [[ "$COMMIT" == *"hardware_serial"* ]]; then
        print_pass "Latest hardware_serial commit deployed: $COMMIT"
    else
        print_warn "Latest commit might not be hardware_serial changes: $COMMIT"
    fi

    # Check 2: Config.py has fallback logic
    print_check "Config fallback implementation"
    if ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "grep -q '_get_hardware_serial' $REPO_PATH/src/config.py" 2>/dev/null; then
        print_pass "Hardware serial fallback function found in config.py"
    else
        print_fail "Hardware serial fallback function not found in config.py"
    fi

    # Check 3: .env file exists
    print_check ".env file presence"
    if ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "test -f $REPO_PATH/.env" 2>/dev/null; then
        print_pass ".env file exists on Pi"
        ENV_CONTENT=$(ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "cat $REPO_PATH/.env | head -10")
        echo "  Content preview:"
        echo "$ENV_CONTENT" | sed 's/^/    /'
    else
        print_fail ".env file not found on Pi"
    fi

    # Part B: Runtime Verification
    print_header "Part B: Runtime Verification"

    # Check 4: Service status
    print_check "Service status"
    SERVICE_STATUS=$(ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo systemctl is-active harvestpilot-raspserver" 2>/dev/null)
    if [ "$SERVICE_STATUS" = "active" ]; then
        print_pass "Service is running (active)"
    else
        print_fail "Service is not running - status: $SERVICE_STATUS"
    fi

    # Check 5: Hardware serial in logs
    print_check "Hardware serial in service logs"
    if ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo journalctl -u harvestpilot-raspserver -n 50 2>/dev/null | grep -q 'hardware_serial'" 2>/dev/null; then
        SERIAL_LOG=$(ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo journalctl -u harvestpilot-raspserver -n 50 2>/dev/null | grep 'hardware_serial' | head -1")
        print_pass "Hardware serial found in logs:"
        echo "  $SERIAL_LOG" | sed 's/^/    /'
    else
        print_warn "Hardware serial not found in recent logs - service may have just restarted"
    fi

    # Check 6: Firebase connection
    print_check "Firebase connection"
    if ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo journalctl -u harvestpilot-raspserver -n 100 2>/dev/null | grep -q 'Connected to Firebase successfully'" 2>/dev/null; then
        print_pass "Firebase connection successful"
    else
        print_warn "Firebase connection not found in logs - may need to wait for full initialization"
    fi

    # Part C: Configuration Verification
    print_header "Part C: Configuration Verification"

    # Check 7: Hardware serial detection
    print_check "Hardware serial detection (config)"
    PYTHON_OUTPUT=$(ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" << 'PYTHON_EOF' 2>/dev/null
python3 << 'INNER_EOF'
import sys
sys.path.insert(0, '/home/monkphx/harvestpilot-raspserver')
try:
    from src import config
    print(f"HARDWARE_SERIAL: {config.HARDWARE_SERIAL}")
    print(f"DEVICE_ID: {config.DEVICE_ID}")
except Exception as e:
    print(f"ERROR: {e}")
INNER_EOF
PYTHON_EOF
)
    
    if [[ "$PYTHON_OUTPUT" == *"HARDWARE_SERIAL:"* ]]; then
        print_pass "Config detects hardware serial:"
        echo "$PYTHON_OUTPUT" | sed 's/^/    /'
    else
        print_fail "Could not detect hardware serial from config"
        echo "$PYTHON_OUTPUT" | sed 's/^/    /'
    fi

    # Check 8: Pi actual serial
    print_check "Raspberry Pi hardware serial (/proc/cpuinfo)"
    PI_SERIAL=$(ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "cat /proc/cpuinfo 2>/dev/null | grep Serial | awk '{print \$NF}'" 2>/dev/null)
    if [ -n "$PI_SERIAL" ]; then
        print_pass "Pi serial from /proc/cpuinfo: $PI_SERIAL"
    else
        print_warn "Could not read serial from /proc/cpuinfo (normal if not actual Pi)"
    fi

    # Part D: Integration Verification
    print_header "Part D: Integration Verification"

    # Check 9: Service file exists
    print_check "Systemd service configuration"
    if ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo test -f /etc/systemd/system/harvestpilot-raspserver.service" 2>/dev/null; then
        print_pass "Systemd service file found"
    else
        print_fail "Systemd service file not found"
    fi

    # Check 10: Requirements.txt
    print_check "Python requirements"
    if ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "test -f $REPO_PATH/requirements.txt" 2>/dev/null; then
        print_pass "requirements.txt exists"
    else
        print_fail "requirements.txt not found"
    fi

    # Summary
    print_header "Verification Summary"
    
    TOTAL=$((PASSED + FAILED + WARNINGS))
    
    echo -e "${GREEN}✓ Passed: $PASSED${NC}"
    echo -e "${RED}✗ Failed: $FAILED${NC}"
    echo -e "${YELLOW}⚠ Warnings: $WARNINGS${NC}"
    echo -e "\n${BLUE}Total Checks: $TOTAL${NC}\n"

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║${NC}  ✅ DEPLOYMENT VERIFICATION SUCCESSFUL!                  ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}  Hardware serial implementation is running correctly    ${GREEN}║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}\n"
        return 0
    else
        echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║${NC}  ❌ DEPLOYMENT VERIFICATION FAILED                       ${RED}║${NC}"
        echo -e "${RED}║${NC}  Please check the errors above and try again            ${RED}║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}\n"
        return 1
    fi
}

# Run main function
main "$@"
