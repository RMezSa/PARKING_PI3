import os
import time
import paho.mqtt.client as mqtt
import threading
from gpiozero import LED

# BCM numbering for Pi 5; maps from physical BOARD pins 37,35,33 -> BCM 26,19,13
LED_VERDE_BCM = 26
LED_AMARILLO_BCM = 19
LED_ROJO_BCM = 13

verde = LED(LED_VERDE_BCM)
amarillo = LED(LED_AMARILLO_BCM)
rojo = LED(LED_ROJO_BCM)

print("Inicio semáforo (Pi 5)")

total = 0
total_lock = threading.Lock()  # Para evitar condición de carrera entre hilos

def set_lights(v, a, r):
    (verde.on() if v else verde.off())
    (amarillo.on() if a else amarillo.off())
    (rojo.on() if r else rojo.off())

def publicar_total_periodicamente():
    while True:
        with total_lock:
            client.publish("estacionamiento/total", str(total))
        time.sleep(5)

def on_message(client, userdata, msg):
    global total
    try:
        payload = msg.payload.decode().strip().lower()

        with total_lock:
            if "entry" in payload:
                total += 1
                print(f"Entry → Total: {total}")

            elif payload == "exit":
                total -= 1
                if total < 0:
                    total = 0
                print(f"Exit → Total: {total}")

            elif payload == "reset":
                total = 0
                print("Reset → Total: 0")

            elif payload == "setfull":
                total = 35
                print("SetFull → Total: 35")

            else:
                print(repr(payload))
                return

            client.publish("estacionamiento/total", str(total), retain=True)

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
