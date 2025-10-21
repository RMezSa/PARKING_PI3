import os
import time
import json
import paho.mqtt.client as mqtt
import threading
import logging
from gpiozero import LED, Device
from iot_hub_client import IoTHubManager

# BCM numbering for Pi 5; maps from physical BOARD pins 37,35,33 -> BCM 26,19,13
LED_VERDE_BCM = 26
LED_AMARILLO_BCM = 19
LED_ROJO_BCM = 13

verde = LED(LED_VERDE_BCM)
amarillo = LED(LED_AMARILLO_BCM)
rojo = LED(LED_ROJO_BCM)

print("Inicio semáforo (Pi 5)")
print(f"GPIOZero pin factory: {Device.pin_factory}")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# State file path for persistence
STATE_FILE = "/app/data/parking_state.json"

# Initialize IoT Hub client
iot_hub_connection_string = os.getenv("IOT_HUB_CONNECTION_STRING")
iot_hub_client = None

if iot_hub_connection_string:
    try:
        iot_hub_manager = IoTHubManager(iot_hub_connection_string)
        if iot_hub_manager.connect():
            logger.info("Successfully connected to Azure IoT Hub")
        else:
            logger.warning("Failed to connect to Azure IoT Hub")
    except Exception as e:
        logger.error(f"Error initializing IoT Hub client: {e}")
        iot_hub_manager = None
else:
    logger.warning("IOT_HUB_CONNECTION_STRING not provided - IoT Hub integration disabled")

# Global state variables
total = 0
leds_enabled = True  # LEDs ON by default
total_lock = threading.Lock()  # Para evitar condición de carrera entre hilos

def load_state():
    """Load parking state from JSON file"""
    global total, leds_enabled
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                total = state.get('total', 0)
                leds_enabled = state.get('leds_enabled', True)
                logger.info(f"State loaded: total={total}, leds_enabled={leds_enabled}")
        else:
            logger.info("No state file found, starting with defaults: total=0, leds_enabled=True")
            save_state()  # Create initial state file
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        total = 0
        leds_enabled = True

