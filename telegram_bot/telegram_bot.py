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
from datetime import datetime, timedelta
import pytz
import threading
import hashlib
import secrets
import re
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
LED_STATE_TOPIC = "estacionamiento/leds_state"
COMMAND_TOPIC = "deepstream/car_count"
MAX_PARKING_SPACES = 35  # Total capacity
LOGS_SCRIPT_PATH = "/host/get_docker_logs.sh"

# Authentication Configuration
INITIAL_ADMIN_PHONE = "5611930911"  # First admin phone number
ADMIN_REGISTRATION_CODE = os.environ.get("ADMIN_REG_CODE", "ADMIN2024PARK")
USER_REGISTRATION_CODE = os.environ.get("USER_REG_CODE", "USER2024PARK")
REPORT_COOLDOWN_MINUTES = 5  # Cooldown for reporting wrong count
VERIFICATION_CODE_TIMEOUT = 300  # 5 minutes timeout for verification codes
REGISTRATION_TIMEOUT = 600  # 10 minutes timeout for pending registrations

# Data files
schedules_file = "/app/data/schedules.json"
users_file = "/app/data/users.json"

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
leds_state = "ON"  # Default to ON
last_update_time = None
mqtt_connected = False
scheduler = None
schedules_file = "/app/data/schedules.json"

# Authentication state
pending_verifications = {}  # {chat_id: {code, phone, role, expires_at}}
pending_registrations = {}  # {chat_id: {phone, role, awaiting_code}}

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


# ==================== USER AUTHENTICATION FUNCTIONS ====================

def hash_phone(phone):
    """Hash phone number using SHA256"""
    return hashlib.sha256(phone.encode()).hexdigest()


def validate_mexican_phone(phone):
    """
    Validate Mexican phone number format
    Accepts 10 digits OR 12 digits with +52 country code
    
    Args:
        phone (str): Phone number to validate
        
    Returns:
        tuple: (is_valid: bool, cleaned_phone: str - always 10 digits)
    """
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', phone)
    
    # If 12 digits and starts with 52, remove the country code
    if len(cleaned) == 12 and cleaned.startswith('52'):
        cleaned = cleaned[2:]  # Remove the '52' prefix
    
    # Must be exactly 10 digits after processing
    if len(cleaned) == 10 and cleaned.isdigit():
        return True, cleaned
    
    return False, ""


def load_users():
    """Load users from JSON file"""
    try:
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return {}


def save_users(users):
    """Save users to JSON file"""
    try:
        os.makedirs(os.path.dirname(users_file), exist_ok=True)
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=2)
        logger.info("Users saved successfully")
    except Exception as e:
        logger.error(f"Error saving users: {e}")


def get_user_by_chat_id(chat_id):
    """
    Get user by chat_id
    
    Returns:
        dict or None: User data if found
    """
    users = load_users()
    chat_id_str = str(chat_id)
    
    for phone_hash, user_data in users.items():
        if user_data.get('chat_id') == chat_id_str:
            return user_data
    
    return None


def get_user_by_phone(phone):
    """
    Get user by phone number (checks hashed version)
    
    Returns:
        tuple: (user_data: dict or None, phone_hash: str)
    """
    users = load_users()
    phone_hash = hash_phone(phone)
    
    if phone_hash in users:
        return users[phone_hash], phone_hash
    
    return None, phone_hash


def is_authenticated(chat_id):
    """Check if user is authenticated"""
    return get_user_by_chat_id(chat_id) is not None


def cleanup_expired_registrations():
    """
    Remove expired pending registrations and verifications
    Should be called before processing registration attempts
    """
    current_time = datetime.now()
    
    # Clean up expired pending registrations
    expired_registrations = []
    for chat_id, data in pending_registrations.items():
        started_at = data.get('started_at')
        if started_at and (current_time - started_at).total_seconds() > REGISTRATION_TIMEOUT:
            expired_registrations.append(chat_id)
    
    for chat_id in expired_registrations:
        del pending_registrations[chat_id]
        logger.info(f"Cleaned up expired registration for chat_id={chat_id}")
    
    # Clean up expired pending verifications
    expired_verifications = []
    for chat_id, data in pending_verifications.items():
        expires_at = data.get('expires_at')
        if expires_at and current_time > expires_at:
            expired_verifications.append(chat_id)
    
    for chat_id in expired_verifications:
        del pending_verifications[chat_id]
        logger.info(f"Cleaned up expired verification for chat_id={chat_id}")


def is_admin(chat_id):
    """Check if user is an admin"""
    user = get_user_by_chat_id(chat_id)
    return user is not None and user.get('role') == 'admin'


