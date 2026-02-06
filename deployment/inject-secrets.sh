#!/bin/bash
# Secrets Injection Script for HarvestPilot Deployment
# Ensures all required secrets are properly injected before deployment
# Run this during automated deployments to inject GitHub Secrets

set -euo pipefail

REPO_PATH="${1:-.}"
LOG_FILE="${LOG_FILE:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Determine log file location - use repo local if /var/log not writable
if [ -z "$LOG_FILE" ]; then
    # Try system log first
    if touch /var/log/harvestpilot-secrets-inject.log 2>/dev/null; then
        LOG_FILE="/var/log/harvestpilot-secrets-inject.log"
    else
        # Fall back to local repo log
        LOG_FILE="$REPO_PATH/.secrets-inject.log"
    fi
fi

# Create log directory if needed
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_message() {
    local level=$1
    shift
    local msg="$@"
    local color=$NC
    
    case $level in
        ERROR)   color=$RED ;;
        SUCCESS) color=$GREEN ;;
        WARN)    color=$YELLOW ;;
    esac
    
    echo -e "${color}[$TIMESTAMP] [$level] $msg${NC}"
    # Try to write to log file, but don't fail if we can't
    echo "[$TIMESTAMP] [$level] $msg" >> "$LOG_FILE" 2>/dev/null || true
}

# Verify environment variables are set
verify_env_vars() {
    local required_vars=(
        "FIREBASE_KEY_JSON"
        "PI_MODEL"
        "MODULE_ID"
        "PUMP_GPIO"
        "LIGHT_GPIO"
        "DHT_GPIO"
        "WATER_GPIO"
    )
    
    log_message "WARN" "Verifying required environment variables..."
    local missing=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            missing+=("$var")
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_message "ERROR" "Missing required environment variables: ${missing[*]}"
        return 1
    fi
    
    log_message "SUCCESS" "All required environment variables are set"
    return 0
}

# Inject Firebase credentials
inject_firebase_credentials() {
    log_message "WARN" "Injecting Firebase credentials..."
    
    if [ -z "${FIREBASE_KEY_JSON:-}" ]; then
        log_message "ERROR" "FIREBASE_KEY_JSON not set"
        return 1
    fi
    
    local firebase_path="$REPO_PATH/firebase-key.json"
    
    # Write Firebase credentials securely
    {
        set +x  # Don't echo credentials
        printf '%s' "$FIREBASE_KEY_JSON" > "$firebase_path"
    } 2>/dev/null
    
    # Verify it's valid JSON
    if ! python3 -c "import json; json.load(open('$firebase_path', 'r', encoding='utf-8'))" 2>/dev/null; then
        log_message "ERROR" "Invalid Firebase JSON credentials"
        rm -f "$firebase_path"
        return 1
    fi
    
    # Set restrictive permissions
    chmod 600 "$firebase_path"
    
    log_message "SUCCESS" "Firebase credentials injected securely"
    return 0
}

