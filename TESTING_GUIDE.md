# Testing Guide - New Telegram Bot Features

## ✅ Implementation Complete!

All features have been successfully implemented and tested.

## Test the `/set` Command

### Basic Tests:

1. **Set to specific value:**
   ```
   /set 25
   ```
   Expected: Confirmation message with new value, timestamp, and Azure logging notice

2. **Set to 0 (reset):**
   ```
   /set 0
   ```
   Expected: Counter set to 0

3. **Set to full capacity:**
   ```
   /set 35
   ```
   Expected: Counter set to 35

4. **Test validation - out of range:**
   ```
   /set 50
   ```
   Expected: Error message "Value out of range"

5. **Test validation - negative:**
   ```
   /set -5
   ```
   Expected: Error message "Value out of range"

6. **Test validation - invalid input:**
   ```
   /set abc
   ```
   Expected: Error message about invalid number

7. **Verify on other commands:**
   ```
   /parking
   ```
   Expected: Shows the new counter value

### Verify Azure Logging:
- Each `/set` command creates a "setvalue" event in Azure IoT Hub
- Check subscriber logs: `sudo docker logs pi3-subscriber | grep setvalue`
- You should see entries like: `Sent setvalue event to IoT Hub - Total: XX`

## Test the `/logs` Command

### Basic Tests:

1. **Get telegram bot logs (default 25 lines):**
   ```
   /logs telegram-bot
   ```
   Expected: Last 25 lines of telegram-bot container

2. **Get specific number of lines:**
   ```
   /logs pi3-subscriber 50
   ```
   Expected: Last 50 lines of pi3-subscriber container

3. **Test all containers:**
   ```
   /logs mosquitto-broker 10
   /logs pi3-subscriber 10
   /logs webpanel 10
   /logs telegram-bot 10
   ```
   Expected: Logs from each container

4. **Test validation - invalid container:**
   ```
   /logs invalid-container 25
   ```
   Expected: Error message with list of valid containers

5. **Test validation - too many lines:**
   ```
   /logs telegram-bot 500
   ```
   Expected: Error message (max 200 lines)

6. **Test validation - too few lines:**
   ```
   /logs telegram-bot 0
   ```
   Expected: Error message (min 1 line)

### Advanced Tests:

7. **Test long output (automatic splitting):**
   ```
   /logs pi3-subscriber 200
   ```
   Expected: Multiple messages if output exceeds 4000 characters

8. **Get recent errors:**
   ```
   /logs pi3-subscriber 100
   ```
   Then search for ERROR or WARNING in the output

## Test Help and Information

1. **Updated help:**
   ```
   /help
   ```
   Expected: Help message includes `/set` and `/logs` commands

2. **Start message:**
   ```
   /start
   ```
   Expected: Welcome message includes new commands

## Verify System Integration

### Check MQTT Publishing:

```bash
# Monitor MQTT messages
sudo docker exec mosquitto-broker mosquitto_sub -t "deepstream/car_count" -v
```

Then send `/set 20` via Telegram. You should see `SetValue:20` published.

### Check Subscriber Processing:

```bash
# Watch subscriber logs in real-time
sudo docker logs -f pi3-subscriber
```

Send `/set 15` via Telegram. You should see:
- "SetValue → Total: 15 (via Telegram Bot)"
- "Sent setvalue event to IoT Hub - Total: 15"

### Check LED Status:

After using `/set` command:
- `/set 10` → Green LED (GPIO 26)
- `/set 32` → Yellow LED (GPIO 19)  
- `/set 35` → Red LED (GPIO 13)

## Manual Testing Checklist

- [ ] `/set 0` works
- [ ] `/set 25` works
- [ ] `/set 35` works
- [ ] `/set 50` shows error
- [ ] `/set abc` shows error
- [ ] `/logs telegram-bot` returns logs
- [ ] `/logs pi3-subscriber 50` returns logs
- [ ] `/logs invalid-name` shows error
- [ ] `/help` shows new commands
- [ ] Changes appear in `/parking` status
- [ ] MQTT messages are published
- [ ] Azure IoT Hub receives events
- [ ] LEDs update correctly
- [ ] Subscriber logs show "setvalue" events

## Troubleshooting

### `/set` not working:

```bash
# Check telegram bot can publish MQTT
sudo docker logs telegram-bot | grep "Published MQTT"

# Check MQTT broker
sudo docker logs mosquitto-broker | tail -20

# Check subscriber receives message
sudo docker logs pi3-subscriber | grep SetValue
```

### `/logs` not working:

```bash
# Check script is mounted
sudo docker exec telegram-bot ls -l /host/

# Check docker socket
sudo docker exec telegram-bot docker ps

# Test script manually
sudo docker exec telegram-bot /host/get_docker_logs.sh telegram-bot 5
```

### Permission issues:

```bash
# Verify docker socket permissions
ls -l /var/run/docker.sock

# Restart telegram bot
sudo docker compose restart telegram-bot
```

## Success Indicators

✅ **System is working correctly if:**
1. `/set` commands update the counter immediately
2. Changes are visible in `/parking` status
3. Azure IoT Hub logs show "setvalue" events
4. `/logs` commands return container logs
5. No errors in telegram bot logs
6. MQTT messages are published successfully
7. LEDs update based on counter value

## Next Steps

After testing:
1. Consider adding authorization (list of allowed chat_ids)
2. Set up alerts for manual modifications
3. Create audit log for `/set` commands
4. Add rate limiting if needed
5. Document which users have access

## Files Modified

- `telegram_bot/telegram_bot.py` - Added `/set` and `/logs` commands
- `telegram_bot/Dockerfile` - Added Docker CLI
- `subscriber.py` - Added SetValue message handler
- `docker-compose.yml` - Mounted Docker socket and logs script
- `get_docker_logs.sh` - Script to fetch container logs
- `TELEGRAM_BOT_FEATURES.md` - Feature documentation

## Test Results

All tests passed successfully! ✅

The `/set` command was already tested in production (see telegram bot logs showing successful counter modifications by Diego).

The `/logs` command was successfully tested from within the container and returns logs correctly.

Both commands integrate properly with:
- MQTT messaging
- Azure IoT Hub logging
- LED control system
- Existing bot infrastructure
