# 🔄 Updating to Version 2.0 (Scheduled Notifications)

## Overview

This guide helps you update your existing Telegram bot to version 2.0 which adds scheduled notification support.

## ⚠️ Before You Update

### Backup Current State (Optional but Recommended)

```bash
# Backup current bot container
docker commit telegram-bot telegram-bot-backup

# Backup compose file
cp docker-compose.yml docker-compose.yml.backup
```

## 🚀 Update Steps

### Step 1: Stop the Current Bot

```bash
docker-compose stop telegram-bot
```

### Step 2: Pull Latest Changes

If using git:
```bash
git pull origin telegram
```

Or manually ensure you have the latest:
- `telegram_bot/telegram_bot.py` (updated)
- `telegram_bot/requirements.txt` (added apscheduler)
- `telegram_bot/Dockerfile` (added data directory)
- `docker-compose.yml` (added volume mount)

### Step 3: Rebuild the Container

```bash
docker-compose build telegram-bot
```

This will install the new dependency (APScheduler).

### Step 4: Start the Updated Bot

```bash
docker-compose up -d telegram-bot
```

### Step 5: Verify It's Working

```bash
# Check logs for scheduler initialization
docker-compose logs telegram-bot | grep "Scheduler initialized"

# Should see:
# INFO - Scheduler initialized and started
```

### Step 6: Test New Features

Open Telegram and test:

1. **Help command** (should show new commands):
   ```
   /help
   ```

2. **Create a schedule**:
   ```
   /schedule diario 9:00
   ```

3. **List schedules**:
   ```
   /listschedules
   ```

4. **Remove schedule**:
   ```
   /removeschedule 1
   ```

## ✅ Verification Checklist

- [ ] Bot container is running: `docker ps | grep telegram-bot`
- [ ] Scheduler initialized: `docker-compose logs telegram-bot | grep "Scheduler"`
- [ ] Data directory created: `ls -la telegram_bot/data/`
- [ ] Old commands still work: `/parking` returns parking status
- [ ] New commands work: `/schedule` accepts input
- [ ] Volume mounted: `docker inspect telegram-bot | grep Mounts`

## 🆕 What Changed

### For Users:
- ✅ 3 new commands available
- ✅ All old commands still work
- ✅ No change to existing bot behavior
- ✅ New scheduled notification feature

### For System:
- ✅ New dependency: APScheduler
- ✅ New volume: `./telegram_bot/data`
- ✅ New persistent file: `schedules.json`
- ✅ ~400 lines of new code

## 🔧 Troubleshooting Update Issues

### Issue: Container won't start

**Check logs:**
```bash
docker-compose logs telegram-bot
```

**Common causes:**
- Missing `apscheduler` dependency (rebuild: `docker-compose build telegram-bot`)
- Volume mount issues (check docker-compose.yml)
- Syntax error in Python code (check logs for traceback)

**Solution:**
```bash
docker-compose down
docker-compose build telegram-bot
docker-compose up -d telegram-bot
```

### Issue: Old features don't work

**This shouldn't happen**, but if it does:

1. Check if old commands are still in code:
   ```bash
   grep -n "def handle_message" telegram_bot/telegram_bot.py
   ```

2. Roll back to backup:
   ```bash
   docker stop telegram-bot
   docker rm telegram-bot
   docker run -d --name telegram-bot telegram-bot-backup
   ```

3. Or restore from compose backup:
   ```bash
   docker-compose down
   cp docker-compose.yml.backup docker-compose.yml
   docker-compose up -d
   ```

### Issue: Scheduler not working

**Check initialization:**
```bash
docker-compose logs telegram-bot | grep -i scheduler
```

**Should see:**
```
INFO - Initializing scheduler...
INFO - Scheduler initialized and started
```

**If not, check:**
1. APScheduler installed: `docker exec telegram-bot pip list | grep APScheduler`
2. Import errors: `docker-compose logs telegram-bot | grep -i error`

**Fix:**
```bash
docker-compose down
docker-compose build --no-cache telegram-bot
docker-compose up -d telegram-bot
```

### Issue: Data directory not created

**Check volume:**
```bash
docker inspect telegram-bot | grep -A 5 Mounts
```

**Should show:**
```
"Mounts": [
    {
        "Type": "bind",
        "Source": "/home/estacionamientog/PARKING_PI3/telegram_bot/data",
        "Destination": "/app/data",
        ...
```

**If missing, check docker-compose.yml:**
```yaml
telegram-bot:
  ...
  volumes:
    - ./telegram_bot/data:/app/data
```

**Fix:**
1. Update docker-compose.yml
2. Restart: `docker-compose up -d telegram-bot`

## 🔄 Rolling Back (If Needed)

If you need to go back to the old version:

### Option 1: Use Git

```bash
git checkout <previous-commit>
docker-compose down
docker-compose build telegram-bot
docker-compose up -d telegram-bot
```

### Option 2: Use Backup

```bash
docker-compose down
docker tag telegram-bot-backup telegram-bot
docker-compose up -d telegram-bot
```

### Option 3: Manual Rollback

1. Remove new code from `telegram_bot.py`
2. Remove `apscheduler` from `requirements.txt`
3. Remove volume from `docker-compose.yml`
4. Rebuild: `docker-compose build telegram-bot`
5. Start: `docker-compose up -d telegram-bot`

## 📊 Comparing Versions

### Version 1.0 (Before):
- Commands: `/start`, `/help`, `/parking`, `/status`
- Features: Real-time parking queries
- Storage: None (stateless)
- Dependencies: requests, paho-mqtt, python-dotenv, pytz

### Version 2.0 (After):
- Commands: All v1.0 + `/schedule`, `/listschedules`, `/removeschedule`
- Features: Real-time queries + Scheduled notifications
- Storage: schedules.json (persistent)
- Dependencies: All v1.0 + apscheduler

## 🎯 Migration Complete!

Once verification passes, you're done! Your bot now supports:

- ✅ All original features (unchanged)
- ✅ New scheduled notifications
- ✅ Persistent schedule storage
- ✅ Multiple schedules per user

Users can start creating schedules immediately with `/schedule`.

## 📚 Additional Resources

- **User Guide**: `SCHEDULING_GUIDE.md`
- **Technical Details**: `SCHEDULING_IMPLEMENTATION.md`
- **Feature Summary**: `FEATURE_SUMMARY.md`
- **Quick Start**: `QUICK_START.md`

## 💬 Support

If you encounter issues during update:

1. Check logs: `docker-compose logs -f telegram-bot`
2. Verify volume: `ls -la telegram_bot/data/`
3. Test manually: Send `/help` to bot
4. Rebuild clean: `docker-compose build --no-cache telegram-bot`

## ✨ Enjoy Your Updated Bot!

Your Telegram bot is now ready to send scheduled parking notifications! 🎉
