# Scheduled Notifications Feature Guide

## 📅 Overview

The Telegram bot now supports scheduled notifications! Users can set up recurring notifications to receive parking availability updates at specific times and days of the week.

## ✨ Key Features

- **Recurring schedules**: Set notifications for specific days (Monday, Wednesday, etc.) or daily
- **Flexible timing**: Choose any time in 24-hour format
- **Mexico City timezone**: All schedules use CDMX timezone
- **Persistent storage**: Schedules survive bot/container restarts
- **User-specific**: Each user manages their own schedules
- **Multiple schedules**: Set as many schedules as you need

## 🚀 How to Use

### 1. Create a Schedule

**Command format:**
```
/schedule <día> <hora>
```

**Examples:**

Get parking updates every Monday at 3:00 PM:
```
/schedule lunes 15:00
```

Get updates every Wednesday at 9:30 AM:
```
/schedule miércoles 9:30
```

Get daily updates at 6:00 PM:
```
/schedule diario 18:00
```

### 2. View Your Schedules

**Command:**
```
/listschedules
```

**Example response:**
```
📋 Tus Notificaciones Programadas

1. Lunes - 15:00
2. Miércoles - 09:30
3. Diario - 18:00

Total: 3 notificación(es)

Para eliminar una notificación usa:
/removeschedule <número>
```

### 3. Remove a Schedule

**Command format:**
```
/removeschedule <número>
```

**Example:**
```
/removeschedule 2
```

This removes the second schedule from your list.

## 📖 Valid Days

### Spanish (recommended):
- `lunes` - Monday
- `martes` - Tuesday
- `miércoles` or `miercoles` - Wednesday
- `jueves` - Thursday
- `viernes` - Friday
- `sábado` or `sabado` - Saturday
- `domingo` - Sunday
- `diario` or `todos` - Every day

### English (also supported):
- `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`
- `daily` - Every day

## ⏰ Time Format

- Use 24-hour format: `HH:MM`
- Valid hours: `00` to `23`
- Valid minutes: `00` to `59`
- Examples: `09:00`, `15:30`, `23:45`
- Single digit is OK: `9:00` works as well as `09:00`

## 📬 What You'll Receive

At your scheduled time, you'll receive a notification like this:

```
🔔 Actualización Programada

🅿️ Parking Status - AVAILABLE 🟢

📊 Occupied: 15/35 spaces
✅ Available: 20/35 spaces

🕐 Last updated: 02/10/2025 15:00:00
📡 System status: 🟢 Connected
```

## 💡 Use Cases

### Example 1: Weekday Commuter
Get updates when you arrive at work and when you leave:
```
/schedule lunes 8:30
/schedule martes 8:30
/schedule miércoles 8:30
/schedule jueves 8:30
/schedule viernes 8:30

/schedule lunes 17:00
/schedule martes 17:00
/schedule miércoles 17:00
/schedule jueves 17:00
/schedule viernes 17:00
```

### Example 2: Weekend Visitor
Get updates on weekend mornings:
```
/schedule sábado 10:00
/schedule domingo 10:00
```

### Example 3: Daily User
Get one update every day at lunch time:
```
/schedule diario 13:00
```

### Example 4: Class Schedule
Get updates before your classes:
```
/schedule lunes 7:30
/schedule miércoles 7:30
/schedule viernes 7:30
```

## 🔧 Technical Details

### Storage
- Schedules are stored in `/app/data/schedules.json`
- This is persisted via Docker volume: `./telegram_bot/data`
- Format: JSON with chat_id as key

### Scheduler
- Uses APScheduler with BackgroundScheduler
- Cron-based triggers for recurring schedules
- All jobs use Mexico City timezone (`America/Mexico_City`)

### Persistence
- Schedules are loaded on bot startup
- All scheduler jobs are recreated after restart
- No data loss even if container is restarted or recreated

## ❓ FAQ

**Q: Can I have multiple schedules?**
A: Yes! Create as many as you need. Use `/listschedules` to see them all.

**Q: What timezone are schedules in?**
A: All schedules use Mexico City timezone (CDMX / America/Mexico_City).

**Q: Will my schedules survive if the bot restarts?**
A: Yes! Schedules are saved to disk and reloaded on startup.

**Q: Can I schedule for a specific date (one-time notification)?**
A: Not yet. Currently only recurring schedules are supported. This could be added in a future update.

**Q: What happens if the bot is offline during my scheduled time?**
A: The notification will be missed. The scheduler only sends notifications if the bot is running.

**Q: How do I change a schedule?**
A: Remove the old one with `/removeschedule` and create a new one with `/schedule`.

**Q: Is there a limit to how many schedules I can create?**
A: No hard limit, but be reasonable! Each schedule creates a scheduler job.

**Q: Can other users see my schedules?**
A: No. Each user's schedules are completely private.

## 🔍 Troubleshooting

### Notification didn't arrive:

1. **Check your schedule is created:**
   ```
   /listschedules
   ```

2. **Verify the time is correct:**
   Remember it's in CDMX timezone and 24-hour format

3. **Check bot is running:**
   The bot must be online to send scheduled notifications

4. **Check bot logs:**
   ```bash
   docker-compose logs telegram-bot | grep "scheduled notification"
   ```

### Can't create schedule:

1. **Check day spelling:**
   Use valid Spanish/English day names

2. **Check time format:**
   Must be HH:MM in 24-hour format

3. **Try with /help:**
   ```
   /help
   ```
   Shows examples and valid formats

### Schedule not persisting:

1. **Check volume mount:**
   ```bash
   docker inspect telegram-bot | grep Mounts
   ```

2. **Check data directory:**
   ```bash
   ls -la telegram_bot/data/
   cat telegram_bot/data/schedules.json
   ```

## 📊 Examples of Common Schedules

### Morning Commute (8 AM arrival):
```
/schedule lunes 7:45
/schedule martes 7:45
/schedule miércoles 7:45
/schedule jueves 7:45
/schedule viernes 7:45
```

### Evening Return (6 PM departure):
```
/schedule lunes 18:00
/schedule martes 18:00
/schedule miércoles 18:00
/schedule jueves 18:00
/schedule viernes 18:00
```

### Weekend Shopping:
```
/schedule sábado 11:00
/schedule domingo 15:00
```

### Daily Lunch Break:
```
/schedule diario 13:30
```

### Before Classes:
```
/schedule lunes 7:00
/schedule miércoles 7:00
/schedule viernes 9:00
```

## 🎯 Best Practices

1. **Set realistic times**: Choose times when you actually need the information
2. **Don't over-schedule**: Too many notifications can be annoying
3. **Use daily for regular needs**: If you need updates every day, use `/schedule diario`
4. **Review regularly**: Use `/listschedules` to see what you have set up
5. **Clean up unused schedules**: Remove schedules you no longer need

## 🆘 Support

If you encounter issues:

1. Try `/help` command in the bot
2. Check the main README.md for bot setup
3. View bot logs: `docker-compose logs -f telegram-bot`
4. Restart the bot: `docker-compose restart telegram-bot`

## 🎉 Success Story

Once configured, you can:
- ✅ Stop checking the bot manually
- ✅ Get automatic updates at your preferred times
- ✅ Plan your visits based on scheduled availability reports
- ✅ Never forget to check parking availability again!

Enjoy your scheduled notifications! 🚀
