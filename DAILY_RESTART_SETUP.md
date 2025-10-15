# Daily Docker Compose Restart Setup

## Overview

This setup provides an automated systemd timer that restarts the Docker Compose stack daily at 4:30 AM. This helps prevent errors from accumulating counts and ensures a clean state each day.

## Files

- **`parking-compose-restart.service`**: Systemd service that executes the restart commands
- **`parking-compose-restart.timer`**: Systemd timer that schedules the service to run at 4:30 AM daily

## Installation

### 1. Copy Service and Timer Files

Copy the systemd files to the system directory:

```bash
sudo cp parking-compose-restart.service /etc/systemd/system/
sudo cp parking-compose-restart.timer /etc/systemd/system/
```

### 2. Reload Systemd

Reload the systemd daemon to recognize the new files:

```bash
sudo systemctl daemon-reload
```

### 3. Enable the Timer

Enable the timer to start automatically on boot:

```bash
sudo systemctl enable parking-compose-restart.timer
```

### 4. Start the Timer

Start the timer immediately:

```bash
sudo systemctl start parking-compose-restart.timer
```

## Verification

### Check Timer Status

View the status and next scheduled run time:

```bash
sudo systemctl status parking-compose-restart.timer
```

### List All Timers

See all active timers and when they'll trigger:

```bash
systemctl list-timers
```

Look for `parking-compose-restart.timer` in the output.

### View Service Logs

Check logs from previous executions:

```bash
sudo journalctl -u parking-compose-restart.service
```

View logs in real-time:

```bash
sudo journalctl -u parking-compose-restart.service -f
```

## Manual Execution

To manually trigger the restart without waiting for the scheduled time:

```bash
sudo systemctl start parking-compose-restart.service
```

## Management Commands

### Stop the Timer

```bash
sudo systemctl stop parking-compose-restart.timer
```

### Disable the Timer

Prevent the timer from starting on boot:

```bash
sudo systemctl disable parking-compose-restart.timer
```

### Restart the Timer

If you make changes to the timer configuration:

```bash
sudo systemctl restart parking-compose-restart.timer
```

## How It Works

1. **Timer Activation**: The timer is configured with `OnCalendar=*-*-* 04:30:00`, which triggers at 4:30 AM every day.

2. **Service Execution**: When triggered, the service:
   - Changes to the project directory: `/home/estacionamientog/PARKING_PI3`
   - Runs `docker compose down` to stop and remove all containers
   - Runs `docker compose up -d` to start fresh containers in detached mode

3. **Persistence**: The `Persistent=true` setting ensures that if the system is off at 4:30 AM, the service will run when the system next starts.

## Troubleshooting

### Timer Not Running

1. Check if the timer is enabled and active:
   ```bash
   sudo systemctl is-enabled parking-compose-restart.timer
   sudo systemctl is-active parking-compose-restart.timer
   ```

2. Verify the timer configuration:
   ```bash
   systemctl cat parking-compose-restart.timer
   ```

### Service Fails to Execute

1. Check service logs for errors:
   ```bash
   sudo journalctl -u parking-compose-restart.service -n 50
   ```

2. Verify Docker is running:
   ```bash
   sudo systemctl status docker
   ```

3. Test the commands manually:
   ```bash
   cd /home/estacionamientog/PARKING_PI3
   docker compose down
   docker compose up -d
   ```

### Permission Issues

Ensure the user `estacionamientog` has permission to run Docker commands:

```bash
sudo usermod -aG docker estacionamientog
```

Then log out and back in for the changes to take effect.

## Modifying the Schedule

To change the restart time, edit the timer file:

```bash
sudo nano /etc/systemd/system/parking-compose-restart.timer
```

Modify the `OnCalendar` line. Examples:

- **Every day at 3:00 AM**: `OnCalendar=*-*-* 03:00:00`
- **Every day at 11:30 PM**: `OnCalendar=*-*-* 23:30:00`
- **Twice daily (6 AM and 6 PM)**: Create a second timer or use `OnCalendar=*-*-* 06,18:00:00`

After making changes:

```bash
sudo systemctl daemon-reload
sudo systemctl restart parking-compose-restart.timer
```

## Benefits

- **Automatic Error Prevention**: Clears accumulated counts and state issues
- **Zero Downtime Concern**: Runs during low-usage hours (4:30 AM)
- **System Integration**: Uses native Linux systemd, no external dependencies
- **Reliable Logging**: All execution logged via journald
- **Persistent**: Catches up if system was offline during scheduled time

## Uninstallation

If you need to remove the automated restart:

```bash
# Stop and disable the timer
sudo systemctl stop parking-compose-restart.timer
sudo systemctl disable parking-compose-restart.timer

# Remove the files
sudo rm /etc/systemd/system/parking-compose-restart.service
sudo rm /etc/systemd/system/parking-compose-restart.timer

# Reload systemd
sudo systemctl daemon-reload
```
