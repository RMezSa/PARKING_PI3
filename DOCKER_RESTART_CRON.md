# Docker Compose Restart Cron Job Setup

This document describes the automated docker compose restart schedule for the PARKING_PI3 system.

## Schedule

The system performs an automatic restart cycle every day:

- **10:00 PM (22:00)** - Docker compose down
- **4:30 AM (04:30)** - Docker compose up

All times are in CDMX timezone (America/Mexico_City - CST/CDT).

## Files

### `docker-restart-cron.sh`
The main script that handles docker compose operations:
- Takes one argument: `down` or `up`
- Logs all operations to `docker-restart-cron.log`
- Changes to the PARKING_PI3 directory before running docker compose commands

### `docker-restart-cron.log`
Log file containing all restart operations with timestamps.

## Cron Job Configuration

The following entries are in the user's crontab:

```cron
# Docker compose restart schedule - Down at 10 PM, Up at 4:30 AM CDMX time
0 22 * * * /home/estacionamientog/PARKING_PI3/docker-restart-cron.sh down
30 4 * * * /home/estacionamientog/PARKING_PI3/docker-restart-cron.sh up
```

## Managing the Cron Jobs

### View current crontab
```bash
crontab -l
```

### Edit crontab
```bash
crontab -e
```

### Remove the restart jobs
```bash
crontab -l | grep -v "docker-restart-cron.sh" | crontab -
```

### Test the script manually
```bash
# Test docker compose down
/home/estacionamientog/PARKING_PI3/docker-restart-cron.sh down

# Test docker compose up
/home/estacionamientog/PARKING_PI3/docker-restart-cron.sh up
```

## View Logs

Check the restart operation logs:
```bash
tail -f /home/estacionamientog/PARKING_PI3/docker-restart-cron.log
```

Or view recent entries:
```bash
tail -n 50 /home/estacionamientog/PARKING_PI3/docker-restart-cron.log
```

## Purpose

This automated restart cycle helps:
- Clear any accumulated memory issues
- Refresh container states
- Ensure clean daily startup
- Perform maintenance during low-usage hours (overnight)

## Notes

- The system timezone is configured as `America/Mexico_City`
- The compose-watchdog service will continue to run every 2 minutes to monitor container health
- All containers defined in `docker-compose.yml` will be affected (mosquitto-broker, pi3-subscriber, webpanel, telegram-bot)
- The restart happens during overnight hours to minimize service disruption
