# Configuration Files

This directory contains configuration files, environment variables, and secrets.

## ⚠️ IMPORTANT: This Directory is NOT Versioned

**Never commit files from this directory to git!**

All files here are in `.gitignore` to protect sensitive credentials.

## 📁 Contents

### Environment Variables
- **`.env.local`** — Your local environment variables (NOT in git)
  - Database credentials
  - API keys
  - Development settings
  
- **`.env.example`** — Template for `.env.local` (in git)
  - Shows required variables
  - Has placeholder values
  - Safe to commit

### Firebase Credentials
- **`firebase-key.json`** — Service account credentials (NOT in git)
  - Authenticates with Firebase
  - Enables database write access
  - Keep extremely confidential

- **`harvest-hub-2025-firebase-adminsdk-*.json`** — Alternative Firebase key (NOT in git)
  - Same purpose as above
  - Different Firebase project format

## 🚀 Setup Instructions

### 1. Create `.env.local` from template

```bash
cp config/.env.example config/.env.local
```

### 2. Edit `.env.local` with your values

```bash
nano config/.env.local
```

**Required variables:**
```env
DEVICE_ID=raspserver-001
HARDWARE_PLATFORM=raspberry_pi
SIMULATE_HARDWARE=false
FIREBASE_PROJECT_ID=harvest-hub
FIREBASE_CREDENTIALS_PATH=./config/firebase-key.json
```

### 3. Add Firebase credentials

Place your Firebase service account JSON file as:
```
config/firebase-key.json
```

Or set the path in `.env.local`:
```env
FIREBASE_CREDENTIALS_PATH=/path/to/your/service-account-key.json
```

## 🔒 Security Best Practices

✅ **DO:**
- Keep credentials in `config/` directory
- Use strong, unique credentials
- Rotate credentials regularly
- Use `.env.local` for development
- Set restrictive file permissions: `chmod 600 config/.env.local`

❌ **DON'T:**
- Commit `.env.local` files to git
- Share credentials in messages or PRs
- Use same credentials across environments
- Store credentials in source code
- Make credential files world-readable

## 📋 Configuration Loading Order

The application loads configuration in this order:

1. **Default values** in `src/config.py`
2. **`.env` file** in repo root (if exists)
3. **`config/.env.local`** (local overrides)
4. **Environment variables** (highest priority)

Later values override earlier ones.

## 🔧 For Development

### Minimal Setup

```bash
# Create local env from template
cp config/.env.example config/.env.local

# Edit with your settings
# Add firebase-key.json from Firebase Console
# Run the app
python main.py
```

### Using Different Firebase Projects

```env
# config/.env.local
FIREBASE_PROJECT_ID=my-other-project
FIREBASE_CREDENTIALS_PATH=./config/firebase-key-other.json
```

## 🚀 For Deployment

On Raspberry Pi, you'll typically:

1. Copy `config/.env.example` → `/etc/harvestpilot/.env`
2. Edit with production values
3. Copy Firebase key to secure location
4. Set environment variable: `export FIREBASE_CREDENTIALS_PATH=/etc/harvestpilot/firebase-key.json`

Or use systemd environment files:

```ini
# /etc/default/harvestpilot
DEVICE_ID=raspserver-001
FIREBASE_CREDENTIALS_PATH=/etc/harvestpilot/firebase-key.json
```

## 📖 Documentation

See [../REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) for project layout.  
See [../docs/SETUP_YOUR_PI.md](../docs/SETUP_YOUR_PI.md) for Raspberry Pi setup.
