#!/usr/bin/env python3
"""
Test SSH connection with different password variations
"""

import paramiko
import sys

HOST = "192.168.1.233"
USER = "pi"

# Try different variations of the password
passwords_to_try = [
    "149246116",           # Original
    "149246116 ",          # With trailing space
    " 149246116",          # With leading space
    "149246116\n",         # With newline
]

print("Testing SSH connection with password variations...")
print(f"Host: {HOST}")
print(f"User: {USER}")
print()

for idx, password in enumerate(passwords_to_try, 1):
    print(f"[{idx}] Testing password: '{password}' (len={len(password)})")
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, username=USER, password=password, timeout=5)
        
        print(f"    [+] SUCCESS! Password is correct: '{password}'")
        
        # Test a command
        stdin, stdout, stderr = client.exec_command("whoami")
        output = stdout.read().decode('utf-8').strip()
        print(f"    [+] User: {output}")
        
        client.close()
        sys.exit(0)
        
    except paramiko.AuthenticationException:
        print(f"    [-] Authentication failed")
    except Exception as e:
        print(f"    [-] Error: {str(e)}")
    print()

print("[!] None of the passwords worked!")
print()
print("Common issues:")
print("  1. Password might be different on the Pi")
print("  2. SSH might require key-based auth")
print("  3. Password auth might be disabled")
print()
print("Try connecting manually:")
print(f"  ssh pi@{HOST}")
print()
