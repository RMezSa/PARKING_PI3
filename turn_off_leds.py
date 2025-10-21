#!/usr/bin/env python3
"""
Script to forcefully turn off all semaforo LEDs
This is run after docker compose down to ensure all LEDs are off
"""

import os
import sys
import time

# Set GPIO factory before importing gpiozero
os.environ['GPIOZERO_PIN_FACTORY'] = 'lgpio'

try:
    from gpiozero import LED
    
    # BCM numbering for Pi 5
    LED_VERDE_BCM = 26
    LED_AMARILLO_BCM = 19
    LED_ROJO_BCM = 13
    
    print("Initializing LEDs...")
    
    # Create LED objects
    verde = LED(LED_VERDE_BCM)
    amarillo = LED(LED_AMARILLO_BCM)
    rojo = LED(LED_ROJO_BCM)
    
    # Turn off all LEDs
    print(f"Turning off Verde (GPIO {LED_VERDE_BCM})...")
    verde.off()
    
    print(f"Turning off Amarillo (GPIO {LED_AMARILLO_BCM})...")
    amarillo.off()
    
    print(f"Turning off Rojo (GPIO {LED_ROJO_BCM})...")
    rojo.off()
    
    # Small delay to ensure the pins are set
    time.sleep(0.1)
    
    # Close the LED objects to release the pins
    verde.close()
    amarillo.close()
    rojo.close()
    
    print("All semaforo LEDs turned off successfully!")
    sys.exit(0)
    
except Exception as e:
    print(f"Error turning off LEDs: {e}", file=sys.stderr)
    sys.exit(1)