def register_user(chat_id, phone, role='user'):
    """
    Register a new user
    
    Args:
        chat_id: Telegram chat ID
        phone: Phone number (will be hashed)
        role: 'admin' or 'user'
        
    Returns:
        tuple: (success: bool, message: str)
    """
    users = load_users()
    phone_hash = hash_phone(phone)
    chat_id_str = str(chat_id)
    
    # Check if phone already exists
    if phone_hash in users:
        existing_user = users[phone_hash]
        existing_chat_id = existing_user.get('chat_id')
        
        # Check if this is pending activation (initial admin with no chat_id)
        if existing_chat_id is None and existing_user.get('pending_activation', False):
            # Activate the pending account
            users[phone_hash]['chat_id'] = chat_id_str
            users[phone_hash]['activated_at'] = get_mexico_city_time()
            users[phone_hash]['pending_activation'] = False
            save_users(users)
            logger.info(f"Pending {existing_user['role']} activated: phone_hash={phone_hash[:8]}..., chat_id={chat_id}")
            return True, "Cuenta activada exitosamente"
        
        # Same user, same chat_id - already registered
        if existing_chat_id == chat_id_str:
            return False, "Ya estás registrado"
        
        # Different chat_id - potential duplicate/account takeover
        return False, "DUPLICATE_PHONE"
    
    # Check if chat_id is already associated with another phone
    for _, user_data in users.items():
        if user_data.get('chat_id') == chat_id_str:
            return False, "Este chat ya está asociado con otro número de teléfono"
    
    # Create new user
    users[phone_hash] = {
        'chat_id': chat_id_str,
        'phone': phone,  # Store plain for reference (you can remove if paranoid)
        'role': role,
        'registered_at': get_mexico_city_time(),
        'notifications_enabled': True if role == 'admin' else False,
        'last_report_time': None
    }
    
    save_users(users)
    logger.info(f"New {role} registered: phone_hash={phone_hash[:8]}..., chat_id={chat_id}")
    
    return True, "Registro exitoso"


def update_user_notifications(chat_id, enabled):
    """Update admin notification preferences"""
    users = load_users()
    chat_id_str = str(chat_id)
    
    for phone_hash, user_data in users.items():
        if user_data.get('chat_id') == chat_id_str:
            users[phone_hash]['notifications_enabled'] = enabled
            save_users(users)
            return True
    
    return False


def can_report(chat_id):
    """
    Check if user can report (5 minute cooldown)
    
    Returns:
        tuple: (can_report: bool, minutes_remaining: int)
    """
    users = load_users()
    chat_id_str = str(chat_id)
    
    for phone_hash, user_data in users.items():
        if user_data.get('chat_id') == chat_id_str:
            last_report = user_data.get('last_report_time')
            
            if not last_report:
                return True, 0
            
            # Parse last report time
            try:
                mexico_tz = pytz.timezone('America/Mexico_City')
                last_time = datetime.strptime(last_report, "%d/%m/%Y %H:%M:%S")
                last_time = mexico_tz.localize(last_time)
                
                now = datetime.now(mexico_tz)
                time_diff = now - last_time
                minutes_passed = time_diff.total_seconds() / 60
                
                if minutes_passed >= REPORT_COOLDOWN_MINUTES:
                    return True, 0
                else:
                    minutes_remaining = int(REPORT_COOLDOWN_MINUTES - minutes_passed) + 1
                    return False, minutes_remaining
                    
            except Exception as e:
                logger.error(f"Error parsing report time: {e}")
                return True, 0
    
    return False, 0


def update_last_report_time(chat_id):
    """Update the last report time for a user"""
    users = load_users()
    chat_id_str = str(chat_id)
    
    for phone_hash, user_data in users.items():
        if user_data.get('chat_id') == chat_id_str:
            users[phone_hash]['last_report_time'] = get_mexico_city_time()
            save_users(users)
            return True
    
    return False


def get_admins_with_notifications():
    """Get list of admin chat_ids with notifications enabled"""
    users = load_users()
    admins = []
    
    for phone_hash, user_data in users.items():
        if user_data.get('role') == 'admin' and user_data.get('notifications_enabled', False):
            admins.append(user_data.get('chat_id'))
    
    return admins


