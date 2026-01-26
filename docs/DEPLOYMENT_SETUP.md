# HarvestPilot RaspServer Deployment Guide

## ✅ Current Status
- **GitHub Actions Runner**: Active on Raspberry Pi
- **Auto-Deployment**: Enabled (git push → automatic Pi update)
- **Service Status**: Running and monitored

## 🚀 Quick Links
- **Repository**: https://github.com/ernemonk/harvestpilot-raspserver
- **GitHub Actions**: https://github.com/ernemonk/harvestpilot-raspserver/actions
- **Raspberry Pi**: 192.168.1.233 (monkphx@)

## 📋 What's Deployed
1. **HarvestPilot RaspServer** - Main Python application
   - Location: `/home/monkphx/harvestpilot-raspserver`
   - Service: `harvestpilot-raspserver.service`
   - Port: Active and running

2. **GitHub Actions Self-Hosted Runner**
   - Location: `/home/monkphx/actions-runner`
   - Service: `actions.runner.ernemonk-harvestpilot-raspserver.raspserver-runner.service`
   - Status: Running and listening for jobs

## 🔄 How Auto-Deployment Works

### Workflow Trigger
```bash
git push origin main
```

### Automatic Steps (on Pi)
1. Checkout latest code from `origin/main`
2. Install Python dependencies: `pip3 install -r requirements.txt`
3. Restart service: `sudo systemctl restart harvestpilot-raspserver`
4. Verify service is running

### Workflow File
Location: `.github/workflows/deploy.yml`
- **Runs on**: `self-hosted` (your Raspberry Pi)
- **Triggers**: Push to `main` or `develop`
- **Time**: ~1-2 minutes for full deployment

## 🔧 Commands

### Check Service Status
```bash
ssh monkphx@192.168.1.233 "sudo systemctl status harvestpilot-raspserver"
```

### View Logs
```bash
ssh monkphx@192.168.1.233 "sudo journalctl -u harvestpilot-raspserver -n 50 -f"
```

### Restart Service Manually
```bash
ssh monkphx@192.168.1.233 "sudo systemctl restart harvestpilot-raspserver"
```

### Check GitHub Actions Runner
```bash
ssh monkphx@192.168.1.233 "sudo systemctl status actions.runner.ernemonk-harvestpilot-raspserver.raspserver-runner"
```

## 📦 Deployment History
- **Commit**: Latest deployed on `main` branch
- **Last Deploy**: When code is pushed to GitHub
- **Next Deploy**: Push new code to trigger

## 🛠️ Troubleshooting

### Service Won't Start
```bash
ssh monkphx@192.168.1.233 "sudo systemctl status harvestpilot-raspserver --no-pager"
```

### Runner Not Executing Jobs
```bash
ssh monkphx@192.168.1.233 "sudo systemctl status actions.runner.ernemonk-harvestpilot-raspserver.raspserver-runner"
```

### View Workflow Logs
Go to: https://github.com/ernemonk/harvestpilot-raspserver/actions

## 📝 Next Steps
1. Make code changes locally
2. Commit and push to `main`
3. GitHub Actions automatically deploys to Pi
4. Service restarts with new code

---

**Deployed**: January 23, 2026
**Status**: ✅ Active and Auto-Deploying
