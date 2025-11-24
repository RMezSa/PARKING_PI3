#!/usr/bin/env python3
"""
Persistent GPIO5 manager service for Raspberry Pi 5
Maintains GPIO5 state and responds to state file changes
"""

import os
import sys
import time
import signal
import logging
from pathlib import Path

# Force unbuffered output for systemd
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Set GPIO factory before importing gpiozero
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

try:
    from gpiozero import LED
except ImportError:
    logger.error("gpiozero not installed. Install with: pip install gpiozero lgpio")
    sys.exit(1)

GPIO_PIN = 5
STATE_FILE = Path("/var/lib/gpio5_state")  # Persistent location
CHECK_INTERVAL = 5  # seconds

# Schedule: ON at 17:30, OFF at 09:00
LIGHTS_ON_HOUR = 17
LIGHTS_ON_MINUTE = 30
LIGHTS_OFF_HOUR = 9
LIGHTS_OFF_MINUTE = 0

# Global LED object
led = None
running = True

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False

def read_desired_state():
    """Read the desired state from the state file"""
    try:
        if STATE_FILE.exists():
            state = STATE_FILE.read_text().strip().lower()
            return state if state in ['on', 'off'] else None
    except Exception as e:
        logger.error(f"Error reading state file: {e}")
    return None

def calculate_state_from_time():
    """Calculate what the GPIO state should be based on current time"""
    from datetime import datetime
    
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    
    lights_on_minutes = LIGHTS_ON_HOUR * 60 + LIGHTS_ON_MINUTE
    lights_off_minutes = LIGHTS_OFF_HOUR * 60 + LIGHTS_OFF_MINUTE
    
    # Check if current time is in the "lights ON" period
    # ON period is from 17:30 to 23:59 and 00:00 to 09:00
    if lights_on_minutes > lights_off_minutes:
        # ON period crosses midnight: 17:30 -> 00:00 -> 09:00
        should_be_on = current_minutes >= lights_on_minutes or current_minutes < lights_off_minutes
    else:
        # Normal case: ON period doesn't cross midnight
        should_be_on = lights_on_minutes <= current_minutes < lights_off_minutes
    
    return 'on' if should_be_on else 'off'

def apply_state(state):
    """Apply the GPIO state"""
    global led
    
    if state == 'on':
        led.on()
        logger.info(f"GPIO {GPIO_PIN} set to HIGH")
    elif state == 'off':
        led.off()
        logger.info(f"GPIO {GPIO_PIN} set to LOW")

def main():
    global led
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info(f"Starting GPIO {GPIO_PIN} manager service...")
    
    try:
        # Initialize the LED
        led = LED(GPIO_PIN)
        logger.info(f"GPIO {GPIO_PIN} initialized successfully")
        
        # Read initial state from file
        current_state = read_desired_state()
        
        if current_state:
            # State file exists, use it
            logger.info(f"Found state file with value: {current_state}")
            apply_state(current_state)
        else:
            # No state file - calculate from current time (handles reboot/first start)
            calculated_state = calculate_state_from_time()
            logger.info(f"No state file found, calculated state from time: {calculated_state}")
            apply_state(calculated_state)
            # Save the calculated state
            try:
                STATE_FILE.write_text(calculated_state)
            except Exception as e:
                logger.warning(f"Could not write initial state file: {e}")
            current_state = calculated_state
        
        last_state = current_state
        
        # Main loop - monitor state file for changes
        while running:
            desired_state = read_desired_state()
            
            if desired_state and desired_state != last_state:
                logger.info(f"State change detected: {last_state} -> {desired_state}")
                apply_state(desired_state)
                last_state = desired_state
            
            time.sleep(CHECK_INTERVAL)
        
        # Cleanup on exit
        logger.info("Cleaning up...")
        led.close()
        
    except Exception as e:
        logger.error(f"ERROR: {e}")
        if led:
            led.close()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