def generate_verification_code():
    """Generate a 6-digit verification code"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])


def initialize_first_admin():
    """Initialize the first admin if no users exist"""
    users = load_users()
    
    if not users:
        logger.info("No users found, creating initial admin...")
        phone_hash = hash_phone(INITIAL_ADMIN_PHONE)
        
        users[phone_hash] = {
            'chat_id': None,  # Will be set when admin registers
            'phone': INITIAL_ADMIN_PHONE,
            'role': 'admin',
            'registered_at': get_mexico_city_time(),
            'notifications_enabled': True,
            'last_report_time': None,
            'pending_activation': True
        }
        
        save_users(users)
        logger.info(f"Initial admin created with phone: {INITIAL_ADMIN_PHONE}")


# ==================== END USER AUTHENTICATION FUNCTIONS ====================


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
    
    def __init__(self, broker, port, topic, led_topic):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.led_topic = led_topic
        self.client = None
        self.is_connected = False
        
    def on_connect(self, client, userdata, flags, rc):
        global mqtt_connected
        if rc == 0:
            self.is_connected = True
            mqtt_connected = True
            logger.info("MQTT connected successfully")
            client.subscribe(self.topic)
            client.subscribe(self.led_topic)
            logger.info(f"Subscribed to topics: {self.topic}, {self.led_topic}")
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
        global current_total, last_update_time, leds_state
        try:
            topic = msg.topic
            payload = msg.payload.decode().strip()
            
            if topic == self.topic:
                # Total parking count update
                new_total = int(payload)
                if new_total != current_total:
                    logger.info(f"Parking count updated: {current_total} -> {new_total}")
                    current_total = new_total
                    last_update_time = get_mexico_city_time()
            
            elif topic == self.led_topic:
                # LED state update
                new_state = payload.upper()
                if new_state in ["ON", "OFF"] and new_state != leds_state:
                    logger.info(f"LED state updated: {leds_state} -> {new_state}")
                    leds_state = new_state
                    
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
    global current_total, last_update_time, leds_state
    
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
    
    # LED status
    led_emoji = "💡" if leds_state == "ON" else "🌑"
    led_text = "Activo" if leds_state == "ON" else "Desactivado"
    message += f"\n{led_emoji} <b>Semáforo:</b> {led_text}"
    
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


def get_led_state():
    """
    Get the current LED state from the subscriber's state file
    
    Returns:
        tuple: (leds_enabled: bool, success: bool)
    """
    try:
        state_file = "/app/data/parking_state.json"
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                leds_enabled = state.get('leds_enabled', True)
                return leds_enabled, True
        else:
            # File doesn't exist yet, assume default ON
            return True, True
    except Exception as e:
        logger.error(f"Error reading LED state: {e}")
        return True, False  # Default to ON if error


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
    user_name = message["from"].get("first_name", "User")
    
    # Handle contact sharing (phone number registration)
    if "contact" in message:
        handle_contact_registration(message)
        return
    
    text = message.get("text", "").strip()
    logger.info(f"Received message from {user_name} (chat_id: {chat_id}): {text}")
    
    # Check if user is in verification process
    if chat_id in pending_verifications:
        # Allow cancel during verification
        if text.lower() == "/cancel":
            del pending_verifications[chat_id]
            response = "❌ <b>Verificación Cancelada</b>\n\n"
            response += "Proceso de verificación cancelado.\n\n"
            response += "Usa /register para comenzar de nuevo."
            send_message(chat_id, response)
            logger.info(f"Verification cancelled by user: chat_id={chat_id}")
            return
        
        handle_verification_code(chat_id, text)
        return
    
    # Check if user is in registration process (awaiting registration code)
    if chat_id in pending_registrations:
        # Allow cancel during registration
        if text.lower() == "/cancel":
            del pending_registrations[chat_id]
            response = "❌ <b>Registro Cancelado</b>\n\n"
            response += "Proceso de registro cancelado.\n\n"
            response += "Usa /register para comenzar de nuevo."
            send_message(chat_id, response)
            logger.info(f"Registration cancelled by user: chat_id={chat_id}")
            return
        
        handle_registration_code(chat_id, text)
        return
    
    # Public commands (no authentication required)
    if text.lower() == "/start":
        handle_start_command(chat_id, user_name)
        return
    
    if text.lower().startswith("/register"):
        handle_register_command(chat_id, text, user_name)
        return
    
    if text.lower() == "/cancel":
        # Nothing to cancel
        response = "ℹ️ No hay ningún proceso activo que cancelar.\n\n"
        response += "Usa /help para ver los comandos disponibles."
        send_message(chat_id, response)
        return
    
    # Check authentication for all other commands
    if not is_authenticated(chat_id):
        response = "🔒 <b>Acceso no autorizado</b>\n\n"
        response += "Debes registrarte primero para usar este bot.\n\n"
        response += "Usa el comando /register para comenzar el proceso de registro."
        send_message(chat_id, response)
        return
    
    # Authenticated user commands
    if text.lower() == "/help":
        handle_help_command(chat_id)
    
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
    
    elif text.lower().startswith("/report"):
        handle_report_command(chat_id, text, user_name)
    
    # Admin-only commands
    elif text.lower().startswith("/set"):
        if is_admin(chat_id):
            handle_set_command(chat_id, text, user_name)
        else:
            send_message(chat_id, "❌ Este comando solo está disponible para administradores.")
    
    elif text.lower().startswith("/logs"):
        if is_admin(chat_id):
            handle_logs_command(chat_id, text, user_name)
        else:
            send_message(chat_id, "❌ Este comando solo está disponible para administradores.")
    
    elif text.lower().startswith("/leds"):
        if is_admin(chat_id):
            handle_leds_command(chat_id, text, user_name)
        else:
            send_message(chat_id, "❌ Este comando solo está disponible para administradores.")
    
    elif text.lower().startswith("/addadmin"):
        if is_admin(chat_id):
            handle_addadmin_command(chat_id, text, user_name)
        else:
            send_message(chat_id, "❌ Este comando solo está disponible para administradores.")
    
    elif text.lower().startswith("/notifications"):
        if is_admin(chat_id):
            handle_notifications_command(chat_id, text)
        else:
            send_message(chat_id, "❌ Este comando solo está disponible para administradores.")
    
    else:
        response = "❓ Comando desconocido. Usa /help para ver los comandos disponibles."
        send_message(chat_id, response)


def handle_start_command(chat_id, user_name):
    """Handle /start command"""
    response = f"👋 ¡Hola {user_name}! Bienvenido al Bot de Estacionamiento.\n\n"
    
    if is_authenticated(chat_id):
        user = get_user_by_chat_id(chat_id)
        role_text = "Administrador" if user.get('role') == 'admin' else "Usuario"
        response += f"🎫 Estado: <b>Autenticado</b> ({role_text})\n\n"
        response += "Usa /help para ver los comandos disponibles."
    else:
        response += "🔒 <b>No estás registrado</b>\n\n"
        response += "Para usar este bot necesitas registrarte primero.\n\n"
        response += "<b>Comandos disponibles:</b>\n"
        response += "/register &lt;código&gt; - Comenzar registro\n"
        response += "/cancel - Cancelar registro en progreso"
    
    send_message(chat_id, response)


def handle_help_command(chat_id):
    """Handle /help command with role-based content"""
    user = get_user_by_chat_id(chat_id)
    
    if user.get('role') == 'admin':
        response = "🅿️ <b>Ayuda del Bot de Estacionamiento (ADMIN)</b>\n\n"
        response += "<b>📊 Comandos de Consulta:</b>\n"
        response += "/parking - Obtener disponibilidad actual\n"
        response += "/status - Ver estado del sistema\n\n"
        response += "<b>🔧 Comandos de Administrador:</b>\n"
        response += "/set &lt;número&gt; - Establecer contador (0-35)\n"
        response += "/leds &lt;on|off&gt; - Controlar semáforo\n"
        response += "/logs &lt;contenedor&gt; &lt;líneas&gt; - Ver logs\n"
        response += "/addadmin &lt;teléfono&gt; - Promover usuario a admin\n"
        response += "/notifications &lt;on|off&gt; - Recibir reportes\n\n"
        response += "<b>📅 Notificaciones Programadas:</b>\n"
        response += "/schedule &lt;día&gt; &lt;hora&gt; - Configurar notificación\n"
        response += "/listschedules - Ver notificaciones\n"
        response += "/removeschedule &lt;#&gt; - Eliminar notificación\n\n"
        response += "<b>🚨 Reportes:</b>\n"
        response += "/report &lt;número&gt; - Reportar conteo incorrecto"
    else:
        response = "🅿️ <b>Ayuda del Bot de Estacionamiento</b>\n\n"
        response += "<b>📊 Comandos de Consulta:</b>\n"
        response += "/parking - Obtener disponibilidad actual\n"
        response += "/status - Ver estado del sistema\n\n"
        response += "<b>📅 Notificaciones Programadas:</b>\n"
        response += "/schedule &lt;día&gt; &lt;hora&gt; - Configurar notificación\n"
        response += "  Ejemplo: /schedule lunes 15:30\n"
        response += "/listschedules - Ver tus notificaciones\n"
        response += "/removeschedule &lt;#&gt; - Eliminar notificación\n\n"
        response += "<b>🚨 Reportar Problema:</b>\n"
        response += "/report &lt;número&gt; - Reportar conteo incorrecto\n"
        response += "  Ejemplo: /report 20\n"
        response += "  (Solo cada 5 minutos)\n\n"
        response += "📅 <b>Días válidos:</b> lunes, martes, miércoles, jueves, viernes, sábado, domingo, diario\n"
        response += "🕐 <b>Formato de hora:</b> HH:MM (horario CDMX)"
    
    send_message(chat_id, response)


def handle_register_command(chat_id, text, user_name):
    """Handle /register command"""
    # Clean up any expired registrations first
    cleanup_expired_registrations()
    
    # Check if already fully registered
    if is_authenticated(chat_id):
        response = "✅ Ya estás registrado en el sistema.\n\nUsa /help para ver los comandos disponibles."
        send_message(chat_id, response)
        return
    
    # Check if user is stuck in pending registration
    if chat_id in pending_registrations:
        # Allow restart if they provide a code again
        parts = text.split()
        if len(parts) >= 2:
            # User is providing code again - clean up old pending state
            logger.info(f"User {chat_id} restarting registration (was stuck in pending)")
            del pending_registrations[chat_id]
        else:
            # Just remind them to share phone
            response = "⚠️ <b>Registro Pendiente</b>\n\n"
            response += "Ya iniciaste el proceso de registro.\n\n"
            response += "Por favor comparte tu número de teléfono usando el botón, o usa:\n"
            response += "• /cancel - Para cancelar y empezar de nuevo\n"
            response += "• /register &lt;código&gt; - Para reintentar con el código"
            send_message(chat_id, response)
            return
    
    parts = text.split()
    
    if len(parts) < 2:
        response = "🔐 <b>Registro de Usuario</b>\n\n"
        response += "Para registrarte necesitas un <b>código de registro</b>.\n\n"
        response += "<b>Uso:</b>\n"
        response += "/register &lt;código&gt;\n\n"
        response += "📝 Solicita tu código al administrador del sistema."
        send_message(chat_id, response)
        return
    
    code = parts[1].upper()
    
    # Validate registration code
    role = None
    if code == ADMIN_REGISTRATION_CODE:
        role = 'admin'
    elif code == USER_REGISTRATION_CODE:
        role = 'user'
    else:
        response = "❌ Código de registro inválido.\n\nContacta al administrador para obtener un código válido."
        send_message(chat_id, response)
        return
    
    # Request phone number
    pending_registrations[chat_id] = {
        'role': role,
        'awaiting_phone': True,
        'started_at': datetime.now()
    }
    
    response = f"✅ Código válido ({role.upper()})\n\n"
    response += "📱 <b>Paso 2: Compartir tu número de teléfono</b>\n\n"
    response += "Por favor comparte tu número de teléfono usando el botón de abajo.\n\n"
    response += "⚠️ <b>Importante:</b>\n"
    response += "• Debe ser un número mexicano (10 dígitos)\n"
    response += "• El número quedará asociado a esta cuenta"
    
    # Create keyboard with contact request button
    keyboard = {
        "keyboard": [[{
            "text": "📱 Compartir mi número",
            "request_contact": True
        }]],
        "one_time_keyboard": True,
        "resize_keyboard": True
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": response,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    }
    
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Error sending contact request: {e}")


def handle_contact_registration(message):
    """Handle contact sharing for registration"""
    chat_id = message["chat"]["id"]
    contact = message.get("contact", {})
    phone_number = contact.get("phone_number", "")
    user_name = message["from"].get("first_name", "User")
    
    # Check if user is in registration process
    if chat_id not in pending_registrations:
        response = "❌ No hay un proceso de registro activo.\n\nUsa /register primero."
        send_message(chat_id, response)
        return
    
    registration_data = pending_registrations[chat_id]
    
    # Validate Mexican phone number
    is_valid, cleaned_phone = validate_mexican_phone(phone_number)
    
    if not is_valid:
        response = "❌ <b>Número de teléfono inválido</b>\n\n"
        response += "El número debe ser mexicano (10 dígitos).\n\n"
        response += f"Recibido: {phone_number}\n\n"
        response += "Por favor comparte un número válido o usa /register para reiniciar."
        send_message(chat_id, response)
        return
    
    logger.info(f"Registration attempt: chat_id={chat_id}, phone={cleaned_phone}, role={registration_data['role']}")
    
    # Attempt to register
    success, result_message = register_user(chat_id, cleaned_phone, registration_data['role'])
    
    if success:
        # Registration successful
        del pending_registrations[chat_id]
        
        role_text = "Administrador" if registration_data['role'] == 'admin' else "Usuario"
        response = "✅ <b>¡Registro Exitoso!</b>\n\n"
        response += f"👤 Nombre: {user_name}\n"
        response += f"📱 Teléfono: {cleaned_phone}\n"
        response += f"🎫 Rol: {role_text}\n"
        response += f"🕐 {get_mexico_city_time()}\n\n"
        response += "Ya puedes usar todos los comandos del bot.\n\n"
        response += "Usa /help para ver los comandos disponibles."
        send_message(chat_id, response)
        
        logger.info(f"User registered successfully: {cleaned_phone} as {registration_data['role']}")
        
    elif result_message == "DUPLICATE_PHONE":
        # Phone number already registered to different chat_id
        handle_duplicate_phone(chat_id, cleaned_phone, registration_data['role'])
    else:
        # Other error
        del pending_registrations[chat_id]
        send_message(chat_id, f"❌ {result_message}")


def handle_duplicate_phone(chat_id, phone, role):
    """Handle case where phone number is already registered"""
    user_data, phone_hash = get_user_by_phone(phone)
    existing_chat_id = user_data.get('chat_id')
    
    # Generate verification code
    verification_code = generate_verification_code()
    expires_at = datetime.now() + timedelta(seconds=VERIFICATION_CODE_TIMEOUT)
    
    # Store verification request
    pending_verifications[chat_id] = {
        'code': verification_code,
        'phone': phone,
        'role': role,
        'expires_at': expires_at,
        'original_chat_id': existing_chat_id
    }
    
    # Remove from pending registrations
    if chat_id in pending_registrations:
        del pending_registrations[chat_id]
    
    # Send verification code to original user
    if existing_chat_id:
        try:
            existing_chat_id_int = int(existing_chat_id)
            alert_message = "🚨 <b>Alerta de Seguridad</b>\n\n"
            alert_message += "Alguien está intentando registrarse con tu número de teléfono.\n\n"
            alert_message += f"📱 Teléfono: {phone}\n"
            alert_message += f"🕐 {get_mexico_city_time()}\n\n"
            alert_message += "Si eres tú en un nuevo dispositivo, usa este código:\n\n"
            alert_message += f"<code>{verification_code}</code>\n\n"
            alert_message += "⏱️ Válido por 5 minutos.\n\n"
            alert_message += "❌ Si NO eres tú, ignora este mensaje."
            send_message(existing_chat_id_int, alert_message)
        except Exception as e:
            logger.error(f"Error sending verification code to original user: {e}")
    
    # Inform new user
    response = "⚠️ <b>Número ya registrado</b>\n\n"
    response += "Este número ya está asociado a otra cuenta.\n\n"
    response += "Se ha enviado un <b>código de verificación</b> al dispositivo original.\n\n"
    response += "Si eres tú en un nuevo dispositivo:\n"
    response += "1. Revisa el mensaje en tu dispositivo anterior\n"
    response += "2. Envía el código de 6 dígitos aquí\n\n"
    response += "⏱️ Tienes 5 minutos para verificar.\n\n"
    response += "Usa /register para reiniciar."
    send_message(chat_id, response)
    
    logger.warning(f"Duplicate phone attempt: {phone}, new_chat_id={chat_id}, existing_chat_id={existing_chat_id}")


def handle_verification_code(chat_id, code):
    """Handle verification code input"""
    if chat_id not in pending_verifications:
        return
    
    verification_data = pending_verifications[chat_id]
    
    # Check if expired
    if datetime.now() > verification_data['expires_at']:
        del pending_verifications[chat_id]
        response = "❌ <b>Código expirado</b>\n\n"
        response += "El tiempo de verificación ha expirado.\n\n"
        response += "Usa /register para intentar de nuevo."
        send_message(chat_id, response)
        return
    
    # Verify code
    if code.strip() == verification_data['code']:
        # Code is correct - transfer account
        phone = verification_data['phone']
        role = verification_data['role']
        old_chat_id = verification_data['original_chat_id']
        
        # Update user with new chat_id
        users = load_users()
        phone_hash = hash_phone(phone)
        
        if phone_hash in users:
            users[phone_hash]['chat_id'] = str(chat_id)
            users[phone_hash]['last_verification'] = get_mexico_city_time()
            save_users(users)
            
            del pending_verifications[chat_id]
            
            response = "✅ <b>Verificación Exitosa</b>\n\n"
            response += "Tu cuenta ha sido transferida a este dispositivo.\n\n"
            response += f"📱 Teléfono: {phone}\n"
            response += f"🕐 {get_mexico_city_time()}\n\n"
            response += "Ya puedes usar el bot normalmente.\n\n"
            response += "Usa /help para ver los comandos disponibles."
            send_message(chat_id, response)
            
            # Notify old device
            if old_chat_id:
                try:
                    old_chat_id_int = int(old_chat_id)
                    old_device_msg = "⚠️ <b>Cuenta Transferida</b>\n\n"
                    old_device_msg += "Tu cuenta ha sido transferida a un nuevo dispositivo.\n\n"
                    old_device_msg += f"🕐 {get_mexico_city_time()}\n\n"
                    old_device_msg += "Si no fuiste tú, contacta al administrador inmediatamente."
                    send_message(old_chat_id_int, old_device_msg)
                except:
                    pass
            
            logger.info(f"Account transferred: phone={phone}, old_chat={old_chat_id}, new_chat={chat_id}")
        else:
            response = "❌ Error en la verificación. Usa /register para intentar de nuevo."
            send_message(chat_id, response)
    else:
        response = "❌ <b>Código incorrecto</b>\n\n"
        response += "El código no coincide. Verifica e intenta de nuevo.\n\n"
        response += "Usa /register para reiniciar el proceso."
        send_message(chat_id, response)


def handle_registration_code(chat_id, text):
    """Handle registration code input (legacy/backup method)"""
    # This is a fallback in case we need text-based phone input
    pass


def handle_report_command(chat_id, text, user_name):
    """Handle /report command for reporting wrong parking count"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            response = "🚨 <b>Reportar Conteo Incorrecto</b>\n\n"
            response += "Si crees que el conteo de espacios es incorrecto, repórtalo.\n\n"
            response += "<b>Uso:</b>\n"
            response += "/report &lt;número&gt;\n\n"
            response += "<b>Ejemplo:</b>\n"
            response += "/report 20 (si crees que hay 20 espacios ocupados)\n\n"
            response += "⏱️ Solo puedes reportar cada 5 minutos.\n"
            response += "📢 Los administradores recibirán tu reporte."
            send_message(chat_id, response)
            return
        
        # Check cooldown
        can_report_now, minutes_remaining = can_report(chat_id)
        
        if not can_report_now:
            response = f"⏱️ <b>Espera un momento</b>\n\n"
            response += f"Puedes reportar nuevamente en <b>{minutes_remaining} minuto(s)</b>.\n\n"
            response += "Esto previene spam y ayuda a mantener reportes de calidad."
            send_message(chat_id, response)
            return
        
        # Parse reported count
        try:
            reported_count = int(parts[1])
            
            if not (0 <= reported_count <= MAX_PARKING_SPACES):
                response = f"❌ Número fuera de rango. Debe estar entre 0 y {MAX_PARKING_SPACES}"
                send_message(chat_id, response)
                return
        except ValueError:
            response = "❌ Número no válido. Debe ser un entero."
            send_message(chat_id, response)
            return
        
        # Update last report time
        update_last_report_time(chat_id)
        
        # Get user info
        user = get_user_by_chat_id(chat_id)
        user_phone = user.get('phone', 'Desconocido')
        
        # Send confirmation to reporter
        response = "✅ <b>Reporte Enviado</b>\n\n"
        response += f"📊 Conteo reportado: {reported_count}/{MAX_PARKING_SPACES}\n"
        response += f"📊 Conteo actual del sistema: {current_total}/{MAX_PARKING_SPACES}\n"
        response += f"🕐 {get_mexico_city_time()}\n\n"
        response += "Tu reporte ha sido enviado a los administradores.\n"
        response += "¡Gracias por ayudarnos a mejorar!"
        send_message(chat_id, response)
        
        # Notify admins with notifications enabled
        admins = get_admins_with_notifications()
        
        admin_message = "🚨 <b>Nuevo Reporte de Usuario</b>\n\n"
        admin_message += f"👤 Usuario: {user_name}\n"
        admin_message += f"📱 Teléfono: {user_phone[-4:]}\n"  # Last 4 digits
        admin_message += f"📊 Reporta: {reported_count} espacios ocupados\n"
        admin_message += f"📊 Sistema muestra: {current_total} espacios ocupados\n"
        admin_message += f"🔢 Diferencia: {abs(reported_count - current_total)} espacios\n"
        admin_message += f"🕐 {get_mexico_city_time()}\n\n"
        
        if reported_count > current_total:
            admin_message += "⚠️ Usuario reporta MÁS espacios ocupados de los que el sistema detecta."
        elif reported_count < current_total:
            admin_message += "⚠️ Usuario reporta MENOS espacios ocupados de los que el sistema detecta."
        else:
            admin_message += "ℹ️ Usuario confirma el conteo actual."
        
        for admin_chat_id in admins:
            try:
                send_message(int(admin_chat_id), admin_message)
            except Exception as e:
                logger.error(f"Error sending report to admin {admin_chat_id}: {e}")
        
        logger.info(f"Report submitted by {user_name} (chat_id={chat_id}): reported={reported_count}, actual={current_total}")
        
    except Exception as e:
        logger.error(f"Error in handle_report_command: {e}")
        response = "❌ Error al procesar el reporte."
        send_message(chat_id, response)


