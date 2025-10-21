#!/usr/bin/env python3
"""
Telegram Parking Bot Service
Monitors MQTT topic for parking space count and responds to Telegram user queries
Supports scheduled notifications for parking availability
"""

import requests
import time
import logging
import os
import json
import subprocess
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish_mqtt
from datetime import datetime
import pytz
import threading
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
POLLING_INTERVAL = 2  # seconds between polling
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOTAL_TOPIC = "estacionamiento/total"
COMMAND_TOPIC = "deepstream/car_count"
MAX_PARKING_SPACES = 35  # Total capacity
LOGS_SCRIPT_PATH = "/host/get_docker_logs.sh"

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable must be set")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
current_total = 0
last_update_time = None
mqtt_connected = False
scheduler = None
schedules_file = "/app/data/schedules.json"

# Day mapping for Spanish
DAY_MAPPING = {
    'lunes': 'mon', 'monday': 'mon',
    'martes': 'tue', 'tuesday': 'tue',
    'miercoles': 'wed', 'miércoles': 'wed', 'wednesday': 'wed',
    'jueves': 'thu', 'thursday': 'thu',
    'viernes': 'fri', 'friday': 'fri',
    'sabado': 'sat', 'sábado': 'sat', 'saturday': 'sat',
    'domingo': 'sun', 'sunday': 'sun',
    'diario': '*', 'daily': '*', 'todos': '*'
}

DAY_NAMES_ES = {
    'mon': 'Lunes',
    'tue': 'Martes', 
    'wed': 'Miércoles',
    'thu': 'Jueves',
    'fri': 'Viernes',
    'sat': 'Sábado',
    'sun': 'Domingo',
    '*': 'Diario'
}


def get_mexico_city_time():
    """Get current time in Mexico City timezone"""
    mexico_tz = pytz.timezone('America/Mexico_City')
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    mexico_time = utc_now.astimezone(mexico_tz)
    return mexico_time.strftime("%d/%m/%Y %H:%M:%S")


