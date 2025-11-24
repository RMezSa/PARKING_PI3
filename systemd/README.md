# GPIO5 Automated Light Control

This folder contains a persistent GPIO manager service and systemd timers to automatically control GPIO5 (lights) ON at 17:30 (5:30 PM) and OFF at 09:00 (9:00 AM) daily.

## Architecture

The system uses a **persistent manager service** approach for reliable GPIO control:

- `gpio5_manager.py` - Python service that maintains GPIO5 state persistently
- `gpio5-manager.service` - Systemd service that runs the manager continuously
- `set_gpio5.sh` - Helper script to change GPIO5 state
- `set-gpio5-on.service` - Oneshot service triggered by timer to turn lights ON
- `set-gpio5-off.service` - Oneshot service triggered by timer to turn lights OFF  
- `set-gpio5-on.timer` - Timer that triggers at 17:30 daily
- `set-gpio5-off.timer` - Timer that triggers at 09:00 daily

## Installation

### 1. Install Python dependencies (if not already installed)

```bash
pip3 install gpiozero lgpio
```

### 2. Copy files to system locations

```bash
# Copy Python manager script
sudo cp systemd/gpio5_manager.py /usr/local/bin/gpio5_manager.py
sudo chmod 755 /usr/local/bin/gpio5_manager.py

# Copy shell helper script
sudo cp systemd/set_gpio5.sh /usr/local/bin/set_gpio5.sh
sudo chmod 755 /usr/local/bin/set_gpio5.sh

# Copy all service and timer files
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
```

### 3. Enable and start services

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable and start the persistent manager service
sudo systemctl enable --now gpio5-manager.service

# Enable and start the timers
sudo systemctl enable --now set-gpio5-on.timer set-gpio5-off.timer
```

## Verification

### Check manager service status

```bash
systemctl status gpio5-manager.service
```

### Check timer status and next scheduled runs

```bash
systemctl list-timers --all | grep set-gpio5
```

### Check GPIO5 current state

```bash
# View manager logs
journalctl -u gpio5-manager.service -f

# Or check state file
cat /var/run/gpio5_state
```

### Manual testing

```bash
# Turn lights ON
sudo /usr/local/bin/set_gpio5.sh on

# Turn lights OFF
sudo /usr/local/bin/set_gpio5.sh off

# Check if GPIO is actually high/low
gpioinfo gpiochip0 | grep "GPIO5"
```

## Troubleshooting

### Timers not triggering

```bash
# Check timer status
systemctl status set-gpio5-on.timer set-gpio5-off.timer

# View timer logs
journalctl -u set-gpio5-on.timer -u set-gpio5-off.timer --since today
```

### Manager service not working

```bash
# Check service status
systemctl status gpio5-manager.service

# View detailed logs
journalctl -u gpio5-manager.service -n 50

# Restart the service
sudo systemctl restart gpio5-manager.service
```

### GPIO conflicts

If you see "Device or resource busy" errors, another process may be using GPIO5:

```bash
# Check what's using the GPIO
ps aux | grep gpio
lsof /dev/gpiochip0 2>/dev/null || fuser /dev/gpiochip0 2>/dev/null

# Kill old gpioset processes if needed
sudo pkill gpioset
```

## How It Works

1. **Persistent Manager**: The `gpio5-manager.service` runs continuously, monitoring a state file
2. **State Changes**: When timers trigger, they call `set_gpio5.sh` which writes the desired state
3. **GPIO Control**: The manager detects state changes and applies them using gpiozero/lgpio
4. **Reliability**: If the manager restarts, it reads the state file and restores the GPIO state

## Notes

- Uses `gpiozero` with `lgpio` backend (compatible with Raspberry Pi 5)
- GPIO5 = BCM GPIO 5 on gpiochip0
- Times are in local system time (CST in this case)
- The manager service auto-restarts if it crashes
- **Reboot-safe**: State persists in `/var/lib/gpio5_state` across reboots
- **Smart recovery**: If state file is missing after reboot, system automatically calculates correct state based on current time
  - Example: Reboot at 20:00 → Lights turn ON (between 17:30 and 09:00)
  - Example: Reboot at 12:00 → Lights stay OFF (between 09:00 and 17:30)