def handle_addadmin_command(chat_id, text, user_name):
    """Handle /addadmin command - promote user to admin"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            response = "👥 <b>Promover Usuario a Admin</b>\n\n"
            response += "<b>Uso:</b>\n"
            response += "/addadmin &lt;teléfono&gt;\n\n"
            response += "<b>Ejemplo:</b>\n"
            response += "/addadmin 5512345678\n\n"
            response += "El usuario debe estar registrado previamente.\n"
            response += "⚠️ Solo administradores pueden usar este comando."
            send_message(chat_id, response)
            return
        
        phone_input = parts[1]
        
        # Validate phone number
        is_valid, cleaned_phone = validate_mexican_phone(phone_input)
        
        if not is_valid:
            response = "❌ Número de teléfono inválido.\n\nDebe ser un número mexicano de 10 dígitos."
            send_message(chat_id, response)
            return
        
        # Find user by phone
        user_data, phone_hash = get_user_by_phone(cleaned_phone)
        
        if not user_data:
            response = "❌ No se encontró un usuario con ese número de teléfono.\n\n"
            response += "El usuario debe registrarse primero usando /register"
            send_message(chat_id, response)
            return
        
        # Check if already admin
        if user_data.get('role') == 'admin':
            response = "ℹ️ Este usuario ya es administrador."
            send_message(chat_id, response)
            return
        
        # Promote to admin
        users = load_users()
        users[phone_hash]['role'] = 'admin'
        users[phone_hash]['promoted_at'] = get_mexico_city_time()
        users[phone_hash]['promoted_by'] = str(chat_id)
        users[phone_hash]['notifications_enabled'] = True  # Enable notifications by default
        save_users(users)
        
        # Send confirmation to promoting admin
        response = "✅ <b>Usuario Promovido</b>\n\n"
        response += f"📱 Teléfono: {cleaned_phone}\n"
        response += f"🎫 Nuevo Rol: Administrador\n"
        response += f"👤 Promovido por: {user_name}\n"
        response += f"🕐 {get_mexico_city_time()}\n\n"
        response += "El usuario ahora tiene acceso a todos los comandos de administrador."
        send_message(chat_id, response)
        
        # Notify the promoted user if they have a chat_id
        promoted_chat_id = user_data.get('chat_id')
        if promoted_chat_id:
            try:
                promoted_msg = "🎉 <b>¡Felicitaciones!</b>\n\n"
                promoted_msg += "Has sido promovido a <b>Administrador</b>.\n\n"
                promoted_msg += f"👤 Promovido por: {user_name}\n"
                promoted_msg += f"🕐 {get_mexico_city_time()}\n\n"
                promoted_msg += "Ahora tienes acceso a:\n"
                promoted_msg += "• Control de LEDs (/leds)\n"
                promoted_msg += "• Modificar contador (/set)\n"
                promoted_msg += "• Ver logs (/logs)\n"
                promoted_msg += "• Promover otros admins (/addadmin)\n"
                promoted_msg += "• Configurar notificaciones (/notifications)\n\n"
                promoted_msg += "Usa /help para ver todos los comandos."
                send_message(int(promoted_chat_id), promoted_msg)
            except Exception as e:
                logger.error(f"Error notifying promoted user: {e}")
        
        logger.info(f"User promoted to admin: phone={cleaned_phone}, by={user_name} (chat_id={chat_id})")
        
    except Exception as e:
        logger.error(f"Error in handle_addadmin_command: {e}")
        response = "❌ Error al promover usuario."
        send_message(chat_id, response)


def handle_notifications_command(chat_id, text):
    """Handle /notifications command - toggle report notifications for admins"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            # Show current status
            user = get_user_by_chat_id(chat_id)
            current_status = user.get('notifications_enabled', False)
            status_text = "activadas" if current_status else "desactivadas"
            
            response = "🔔 <b>Notificaciones de Reportes</b>\n\n"
            response += f"Estado actual: <b>{status_text}</b>\n\n"
            response += "<b>Uso:</b>\n"
            response += "/notifications on - Activar notificaciones\n"
            response += "/notifications off - Desactivar notificaciones\n\n"
            response += "Cuando están activadas, recibirás alertas cuando los usuarios reporten problemas con el conteo."
            send_message(chat_id, response)
            return
        
        command = parts[1].lower()
        
        if command not in ["on", "off"]:
            response = "❌ Comando no válido.\n\nUsa: /notifications on o /notifications off"
            send_message(chat_id, response)
            return
        
        enabled = (command == "on")
        
        if update_user_notifications(chat_id, enabled):
            status_text = "activadas ✅" if enabled else "desactivadas ❌"
            response = f"🔔 <b>Notificaciones {status_text}</b>\n\n"
            
            if enabled:
                response += "Ahora recibirás notificaciones cuando los usuarios reporten problemas con el conteo del estacionamiento."
            else:
                response += "Ya no recibirás notificaciones de reportes de usuarios."
            
            send_message(chat_id, response)
            logger.info(f"Admin notifications {command} for chat_id={chat_id}")
        else:
            response = "❌ Error al actualizar las notificaciones."
            send_message(chat_id, response)
            
    except Exception as e:
        logger.error(f"Error in handle_notifications_command: {e}")
        response = "❌ Error al procesar el comando."
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


