# LED Control & State Persistence Implementation

## Overview
Implemented persistent state management for the parking system with independent LED control.

## Features

### 1. Persistent State Storage
- **Location:** `/home/estacionamientog/PARKING_PI3/subscriber_data/parking_state.json`
- **Survives:** Docker restarts, container recreations
- **Contents:**
  - `total`: Current parking counter (0-35)
  - `leds_enabled`: LED state (true/false)
  - `last_updated`: Timestamp of last update

### 2. Independent LED Control
- LEDs can be turned OFF for testing
- Counter continues working when LEDs are OFF
- Perfect for testing without displaying to public
- LED state survives container restarts

### 3. Daily Counter Reset
- Every day at 4:30 AM CDMX time
- Counter resets to 0
- LED state is PRESERVED
- Automatic via cron job

## Telegram Bot Commands

### `/leds on`
Enables the semaforo LEDs.
- LEDs will display current parking status
- Green (< 30), Yellow (30-34), Red (35)
- Logged to Azure IoT Hub

**Example:**
```
/leds on
```

**Response:**
```
✅ Semáforo Encendido

💡 Los LEDs están activos
👤 Activado por: Diego
🕐 21/10/2025 18:45:00

Los LEDs reflejarán el estado actual del estacionamiento

📝 Este cambio ha sido registrado en Azure IoT Hub
```

### `/leds off`
Disables the semaforo LEDs.
- All LEDs turn OFF
- Counter continues working normally
- Perfect for testing
- Logged to Azure IoT Hub

**Example:**
```
/leds off
```

**Response:**
```
✅ Semáforo Apagado

🌑 Los LEDs están desactivados
👤 Desactivado por: Diego
🕐 21/10/2025 18:45:15

⚠️ El contador seguirá funcionando normalmente
Ideal para pruebas sin mostrar datos al público

📝 Este cambio ha sido registrado en Azure IoT Hub
```

### `/status` or `/parking`
Now shows LED state in addition to parking count.

**Example Response:**
```
🅿️ Parking Status - AVAILABLE 🟢

📊 Occupied: 15/35 spaces
✅ Available: 20/35 spaces

💡 Semáforo: Activo
🕐 Last updated: 21/10/2025 18:45:30
📡 System status: 🟢 Connected
```

When LEDs are OFF:
```
🌑 Semáforo: Desactivado
```

## Technical Implementation

### MQTT Topics

#### Input Commands (deepstream/car_count)
- `Entry` - Increment counter
- `Exit` - Decrement counter
- `Reset` - Reset to 0
- `SetFull` - Set to 35
- `SetValue:XX` - Set to specific value
- **`LEDOn`** - Enable LEDs
- **`LEDOff`** - Disable LEDs

#### Output Topics
- `estacionamiento/total` - Current count (retained)
- **`estacionamiento/leds_state`** - LED state: "ON" or "OFF" (retained)

### State File Structure
```json
{
  "total": 25,
  "leds_enabled": true,
  "last_updated": "2025-10-21 18:45:30"
}
```

### Files Modified

1. **subscriber.py**
   - Added `load_state()` and `save_state()` functions
   - State loaded on startup
   - State saved after every counter change
   - LED control respects `leds_enabled` flag
   - Handles `LEDOn` and `LEDOff` MQTT messages
   - Publishes LED state to MQTT

2. **telegram_bot/telegram_bot.py**
   - Added `handle_leds_command()` function
   - Added `leds_state` global variable
   - Updated `MQTTListener` to subscribe to LED state topic
   - Updated `/status` and `/parking` to show LED state
   - Updated help messages

3. **docker-compose.yml**
   - Mounted `./subscriber_data:/app/data` for pi3-subscriber
   - Persistent storage for state file

4. **docker-restart-cron.sh**
   - Calls `reset_counter_host.py` before starting containers
   - Resets counter to 0 at 4:30 AM
   - Preserves LED state

5. **New Files**
   - `reset_counter_host.py` - Resets counter from host
   - `reset_counter.py` - Resets counter from container (backup)

## Usage Scenarios

### Scenario 1: Normal Operation
1. System starts with LEDs ON (default)
2. Counter tracks entries/exits
3. LEDs display status (Green/Yellow/Red)
4. State survives restarts

### Scenario 2: Testing Mode
1. Send `/leds off` via Telegram
2. LEDs turn off
3. Counter continues working
4. Test entries/exits without public display
5. Check counter with `/parking` command
6. When done: `/leds on` to resume normal operation

### Scenario 3: Container Restart
1. Container stops (planned or unplanned)
2. State file preserves:
   - Current counter value
   - LED on/off state
