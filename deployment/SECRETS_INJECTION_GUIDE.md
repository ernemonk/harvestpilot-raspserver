# Secrets Injection Strategy for HarvestPilot Deployment

## Overview

This document explains how HarvestPilot ensures that sensitive information (API keys, Firebase credentials, GPIO configurations) are securely injected into the application during deployment across all environments (web app, Raspberry Pi servers, and local testing).

## Architecture

### 1. GitHub Secrets Storage

All sensitive information is stored in GitHub Actions secrets:

```
Repository Settings → Secrets and variables → Actions
```

**Required Secrets:**

#### Firebase Credentials
- `FIREBASE_KEY_JSON` - Complete Firebase service account JSON
- `VITE_FIREBASE_API_KEY` - Firebase API key for web
- `VITE_FIREBASE_AUTH_DOMAIN` - Auth domain
- `VITE_FIREBASE_PROJECT_ID` - Project ID
- `VITE_FIREBASE_STORAGE_BUCKET` - Storage bucket
- `VITE_FIREBASE_MESSAGING_SENDER_ID` - Messaging sender ID
- `VITE_FIREBASE_APP_ID` - App ID

#### Raspberry Pi Configuration
- `PI_MODEL` - Pi model (pi4, pi5, etc.)
- `MODULE_ID` - Device identifier
- `PUMP_GPIO` - GPIO pin for pump
- `LIGHT_GPIO` - GPIO pin for lights
- `DHT_GPIO` - GPIO pin for temperature/humidity sensor
- `WATER_GPIO` - GPIO pin for water level sensor

#### Webhook Secrets (optional)
- `GITHUB_WEBHOOK_SECRET` - Secret for verifying GitHub webhooks
- `DEPLOY_TOKEN` - Token for triggering deployments

### 2. Deployment Flow

```
┌─────────────────────────┐
│  Code Push to GitHub    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  GitHub Actions Workflow Triggered  │
└────────────┬────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│  Step 1: Checkout Code                 │
└────────────┬───────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│  Step 2: Inject Secrets (inject-secrets  │
│          .sh with GitHub Secrets env)    │
│  ├─ Write Firebase credentials           │
│  ├─ Generate .env file                   │
│  ├─ Configure webhook secrets            │
│  └─ Validate all injected secrets        │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│  Step 3: Setup & Deploy                  │
│  ├─ Setup GPIO configuration             │
│  ├─ Initialize device registration       │
│  └─ Restart services                     │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│  Step 4: Deployment Complete             │
│  ├─ Generate deployment report           │
│  └─ Verify all services running          │
└──────────────────────────────────────────┘
```

## Scripts Overview

### 1. `deployment/inject-secrets.sh`

**Purpose:** Injects GitHub secrets into the deployment environment

**Usage:**
```bash
bash deployment/inject-secrets.sh [REPO_PATH]
```

**What it does:**
- ✅ Verifies all required environment variables are set
- ✅ Writes Firebase credentials to `firebase-key.json`
- ✅ Generates/updates `.env` file with all configuration
- ✅ Configures webhook secrets (if provided)
- ✅ Validates all injected secrets
- ✅ Generates deployment report

**Output:**
- `firebase-key.json` - Firebase service account (600 permissions)
- `.env` - Environment configuration with deployment metadata
- `.deployment-secrets-report.json` - Validation report

### 2. `deployment/auto-deploy.sh`

**Purpose:** Automatically pulls updates and injects secrets when called by webhook

**Updated to:**
1. Fetch latest code
2. **Call `inject-secrets.sh`** to inject all secrets
3. Restart services

This ensures secrets are refreshed on each deployment.

## Workflow Integration

### GitHub Actions Workflow (`harvestpilot-raspserver/.github/workflows/deploy.yml`)

```yaml
- name: Inject secrets and environment configuration
  env:
    FIREBASE_KEY_JSON: ${{ secrets.FIREBASE_KEY_JSON }}
    PI_MODEL: ${{ secrets.PI_MODEL || 'pi4' }}
    MODULE_ID: ${{ secrets.MODULE_ID || '' }}
    # ... other secrets ...
  run: |
    bash deployment/inject-secrets.sh "$(pwd)"
```

**Key Features:**
- All secrets passed as environment variables
- Secrets never logged or exposed in CI output
- Automatic validation and reporting
- Works with both initial deployment and updates

## Security Best Practices

### ✅ What We Do Right

1. **Environment Variables** - Secrets passed via environment, not hardcoded
2. **File Permissions** - Firebase key and .env files created with 600 permissions (owner read/write only)
3. **Secure Execution** - `set +x` in scripts prevents secret output in logs
4. **Validation** - JSON validation ensures credentials are correct before use
5. **Backup Creation** - Old .env files backed up before updates
6. **Metadata Tracking** - Deployment reports track when/what was deployed
7. **Separation of Concerns** - Secrets injected separately from deployment logic

