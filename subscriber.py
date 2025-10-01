import os
import time
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

total = 0
total_lock = threading.Lock()  # Para evitar condición de carrera entre hilos

def set_lights(v, a, r):
    (verde.on() if v else verde.off())
    (amarillo.on() if a else amarillo.off())
    (rojo.on() if r else rojo.off())

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
    global total
    try:
        payload = msg.payload.decode().strip().lower()
        event_type = None

        with total_lock:
            if "entry" in payload:
                total += 1
                event_type = "entry"
                print(f"Entry → Total: {total}")

            elif payload == "exit":
                total -= 1
                if total < 0:
                    total = 0
                event_type = "exit"
                print(f"Exit → Total: {total}")

            elif payload == "reset":
                total = 0
                event_type = "reset"
                print("Reset → Total: 0")

            elif payload == "setfull":
                total = 35
                event_type = "setfull"
                print("SetFull → Total: 35")

            else:
                print(repr(payload))
                return

            # Publish to MQTT
            client.publish("estacionamiento/total", str(total), retain=True)
            
            # Send event to IoT Hub
            if iot_hub_manager and event_type:
                try:
                    success = iot_hub_manager.send_parking_event(event_type, total)
                    if success:
                        logger.info(f"Sent {event_type} event to IoT Hub - Total: {total}")
                    else:
                        logger.warning(f"Failed to send {event_type} event to IoT Hub")
                except Exception as e:
                    logger.error(f"Error sending {event_type} event to IoT Hub: {e}")

            # Actualizar luces
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

client = mqtt.Client()
client.on_message = on_message
client.connect(broker_ip, port)
client.subscribe(topic)

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
