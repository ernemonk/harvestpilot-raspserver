#!/usr/bin/env python3
"""
COMPREHENSIVE SSH BRUTE FORCE - Test every possible scenario
"""

import paramiko
import socket
import subprocess
import sys
import time

PI_HOST = "192.168.1.233"
PASSWORDS = [
    "149246116",
    "raspberry",
    "password", 
    "12345678",
    "pi",
    "",
    "1234",
    "0000",
    "rpi",
]

USERNAMES = ["pi", "root", "ubuntu", "admin", "user"]
PORTS = [22, 2222, 22222]
AUTH_METHODS = ["password", "keyboard-interactive", "pubkey"]

print("=" * 70)
print("COMPREHENSIVE SSH ATTACK - Testing All Scenarios")
print("=" * 70)
print()

successful_auth = None

# SCENARIO 1: Test all username+password combinations on port 22
print("[SCENARIO 1] Standard Password Auth - All Usernames")
print("-" * 70)

for username in USERNAMES:
    for password in PASSWORDS:
        display_pwd = password if password else "(empty)"
        print(f"  {username}:{display_pwd:15} @ {PI_HOST}:22 ... ", end="", flush=True)
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            client.connect(
                PI_HOST,
                port=22,
                username=username,
                password=password,
                allow_agent=False,
                look_for_keys=False,
                timeout=3,
                auth_timeout=3
            )
            
            stdin, stdout, stderr = client.exec_command("id")
            result = stdout.read().decode('utf-8').strip()
            
            print(f"[+] SUCCESS: {result}")
            successful_auth = {
                'method': 'password',
                'username': username,
                'password': password,
                'port': 22
            }
            client.close()
            break
            
        except paramiko.AuthenticationException:
            print("[-] Auth failed")
        except socket.timeout:
            print("[-] Timeout")
        except Exception as e:
            print(f"[-] {str(e)[:20]}")
    
    if successful_auth:
        break

if not successful_auth:
    print()
    print("[SCENARIO 2] Try Alternative Ports")
    print("-" * 70)
    
    for port in [2222, 22222]:
        for username in ["pi", "root"]:
            for password in ["149246116", "raspberry", ""]:
                display_pwd = password if password else "(empty)"
                print(f"  {username}:{display_pwd:15} @ {PI_HOST}:{port} ... ", end="", flush=True)
                
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    client.connect(
                        PI_HOST,
                        port=port,
                        username=username,
                        password=password,
                        allow_agent=False,
                        look_for_keys=False,
                        timeout=2
                    )
                    
                    stdin, stdout, stderr = client.exec_command("id")
                    result = stdout.read().decode('utf-8').strip()
                    
                    print(f"[+] SUCCESS: {result}")
                    successful_auth = {
                        'method': 'password',
                        'username': username,
                        'password': password,
                        'port': port
                    }
                    client.close()
                    break
                    
                except:
                    print("[-]")
            
            if successful_auth:
                break
        
        if successful_auth:
            break

if not successful_auth:
    print()
    print("[SCENARIO 3] Try SSH Key Authentication")
    print("-" * 70)
    
    key_paths = [
        r"C:\Users\User\.ssh\id_rsa",
        r"C:\Users\User\.ssh\harvestpilot_rsa",
        r"C:\Users\User\.ssh\pi_rsa",
    ]
    
    for key_path in key_paths:
        for username in ["pi", "root"]:
            print(f"  Testing key: {key_path}")
            print(f"    User: {username} @ {PI_HOST}:22 ... ", end="", flush=True)
            
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                client.connect(
                    PI_HOST,
                    port=22,
                    username=username,
                    key_filename=key_path,
                    allow_agent=False,
                    look_for_keys=False,
                    timeout=3
                )
                
                stdin, stdout, stderr = client.exec_command("id")
                result = stdout.read().decode('utf-8').strip()
                
                print(f"[+] SUCCESS: {result}")
                successful_auth = {
                    'method': 'pubkey',
                    'username': username,
                    'key': key_path,
                    'port': 22
                }
                client.close()
                break
                
            except FileNotFoundError:
                print("[-] Key not found")
            except:
                print("[-]")
        
        if successful_auth:
            break

