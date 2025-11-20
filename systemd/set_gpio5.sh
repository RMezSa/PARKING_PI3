#!/bin/bash
# GPIO5 control script using Python and gpiozero for Raspberry Pi 5
# This properly manages GPIO state persistently using a systemd service
# Usage: set_gpio5.sh on|off

GPIO_PIN=5
STATE_FILE=/var/lib/gpio5_state
PYTHON_SCRIPT=/usr/local/bin/gpio5_manager.py

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root (sudo)" >&2
  exit 1
fi

action="$1"
if [ "$action" != "on" ] && [ "$action" != "off" ]; then
  echo "Usage: $0 on|off" >&2
  exit 2
fi

# Write the desired state
echo "$action" > "$STATE_FILE"

# If the manager service is running, it will pick up the state change
# Otherwise, apply the change directly using Python
if ! systemctl is-active --quiet gpio5-manager.service; then
  python3 -c "
import os
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'
from gpiozero import LED
from time import sleep

led = LED($GPIO_PIN)
if '$action' == 'on':
    led.on()
    print('GPIO $GPIO_PIN set to HIGH')
else:
    led.off()
    print('GPIO $GPIO_PIN set to LOW')
sleep(0.1)
"
fi

echo "GPIO $GPIO_PIN state set to: $action"
exit 0

