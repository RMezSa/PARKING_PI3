import RPi.GPIO as GPIO
import time
import paho.mqtt.client as mqtt
import threading

GPIO.setmode(GPIO.BOARD)
verde, amarillo, rojo = 37, 35, 33

GPIO.setup(verde, GPIO.OUT)
GPIO.setup(amarillo, GPIO.OUT)
GPIO.setup(rojo, GPIO.OUT)

print("Inicio semáforo")

total = 0
total_lock = threading.Lock()  # Para evitar condición de carrera entre hilos

def set_lights(v, a, r):
    GPIO.output(verde, v)
    GPIO.output(amarillo, a)
    GPIO.output(rojo, r)

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

broker_ip = "10.244.140.146"
port = 1883
topic = "deepstream/car_count"

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
    GPIO.cleanup()