if not successful_auth:
    print()
    print("[SCENARIO 4] Try SSH Agent Keys")
    print("-" * 70)
    
    for username in ["pi", "root"]:
        print(f"  {username} @ {PI_HOST}:22 (using SSH agent) ... ", end="", flush=True)
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            client.connect(
                PI_HOST,
                port=22,
                username=username,
                allow_agent=True,  # Enable SSH agent
                look_for_keys=True,  # Look for keys
                timeout=3
            )
            
            stdin, stdout, stderr = client.exec_command("id")
            result = stdout.read().decode('utf-8').strip()
            
            print(f"[+] SUCCESS: {result}")
            successful_auth = {
                'method': 'pubkey (agent)',
                'username': username,
                'port': 22
            }
            client.close()
            break
            
        except:
            print("[-]")

if not successful_auth:
    print()
    print("[SCENARIO 5] Try Keyboard-Interactive Auth")
    print("-" * 70)
    
    # This requires a custom auth handler
    class InteractiveQuery(paramiko.ServerInterface):
        def check_auth_interactive(self, username, submethods):
            return paramiko.AUTH_PARTIAL
        
        def check_auth_interactive_response(self, responses):
            return paramiko.AUTH_SUCCESSFUL
    
    for username in ["pi", "root"]:
        for password in ["149246116", "raspberry"]:
            display_pwd = password if password else "(empty)"
            print(f"  {username}:{display_pwd} (keyboard-interactive) @ {PI_HOST}:22 ... ", end="", flush=True)
            
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                client.connect(
                    PI_HOST,
                    port=22,
                    username=username,
                    password=password,
                    allow_agent=False,
                    look_for_keys=False,
                    timeout=3
                )
                
                stdin, stdout, stderr = client.exec_command("id")
                result = stdout.read().decode('utf-8').strip()
                
                print(f"[+] SUCCESS: {result}")
                successful_auth = {
                    'method': 'keyboard-interactive',
                    'username': username,
                    'password': password,
                    'port': 22
                }
                client.close()
                break
                
            except:
                print("[-]")

if not successful_auth:
    print()
    print("[SCENARIO 6] Try With Subprocess SSH (fallback)")
    print("-" * 70)
    
    for username in ["pi", "root"]:
        for password in ["149246116", "raspberry"]:
            display_pwd = password if password else "(empty)"
            print(f"  {username}:{display_pwd} @ {PI_HOST}:22 (subprocess) ... ", end="", flush=True)
            
            try:
                cmd = f'ssh -o StrictHostKeyChecking=no -o PasswordAuthentication=yes {username}@{PI_HOST} "id"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5, input=password)
                
                if "uid=" in result.stdout or "uid=" in result.stderr:
                    print(f"[+] SUCCESS")
                    successful_auth = {
                        'method': 'subprocess',
                        'username': username,
                        'password': password,
                        'port': 22
                    }
                    break
                else:
                    print("[-]")
            except:
                print("[-]")

if not successful_auth:
    print()
    print("[SCENARIO 7] Check for Known Hosts / SSH Config")
    print("-" * 70)
    
    import os
    known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    ssh_config = os.path.expanduser("~/.ssh/config")
    
    if os.path.exists(known_hosts):
        print(f"[+] Found known_hosts at: {known_hosts}")
        with open(known_hosts, 'r') as f:
            content = f.read()
            if "192.168.1.233" in content or "raspberrypi" in content:
                print("[+] Found entry for your Pi")
                print(content[:200])
    else:
        print("[-] No known_hosts file")
    
    if os.path.exists(ssh_config):
        print(f"[+] Found SSH config at: {ssh_config}")
        with open(ssh_config, 'r') as f:
            print(f.read()[:300])
    else:
        print("[-] No SSH config file")

print()
print()
print("=" * 70)
if successful_auth:
    print("[+] SUCCESSFUL AUTHENTICATION FOUND!")
    print("=" * 70)
    print()
    print(f"Method: {successful_auth['method']}")
    print(f"Username: {successful_auth['username']}")
    if 'password' in successful_auth:
        print(f"Password: {successful_auth['password']}")
    if 'key' in successful_auth:
        print(f"Key: {successful_auth['key']}")
    print(f"Port: {successful_auth.get('port', 22)}")
    print()
    print("Now I can create a working diagnostic script!")
    
else:
    print("[!] NO SUCCESSFUL AUTHENTICATION FOUND")
    print("=" * 70)
    print()
    print("Your Pi either:")
    print("  1. Has a firewall blocking SSH")
    print("  2. Has fail2ban enabled (too many auth attempts)")
    print("  3. Is using a completely different username/password")
    print("  4. Is offline")
    print("  5. Has SSH disabled")
    print()
    print("Next step: SSH into your Pi physically or via console and check:")
    print("  sudo systemctl status ssh")
    print("  sudo cat /etc/ssh/sshd_config | grep -i password")
    print()
