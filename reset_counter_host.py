#!/usr/bin/env python3
"""
Script to reset the parking counter to 0 at 4:30 AM from the host
This preserves the LED state but resets the counter
Runs on the host before starting containers
"""

import json
import os
import sys

# Path where docker volumes are mounted
STATE_FILE = "/home/estacionamientog/PARKING_PI3/subscriber_data/parking_state.json"

try:
    # Load current state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        
        # Reset total to 0, but preserve leds_enabled
        old_total = state.get('total', 0)
        leds_state = state.get('leds_enabled', True)
        
        state['total'] = 0
        state['last_updated'] = '4:30 AM Daily Reset'
        
        # Save the updated state
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"Counter reset: {old_total} → 0, LED state preserved: {'ON' if leds_state else 'OFF'}")
    else:
        # Create initial state file
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        state = {
            'total': 0,
            'leds_enabled': True,
            'last_updated': '4:30 AM Daily Reset - Initial'
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        print("Created initial state file with counter=0, LEDs=ON")
    
    sys.exit(0)
    
except Exception as e:
    print(f"Error resetting counter: {e}", file=sys.stderr)
    sys.exit(1)
