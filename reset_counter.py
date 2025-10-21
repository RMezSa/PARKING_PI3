#!/usr/bin/env python3
"""
Script to reset the parking counter to 0 at 4:30 AM
This preserves the LED state but resets the counter
"""

import json
import os
import sys

STATE_FILE = "/app/data/parking_state.json"

try:
    # Load current state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
    else:
        state = {}
    
    # Reset total to 0, but preserve leds_enabled
    state['total'] = 0
    state['leds_enabled'] = state.get('leds_enabled', True)  # Preserve LED state
    state['last_updated'] = '4:30 AM Daily Reset'
    
    # Save the updated state
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"Counter reset to 0, LED state preserved: {state['leds_enabled']}")
    sys.exit(0)
    
except Exception as e:
    print(f"Error resetting counter: {e}", file=sys.stderr)
    sys.exit(1)