def handle_leds_command(chat_id, text, user_name):
    """Handle /leds command to control semaforo LEDs"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            response = "❌ <b>Formato incorrecto</b>\n\n"
            response += "Uso: /leds &lt;on|off&gt;\n\n"
            response += "<b>Ejemplos:</b>\n"
            response += "• /leds on - Encender semáforo\n"
            response += "• /leds off - Apagar semáforo\n\n"
            response += "ℹ️ El contador seguirá funcionando incluso con LEDs apagados"
            send_message(chat_id, response)
            return
        
        command = parts[1].lower()
        
        if command not in ["on", "off"]:
            response = "❌ Comando no válido. Usa: /leds on o /leds off"
            send_message(chat_id, response)
            return
        
        # Publish MQTT command
        mqtt_command = "LEDOn" if command == "on" else "LEDOff"
        
        if publish_mqtt_command(mqtt_command):
            if command == "on":
                response = "✅ <b>Semáforo Encendido</b>\n\n"
                response += "💡 Los LEDs están activos\n"
                response += f"👤 Activado por: {user_name}\n"
                response += f"🕐 {get_mexico_city_time()}\n\n"
                response += "Los LEDs reflejarán el estado actual del estacionamiento"
            else:
                response = "✅ <b>Semáforo Apagado</b>\n\n"
                response += "🌑 Los LEDs están desactivados\n"
                response += f"👤 Desactivado por: {user_name}\n"
                response += f"🕐 {get_mexico_city_time()}\n\n"
                response += "⚠️ El contador seguirá funcionando normalmente\n"
                response += "Ideal para pruebas sin mostrar datos al público"
            
            response += "\n📝 Este cambio ha sido registrado en Azure IoT Hub"
            send_message(chat_id, response)
            logger.info(f"LEDs {command} by {user_name} (chat_id: {chat_id})")
        else:
            response = "❌ Error al publicar el comando MQTT. Intenta de nuevo."
            send_message(chat_id, response)
            
    except Exception as e:
        logger.error(f"Error in handle_leds_command: {e}")
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
        # Initialize first admin if needed
        logger.info("Checking for initial admin...")
        initialize_first_admin()
        
        # Initialize scheduler
        logger.info("Initializing scheduler...")
        init_scheduler()
        
        # Initialize MQTT listener
        mqtt_listener = MQTTListener(MQTT_BROKER, MQTT_PORT, TOTAL_TOPIC, LED_STATE_TOPIC)
        
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
