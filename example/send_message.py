import requests

# Configuration
BOT_TOKEN = "8414943579:AAGdyjGhBnSGqFrA3qQ-olq8HUn9OrduS4M"  # Replace with your actual bot token
CHAT_ID = "7155603363"      # Replace with the chat ID where you want to send the message

def send_message(bot_token, chat_id, text):
    """
    Send a message using Telegram Bot API
    
    Args:
        bot_token (str): Your Telegram bot token
        chat_id (str): The chat ID to send the message to
        text (str): The message text to send
    
    Returns:
        dict: Response from Telegram API
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"  # Optional: supports HTML formatting
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    message_text = "Hay actualmente 4 lugares disponibles en estacionamiento G"
    
    result = send_message(BOT_TOKEN, CHAT_ID, message_text)
    
    if result and result.get("ok"):
        print("Message sent successfully!")
        print(f"Message ID: {result['result']['message_id']}")
    else:
        print("Failed to send message")
        if result:
            print(f"Error: {result}")
