# How to Check Your Heartbeat Status

Since SSH password authentication isn't working, here's the workaround:

## Option 1: SSH In Manually (One Time)

```bash
ssh pi@192.168.1.233
# Enter your password when prompted (the correct one)
```

Once logged in, run this to see your heartbeat logs:

```bash
sudo journalctl -u harvestpilot-autodeploy.service -n 100
```

Look for messages like:
- `💓 Heartbeat #1 sent successfully` ✅ (good - service is running)
- `❌ Heartbeat failed` (service running but Firebase error)
- No heartbeat lines (service not running)

## Option 2: Check Service Status

```bash
ssh pi@192.168.1.233 "sudo systemctl status harvestpilot-autodeploy.service"
# Again, enter your password
```

## Option 3: Stream Live Logs

```bash
ssh pi@192.168.1.233 "sudo journalctl -u harvestpilot-autodeploy.service -f"
# Ctrl+C to stop
```

---

## The Real Issue

Your Python heartbeat code is **correct and should be working**, but the service appears to not be running based on Firebase showing a stale `lastHeartbeat` timestamp.

## What We Know

From your Firebase data:
- `lastHeartbeat`: February 6, 2026 at 7:34:42 PM (STALE - from yesterday)
- `lastSyncAt`: February 6, 2026 at 7:34:42 PM (also stale)
- Service might have crashed or stopped

## Next Steps

1. **SSH into your Pi** and check the logs (see Option 1 above)
2. **Look for error messages** in journalctl output
3. **If service is stopped**, restart it:
   ```bash
   sudo systemctl restart harvestpilot-autodeploy.service
   ```

4. **Check if it starts without errors:**
   ```bash
   sudo systemctl start harvestpilot-autodeploy.service
   sleep 5
   sudo journalctl -u harvestpilot-autodeploy.service -n 50
   ```

---

## Still Need Help?

If you're stuck on the SSH password, can you:
1. Tell me the actual correct password for the `pi` user on your Raspberry Pi?
2. Or try these common defaults: `raspberry`, `password`, `123456`?

The password "149246116" doesn't seem to work with SSH auth on your Pi.