### 🔒 Additional Security Measures

1. **GitHub Secret Encryption** - GitHub encrypts all secrets at rest
2. **Limited Scope** - Self-hosted runner means secrets only accessible to your infrastructure
3. **Audit Trail** - All injections logged to deployment logs
4. **Rate Limiting** - Webhook receiver validates signatures

## Setup Instructions

### 1. Add GitHub Secrets

For **harvestpilot-raspserver**:
```bash
gh secret set FIREBASE_KEY_JSON < firebase-key.json
gh secret set PI_MODEL -b harvestpilot-raspserver
gh secret set MODULE_ID "raspserver-001" -b harvestpilot-raspserver
gh secret set PUMP_GPIO "17" -b harvestpilot-raspserver
# ... etc
```

For **harvestpilot-webapp**:
```bash
gh secret set VITE_FIREBASE_API_KEY < ~/.env
# ... other VITE_ secrets
```

### 2. Verify Secrets Are Set

```bash
# Check secrets are configured
gh secret list -R ernemonk/harvestpilot-raspserver
gh secret list -R ernemonk/harvestpilot-webapp
```

### 3. Test Deployment

```bash
# Trigger test deployment
git push origin main
# Watch GitHub Actions workflow
```

## Environment Variables Reference

### `.env` File Structure

```bash
# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=firebase-key.json

# Device Configuration
PI_MODEL=pi4
MODULE_ID=raspserver-001

# GPIO Configuration
PUMP_GPIO=17
LIGHT_GPIO=18
DHT_GPIO=4
WATER_GPIO=23

# Service Configuration
SYNC_INTERVAL_MS=3600000
HEARTBEAT_INTERVAL_MS=300000
LOG_LEVEL=INFO

# Deployment metadata (auto-generated)
DEPLOYED_AT=2026-02-06T12:34:56Z
DEPLOYED_COMMIT=abc123def456...
DEPLOYED_BRANCH=main
```

## Deployment Report

After injection, check `.deployment-secrets-report.json`:

```json
{
  "injected_at": "2026-02-06T12:34:56Z",
  "secrets_status": {
    "firebase_credentials": "✓ injected",
    "env_file": "✓ injected",
    "gpio_config": "✓ set",
    "webhook_secrets": "✓ configured"
  },
  "deployment_info": {
    "repository": "/home/monkphx/harvestpilot-raspserver",
    "hostname": "raspberrypi",
    "git_commit": "abc123def456...",
    "git_branch": "main"
  }
}
```

## Troubleshooting

### Secrets Not Injected?

1. **Check GitHub Secrets are set:**
   ```bash
   gh secret list -R ernemonk/harvestpilot-raspserver
   ```

2. **Check workflow logs:**
   - Go to: Actions → Last workflow run → Logs
   - Look for "inject-secrets.sh" step

3. **Verify script permissions:**
   ```bash
   ls -la deployment/inject-secrets.sh
   # Should show x (executable)
   ```

### Firebase Credentials Invalid?

1. **Verify JSON is valid:**
   ```bash
   python3 -c "import json; json.load(open('firebase-key.json'))"
   ```

2. **Check file permissions:**
   ```bash
   ls -la firebase-key.json
   # Should show 600 (-rw-------)
   ```

### .env File Missing Variables?

1. **Check all GitHub secrets are set**
2. **Look at deployment logs for errors**
3. **Manually verify .env file:**
   ```bash
   cat .env
   ```

## Monitoring and Validation

### Deployment Logs

Check logs to verify successful injection:

```bash
# On Raspberry Pi:
cat /var/log/harvestpilot-autodeploy.log
cat /var/log/harvestpilot-secrets-inject.log

# Check service status:
sudo systemctl status harvestpilot-raspserver
sudo journalctl -u harvestpilot-raspserver -f

# Check web app environment:
echo $VITE_FIREBASE_API_KEY  # Should be set during build
```

### Validation Steps

The injection script automatically validates:
- ✅ Firebase JSON is valid and readable
- ✅ All environment variables are set
- ✅ File permissions are restrictive (600)
- ✅ Deployment metadata is recorded
- ✅ Services can access credentials

## Future Improvements

1. **Hashicorp Vault** - Replace GitHub secrets with Vault for larger deployments
2. **Secrets Rotation** - Automatic rotation of Firebase credentials
3. **Encryption at Rest** - Encrypt .env files on disk
4. **Audit Logging** - Enhanced audit trail of secret access
5. **Multi-Region Sync** - Automatically sync secrets to multiple devices
6. **Emergency Rotation** - Quick procedure to rotate all secrets if compromised

## References

- [GitHub Actions: Encrypted secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Firebase Service Account Documentation](https://firebase.google.com/docs/admin/setup#node.js)
- [Linux File Permissions](https://en.wikipedia.org/wiki/File_system_permissions)
- [Secure Shell Scripting](https://mywiki.wooledge.org/BashGuide/Practices)
