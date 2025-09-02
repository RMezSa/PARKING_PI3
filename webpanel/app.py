from flask import Flask, request, render_template_string, redirect, session, url_for, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import time
import os
import threading
import logging
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-for-dev')
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuración MQTT
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = "deepstream/car_count"
TOTAL_TOPIC = "estacionamiento/total"
PASSWORD = os.environ.get("WEB_PASSWORD")

# Validar variables de entorno críticas
if not PASSWORD:
    raise ValueError("WEB_PASSWORD environment variable must be set")
if not MQTT_BROKER:
    raise ValueError("MQTT_BROKER environment variable must be set")

# Variables globales para MQTT
mqtt_client = None
current_total = "0"
is_connected = False

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Panel Estacionamiento</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #121212;
            color: white;
            font-family: Arial, sans-serif;
        }
        h2{
            color: white;
        } 
        .card {
            background-color: #1e1e1e;
            border: none;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }
        .btn-green {
            background-color: #76B900;
            color: black;
            font-weight: bold;
        }
        .btn-green:hover {
            background-color: #8fd127;
            color: black;
        }
    </style>
</head>
<body class="d-flex align-items-center justify-content-center vh-100">
    <div class="card text-center" style="max-width: 400px;">
        <h2 class="mb-4">Acceso al Panel</h2>
        <form method="post">
            <input type="password" name="password" class="form-control mb-3" placeholder="Contraseña" required>
            <button type="submit" class="btn btn-green w-100">Ingresar</button>
        </form>
        <p class="mt-3 text-danger">{{ msg }}</p>
    </div>
</body>
</html>
"""

HTML_PANEL = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Control - Estacionamiento</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body {
            background-color: #121212;
            color: white;
            font-family: Arial, sans-serif;
        }
        h2 {
            color: white;
        }
        .counter + p {
            color: white;
        }
        .container {
            padding-top: 2rem;
        }
        .card {
            background-color: #1e1e1e;
            border: none;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }
        .counter {
            font-size: 4rem;
            font-weight: bold;
            color: #76B900;
        }
        .btn-green {
            background-color: #76B900;
            color: black;
            font-weight: bold;
            border: none;
        }
        .btn-green:hover {
            background-color: #8fd127;
        }
        .btn-red {
            background-color: #ff4c4c;
            color: white;
            font-weight: bold;
            border: none;
        }
        .btn-red:hover {
            background-color: #ff6666;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-left: 10px;
        }
        .status-connected {
            background-color: #76B900;
        }
        .status-disconnected {
            background-color: #ff4c4c;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card text-center mb-4">
            <h2 class="mb-3">
                Panel de Control - Estacionamiento
                <span id="status-indicator" class="status-indicator status-disconnected"></span>
            </h2>
            <p id="total" class="counter">{{ total }}</p>
            <p>Número actual de autos</p>
            <small id="last-update" class="text-muted">Última actualización: {{ last_update }}</small>
        </div>
        <div class="card text-center">
            <form id="control-form" class="mb-3">
                <div class="d-flex flex-wrap gap-2 justify-content-center">
                    <button type="button" onclick="sendAction('Entry')" class="btn btn-green btn-lg">+1 (Entry)</button>
                    <button type="button" onclick="sendAction('Exit')" class="btn btn-green btn-lg">-1 (Exit)</button>
                    <button type="button" onclick="sendAction('Reset')" class="btn btn-red btn-lg">Reset</button>
                    <button type="button" onclick="sendAction('SetFull')" class="btn btn-red btn-lg">Set Full</button>
                </div>
            </form>
            <form method="post" action="{{ url_for('logout') }}">
                <button type="submit" class="btn btn-secondary">Cerrar sesión</button>
            </form>
            <p id="message" class="mt-3 text-success">{{ msg }}</p>
        </div>
    </div>

    <script>
        const socket = io();
        
        socket.on('connect', function() {
            console.log('WebSocket conectado');
            document.getElementById('status-indicator').className = 'status-indicator status-connected';
        });
        
        socket.on('disconnect', function() {
            console.log('WebSocket desconectado');
            document.getElementById('status-indicator').className = 'status-indicator status-disconnected';
        });
        
        socket.on('total_update', function(data) {
            console.log('Total actualizado:', data.total);
            document.getElementById('total').innerText = data.total;
            document.getElementById('last-update').innerText = 'Última actualización: ' + new Date().toLocaleTimeString();
        });
        
        socket.on('action_response', function(data) {
            document.getElementById('message').innerText = data.message;
            setTimeout(() => {
                document.getElementById('message').innerText = '';
            }, 3000);
        });
        
        function sendAction(action) {
            socket.emit('send_action', {action: action});
            document.getElementById('message').innerText = 'Enviando acción: ' + action;
        }
    </script>
</body>
</html>
"""

