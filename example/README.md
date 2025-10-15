# Telegram Parking Bot

A Telegram bot service that provides real-time parking availability information. Designed to run continuously on a Raspberry Pi.

## 📁 Files

- **`parking_bot.py`** - Main bot service that polls for messages and responds with parking data
- **`send_message.py`** - Simple script to send one-time messages
- **`get_chat_id.py`** - Helper to retrieve your chat ID
- **`parking-bot.service`** - Systemd service file for auto-starting on Pi
- **`requirements.txt`** - Python dependencies

## 🚀 Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your bot

The bot token is already configured in the files. Make sure you have:
- Started a conversation with your bot on Telegram (send `/start`)
- Your bot token is correct

### 3. Test the bot locally

```bash
python3 parking_bot.py
```

The bot will start polling for messages. Try sending `/parking` to your bot!

## 🤖 Bot Commands

- `/start` - Welcome message and command list
- `/parking` - Get current parking availability for all segments
- `/help` - Show help message

## 🅿️ Implementing Parking Data

The `get_parking_data()` function in `parking_bot.py` currently returns placeholder data. Replace this with your actual parking system implementation:

```python
def get_parking_data():
    # TODO: Implement your parking data retrieval here
    # Examples:
    # - Query a database
    # - Read from sensors via GPIO
    # - Call an API
    # - Read from a file
    
    # Return formatted message string
    return parking_message
```

## 🔧 Raspberry Pi Setup (Run as Service)

### 1. Copy files to your Pi

```bash
# On your Pi, create directory
mkdir -p /home/pi/telegram
cd /home/pi/telegram

# Copy all Python files here
```

### 2. Install as systemd service

```bash
# Copy service file
sudo cp parking-bot.service /etc/systemd/system/

# Edit the service file if needed (change paths/user)
sudo nano /etc/systemd/system/parking-bot.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable parking-bot.service

# Start the service
sudo systemctl start parking-bot.service
```

### 3. Manage the service

```bash
# Check status
sudo systemctl status parking-bot.service

# View logs
sudo journalctl -u parking-bot.service -f

# Stop the service
sudo systemctl stop parking-bot.service

# Restart the service
sudo systemctl restart parking-bot.service
```

## 📊 Features

- ✅ Continuous polling for new messages
- ✅ Command-based interaction
- ✅ HTML formatted responses with emojis
- ✅ Color-coded availability indicators (🟢🟡🔴)
- ✅ Error handling and automatic recovery
- ✅ Logging for debugging
- ✅ Systemd service for auto-start on boot

## 🔐 Security Notes

- Keep your bot token secure
- Don't commit tokens to version control
- Consider using environment variables for sensitive data
- The bot responds to any user who messages it - add authentication if needed

## 📝 Example Response

```
🅿️ Parking Status

🟢 Segment A: 5/20 available
🟢 Segment B: 5/15 available
🟢 Segment C: 5/25 available
🟢 Segment D: 5/30 available

📊 Total: 20 spaces available (70 occupied)
🕐 Updated: 14:32:15
```