3. Container starts
4. State loaded from file
5. System resumes exactly where it left off

### Scenario 4: Daily Reset (4:30 AM)
1. Cron job triggers at 4:30 AM
2. `reset_counter_host.py` runs
3. Counter reset to 0 in state file
4. LED state preserved (ON or OFF)
5. Containers start
6. New day begins with fresh counter

## Testing Guide

### Test 1: LED Control
```bash
# Via Telegram
/leds off
# Verify all LEDs are OFF
# Check counter still works
/set 20
/parking
# Should show count=20, LEDs=OFF

/leds on
# Verify LEDs turn on and show correct color
```

### Test 2: State Persistence
```bash
# Set counter and LED state
/set 25
/leds off

# Restart container
sudo docker restart pi3-subscriber

# Wait 10 seconds
sudo docker logs pi3-subscriber --tail 10
# Should show: "State loaded: total=25, leds_enabled=False"

# Verify via Telegram
/parking
# Should show count=25, LEDs=OFF
```

### Test 3: Daily Reset Simulation
```bash
# Set counter and turn off LEDs
/set 30
/leds off

# Manually run the reset script
python3 /home/estacionamientog/PARKING_PI3/reset_counter_host.py

# Check state file
cat /home/estacionamientog/PARKING_PI3/subscriber_data/parking_state.json
# Should show: total=0, leds_enabled=false

# Restart subscriber to load new state
sudo docker restart pi3-subscriber

# Verify
/parking
# Should show count=0, LEDs=OFF
```

### Test 4: Azure Logging
```bash
# Turn LEDs off
/leds off

# Check subscriber logs
sudo docker logs pi3-subscriber | grep "leds_off"
# Should see: "Sent leds_off event to IoT Hub"

# Turn LEDs on
/leds on

# Check logs again
sudo docker logs pi3-subscriber | grep "leds_on"
# Should see: "Sent leds_on event to IoT Hub"
```

## Monitoring

### Check State File
```bash
cat /home/estacionamientog/PARKING_PI3/subscriber_data/parking_state.json
```

### Check Subscriber Logs
```bash
sudo docker logs pi3-subscriber --tail 50
```

### Check LED State via MQTT
```bash
sudo docker exec mosquitto-broker mosquitto_sub -t "estacionamiento/leds_state" -v
```

### Check Counter via MQTT
```bash
sudo docker exec mosquitto-broker mosquitto_sub -t "estacionamiento/total" -v
```

## Troubleshooting

### LEDs not responding to /leds command
1. Check MQTT broker: `sudo docker ps | grep mosquitto`
2. Check subscriber logs: `sudo docker logs pi3-subscriber`
3. Verify MQTT message received: Check logs for "LEDOn" or "LEDOff"

### State not persisting
1. Check state file exists: `ls -l subscriber_data/parking_state.json`
2. Check file permissions: `ls -la subscriber_data/`
3. Check subscriber logs for "Error saving state"

### Counter not resetting at 4:30 AM
1. Check cron job: `crontab -l | grep 4:30`
2. Check cron log: `tail -f /home/estacionamientog/PARKING_PI3/docker-restart-cron.log`
3. Test reset script manually: `python3 reset_counter_host.py`

### LED state not showing in Telegram
1. Check bot subscribed to topic: `sudo docker logs telegram-bot | grep leds_state`
2. Check MQTT retained message: `sudo docker exec mosquitto-broker mosquitto_sub -t "estacionamiento/leds_state" -C 1`

## Azure IoT Hub Events

### New Event Types
- `leds_on` - LEDs enabled
- `leds_off` - LEDs disabled

### Event Data Structure
```json
{
  "event_type": "leds_on",
  "total": 25,
  "timestamp": "2025-10-21T18:45:00Z"
}
```

## Benefits

✅ **Independent Testing**: Test counter without public display
✅ **State Persistence**: No data loss on restarts
✅ **Daily Fresh Start**: Counter resets automatically
✅ **Full Audit Trail**: All LED changes logged to Azure
✅ **Flexible Control**: Turn LEDs on/off as needed
✅ **Survives Outages**: System recovers to last known state

## Future Enhancements

1. **Schedule LED Control**: Auto off/on at specific times
2. **LED Patterns**: Blink for alerts or errors
3. **Counter History**: Track daily max/min values
4. **Web Panel Integration**: LED control from web interface
5. **Multiple Profiles**: Different LED behaviors for different scenarios

## Support

For issues:
- Check logs: `sudo docker logs pi3-subscriber`
- Check state: `cat subscriber_data/parking_state.json`
- View this guide: `/home/estacionamientog/PARKING_PI3/LED_CONTROL_GUIDE.md`
