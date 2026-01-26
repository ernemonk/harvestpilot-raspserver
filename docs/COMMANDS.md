# RaspServer Control Commands

Quick reference for controlling HarvestPilot RaspServer

## Service Management

```bash
# Start service
sudo systemctl start harvestpilot-raspserver

# Stop service
sudo systemctl stop harvestpilot-raspserver

# Restart service
sudo systemctl restart harvestpilot-raspserver

# Enable auto-start on boot
sudo systemctl enable harvestpilot-raspserver

# Disable auto-start
sudo systemctl disable harvestpilot-raspserver

# Check status
sudo systemctl status harvestpilot-raspserver

# View service logs
journalctl -u harvestpilot-raspserver -f
```

## Application Logs

```bash
# View live logs
tail -f logs/raspserver.log

# View last 50 lines
tail -50 logs/raspserver.log

# Search for errors
grep ERROR logs/raspserver.log

# Watch MQTT messages
mosquitto_sub -h localhost -t "harvestpilot/#" -v
```

## Configuration

```bash
# Edit configuration
nano config.py

# View current config
cat config.py | grep -E "^[A-Z_]+ ="
```

## Hardware Testing

```bash
# Test GPIO access
python3 -c "import RPi.GPIO; print('✅ GPIO OK')"

# Test DHT22 sensor
python3 -c "import adafruit_dht; print('✅ DHT22 OK')"

# Read sensors manually
python3 << EOF
import asyncio
from controllers.sensors import SensorController
sensor = SensorController()
result = asyncio.run(sensor.read_all())
print(result)
EOF
```

## Deployment

```bash
# Pull latest code
git pull origin main

# Install dependencies
pip3 install -r requirements.txt

# Deploy and restart
bash ../scripts/deploy-raspserver.sh
```

## Emergency Stop

```bash
# Kill service immediately
sudo systemctl stop harvestpilot-raspserver

# Kill all Python processes
pkill -f main.py

# GPIO cleanup
python3 -c "import RPi.GPIO; RPi.GPIO.cleanup()"
```

## System Info

```bash
# Pi system info
uname -a

# Disk usage
df -h

# Memory usage
free -h

# CPU temperature
vcgencmd measure_temp

# Check internet
ping -c 3 8.8.8.8

# Check MQTT broker
nc -zv YOUR_AGENT_IP 1883
```

## Debugging

```bash
# Run in debug mode
DEBUG=true python3 main.py

# Simulate hardware (no GPIO)
SIMULATE_HARDWARE=true python3 main.py

# Run with detailed logging
LOG_LEVEL=DEBUG python3 main.py

# Monitor in real-time
watch -n 1 'systemctl status harvestpilot-raspserver'
```

## Backup & Restore

```bash
# Backup config
cp config.py config.py.backup

# Backup logs
tar czf raspserver-logs-$(date +%Y%m%d).tar.gz logs/

# Restore config
cp config.py.backup config.py
```

## Performance Monitoring

```bash
# CPU/Memory usage
top -p $(pgrep -f main.py)

# Network traffic
iftop -i eth0

# GPIO status
gpio readall

# Process info
ps aux | grep main.py
```
