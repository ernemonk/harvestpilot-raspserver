# How To Update Your Raspberry Pi & Verify Secrets Injection

## Quick Summary

Your Raspberry Pi deployment system is now set up to:
- ✅ Automatically pull latest code from GitHub
- ✅ Automatically inject secrets from environment or cached configuration
- ✅ Validate all credentials before starting services
- ✅ Generate deployment verification reports

## Verify Current Deployment Status

**On your Raspberry Pi, run:**

```bash
cd harvestpilot-raspserver
bash deployment/verify-pi-deployment.sh
```

This script will check:
- ✓ Latest code is deployed
- ✓ Secrets files (.env, firebase-key.json) exist and are valid
- ✓ File permissions are restrictive (600)
- ✓ Service is running
- ✓ Deployment report shows successful injection

## Manually Update Pi & Reinject Secrets

**If you need to update the Pi to latest code:**

```bash
cd harvestpilot-raspserver
bash deployment/update-pi-deployment.sh
```

This script will:
1. Fetch latest changes from GitHub
2. Pull if updates available
3. Run auto-deploy.sh to:
   - Inject secrets (from environment variables if set, or cached)
   - Validate credentials
   - Restart service
4. Verify deployment success

## Understanding Secrets Injection

### How Secrets Get Injected

**Option 1: From GitHub Actions (Automated)**
- When you push to main, GitHub Actions runs
- GitHub Actions loads secrets from GitHub Secrets
- Secrets passed to `inject-secrets.sh` via environment variables
- Script creates .env and firebase-key.json on Pi

**Option 2: From Environment Variables (Manual)**
- If environment variables are set on Pi, they're used
- Useful for testing or manual updates
- Set before calling update script:
  ```bash
  export FIREBASE_KEY_JSON='{"type":"service_account",...}'
  export PI_MODEL="pi4"
  export MODULE_ID="raspserver-001"
  # ... etc
  bash deployment/update-pi-deployment.sh
  ```

**Option 3: From Cached Configuration**
- If .env and firebase-key.json already exist
- Script validates they're still good
- Useful for automatic updates without re-injecting

## Quick Verification Checklist

✅ **Code is Latest**
```bash
cd harvestpilot-raspserver
git log --oneline -1  # Should match GitHub main branch
git status            # Should show "nothing to commit, working tree clean"
```

✅ **Secrets Are Present**
```bash
ls -la firebase-key.json .env
# Both should exist with permissions 600 (-rw-------)

# Validate Firebase JSON
python3 -c "import json; json.load(open('firebase-key.json'))"
# Should not error
```

✅ **Service Is Running**
```bash
sudo systemctl status harvestpilot-raspserver
# Should show "active (running)"

# Check recent logs
sudo journalctl -u harvestpilot-raspserver -n 20
# Should show successful startup and Firebase connections
```

✅ **Deployment Report**
```bash
cat .deployment-secrets-report.json
# Should show all secrets marked as "✓ injected"
```

## Troubleshooting

### Secrets Not Injected?

```bash
# Check if GitHub Actions ran
# Go to: GitHub repo → Actions → Latest workflow

# Check Pi deployment logs
tail -50 /var/log/harvestpilot-secrets-inject.log
tail -50 /var/log/harvestpilot-autodeploy.log

# Check service logs
sudo journalctl -u harvestpilot-raspserver -n 100
```

### Service Won't Start?

```bash
# Verify Firebase credentials are valid
python3 -c "import json; json.load(open('firebase-key.json'))"

# Check file permissions
ls -la firebase-key.json .env
# Both should be 600

# Try restarting manually
sudo systemctl restart harvestpilot-raspserver

# Check full error log
sudo journalctl -u harvestpilot-raspserver --no-pager | tail -50
```

### Manual Secrets Injection

If automated injection didn't work, you can inject manually:

```bash
# 1. Export environment variables (get from GitHub Secrets)
export FIREBASE_KEY_JSON='<YOUR_FIREBASE_JSON>'
export PI_MODEL="pi4"
export MODULE_ID="raspserver-001"
export PUMP_GPIO="17"
export LIGHT_GPIO="18"
export DHT_GPIO="4"
export WATER_GPIO="23"

# 2. Run injection script
bash deployment/inject-secrets.sh

# 3. Restart service
sudo systemctl restart harvestpilot-raspserver

# 4. Verify
bash deployment/verify-pi-deployment.sh
```

## What's New

### New Scripts Added (Commit: de01b5f)

1. **deployment/verify-pi-deployment.sh**
   - Comprehensive deployment status check
   - Verifies code, secrets, permissions, service
   - Shows deployment report
   - Quick checklist summary

2. **deployment/update-pi-deployment.sh**
   - One-command Pi update
   - Pulls latest code
   - Reinjects secrets
   - Verifies deployment

### Complete Secrets Injection System

- ✅ **inject-secrets.sh** - Core injection script
- ✅ **auto-deploy.sh** - Calls injection on updates
- ✅ **GitHub Actions workflow** - Automated deployment
- ✅ **verify-pi-deployment.sh** - Status verification
- ✅ **update-pi-deployment.sh** - Manual updates
- ✅ **Comprehensive documentation** - Setup and troubleshooting

## Example: Complete Workflow

```bash
# 1. On your Pi, check current status
bash harvestpilot-raspserver/deployment/verify-pi-deployment.sh

# 2. If updates needed, update and reinject secrets
bash harvestpilot-raspserver/deployment/update-pi-deployment.sh

# 3. Monitor the update
sudo journalctl -u harvestpilot-raspserver -f

# 4. Verify success
bash harvestpilot-raspserver/deployment/verify-pi-deployment.sh
```

## Key Points

1. **Automated Deployments** - Push to GitHub → Secrets injected → Service updated
2. **Manual Verification** - Run verify script to check status
3. **Manual Updates** - Run update script for on-demand updates
4. **Secrets Validation** - All credentials validated before service starts
5. **Audit Trail** - Deployment report shows when and what was deployed

## Support

For detailed guides, see:
- `deployment/SECRETS_INJECTION_GUIDE.md` - Complete architecture
- `SECRETS_QUICK_REFERENCE.md` - Quick setup guide
- `SECRETS_INDEX.md` - Documentation hub

## Status

✅ Latest code: `de01b5f` - Deployment verification scripts  
✅ Secrets injection: **ACTIVE & READY**  
✅ Automated deployments: **ENABLED**  
✅ Manual update scripts: **AVAILABLE**

---

Your Pi deployment system is now fully equipped with:
- Automatic secrets injection on every deployment
- Manual verification tools
- Easy update commands
- Comprehensive troubleshooting guides

**Everything is ready to go!**
