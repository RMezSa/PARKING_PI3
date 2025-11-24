import requests

# Configuration
BOT_TOKEN = "8414943579:AAGdyjGhBnSGqFrA3qQ-olq8HUn9OrduS4M"  # Replace with your actual bot token

def get_updates(bot_token):
    """
    Get recent messages sent to the bot to find chat IDs
    
    Args:
        bot_token (str): Your Telegram bot token
    
    Returns:
        dict: Response from Telegram API
    """
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting updates: {e}")
        return None

if __name__ == "__main__":
    print("Fetching recent messages...")
    print("Note: Make sure you've sent /start to your bot first!\n")
    
    result = get_updates(BOT_TOKEN)
    
    if result and result.get("ok"):
        updates = result.get("result", [])
        
        if not updates:
            print("No messages found.")
            print("\nTo get your Chat ID:")
            print("1. Open Telegram and search for your bot")
            print("2. Send /start to your bot")
            print("3. Run this script again")
        else:
            print("Found the following chats:\n")
            seen_chats = set()
            
            for update in updates:
                if "message" in update:
                    chat = update["message"]["chat"]
                    chat_id = chat["id"]
                    
                    if chat_id not in seen_chats:
                        seen_chats.add(chat_id)
                        chat_type = chat["type"]
                        
                        print(f"Chat ID: {chat_id}")
                        print(f"  Type: {chat_type}")
                        
                        if "username" in chat:
                            print(f"  Username: @{chat['username']}")
                        if "first_name" in chat:
                            print(f"  Name: {chat['first_name']}", end="")
                            if "last_name" in chat:
                                print(f" {chat['last_name']}")
                            else:
                                print()
                        if "title" in chat:
                            print(f"  Group: {chat['title']}")
                        
                        print()
            
            print("\nCopy one of the Chat IDs above and use it in send_message.py")
    else:
        print("Failed to get updates")
        if result:
            print(f"Error: {result}")
