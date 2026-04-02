# 🚨 CRITICAL: Windows Reinstall Backup Guide

## ⚠️ YOUR ENTIRE FREQ SWARM WILL BE WIPED

When you reinstall Windows:
- ✅ Windows files survive (on C: drive)
- ❌ **WSL2 Ubuntu = DELETED** (entire Linux system)
- ❌ **All Docker containers = DELETED**
- ❌ **All SQLite databases = DELETED**
- ❌ **All trade history = GONE**

## BEFORE YOU REINSTALL WINDOWS - DO THIS:

### Step 1: Stop All Trading (Preserve final state)
```bash
cd /root/.openclaw/workspace/freqtrade
docker-compose down
```

### Step 2: Run Complete Backup Script
```bash
cd /root/.openclaw/workspace
./scripts/complete_system_backup.sh
```

This creates:
- `C:\Freq-Backup-YYYYMMDD\wsl-ubuntu-backup.tar` (ENTIRE Linux system ~10-50GB)
- `C:\Freq-Backup-YYYYMMDD\wsl-backup\freqtrade-complete\` (all configs, strategies, DBs)
- `C:\Freq-Backup-YYYYMMDD\wsl-backup\dotfiles\` (SSH keys, configs)

### Step 3: Copy to External Drive
**CRITICAL:** Copy `C:\Freq-Backup-*` folder to:
- External USB drive
- Cloud storage (Google Drive, Dropbox)
- Network share

### Step 4: Note These Items
- Windows product key (from email/sticker/settings)
- Any passwords saved in browser
- Your OpenClaw configuration

## AFTER WINDOWS REINSTALL:

### Step 1: Install WSL2
```powershell
# In PowerShell as Administrator
wsl --install -d Ubuntu
```

### Step 2: Restore WSL (Option A: Import backup)
```powershell
# If you have the .tar backup
wsl --import Ubuntu C:\WSL\Ubuntu C:\Freq-Backup-*\wsl-ubuntu-backup.tar
```

### Step 3: Restore Files (Option B: Fresh install + restore)
```bash
# In new Ubuntu
sudo apt update && sudo apt install -y docker.io docker-compose

# Copy back Freq files
sudo mkdir -p /root/.openclaw/workspace
sudo cp -r /mnt/c/Freq-Backup-*/wsl-backup/freqtrade-complete/* /root/.openclaw/workspace/

# Start swarm
cd /root/.openclaw/workspace/freqtrade
docker-compose up -d
```

## WHAT GETS LOST IF YOU DON'T BACKUP:

| Item | Importance | Backup? |
|------|-----------|---------|
| Trade history (SQLite) | **CRITICAL** | ✅ Yes |
| Strategy configs | **CRITICAL** | ✅ Yes |
| FreqAI models | High | ✅ Yes |
| SSH keys | High | ✅ Yes |
| Docker images | Medium | ⚠️ Can rebuild |
| OHLCV data | Low | ❌ Can re-download |

## EMERGENCY CONTACT
If backup fails or you need help during restore:
- WhatsApp: +19562004041 (working)
- Telegram: Currently broken
