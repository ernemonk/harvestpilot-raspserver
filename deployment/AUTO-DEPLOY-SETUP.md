# 🤖 GitHub Auto-Deploy Setup for HarvestPilot RaspServer

This guide sets up automatic deployment on your Raspberry Pi with three methods:

1. **Auto-deploy on boot** - Pulls latest code when Pi starts
2. **Periodic auto-deploy** - Pulls every 5 minutes (systemd timer)
3. **GitHub webhook** - Real-time push-triggered deployment

---

## Quick Setup (5 minutes)

### Step 1: Copy deployment scripts to Pi

```bash
scp -r deployment/ monkphx@192.168.1.233:/home/monkphx/harvestpilot-raspserver/
```

### Step 2: Install dependencies on Pi

```bash
ssh monkphx@192.168.1.233
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install flask
```

### Step 3: Create log directory

```bash
ssh monkphx@192.168.1.233
sudo mkdir -p /var/log/harvestpilot
sudo chown monkphx:monkphx /var/log/harvestpilot
```

### Step 4: Install systemd services

```bash
ssh monkphx@192.168.1.233

# Make script executable
chmod +x ~/harvestpilot-raspserver/deployment/auto-deploy.sh

# Install auto-deploy service (runs on boot)
sudo cp ~/harvestpilot-raspserver/deployment/harvestpilot-autodeploy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable harvestpilot-autodeploy.service

# Install auto-deploy timer (runs every 5 minutes)
sudo cp ~/harvestpilot-raspserver/deployment/harvestpilot-autodeploy.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable harvestpilot-autodeploy.timer
sudo systemctl start harvestpilot-autodeploy.timer
```

### Step 5: (Optional) Install webhook receiver for real-time deployments

```bash
ssh monkphx@192.168.1.233

# Install webhook service
sudo cp ~/harvestpilot-raspserver/deployment/harvestpilot-webhook.service /etc/systemd/system/

# Set webhook secret (generate a random string)
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "Webhook secret: $WEBHOOK_SECRET"  # Save this for GitHub

# Update service with secret
sudo sed -i "s/your-webhook-secret-here/$WEBHOOK_SECRET/" /etc/systemd/system/harvestpilot-webhook.service

# Enable and start webhook service
sudo systemctl daemon-reload
sudo systemctl enable harvestpilot-webhook.service
sudo systemctl start harvestpilot-webhook.service

# Verify it's running
sudo systemctl status harvestpilot-webhook.service
```

---

## Method 1: Auto-Deploy on Boot ✅

**What it does:** Automatically pulls latest code and restarts service when Pi starts up

**Enabled by:**
```bash
sudo systemctl enable harvestpilot-autodeploy.service
sudo systemctl start harvestpilot-autodeploy.service
```

**Check status:**
```bash
sudo systemctl status harvestpilot-autodeploy.service
journalctl -u harvestpilot-autodeploy -f  # View live logs
```

---

## Method 2: Periodic Auto-Deploy (Every 5 minutes) ✅

**What it does:** Checks for new code every 5 minutes and pulls if available

**Enabled by:**
```bash
sudo systemctl enable harvestpilot-autodeploy.timer
sudo systemctl start harvestpilot-autodeploy.timer
```

**Check status:**
```bash
sudo systemctl list-timers  # See all timers
sudo systemctl status harvestpilot-autodeploy.timer
journalctl -u harvestpilot-autodeploy -f  # View all runs
```

**Customize interval:**
```bash
# Edit the timer file
sudo nano /etc/systemd/system/harvestpilot-autodeploy.timer

# Change `OnUnitActiveSec=5min` to desired interval:
# - OnUnitActiveSec=1min  (every 1 minute)
# - OnUnitActiveSec=10min (every 10 minutes)
# - OnUnitActiveSec=1h    (every 1 hour)

# Reload
sudo systemctl daemon-reload
sudo systemctl restart harvestpilot-autodeploy.timer
```

---

## Method 3: GitHub Webhook (Real-Time) 🚀

**What it does:** Immediately deploys when you push to GitHub's main branch

### Step 1: Get webhook secret

```bash
ssh monkphx@192.168.1.233
sudo systemctl show -p Environment harvestpilot-webhook.service | grep GITHUB_WEBHOOK_SECRET
```

