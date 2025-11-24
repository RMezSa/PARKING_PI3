# Telegram Bot New Features - Implementation Summary

## Overview
Added two new commands to the Telegram Bot for enhanced parking management and system monitoring.

## New Features

### 1. `/set` Command - Parking Counter Control

**Purpose:** Allows authorized users to manually set the parking counter to any value.

**Usage:**
```
/set <number>
```

**Examples:**
- `/set 0` - Reset counter to 0
- `/set 25` - Set counter to 25
- `/set 35` - Set to full capacity

**How it Works:**
1. User sends `/set 25` command via Telegram
2. Bot validates the number (must be 0-35)
3. Bot publishes `SetValue:25` message to MQTT topic `deepstream/car_count`
4. `subscriber.py` receives the message and updates the counter
5. Event is logged to Azure IoT Hub as `setvalue` event type
6. User receives confirmation with timestamp and username

**Azure Integration:**
- All `/set` commands are logged to Azure IoT Hub
- Event type: `setvalue`
- Includes timestamp and new value
- Allows tracking of manual modifications

### 2. `/logs` Command - Docker Container Logs

**Purpose:** Fetch and view logs from any Docker container in the system.

**Usage:**
```
/logs <container-name> [number-of-lines]
```

**Examples:**
- `/logs telegram-bot` - Get last 25 lines (default)
- `/logs pi3-subscriber 50` - Get last 50 lines
- `/logs webpanel 100` - Get last 100 lines

**Available Containers:**
- `mosquitto-broker` - MQTT broker logs
- `pi3-subscriber` - Main parking system logs (GPIO, MQTT, Azure)
- `webpanel` - Web panel logs
- `telegram-bot` - Telegram bot logs

**How it Works:**
1. User sends `/logs telegram-bot 50` command
2. Bot validates container name and line count
3. Bot calls `/host/get_docker_logs.sh` script on the host
4. Script uses `sudo docker logs` to fetch the logs
5. Bot returns logs to user (split into multiple messages if needed)

**Limitations:**
- Maximum 200 lines per request
- Long logs are split into multiple messages (Telegram 4096 char limit)
- Requires containers to be running

## Files Modified/Created

### New Files:
1. **`/home/estacionamientog/PARKING_PI3/get_docker_logs.sh`**
   - Bash script to fetch Docker container logs
   - Validates container names and line counts
   - Uses sudo to access Docker

### Modified Files:
1. **`telegram_bot/telegram_bot.py`**
   - Added `publish_mqtt_command()` function
   - Added `get_container_logs()` function
   - Added `handle_set_command()` function
   - Added `handle_logs_command()` function
   - Updated help message and start message
   - Added imports for subprocess and paho.mqtt.publish

2. **`subscriber.py`**
   - Added handler for `SetValue:<number>` MQTT messages
   - Validates value range (0-35)
   - Logs event to Azure IoT Hub as "setvalue" type

3. **`docker-compose.yml`**
   - Mounted `get_docker_logs.sh` into telegram-bot container
   - Mount path: `/host/get_docker_logs.sh` (read-only)

## Security Considerations

### `/set` Command:
- ⚠️ Currently accessible to all Telegram users who have the bot
- All modifications are logged to Azure IoT Hub with timestamp
- Value range is restricted (0-35)
- Changes are visible in system logs

**Future Enhancement Suggestion:**
- Add authorized user list (chat_ids)
- Require confirmation for large changes
- Add admin-only mode

### `/logs` Command:
- ⚠️ Currently accessible to all Telegram users
- Limited to 200 lines per request
- Only allows viewing, not modification
- No sensitive data should be in logs

**Future Enhancement Suggestion:**
- Add authorized user list
- Rate limiting
- Restrict to specific containers per user

## Testing the Features

### Test `/set` Command:
1. Send message to bot: `/set 15`
2. Verify response shows confirmation
3. Check `/parking` or `/status` to see updated count
4. Check Azure IoT Hub for logged event

### Test `/logs` Command:
1. Send message to bot: `/logs telegram-bot 25`
2. Verify you receive log output
3. Try different containers and line counts
4. Test error handling: `/logs invalid-name`

## MQTT Message Format

### Published by Telegram Bot:
```
Topic: deepstream/car_count
Message: SetValue:25
```

### Processed by subscriber.py:
```python
if payload_lower.startswith("setvalue:"):
    new_value = int(payload.split(":", 1)[1].strip())
    # Validates 0-35 range
    # Updates counter
    # Logs to Azure IoT Hub
```

## Troubleshooting

### `/set` command not working:
1. Check MQTT broker is running: `sudo docker ps`
2. Check telegram bot logs: `sudo docker logs telegram-bot`
3. Check subscriber logs: `sudo docker logs pi3-subscriber`
4. Verify MQTT_BROKER env variable in docker-compose.yml

### `/logs` command not working:
1. Verify script is mounted: `sudo docker exec telegram-bot ls -l /host/`
2. Check script permissions: `ls -l get_docker_logs.sh` (should be executable)
3. Test script manually: `./get_docker_logs.sh telegram-bot 25`
4. Check telegram bot logs for errors

### Script permissions error:
```bash
sudo chmod +x /home/estacionamientog/PARKING_PI3/get_docker_logs.sh
```

## Future Enhancements

1. **Authorization System:**
   - Maintain list of authorized chat_ids
   - Different permission levels (admin, viewer)
   - Role-based access control

2. **Audit Trail:**
   - Keep local log of all `/set` commands
   - Include user info, timestamp, old/new values
   - Periodic reports of manual modifications

3. **Additional Commands:**
   - `/increase` and `/decrease` for +1/-1 operations
   - `/history` to show recent counter changes
   - `/restart` to restart specific containers
   - `/status advanced` for detailed system metrics

4. **Rate Limiting:**
   - Prevent spam of `/set` or `/logs` commands
   - Cooldown period between operations

5. **Notifications:**
   - Alert admin when counter is manually modified
   - Notify when logs show errors
   - System health alerts

## Support

For issues or questions:
- Check logs: `sudo docker logs telegram-bot`
- View this guide: `/home/estacionamientog/PARKING_PI3/TELEGRAM_BOT_FEATURES.md`
- Check main README: `/home/estacionamientog/PARKING_PI3/telegram_bot/README.md`
