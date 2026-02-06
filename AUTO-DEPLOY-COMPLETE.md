# 🚀 HarvestPilot Auto-Deploy System - COMPLETE

## ✅ Setup Status

Your Raspberry Pi is now fully configured with **3 automatic deployment methods**:

| Method | Status | Trigger | Action |
|--------|--------|---------|--------|
| **Boot Startup** | ✅ Active | System restart | Auto pull + restart |
| **Periodic Timer** | ✅ Active | Every 5 minutes | Check & pull if new code |
| **GitHub Webhook** | ✅ Active | Git push to `main` | Instant deployment |

---

## 📋 Services Running

```
✅ harvestpilot-autodeploy.service    - Boot-time auto-deploy
✅ harvestpilot-autodeploy.timer      - Periodic 5-min timer
✅ harvestpilot-webhook.service       - GitHub webhook receiver
✅ harvestpilot-raspserver            - Main service (RaspServer)
```

---

## 🎯 How It Works

### 1️⃣ **Automatic on Boot**
When your Pi restarts, the auto-deploy service automatically:
- Fetches latest code from GitHub main branch
- Pulls changes if newer code exists
- Restarts RaspServer with new code
- **Zero manual intervention needed!**

### 2️⃣ **Periodic Checks (Every 5 Minutes)**
Background timer continuously:
- Checks GitHub for updates
- Pulls new code if available
- Restarts service if needed
- Acts as safety net if boot deploy fails

### 3️⃣ **Real-Time GitHub Webhooks** 
When you push to GitHub:
- GitHub sends webhook to Pi (port 5000)
- Webhook receiver verifies request authenticity
- Auto-deploy runs immediately
- See new code live in seconds!

---

## 🔧 Quick Start Guide

### To Use Auto-Deployment

**Just commit and push to GitHub:**
```bash
git add .
git commit -m "my changes"
git push origin main
```

Your Pi will automatically pull and restart within seconds! ⚡

### To Manually Check Deployment Status

```bash
# View auto-deploy logs
tail -f /var/log/harvestpilot-autodeploy.log

# View webhook logs
tail -f /var/log/harvestpilot-webhook.log

# Check timer next run time
systemctl list-timers harvestpilot-autodeploy.timer

# Manual trigger (optional)
bash ~/harvestpilot-raspserver/deployment/auto-deploy.sh
```

### Service Management Commands

```bash
# View service status
systemctl status harvestpilot-autodeploy.timer
systemctl status harvestpilot-webhook.service
systemctl status harvestpilot-raspserver

# Restart services (if needed)
sudo systemctl restart harvestpilot-webhook.service
sudo systemctl restart harvestpilot-raspserver

# View recent logs
journalctl -u harvestpilot-autodeploy.timer -n 20
journalctl -u harvestpilot-webhook.service -n 20
journalctl -u harvestpilot-raspserver -n 50
```

---

## 🔐 GitHub Webhook Setup (Optional but Recommended)

For **real-time deployments** when you push code, configure GitHub webhook:

1. Go to: https://github.com/ernemonk/harvestpilot-raspserver/settings/hooks
2. Click **Add webhook**
3. Fill in:
   - **Payload URL:** `http://192.168.1.233:5000/webhook`
   - **Content type:** `application/json`
   - **Events:** Check "Push events" only
   - **Active:** ✅ Yes
4. Click **Add webhook**
5. GitHub will test connection - you should see ✅ delivery success

**After setup:**
- Every `git push origin main` triggers instant deployment on Pi
- Check logs: `tail -f /var/log/harvestpilot-webhook.log`

---

## 📂 File Structure

```
deployment/
├── auto-deploy.sh                      # Main deployment script
├── github-webhook-receiver.py          # GitHub webhook listener
├── harvestpilot-autodeploy.service    # Boot systemd service
├── harvestpilot-autodeploy.timer      # 5-min periodic timer
├── harvestpilot-webhook.service       # Webhook systemd service
├── AUTO-DEPLOY-SETUP.md               # Detailed setup guide
└── AUTO-DEPLOY-COMPLETE.md            # This file
```

**System Logs:**
- `/var/log/harvestpilot-autodeploy.log` - Auto-deploy activity
- `/var/log/harvestpilot-webhook.log` - GitHub webhook events
- `journalctl -u harvestpilot-*` - systemd journal entries

---

## 🧪 Testing Deployment

### Test 1: Manual Auto-Deploy
```bash
ssh monkphx@192.168.1.233
bash ~/harvestpilot-raspserver/deployment/auto-deploy.sh
```
Should show:
```
[timestamp] === Auto-Deploy Started ===
[timestamp] ✓ Already up to date. No changes to deploy.
```

### Test 2: Test Webhook Health
```bash
curl http://192.168.1.233:5000/health
```
Should return:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-05T...",
  "service": "harvestpilot-webhook-receiver"
}
```

### Test 3: Full End-to-End Deploy
1. Make a small change locally (e.g., comment in README)
2. Commit and push: `git push origin main`
3. Within seconds, check: `ssh monkphx@192.168.1.233 tail -f /var/log/harvestpilot-autodeploy.log`
4. Should see deployment log entries

---

## ⚠️ Troubleshooting

### Service not running?
```bash
# Check what's wrong
sudo systemctl status harvestpilot-webhook.service
journalctl -u harvestpilot-webhook.service -n 50

# Restart service
sudo systemctl restart harvestpilot-webhook.service
```

### Git pull failures?
```bash
# Check git status on Pi
cd ~/harvestpilot-raspserver
git status
git log --oneline -3

# If conflicts, manually fix:
git stash
git pull origin main
```

### Webhook not receiving?
1. Verify port 5000 is listening: `sudo lsof -i :5000`
2. Check firewall: Ensure port 5000 accessible from internet
3. Test webhook: `curl -X POST http://192.168.1.233:5000/webhook -H "Content-Type: application/json" -d "{}"`
4. Check logs: `tail -f /var/log/harvestpilot-webhook.log`

---

## 📚 Environment Variables

These can be configured via systemd service files:

```bash
# In /etc/systemd/system/harvestpilot-webhook.service
Environment='GITHUB_WEBHOOK_SECRET=your-secret-here'
Environment='DEPLOY_TOKEN=manual-deploy-token'
```

**Webhook Secret:** GitHub generates this when creating webhook. Add to service file for signature verification.

---

## 🎉 You're All Set!

Your HarvestPilot RaspServer now has enterprise-grade auto-deployment:

✅ Survives Pi reboots (auto-pulls on startup)
✅ Handles missed updates (5-min safety check)
✅ Instant deployments (GitHub webhook)
✅ Full logging & monitoring
✅ Easy to debug and troubleshoot

**Next steps:**
1. Reboot Pi to test boot auto-deploy: `sudo reboot`
2. After reboot, verify service running: `systemctl status harvestpilot-raspserver`
3. (Optional) Set up GitHub webhook for real-time deployments

---

**Questions?** Check the logs:
```bash
# All relevant logs
tail -f /var/log/harvestpilot-autodeploy.log
tail -f /var/log/harvestpilot-webhook.log
journalctl -u harvestpilot-raspserver -f
```