# Inject environment variables into .env file
inject_env_file() {
    log_message "WARN" "Injecting environment configuration..."
    
    local env_path="$REPO_PATH/.env"
    local env_tmp="${env_path}.tmp.$$"
    
    # Create or update .env file
    cat > "$env_tmp" << EOF
# HarvestPilot RaspServer Configuration
# Auto-generated during deployment - $(date)

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=$REPO_PATH/firebase-key.json

# Device Configuration
PI_MODEL=${PI_MODEL:-pi4}
MODULE_ID=${MODULE_ID:-raspserver-001}

# GPIO Configuration
PUMP_GPIO=${PUMP_GPIO:-17}
LIGHT_GPIO=${LIGHT_GPIO:-18}
DHT_GPIO=${DHT_GPIO:-4}
WATER_GPIO=${WATER_GPIO:-23}

# Service Configuration
SYNC_INTERVAL_MS=3600000
HEARTBEAT_INTERVAL_MS=300000
LOG_LEVEL=INFO

# Deployment metadata
DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DEPLOYED_COMMIT=$(cd "$REPO_PATH" && git rev-parse HEAD 2>/dev/null || echo "unknown")
DEPLOYED_BRANCH=$(cd "$REPO_PATH" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
EOF

    # Backup existing .env if it exists
    if [ -f "$env_path" ]; then
        local backup_path="${env_path}.backup.$(date +%s)"
        cp "$env_path" "$backup_path"
        log_message "WARN" "Backed up existing .env to $backup_path"
    fi
    
    # Move new env file into place
    mv "$env_tmp" "$env_path"
    chmod 600 "$env_path"
    
    log_message "SUCCESS" "Environment configuration injected"
    return 0
}

# Inject GitHub webhook secrets (if applicable)
inject_webhook_secrets() {
    if [ -z "${GITHUB_WEBHOOK_SECRET:-}" ] || [ -z "${DEPLOY_TOKEN:-}" ]; then
        log_message "WARN" "GitHub webhook secrets not provided, skipping webhook setup"
        return 0
    fi
    
    log_message "WARN" "Configuring GitHub webhook..."
    
    local webhook_env="/etc/systemd/system/harvestpilot-webhook.service.d/secrets.conf"
    local webhook_dir="$(dirname "$webhook_env")"
    
    if [ ! -d "$webhook_dir" ]; then
        log_message "WARN" "Webhook systemd directory not found, skipping..."
        return 0
    fi
    
    # Create secrets override file for systemd
    {
        set +x
        cat > "$webhook_env" << EOF
[Service]
Environment="GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET"
Environment="DEPLOY_TOKEN=$DEPLOY_TOKEN"
EOF
    } 2>/dev/null
    
    chmod 600 "$webhook_env"
    
    log_message "SUCCESS" "Webhook secrets configured"
    return 0
}

# Validate all injected secrets
validate_secrets() {
    log_message "WARN" "Validating injected secrets..."
    
    local checks_passed=0
    local checks_total=0
    
    # Check Firebase credentials
    ((checks_total++))
    if [ -f "$REPO_PATH/firebase-key.json" ]; then
        if python3 -c "import json; json.load(open('$REPO_PATH/firebase-key.json', 'r', encoding='utf-8'))" 2>/dev/null; then
            log_message "SUCCESS" "✓ Firebase credentials are valid"
            ((checks_passed++))
        else
            log_message "ERROR" "✗ Firebase credentials are invalid"
        fi
    else
        log_message "ERROR" "✗ Firebase credentials file not found"
    fi
    
    # Check .env file
    ((checks_total++))
    if [ -f "$REPO_PATH/.env" ]; then
        if grep -q "FIREBASE_CREDENTIALS_PATH" "$REPO_PATH/.env"; then
            log_message "SUCCESS" "✓ Environment file configured"
            ((checks_passed++))
        else
            log_message "ERROR" "✗ Environment file incomplete"
        fi
    else
        log_message "ERROR" "✗ Environment file not found"
    fi
    
    # Check GPIO configuration
    ((checks_total++))
    if grep -q "PUMP_GPIO" "$REPO_PATH/.env" && grep -q "LIGHT_GPIO" "$REPO_PATH/.env"; then
        log_message "SUCCESS" "✓ GPIO configuration set"
        ((checks_passed++))
    else
        log_message "ERROR" "✗ GPIO configuration incomplete"
    fi
    
    log_message "WARN" "Validation: $checks_passed/$checks_total checks passed"
    
    if [ $checks_passed -eq $checks_total ]; then
        log_message "SUCCESS" "All secrets validated successfully"
        return 0
    else
        log_message "ERROR" "Some secrets validation checks failed"
        return 1
    fi
}

# Generate secrets status report
generate_report() {
    log_message "WARN" "Generating deployment report..."
    
    local report_file="$REPO_PATH/.deployment-secrets-report.json"
    
    cat > "$report_file" << EOF
{
  "injected_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "secrets_status": {
    "firebase_credentials": $([ -f "$REPO_PATH/firebase-key.json" ] && echo "✓ injected" || echo "✗ missing"),
    "env_file": $([ -f "$REPO_PATH/.env" ] && echo "✓ injected" || echo "✗ missing"),
    "gpio_config": $(grep -q "PUMP_GPIO" "$REPO_PATH/.env" 2>/dev/null && echo "✓ set" || echo "✗ missing"),
    "webhook_secrets": $([ -f "/etc/systemd/system/harvestpilot-webhook.service.d/secrets.conf" ] 2>/dev/null && echo "✓ configured" || echo "✗ not configured")
  },
  "deployment_info": {
    "repository": "$REPO_PATH",
    "hostname": "$(hostname)",
    "username": "$(whoami)",
    "git_commit": "$(cd "$REPO_PATH" && git rev-parse HEAD 2>/dev/null || echo "unknown")",
    "git_branch": "$(cd "$REPO_PATH" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
  }
}
EOF
    
    chmod 644 "$report_file"
    log_message "SUCCESS" "Report generated: $report_file"
}

# Main execution
main() {
    log_message "WARN" "=== HarvestPilot Secrets Injection Started ==="
    log_message "WARN" "Repository: $REPO_PATH"
    
    cd "$REPO_PATH"
    
    # Execute injection steps
    if ! verify_env_vars; then
        log_message "ERROR" "Environment variable verification failed"
        return 1
    fi
    
    if ! inject_firebase_credentials; then
        log_message "ERROR" "Firebase credentials injection failed"
        return 1
    fi
    
    if ! inject_env_file; then
        log_message "ERROR" "Environment file injection failed"
        return 1
    fi
    
    inject_webhook_secrets || true  # Non-fatal if webhook not available
    
    if ! validate_secrets; then
        log_message "ERROR" "Secrets validation failed"
        return 1
    fi
    
    generate_report
    
    log_message "SUCCESS" "=== HarvestPilot Secrets Injection Complete ==="
    return 0
}

# Run main function
main "$@"
