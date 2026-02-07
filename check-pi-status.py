#!/usr/bin/env python3
"""
HarvestPilot Pi Diagnostics - PROPER SSH with automatic password
Uses paramiko with forced password auth, NO prompts
"""

import sys
import subprocess

# Install paramiko if needed
try:
    import paramiko
except ImportError:
    print("[*] Installing paramiko...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "paramiko"], check=True)
    import paramiko

import logging
logging.basicConfig(level=logging.CRITICAL)

# Configuration
PI_HOST = "192.168.1.233"
PI_USER = "pi"
PI_PASSWORD = "149246116"

print("=" * 60)
print("HarvestPilot Pi Diagnostics - AUTOMATIC PASSWORD AUTH")
print("=" * 60)
print(f"Connecting to: {PI_USER}@{PI_HOST}")
print()

class SSHClient:
    """SSH client with forced password authentication"""
    
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.client = None
        self.connected = False
        
    def connect(self):
        """Connect with ONLY password auth (disable keys)"""
        try:
            self.client = paramiko.SSHClient()
            
            # Trust the host key automatically
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # CRITICAL: Disable public key auth, force password only
            transport_options = {
                'username': self.username,
                'password': self.password,
                'allow_agent': False,  # Disable SSH agent
                'look_for_keys': False,  # Don't look for key files
                'timeout': 15
            }
            
            print(f"[*] Connecting with password authentication...")
            self.client.connect(
                self.host,
                **transport_options
            )
            
            self.connected = True
            print("[+] Connected successfully - NO PROMPTS")
            return True
            
        except paramiko.AuthenticationException as e:
            print(f"[!] Authentication failed: {e}")
            return False
        except Exception as e:
            print(f"[!] Connection error: {e}")
            return False
    
    def run_command(self, command):
        """Execute command and return output"""
        if not self.connected:
            return "[!] Not connected"
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            
            # Return output + errors (some commands output to stderr)
            return output + error
            
        except Exception as e:
            return f"[!] Error running command: {e}"
    
    def close(self):
        """Close connection"""
        if self.client:
            self.client.close()


# Create and connect
ssh = SSHClient(PI_HOST, PI_USER, PI_PASSWORD)

if not ssh.connect():
    print()
    print("[!] Connection failed - checking possible issues:")
    print("    1. Is Pi online at 192.168.1.233?")
    print("    2. Is SSH enabled on Pi?")
    print("    3. Is password '149246116' correct?")
    sys.exit(1)

print()

# Run diagnostics
def print_section(title):
    print()
    print(f"[*] {title}")
    print("-" * 60)

# Service Status
print_section("SERVICE STATUS")
output = ssh.run_command("sudo systemctl status harvestpilot-autodeploy.service --no-pager")
print(output)

# Process Check  
print_section("PROCESS CHECK")
output = ssh.run_command("ps aux | grep -E 'python.*main' | grep -v grep")
print(output if output.strip() else "[-] No HarvestPilot process running")

# Recent Logs
print_section("RECENT LOGS (Last 100 lines)")
output = ssh.run_command("sudo journalctl -u harvestpilot-autodeploy.service -n 100 --no-pager")
print(output if output else "[!] No logs found")

# Recent Errors
print_section("RECENT ERRORS")
output = ssh.run_command("sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -i 'error\\|failed' | tail -30")
print(output if output.strip() else "[-] No errors found")

# Heartbeat/Sync Status
print_section("HEARTBEAT / SYNC STATUS")
output = ssh.run_command("sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -iE 'heartbeat|sync' | tail -25")
print(output if output.strip() else "[-] No heartbeat/sync entries found")

# Service Active Status
print_section("SERVICE ACTIVE CHECK")
output = ssh.run_command("sudo systemctl is-active harvestpilot-autodeploy.service")
status = output.strip()
if status == "active":
    print("[+] Service is RUNNING")
else:
    print(f"[!] Service is {status.upper()}")

ssh.close()

print()
print("=" * 60)
print("[+] Diagnostics complete - NO PASSWORD PROMPTS USED")
print("=" * 60)
print()
print("INTERPRETATION:")
print("  • Look for 'Heartbeat published' in HEARTBEAT section")
print("  • Check RECENT ERRORS for any issues")
print("  • Service should show as RUNNING above")
print()