def save_state():
    """Save parking state to JSON file"""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        state = {
            'total': total,
            'leds_enabled': leds_enabled,
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving state: {e}")

def set_lights(v, a, r):
    """Set LED states - only if LEDs are enabled"""
    if leds_enabled:
        (verde.on() if v else verde.off())
        (amarillo.on() if a else amarillo.off())
        (rojo.on() if r else rojo.off())
    else:
        # Keep all LEDs off when disabled
        verde.off()
        amarillo.off()
        rojo.off()

def publicar_total_periodicamente():
    while True:
        with total_lock:
            current_total = total
            # Publish to MQTT
            client.publish("estacionamiento/total", str(current_total))
            
            # Send periodic update to IoT Hub
            if iot_hub_client:
                try:
                    iot_hub_client.send_parking_event("periodic", current_total)
                except Exception as e:
                    logger.error(f"Error sending periodic update to IoT Hub: {e}")
                    
        time.sleep(5)

def on_message(client, userdata, msg):
    global total, leds_enabled
    try:
        payload = msg.payload.decode().strip()
        payload_lower = payload.lower()
        event_type = None

        with total_lock:
            if "entry" in payload_lower:
                total += 1
                event_type = "entry"
                print(f"Entry → Total: {total}")
                save_state()

            elif payload_lower == "exit":
                total -= 1
                if total < 0:
                    total = 0
                event_type = "exit"
                print(f"Exit → Total: {total}")
                save_state()

            elif payload_lower == "reset":
                total = 0
                event_type = "reset"
                print("Reset → Total: 0")
                save_state()

            elif payload_lower == "setfull":
                total = 35
                event_type = "setfull"
                print("SetFull → Total: 35")
                save_state()

            elif payload_lower.startswith("setvalue:"):
                try:
                    # Extract the number from "SetValue:XX"
                    new_value = int(payload.split(":", 1)[1].strip())
                    if 0 <= new_value <= 35:
                        total = new_value
                        event_type = "setvalue"
                        print(f"SetValue → Total: {total} (via Telegram Bot)")
                        save_state()
                    else:
                        print(f"SetValue rejected: {new_value} out of range (0-35)")
                        return
                except (ValueError, IndexError) as e:
                    print(f"Invalid SetValue format: {payload}")
                    return

            elif payload_lower == "ledon":
                leds_enabled = True
                event_type = "leds_on"
                print("LEDs → Enabled")
                save_state()
                # Publish LED state to MQTT
                client.publish("estacionamiento/leds_state", "ON", retain=True)
                # Update LEDs immediately based on current count
                if total >= 35:
                    set_lights(0, 0, 1)
                elif total >= 30:
                    set_lights(0, 1, 0)
                else:
                    set_lights(1, 0, 0)

            elif payload_lower == "ledoff":
                leds_enabled = False
                event_type = "leds_off"
                print("LEDs → Disabled")
                save_state()
                # Publish LED state to MQTT
                client.publish("estacionamiento/leds_state", "OFF", retain=True)
                # Turn off all LEDs immediately
                set_lights(0, 0, 0)

            else:
                print(repr(payload))
                return

            # Publish to MQTT
            client.publish("estacionamiento/total", str(total), retain=True)
            
            # Send event to IoT Hub
            if iot_hub_manager and event_type:
                try:
                    # For LED events, send a special message without total
                    if event_type in ["leds_on", "leds_off"]:
                        success = iot_hub_manager.send_parking_event(event_type, total)
                    else:
                        success = iot_hub_manager.send_parking_event(event_type, total)
                    
                    if success:
                        logger.info(f"Sent {event_type} event to IoT Hub - Total: {total}")
                    else:
                        logger.warning(f"Failed to send {event_type} event to IoT Hub")
                except Exception as e:
                    logger.error(f"Error sending {event_type} event to IoT Hub: {e}")

            # Actualizar luces (skip for LED control commands, already handled above)
            if event_type not in ["leds_on", "leds_off"]:
                if total >= 35:
                    print("Rojo")
                    set_lights(0, 0, 1)
                elif total >= 30:
                    print("Amarillo")
                    set_lights(0, 1, 0)
                else:
                    print("Verde")
                    set_lights(1, 0, 0)

    except Exception as e:
        print(f"Error al procesar el mensaje: {e}")

broker_ip = os.getenv("BROKER_HOST", "localhost")
port = int(os.getenv("BROKER_PORT", "1883"))
topic = os.getenv("TOPIC", "deepstream/car_count")

# Load state before starting
load_state()

client = mqtt.Client()
client.on_message = on_message
client.connect(broker_ip, port)
client.subscribe(topic)

# Publish initial state to MQTT
client.publish("estacionamiento/leds_state", "ON" if leds_enabled else "OFF", retain=True)
client.publish("estacionamiento/total", str(total), retain=True)

# Set initial LED state based on current count (only if LEDs are enabled)
if leds_enabled:
    if total >= 35:
        set_lights(0, 0, 1)
    elif total >= 30:
        set_lights(0, 1, 0)
    else:
        set_lights(1, 0, 0)
else:
    set_lights(0, 0, 0)

# Lanzar hilo de publicación periódica
threading.Thread(target=publicar_total_periodicamente, daemon=True).start()

print("Esperando mensajes...")
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("Apagando...")
    set_lights(0, 0, 0)
finally:
    # Ensure LEDs are off on exit
    try:
        verde.off(); amarillo.off(); rojo.off()
    except Exception:
        pass
    
    # Disconnect from IoT Hub
    if iot_hub_manager:
        try:
            logger.info("Disconnecting from Azure IoT Hub...")
            iot_hub_manager.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from IoT Hub: {e}")