# Clase para manejar MQTT con reconexión automática
class MQTTManager:
    def __init__(self, broker, port, total_topic, command_topic):
        self.broker = broker
        self.port = port
        self.total_topic = total_topic
        self.command_topic = command_topic
        self.client = None
        self.is_connected = False
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            self.reconnect_delay = 5  # Reset delay on successful connection
            logger.info("MQTT conectado exitosamente")
            client.subscribe(self.total_topic)
            logger.info(f"Suscrito al tópico: {self.total_topic}")
        else:
            self.is_connected = False
            logger.error(f"Error de conexión MQTT: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        logger.warning("MQTT desconectado")
        if rc != 0:
            logger.info("Desconexión inesperada, intentando reconectar...")
            self.schedule_reconnect()
    
    def on_message(self, client, userdata, msg):
        global current_total
        try:
            new_total = msg.payload.decode().strip()
            if new_total != current_total:
                current_total = new_total
                logger.info(f"Total actualizado: {current_total}")
                # Enviar actualización via WebSocket
                socketio.emit('total_update', {'total': current_total})
        except Exception as e:
            logger.error(f"Error procesando mensaje MQTT: {e}")
    
    def schedule_reconnect(self):
        def reconnect():
            time.sleep(self.reconnect_delay)
            if not self.is_connected:
                logger.info(f"Intentando reconectar MQTT en {self.reconnect_delay} segundos...")
                self.connect()
                # Incrementar delay para próximo intento (backoff exponencial)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        
        threading.Thread(target=reconnect, daemon=True).start()
    
    def connect(self):
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            
            # Configurar keep alive y timeouts
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Error conectando MQTT: {e}")
            self.schedule_reconnect()
    
    def publish_action(self, action):
        if self.is_connected and self.client:
            try:
                result = self.client.publish(self.command_topic, action)
                if result.rc == 0:
                    logger.info(f"Acción enviada: {action}")
                    return True
                else:
                    logger.error(f"Error enviando acción: {result.rc}")
                    return False
            except Exception as e:
                logger.error(f"Error publicando acción: {e}")
                return False
        else:
            logger.warning("MQTT no conectado, no se puede enviar acción")
            return False

# Inicializar MQTT Manager
mqtt_manager = MQTTManager(MQTT_BROKER, MQTT_PORT, TOTAL_TOPIC, MQTT_TOPIC)

@app.route("/", methods=["GET", "POST"])
def control():
    if not session.get("authenticated"):
        if request.method == "POST":
            password = request.form.get("password", "")
            if password == PASSWORD:
                session["authenticated"] = True
                return redirect(url_for("control"))
            else:
                return render_template_string(HTML_LOGIN, msg="Contraseña incorrecta.")
        return render_template_string(HTML_LOGIN, msg="")

    msg = session.pop("msg", "")
    return render_template_string(HTML_PANEL, msg=msg, total=current_total, 
                                last_update=time.strftime("%H:%M:%S"))

@app.route("/get_total")
def get_total():
    return jsonify({"total": current_total, "connected": mqtt_manager.is_connected})

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("control"))

# WebSocket events
@socketio.on('connect')
def handle_connect():
    logger.info('Cliente WebSocket conectado')
    emit('total_update', {'total': current_total})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Cliente WebSocket desconectado')

@socketio.on('send_action')
def handle_action(data):
    action = data.get('action', '')
    if action in ["Entry", "Exit", "Reset", "SetFull"]:
        success = mqtt_manager.publish_action(action)
        if success:
            message = f"Acción enviada: {action}"
        else:
            message = f"Error enviando acción: {action} (MQTT desconectado)"
    else:
        message = "Acción no válida"
    
    emit('action_response', {'message': message})

def init_mqtt():
    """Inicializar conexión MQTT"""
    logger.info("Inicializando conexión MQTT...")
    mqtt_manager.connect()

if __name__ == "__main__":
    # Inicializar MQTT en un hilo separado
    threading.Thread(target=init_mqtt, daemon=True).start()
    
    # Iniciar la aplicación
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)