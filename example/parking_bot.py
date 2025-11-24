import requests
import time
import logging
from datetime import datetime

# Configuration
BOT_TOKEN = "8414943579:AAGdyjGhBnSGqFrA3qQ-olq8HUn9OrduS4M"
POLLING_INTERVAL = 2  # seconds between polling

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_parking_data():
    """
    TODO: Implement this function to fetch real parking data
    
    This function should retrieve the current parking occupancy data
    from your parking system (database, API, sensors, etc.)
    
    Returns:
        str: Formatted parking data message
    """
    # PLACEHOLDER - Replace with your actual parking data retrieval logic
    # Example format:
    parking_spaces = {
        "Segment A": {"total": 20, "occupied": 15, "available": 5},
        "Segment B": {"total": 15, "occupied": 10, "available": 5},
        "Segment C": {"total": 25, "occupied": 20, "available": 5},
        "Segment D": {"total": 30, "occupied": 25, "available": 5},
    }
    
    # Format the message
    message = "🅿️ <b>Parking Status</b>\n\n"
    total_available = 0
    total_occupied = 0
    
    for segment, data in parking_spaces.items():
        available = data["available"]
        occupied = data["occupied"]
        total = data["total"]
        total_available += available
        total_occupied += occupied
        
        # Add emoji indicator
        if available == 0:
            indicator = "🔴"
        elif available < 5:
            indicator = "🟡"
        else:
            indicator = "🟢"
        
        message += f"{indicator} <b>{segment}</b>: {available}/{total} available\n"
    
    message += f"\n📊 <b>Total</b>: {total_available} spaces available ({total_occupied} occupied)"
    message += f"\n🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
    
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
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message: {e}")
        return None


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
    text = message.get("text", "").strip().lower()
    user_name = message["from"].get("first_name", "User")
    
    logger.info(f"Received message from {user_name} (chat_id: {chat_id}): {text}")
    
    # Handle different commands
    if text == "/start":
        response = f"👋 Hello {user_name}! Welcome to the Parking Status Bot.\n\n"
        response += "Use the following commands:\n"
        response += "/parking - Get current parking status\n"
        response += "/help - Show this help message"
        send_message(chat_id, response)
    
    elif text == "/help":
        response = "🅿️ <b>Parking Bot Help</b>\n\n"
        response += "/parking - Get current parking availability\n"
        response += "/start - Show welcome message\n"
        response += "/help - Show this help message"
        send_message(chat_id, response)
    
    elif text == "/parking" or text == "parking":
        # Fetch and send parking data
        parking_data = get_parking_data()
        send_message(chat_id, parking_data)
    
    else:
        response = "❓ Unknown command. Use /help to see available commands."
        send_message(chat_id, response)


def run_bot():
    """
    Main bot loop - continuously poll for new messages
    """
    logger.info("🤖 Parking Bot started!")
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
            logger.error(f"Unexpected error: {e}")
            time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    run_bot()
