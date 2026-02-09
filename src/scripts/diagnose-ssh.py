#!/usr/bin/env python3
"""
Deep diagnosis - Test SSH connectivity and debug authentication
"""

import socket
import sys

PI_HOST = "192.168.1.233"
PI_PORT = 22

print("=" * 60)
print("SSH Connectivity Deep Diagnosis")
print("=" * 60)
print()

# Test 1: Basic connectivity
print("[*] Test 1: SSH Port Reachability")
print("-" * 60)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((PI_HOST, PI_PORT))
    sock.close()
    
    if result == 0:
        print(f"[+] Port 22 is OPEN on {PI_HOST}")
        print("[+] SSH service is listening")
    else:
        print(f"[!] Port 22 is CLOSED on {PI_HOST}")
        print("[!] SSH might not be enabled")
        sys.exit(1)
except Exception as e:
    print(f"[!] Error: {e}")
    sys.exit(1)

print()

# Test 2: Try multiple passwords
print("[*] Test 2: Try Multiple Passwords")
print("-" * 60)

try:
    import paramiko
except ImportError:
    print("[*] Installing paramiko...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "paramiko"], check=True)
    import paramiko

import logging
logging.basicConfig(level=logging.CRITICAL)

passwords_to_try = [
    "149246116",
    "raspberry",
    "password",
    "12345678",
    "pi",
    "",
]

for pwd in passwords_to_try:
    display_pwd = pwd if pwd else "(empty)"
    print(f"[*] Trying password: '{display_pwd}'", end=" ... ")
    sys.stdout.flush()
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        client.connect(
            PI_HOST,
            username="pi",
            password=pwd,
            allow_agent=False,
            look_for_keys=False,
            timeout=5
        )
        
        print("[+] SUCCESS!")
        print(f"[+] CORRECT PASSWORD: '{pwd}'")
        
        # Test a command
        stdin, stdout, stderr = client.exec_command("whoami")
        output = stdout.read().decode('utf-8').strip()
        print(f"[+] User: {output}")
        
        client.close()
        sys.exit(0)
        
    except paramiko.AuthenticationException:
        print("[-] Auth failed")
    except Exception as e:
        print(f"[-] Error: {str(e)[:30]}")

print()
print("[!] None of the common passwords worked!")
print()
print("=" * 60)
print("POSSIBLE SOLUTIONS:")
print("=" * 60)
print()
print("1. SSH Key Authentication:")
print("   The Pi might be using SSH keys instead of passwords")
print("   Do you have SSH keys set up on your Pi?")
print()
print("2. Different Login:")
print("   Is the username really 'pi'?")
print("   Is the password really '149246116'?")
print()
print("3. SSH Disabled:")
print("   Is SSH enabled on your Pi?")
print()
print("4. Security:")
print("   Is there a firewall blocking SSH?")
print("   Is fail2ban activated?")
print()