### Step 2: Configure GitHub webhook

1. Go to GitHub repo: https://github.com/ernemonk/harvestpilot-raspserver
2. Settings → Webhooks → Add webhook
3. Fill in:
   - **Payload URL:** `http://192.168.1.233:5000/webhook`
   - **Content type:** application/json
   - **Secret:** (paste webhook secret from Step 1)
   - **Events:** Just the push event
4. Click "Add webhook"

### Step 3: Test webhook

```bash
# Push a test commit
git commit --allow-empty -m "test webhook"
git push origin main

# Watch logs on Pi
ssh monkphx@192.168.1.233
journalctl -u harvestpilot-webhook -f
```

### Step 4: Setup reverse proxy (optional but recommended)

Use nginx to proxy port 5000 on port 80 (so firewall friendly):

```bash
ssh monkphx@192.168.1.233
sudo apt-get install -y nginx

# Create nginx config
sudo tee /etc/nginx/sites-available/harvestpilot-webhook > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location /webhook {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:5000;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/harvestpilot-webhook /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload
sudo nginx -t
sudo systemctl restart nginx
```

Then update GitHub webhook to: `http://192.168.1.233/webhook`

---

## Checking Everything is Working

### 1. Verify all services are enabled

```bash
ssh monkphx@192.168.1.233
sudo systemctl list-units --all | grep harvestpilot
```

Expected output:
```
harvestpilot-autodeploy.service  loaded   active   exited   HarvestPilot Auto-Deploy Service
harvestpilot-autodeploy.timer    loaded   active   running  HarvestPilot Auto-Deploy Timer
harvestpilot-webhook.service     loaded   active   running  HarvestPilot GitHub Webhook Receiver
```

### 2. View deployment logs

```bash
# Auto-deploy logs
ssh monkphx@192.168.1.233
cat /var/log/harvestpilot-autodeploy.log

# Webhook logs
journalctl -u harvestpilot-webhook -n 50
```

### 3. Test webhook manually

```bash
curl -X POST http://192.168.1.233:5000/webhook \
  -H "X-GitHub-Event: ping" \
  -H "Content-Type: application/json" \
  -d '{"action":"ping"}'

# Should return: {"status":"pong"}
```

### 4. Test manual deployment

```bash
# Get deploy token
ssh monkphx@192.168.1.233
echo $DEPLOY_TOKEN  # Should show random token

# Trigger manual deploy
curl -X POST http://192.168.1.233:5000/deploy \
  -H "X-Deploy-Token: YOUR_TOKEN_HERE"
```

---

## Troubleshooting

### Service won't start

```bash
ssh monkphx@192.168.1.233
sudo journalctl -u harvestpilot-autodeploy -n 20  # Check for errors
sudo systemctl restart harvestpilot-autodeploy.service
```

### Webhook not receiving events

1. Check if webhook service is running:
   ```bash
   sudo systemctl status harvestpilot-webhook.service
   ```

2. Check webhook logs on GitHub (Settings → Webhooks → your webhook → Deliveries)

3. Test connectivity:
   ```bash
   curl -v http://192.168.1.233:5000/health
   ```

### Timer not running

```bash
ssh monkphx@192.168.1.233
sudo systemctl status harvestpilot-autodeploy.timer
sudo systemctl list-timers
journalctl -u harvestpilot-autodeploy.timer -f
```

### Permission denied errors

```bash
ssh monkphx@192.168.1.233
# Make sure script is executable
chmod +x ~/harvestpilot-raspserver/deployment/auto-deploy.sh

# Make sure monkphx can restart service
sudo visudo
# Add this line at bottom:
# monkphx ALL=(ALL) NOPASSWD: /bin/systemctl restart harvestpilot-raspserver
```

---

## Summary

| Method | Trigger | Latency | Setup |
|--------|---------|---------|-------|
| **On Boot** | Pi restart | On next boot | ✅ Easy |
| **Every 5 min** | Timer | 0-5 minutes | ✅ Easy |
| **Webhook** | GitHub push | Immediate | 🔧 Medium |

**Recommended:** Use **Method 1 + 2** for reliability, **Method 3** for speed.

---

**Next:** Make a test commit and watch your Pi auto-deploy! 🚀

