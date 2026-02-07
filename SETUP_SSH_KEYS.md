# Setup SSH Keys for Passwordless Pi Access

Since `sshpass` is not available, use SSH keys instead (more secure and automatic):

## Option 1: Generate SSH Keys (Recommended)

### On Windows (PowerShell):
```powershell
# Generate key pair
ssh-keygen -t rsa -b 4096 -f $HOME\.ssh\id_rsa -N ""

# Copy public key to Pi
cat $HOME\.ssh\id_rsa.pub | ssh pi@192.168.1.233 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Then the script will work without passwords!

## Option 2: Use expect (if WSL available)

If you have WSL installed, you can use the Linux version with `expect`.

## Option 3: Update Script with Your Password (Current)

The password is already in the script. Just try running it with sshpass installed.

## To Install sshpass:

### Via scoop (Windows package manager):
```powershell
# Install scoop
iwr -useb get.scoop.sh | iex

# Install sshpass
scoop install sshpass
```

### Via WSL:
```bash
wsl sudo apt-get install sshpass
```

Then run:
```powershell
.\check-pi-status.ps1
```