def load_schedules():
    """Load schedules from JSON file"""
    try:
        if os.path.exists(schedules_file):
            with open(schedules_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading schedules: {e}")
        return {}


def save_schedules(schedules):
    """Save schedules to JSON file"""
    try:
        os.makedirs(os.path.dirname(schedules_file), exist_ok=True)
        with open(schedules_file, 'w') as f:
            json.dump(schedules, f, indent=2)
        logger.info("Schedules saved successfully")
    except Exception as e:
        logger.error(f"Error saving schedules: {e}")


def add_schedule(chat_id, day, hour, minute):
    """Add a new schedule for a user"""
    schedules = load_schedules()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in schedules:
        schedules[chat_id_str] = []
    
    schedule_entry = {
        'day': day,
        'hour': hour,
        'minute': minute,
        'created_at': get_mexico_city_time()
    }
    
    schedules[chat_id_str].append(schedule_entry)
    save_schedules(schedules)
    
    # Add job to scheduler
    add_scheduler_job(chat_id, day, hour, minute, len(schedules[chat_id_str]) - 1)
    
    return True


def remove_schedule(chat_id, schedule_index):
    """Remove a schedule for a user"""
    schedules = load_schedules()
    chat_id_str = str(chat_id)
    
    if chat_id_str in schedules and 0 <= schedule_index < len(schedules[chat_id_str]):
        removed = schedules[chat_id_str].pop(schedule_index)
        
        # Clean up if no schedules left
        if not schedules[chat_id_str]:
            del schedules[chat_id_str]
        
        save_schedules(schedules)
        
        # Remove job from scheduler
        job_id = f"schedule_{chat_id}_{schedule_index}"
        try:
            scheduler.remove_job(job_id)
        except:
            pass  # Job might not exist
        
        return True
    
    return False


def get_user_schedules(chat_id):
    """Get all schedules for a user"""
    schedules = load_schedules()
    return schedules.get(str(chat_id), [])


def send_scheduled_notification(chat_id):
    """Send scheduled parking update to user"""
    try:
        parking_data = get_parking_data()
        message = f"🔔 <b>Actualización Programada</b>\n\n{parking_data}"
        send_message(chat_id, message)
        logger.info(f"Sent scheduled notification to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error sending scheduled notification: {e}")


def add_scheduler_job(chat_id, day, hour, minute, index):
    """Add a job to the scheduler"""
    job_id = f"schedule_{chat_id}_{index}"
    
    try:
        # Create cron trigger
        trigger = CronTrigger(
            day_of_week=day,
            hour=hour,
            minute=minute,
            timezone='America/Mexico_City'
        )
        
        scheduler.add_job(
            send_scheduled_notification,
            trigger=trigger,
            args=[chat_id],
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"Added scheduler job: {job_id} for day={day}, hour={hour}, minute={minute}")
    except Exception as e:
        logger.error(f"Error adding scheduler job: {e}")


def init_scheduler():
    """Initialize the scheduler and load all existing schedules"""
    global scheduler
    
    scheduler = BackgroundScheduler(timezone='America/Mexico_City')
    
    # Load existing schedules
    schedules = load_schedules()
    for chat_id_str, user_schedules in schedules.items():
        chat_id = int(chat_id_str)
        for index, schedule in enumerate(user_schedules):
            add_scheduler_job(
                chat_id,
                schedule['day'],
                schedule['hour'],
                schedule['minute'],
                index
            )
    
    scheduler.start()
    logger.info("Scheduler initialized and started")


class MQTTListener:
    """Handle MQTT connection and listen for parking updates"""
    
    def __init__(self, broker, port, topic):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = None
        self.is_connected = False
        
    def on_connect(self, client, userdata, flags, rc):
        global mqtt_connected
        if rc == 0:
            self.is_connected = True
            mqtt_connected = True
            logger.info("MQTT connected successfully")
            client.subscribe(self.topic)
            logger.info(f"Subscribed to topic: {self.topic}")
        else:
            self.is_connected = False
            mqtt_connected = False
            logger.error(f"MQTT connection error: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        global mqtt_connected
        self.is_connected = False
        mqtt_connected = False
        logger.warning("MQTT disconnected")
        if rc != 0:
            logger.info("Unexpected disconnection, will attempt to reconnect...")
    
    def on_message(self, client, userdata, msg):
        global current_total, last_update_time
        try:
            new_total = int(msg.payload.decode().strip())
            if new_total != current_total:
                logger.info(f"Parking count updated: {current_total} -> {new_total}")
                current_total = new_total
                last_update_time = get_mexico_city_time()
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            
            logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT: {e}")
            raise


def get_parking_data():
    """
    Get current parking data from MQTT state
    
    Returns:
        str: Formatted parking data message
    """
    global current_total, last_update_time
    
    available = MAX_PARKING_SPACES - current_total
    occupied = current_total
    
    # Determine status and emoji
    if available == 0:
        status_emoji = "🔴"
        status_text = "FULL"
    elif available <= 5:
        status_emoji = "🟡"
        status_text = "ALMOST FULL"
    else:
        status_emoji = "🟢"
        status_text = "AVAILABLE"
    
    # Format the message
    message = f"🅿️ <b>Parking Status - {status_text}</b> {status_emoji}\n\n"
    message += f"📊 <b>Occupied:</b> {occupied}/{MAX_PARKING_SPACES} spaces\n"
    message += f"✅ <b>Available:</b> {available}/{MAX_PARKING_SPACES} spaces\n"
    
    if last_update_time:
        message += f"\n🕐 <b>Last updated:</b> {last_update_time}"
    else:
        message += f"\n🕐 <b>Last updated:</b> No data yet"
    
    mqtt_status = "🟢 Connected" if mqtt_connected else "🔴 Disconnected"
    message += f"\n📡 <b>System status:</b> {mqtt_status}"
    
    return message


def send_message(chat_id, text):
    """
    Send a message using Telegram Bot API
    
    Args:
        chat_id (str/int): The chat ID to send the message to
        text (str): The message text to send
    
    Returns:
        dict: Response from Telegram API
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message: {e}")
        return None


def publish_mqtt_command(command):
    """
    Publish a command to the MQTT broker
    
    Args:
        command (str): Command to publish (e.g., "SetValue:25")
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        publish_mqtt.single(
            COMMAND_TOPIC,
            command,
            hostname=MQTT_BROKER,
            port=MQTT_PORT
        )
        logger.info(f"Published MQTT command: {command}")
        return True
    except Exception as e:
        logger.error(f"Error publishing MQTT command: {e}")
        return False


def get_container_logs(container_name, num_lines):
    """
    Get logs from a Docker container using the host script
    
    Args:
        container_name (str): Name of the container
        num_lines (int): Number of lines to retrieve
    
    Returns:
        tuple: (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            [LOGS_SCRIPT_PATH, container_name, str(num_lines)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stdout or result.stderr
            
    except subprocess.TimeoutExpired:
        return False, "Error: Command timed out"
    except Exception as e:
        logger.error(f"Error getting container logs: {e}")
        return False, f"Error: {str(e)}"


def get_updates(offset=None):
    """
    Get new messages from Telegram
    
    Args:
        offset (int): Update ID to start from
    
    Returns:
        dict: Response from Telegram API
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {
        "timeout": 30,
        "offset": offset
    }
    
    try:
        response = requests.get(url, params=params, timeout=35)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting updates: {e}")
        return None


def handle_message(message):
    """
    Process incoming messages and respond accordingly
    
    Args:
        message (dict): Message object from Telegram
    """
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user_name = message["from"].get("first_name", "User")
    
    logger.info(f"Received message from {user_name} (chat_id: {chat_id}): {text}")
    
    # Handle different commands
    if text.lower() == "/start":
        response = f"👋 ¡Hola {user_name}! Bienvenido al Bot de Estacionamiento.\n\n"
        response += "Usa los siguientes comandos:\n"
        response += "/parking - Ver estado actual del estacionamiento\n"
        response += "/status - Ver estado del sistema\n"
        response += "/set - Modificar el contador del estacionamiento\n"
        response += "/logs - Ver logs de contenedores Docker\n"
        response += "/schedule - Configurar notificaciones programadas\n"
        response += "/listschedules - Ver tus notificaciones programadas\n"
        response += "/help - Mostrar este mensaje de ayuda"
        send_message(chat_id, response)
    
    elif text.lower() == "/help":
        response = "🅿️ <b>Ayuda del Bot de Estacionamiento</b>\n\n"
        response += "<b>/parking</b> - Obtener disponibilidad actual\n"
        response += "<b>/status</b> - Ver estado del sistema\n"
        response += "<b>/set &lt;número&gt;</b> - Establecer contador (0-35)\n"
        response += "  Ejemplo: /set 25\n"
        response += "<b>/logs &lt;contenedor&gt; &lt;líneas&gt;</b> - Ver logs\n"
        response += "  Ejemplo: /logs telegram-bot 50\n"
        response += "  Contenedores: mosquitto-broker, pi3-subscriber, webpanel, telegram-bot\n"
        response += "<b>/schedule</b> - Configurar notificaciones programadas\n"
        response += "  Ejemplo: /schedule lunes 15:30\n"
        response += "  Ejemplo: /schedule diario 9:00\n"
        response += "<b>/listschedules</b> - Ver tus notificaciones\n"
        response += "<b>/removeschedule</b> - Eliminar notificación\n"
        response += "  Ejemplo: /removeschedule 1\n"
        response += "<b>/start</b> - Mostrar mensaje de bienvenida\n\n"
        response += "📅 <b>Días válidos:</b> lunes, martes, miércoles, jueves, viernes, sábado, domingo, diario\n"
        response += "🕐 <b>Formato de hora:</b> HH:MM (horario CDMX)"
        send_message(chat_id, response)
    
    elif text.lower() in ["/parking", "parking", "/status", "status"]:
        # Fetch and send parking data
        parking_data = get_parking_data()
        send_message(chat_id, parking_data)
    
    elif text.lower().startswith("/schedule"):
        handle_schedule_command(chat_id, text, user_name)
    
    elif text.lower().startswith("/listschedules"):
        handle_list_schedules_command(chat_id)
    
    elif text.lower().startswith("/removeschedule"):
        handle_remove_schedule_command(chat_id, text)
    
    elif text.lower().startswith("/set"):
        handle_set_command(chat_id, text, user_name)
    
    elif text.lower().startswith("/logs"):
        handle_logs_command(chat_id, text, user_name)
    
    else:
        response = "❓ Comando desconocido. Usa /help para ver los comandos disponibles."
        send_message(chat_id, response)


def handle_schedule_command(chat_id, text, user_name):
    """Handle /schedule command"""
    try:
        parts = text.split()
        
        if len(parts) < 3:
            response = "❌ <b>Formato incorrecto</b>\n\n"
            response += "Uso: /schedule &lt;día&gt; &lt;hora&gt;\n\n"
            response += "<b>Ejemplos:</b>\n"
            response += "• /schedule lunes 15:30\n"
            response += "• /schedule miércoles 9:00\n"
            response += "• /schedule diario 18:00\n\n"
            response += "<b>Días válidos:</b>\n"
            response += "lunes, martes, miércoles, jueves, viernes, sábado, domingo, diario"
            send_message(chat_id, response)
            return
        
        day_input = parts[1].lower()
        time_input = parts[2]
        
        # Map day to cron format
        if day_input not in DAY_MAPPING:
            response = "❌ Día no válido. Usa: lunes, martes, miércoles, jueves, viernes, sábado, domingo, o diario"
            send_message(chat_id, response)
            return
        
        day_cron = DAY_MAPPING[day_input]
        
        # Parse time
        try:
            time_parts = time_input.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError("Invalid time range")
        except:
            response = "❌ Hora no válida. Usa formato HH:MM (ejemplo: 15:30)"
            send_message(chat_id, response)
            return
        
        # Add schedule
        if add_schedule(chat_id, day_cron, hour, minute):
            day_name = DAY_NAMES_ES.get(day_cron, day_input.capitalize())
            response = f"✅ <b>Notificación programada</b>\n\n"
            response += f"📅 Día: {day_name}\n"
            response += f"🕐 Hora: {hour:02d}:{minute:02d} (CDMX)\n\n"
            response += f"Recibirás la disponibilidad del estacionamiento cada {day_name.lower()} a las {hour:02d}:{minute:02d}.\n\n"
            response += "Usa /listschedules para ver todas tus notificaciones."
            send_message(chat_id, response)
        else:
            response = "❌ Error al crear la notificación. Intenta de nuevo."
            send_message(chat_id, response)
            
    except Exception as e:
        logger.error(f"Error in handle_schedule_command: {e}")
        response = "❌ Error al procesar el comando. Usa /help para ver el formato correcto."
        send_message(chat_id, response)


def handle_list_schedules_command(chat_id):
    """Handle /listschedules command"""
    try:
        schedules = get_user_schedules(chat_id)
        
        if not schedules:
            response = "📋 No tienes notificaciones programadas.\n\n"
            response += "Usa /schedule para crear una.\n"
            response += "Ejemplo: /schedule lunes 15:30"
            send_message(chat_id, response)
            return
        
        response = "📋 <b>Tus Notificaciones Programadas</b>\n\n"
        
        for index, schedule in enumerate(schedules):
            day_name = DAY_NAMES_ES.get(schedule['day'], schedule['day'])
            hour = schedule['hour']
            minute = schedule['minute']
            
            response += f"{index + 1}. {day_name} - {hour:02d}:{minute:02d}\n"
        
        response += f"\n<b>Total:</b> {len(schedules)} notificación(es)\n"
        response += "\nPara eliminar una notificación usa:\n"
        response += "/removeschedule &lt;número&gt;"
        
        send_message(chat_id, response)
        
    except Exception as e:
        logger.error(f"Error in handle_list_schedules_command: {e}")
        response = "❌ Error al obtener tus notificaciones."
        send_message(chat_id, response)


def handle_remove_schedule_command(chat_id, text):
    """Handle /removeschedule command"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            response = "❌ <b>Formato incorrecto</b>\n\n"
            response += "Uso: /removeschedule &lt;número&gt;\n\n"
            response += "Usa /listschedules para ver tus notificaciones y sus números."
            send_message(chat_id, response)
            return
        
        try:
            schedule_num = int(parts[1])
            schedule_index = schedule_num - 1  # Convert to 0-based index
        except:
            response = "❌ Número no válido. Usa /listschedules para ver los números."
            send_message(chat_id, response)
            return
        
        if remove_schedule(chat_id, schedule_index):
            response = "✅ Notificación eliminada exitosamente.\n\n"
            response += "Usa /listschedules para ver tus notificaciones restantes."
            send_message(chat_id, response)
        else:
            response = "❌ No se encontró la notificación. Verifica el número con /listschedules"
            send_message(chat_id, response)
            
    except Exception as e:
        logger.error(f"Error in handle_remove_schedule_command: {e}")
        response = "❌ Error al eliminar la notificación."
        send_message(chat_id, response)


def handle_set_command(chat_id, text, user_name):
    """Handle /set command to change parking counter"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            response = "❌ <b>Formato incorrecto</b>\n\n"
            response += "Uso: /set &lt;número&gt;\n\n"
            response += "<b>Ejemplos:</b>\n"
            response += "• /set 0 - Establecer contador a 0\n"
            response += "• /set 25 - Establecer contador a 25\n"
            response += "• /set 35 - Establecer contador a 35 (full)\n\n"
            response += "⚠️ El valor debe estar entre 0 y 35"
            send_message(chat_id, response)
            return
        
        try:
            new_value = int(parts[1])
            
            if not (0 <= new_value <= MAX_PARKING_SPACES):
                response = f"❌ Valor fuera de rango. Debe estar entre 0 y {MAX_PARKING_SPACES}"
                send_message(chat_id, response)
                return
            
            # Publish MQTT command
            command = f"SetValue:{new_value}"
            if publish_mqtt_command(command):
                response = f"✅ <b>Contador actualizado</b>\n\n"
                response += f"📊 Nuevo valor: {new_value}/{MAX_PARKING_SPACES}\n"
                response += f"👤 Modificado por: {user_name}\n"
                response += f"🕐 {get_mexico_city_time()}\n\n"
                response += "⚠️ Este cambio ha sido registrado en Azure IoT Hub"
                send_message(chat_id, response)
                logger.info(f"Counter set to {new_value} by {user_name} (chat_id: {chat_id})")
            else:
                response = "❌ Error al publicar el comando MQTT. Intenta de nuevo."
                send_message(chat_id, response)
                
        except ValueError:
            response = "❌ Valor no válido. Debe ser un número entero entre 0 y 35"
            send_message(chat_id, response)
            
    except Exception as e:
        logger.error(f"Error in handle_set_command: {e}")
        response = "❌ Error al procesar el comando."
        send_message(chat_id, response)


def handle_logs_command(chat_id, text, user_name):
    """Handle /logs command to fetch Docker container logs"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            response = "❌ <b>Formato incorrecto</b>\n\n"
            response += "Uso: /logs &lt;contenedor&gt; [líneas]\n\n"
            response += "<b>Contenedores disponibles:</b>\n"
            response += "• mosquitto-broker\n"
            response += "• pi3-subscriber\n"
            response += "• webpanel\n"
            response += "• telegram-bot\n\n"
            response += "<b>Ejemplos:</b>\n"
            response += "• /logs telegram-bot 25 (últimas 25 líneas)\n"
            response += "• /logs pi3-subscriber 50\n"
            response += "• /logs webpanel (últimas 25 líneas por defecto)"
            send_message(chat_id, response)
            return
        
        container_name = parts[1]
        num_lines = int(parts[2]) if len(parts) > 2 else 25
        
        # Validate number of lines
        if not (1 <= num_lines <= 200):
            response = "❌ Número de líneas debe estar entre 1 y 200"
            send_message(chat_id, response)
            return
        
        # Valid containers
        valid_containers = ["mosquitto-broker", "pi3-subscriber", "webpanel", "telegram-bot"]
        if container_name not in valid_containers:
            response = f"❌ Contenedor no válido: {container_name}\n\n"
            response += "Contenedores válidos:\n"
            response += "\n".join(f"• {c}" for c in valid_containers)
            send_message(chat_id, response)
            return
        
        # Send "processing" message
        send_message(chat_id, f"⏳ Obteniendo últimas {num_lines} líneas de <b>{container_name}</b>...")
        
        # Get logs
        success, output = get_container_logs(container_name, num_lines)
        
        if success:
            # Split output into chunks if too long (Telegram has a 4096 character limit)
            max_length = 4000
            if len(output) <= max_length:
                response = f"📋 <b>Logs de {container_name}</b>\n\n"
                response += f"<pre>{output}</pre>"
                send_message(chat_id, response)
            else:
                # Split into multiple messages
                chunks = [output[i:i+max_length] for i in range(0, len(output), max_length)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        response = f"📋 <b>Logs de {container_name}</b> (parte {i+1}/{len(chunks)})\n\n"
                    else:
                        response = f"📋 <b>Parte {i+1}/{len(chunks)}</b>\n\n"
                    response += f"<pre>{chunk}</pre>"
                    send_message(chat_id, response)
                    time.sleep(0.5)  # Small delay between messages
            
            logger.info(f"Logs fetched for {container_name} by {user_name} (chat_id: {chat_id})")
        else:
            response = f"❌ Error al obtener logs:\n\n<pre>{output}</pre>"
            send_message(chat_id, response)
            
    except ValueError:
        response = "❌ Número de líneas no válido. Debe ser un entero entre 1 y 200"
        send_message(chat_id, response)
    except Exception as e:
        logger.error(f"Error in handle_logs_command: {e}")
        response = "❌ Error al procesar el comando."
        send_message(chat_id, response)


def run_bot():
    """
    Main bot loop - continuously poll for new messages
    """
    logger.info("🤖 Telegram Parking Bot started!")
    logger.info(f"Polling for messages every {POLLING_INTERVAL} seconds...")
    
    offset = None
    
    while True:
        try:
            # Get new updates
            result = get_updates(offset)
            
            if result and result.get("ok"):
                updates = result.get("result", [])
                
                for update in updates:
                    # Update offset to mark message as processed
                    offset = update["update_id"] + 1
                    
                    # Process message if it exists
                    if "message" in update:
                        handle_message(update["message"])
            
            # Small delay between polls
            time.sleep(POLLING_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("\n🛑 Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in bot loop: {e}")
            time.sleep(5)  # Wait before retrying


def main():
    """Initialize MQTT listener and start bot"""
    try:
        # Initialize scheduler
        logger.info("Initializing scheduler...")
        init_scheduler()
        
        # Initialize MQTT listener
        mqtt_listener = MQTTListener(MQTT_BROKER, MQTT_PORT, TOTAL_TOPIC)
        
        # Start MQTT connection in a separate thread
        logger.info("Starting MQTT listener...")
        mqtt_listener.connect()
        
        # Wait a moment for MQTT to connect
        time.sleep(2)
        
        # Start Telegram bot
        run_bot()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
