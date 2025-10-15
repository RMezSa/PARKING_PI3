# Quick Start Guide - Telegram Bot Service

## 🚀 Getting Started in 3 Steps

### Step 1: Verify Configuration

Check that your `.env` file has the bot token:

```bash
cat .env | grep TELEGRAM_BOT_TOKEN
```

Should show:
```
TELEGRAM_BOT_TOKEN=8414943579:AAGdyjGhBnSGqFrA3qQ-olq8HUn9OrduS4M
```

### Step 2: Start the Service

Build and start the Telegram bot:

```bash
docker-compose up -d telegram-bot
```

Or start all services:

```bash
docker-compose up -d
```

### Step 3: Test the Bot

1. Open Telegram
2. Search for your bot (the username associated with the token)
3. Send `/start` to begin
4. Send `/parking` to check availability

## 📊 Monitoring

### View live logs:
```bash
docker-compose logs -f telegram-bot
```

### Check if bot is running:
```bash
docker ps | grep telegram-bot
```

### Restart the bot:
```bash
docker-compose restart telegram-bot
```

## 🔧 Troubleshooting

### Bot not responding?

1. Check container status:
   ```bash
   docker-compose ps telegram-bot
   ```

2. Check logs for errors:
   ```bash
   docker-compose logs telegram-bot
   ```

3. Verify MQTT connection:
   ```bash
   docker-compose logs telegram-bot | grep "MQTT connected"
   ```

### Update bot token:

1. Edit `.env` file:
   ```bash
   nano .env
   ```

2. Update the `TELEGRAM_BOT_TOKEN` line

3. Restart the service:
   ```bash
   docker-compose restart telegram-bot
   ```

## 📱 User Commands

Your users can use these commands:

- `/start` - Introduction and commands list
- `/parking` - Current parking availability  
- `/status` - Same as /parking
- `/help` - Help message
- `/schedule <día> <hora>` - Set up recurring notifications
  - Example: `/schedule lunes 15:00`
- `/listschedules` - View your scheduled notifications
- `/removeschedule <número>` - Remove a notification

### Quick Scheduling Examples:

Get updates every Monday at 3 PM:
```
/schedule lunes 15:00
```

Get daily updates at 9 AM:
```
/schedule diario 9:00
```

View your schedules:
```
/listschedules
```

Remove schedule #1:
```
/removeschedule 1
```

**See SCHEDULING_GUIDE.md for complete scheduling documentation.**

## 🎯 What Users See

```
🅿️ Parking Status - AVAILABLE 🟢

📊 Occupied: 15/35 spaces
✅ Available: 20/35 spaces

🕐 Last updated: 02/10/2025 14:30:45
📡 System status: 🟢 Connected
```

## ✅ Verification Checklist

- [ ] `.env` file has `TELEGRAM_BOT_TOKEN`
- [ ] Container `telegram-bot` is running
- [ ] Logs show "MQTT connected successfully"
- [ ] Bot responds to `/start` on Telegram
- [ ] Bot shows correct parking count

## 🆘 Need Help?

Check the full documentation:
- `telegram_bot/README.md` - Complete guide
- `telegram_bot/IMPLEMENTATION_SUMMARY.md` - Technical details

View service status:
```bash
docker-compose ps
```

View all logs:
```bash
docker-compose logs
```

That's it! Your Telegram bot service is ready to use! 🎉
