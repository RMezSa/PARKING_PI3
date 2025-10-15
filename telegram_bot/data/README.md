# Telegram Bot Data Directory

This directory contains persistent storage for user schedules.

## Files:
- `schedules.json` - User notification schedules (auto-generated)

## Note:
This directory is mounted as a Docker volume from the host filesystem.
The schedules.json file is automatically created when the first schedule is added.

## Do Not:
- Manually edit schedules.json while the bot is running
- Delete this directory if you want to preserve user schedules
- Commit schedules.json to version control (contains user chat IDs)

## Backup:
To backup user schedules:
```bash
cp telegram_bot/data/schedules.json telegram_bot/data/schedules.backup.json
```

To restore:
```bash
cp telegram_bot/data/schedules.backup.json telegram_bot/data/schedules.json
docker-compose restart telegram-bot
```
