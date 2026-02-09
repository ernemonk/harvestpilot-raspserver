# HarvestPilot Log Retrieval Script

**One-command log access from your Pi!**

Easy scripting for retrieving and filtering logs from your Raspberry Pi deployment.

---

## Quick Start

Run any of these commands from PowerShell:

```powershell
# Get last 50 recent logs (default)
.\get-pi-logs.ps1

# Get GPIO state changes
.\get-pi-logs.ps1 -LogType gpio

# Get errors only
.\get-pi-logs.ps1 -LogType errors

# Get heartbeat activity
.\get-pi-logs.ps1 -LogType heartbeat

# Get Firebase activity
.\get-pi-logs.ps1 -LogType firebase

# Get more lines (e.g., 200 instead of 50)
.\get-pi-logs.ps1 -Lines 200

# Get logs from both services
.\get-pi-logs.ps1 -Service both

# Stream live logs (press Ctrl+C to stop)
.\get-pi-logs.ps1 -Follow

# Custom filter (e.g., grep for 'sync' or 'connected')
.\get-pi-logs.ps1 -Pattern 'sync|connect'

# Combine options
.\get-pi-logs.ps1 -LogType gpio -Lines 30 -Service harvestpilot-autodeploy
```

---

## All Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `-LogType` | `recent`, `errors`, `gpio`, `heartbeat`, `firebase`, `all` | `recent` | Type of logs to filter |
| `-Lines` | Integer | `50` | Number of log lines to retrieve |
| `-Service` | `harvestpilot-raspserver`, `harvestpilot-autodeploy`, `both` | `harvestpilot-raspserver` | Which service(s) to query |
| `-Pattern` | String | - | Custom grep filter (regex) |
| `-Follow` | Switch | - | Stream live logs in real-time |

---

## Examples

### GPIO Monitoring
```powershell
# Watch GPIO state changes
.\get-pi-logs.ps1 -LogType gpio -Lines 50

# Live GPIO monitoring
.\get-pi-logs.ps1 -LogType gpio -Follow
```

### Error Debugging
```powershell
# Show last 100 errors
.\get-pi-logs.ps1 -LogType errors -Lines 100

# Custom error search
.\get-pi-logs.ps1 -Pattern 'error|exception|failed' -Lines 50
```

### Firebase Sync Status
```powershell
# Check Firebase connectivity
.\get-pi-logs.ps1 -LogType firebase -Lines 30

# Check both services for Firebase activity
.\get-pi-logs.ps1 -LogType firebase -Service both
```

### Real-Time Monitoring
```powershell
# Stream all logs from main service
.\get-pi-logs.ps1 -Follow

# Stream only GPIO changes
.\get-pi-logs.ps1 -LogType gpio -Follow

# Press Ctrl+C to stop at any time
```

---

## What Each LogType Shows

- **`recent`** - Last N lines from the service log
- **`errors`** - Errors, failures, exceptions, and critical messages
- **`gpio`** - GPIO state changes, actuator updates, and state changes
- **`heartbeat`** - Heartbeat and sync activity with Firebase
- **`firebase`** - Firebase, Firestore, and database operations
- **`all`** - All log entries (unfiltered, last N lines)

---

## Connection Details

The script uses:
- **Host:** 192.168.1.233
- **User:** monkphx
- **Service:** harvestpilot-raspserver (default)
- **Alternate Service:** harvestpilot-autodeploy

Connection is via `plink.exe` (PuTTY's command-line SSH tool).

---

## Tips

1. **Get more context** → Increase `-Lines` (e.g., `-Lines 200`)
2. **Multiple services** → Use `-Service both` to query both simultaneously
3. **Custom filters** → Use `-Pattern` with regex (case-insensitive)
4. **Live monitoring** → Use `-Follow` instead of scrolling through logs
5. **Chain commands** → Combine parameters for precise queries

---

## Examples with Real Scenarios

### Your Pi crashed, what happened?
```powershell
.\get-pi-logs.ps1 -LogType errors -Lines 200
```

### Is GPIO responding to Firestore commands?
```powershell
.\get-pi-logs.ps1 -LogType gpio -Lines 50
```

### When did Firebase last sync?
```powershell
.\get-pi-logs.ps1 -LogType firebase -Lines 20
```

### Monitor what's happening right now
```powershell
.\get-pi-logs.ps1 -Follow
# Press Ctrl+C when done
```

### Find all "connection" events in the last 100 lines
```powershell
.\get-pi-logs.ps1 -Pattern 'connect' -Lines 100
```

---

## Troubleshooting

If the script fails to connect:
1. Check that plink.exe is at: `C:\Users\User\plink.exe`
2. Verify Pi is online: `ping 192.168.1.233`
3. Test SSH manually with the plink.exe tool
4. Ensure firewall allows SSH (port 22)

---

**Enjoy easy log access! 🚀**
