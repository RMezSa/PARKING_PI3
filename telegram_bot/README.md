# Telegram Parking Bot Service

A containerized Telegram bot service that allows users to query real-time parking availability via Telegram.

## 🚀 Features

- **Real-time updates**: Subscribes to MQTT topic `estacionamiento/total` to get live parking count
- **User-friendly commands**: Simple commands for checking parking status
- **Scheduled notifications**: Users can set up recurring notifications for specific days/times
- **Status indicators**: Visual emoji indicators (🟢 🟡 🔴) for parking availability
- **Timezone aware**: Shows times in Mexico City timezone
- **Persistent schedules**: User schedules are saved and survive container restarts
- **Dockerized**: Runs as a containerized service alongside other parking system components

## 📋 Commands

Users can interact with the bot using these commands:

- `/start` - Welcome message and list of available commands
- `/parking` - Get current parking availability (occupied/available spaces)
- `/status` - Same as /parking, shows current status
- `/help` - Display help message with available commands
- `/schedule <día> <hora>` - Set up scheduled notifications
  - Example: `/schedule lunes 15:30` (every Monday at 3:30 PM)
  - Example: `/schedule miércoles 9:00` (every Wednesday at 9:00 AM)
  - Example: `/schedule diario 18:00` (every day at 6:00 PM)
- `/listschedules` - View all your scheduled notifications
- `/removeschedule <número>` - Remove a scheduled notification
  - Example: `/removeschedule 1` (removes notification #1)

### Valid Days (Spanish/English):
- `lunes/monday` - Monday
- `martes/tuesday` - Tuesday
- `miércoles/wednesday` - Wednesday
- `jueves/thursday` - Thursday
- `viernes/friday` - Friday
- `sábado/saturday` - Saturday
- `domingo/sunday` - Sunday
- `diario/daily` - Every day

### Time Format:
- Use 24-hour format: `HH:MM`
- All times are in Mexico City timezone (CDMX)
- Examples: `09:00`, `15:30`, `23:45`

## 🔧 Configuration

The bot is configured via environment variables in the `.env` file:

```bash
# Telegram Bot Token (get from @BotFather on Telegram)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# MQTT Configuration (should match your MQTT broker)
MQTT_BROKER=10.244.134.153
MQTT_PORT=1883
```

## 🏗️ Architecture

The bot consists of three main components:

1. **MQTT Listener**: Subscribes to the `estacionamiento/total` topic and maintains the current parking count in memory
2. **Telegram Poller**: Continuously polls Telegram API for new messages and responds to user commands
3. **Scheduler**: Manages recurring notifications using APScheduler with cron-like triggers

### How it works:

```
MQTT Broker (mosquitto) 
    ↓ publishes to "estacionamiento/total"
MQTT Listener (in bot)
    ↓ updates global state
User sends /parking command
    ↓ bot receives via Telegram API
Bot responds with current count

User sets schedule
    ↓ saved to schedules.json
APScheduler triggers at scheduled time
    ↓ sends notification to user
User receives parking update
```

### Persistent Storage:

Schedules are stored in `/app/data/schedules.json` which is mounted as a Docker volume at `./telegram_bot/data/schedules.json`. This ensures schedules persist across container restarts.

## 🐳 Docker Deployment

The bot runs as part of the docker-compose stack:

```yaml
telegram-bot:
  build: ./telegram_bot
  container_name: telegram-bot
  restart: unless-stopped
  depends_on:
    - mosquitto-broker
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - MQTT_BROKER=${MQTT_BROKER}
    - MQTT_PORT=${MQTT_PORT:-1883}
  volumes:
    - ./telegram_bot/data:/app/data
```

### Starting the service:

```bash
# Build and start the bot
docker-compose up -d telegram-bot

# View logs
docker-compose logs -f telegram-bot

# Restart the bot
docker-compose restart telegram-bot

# Stop the bot
docker-compose stop telegram-bot
```

## 📱 Setting up your Telegram Bot

1. **Create a bot with BotFather:**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` command
   - Follow the prompts to choose a name and username
   - Copy the bot token provided

2. **Add token to .env:**
   ```bash
   TELEGRAM_BOT_TOKEN=your_token_here
   ```

3. **Start the service:**
   ```bash
   docker-compose up -d telegram-bot
   ```

4. **Test your bot:**
   - Search for your bot on Telegram
   - Send `/start` to begin
   - Send `/parking` to check availability

5. **Set up a scheduled notification (optional):**
   - Send `/schedule lunes 15:00` to get updates every Monday at 3 PM
   - Send `/listschedules` to view your schedules
   - Send `/removeschedule 1` to remove a schedule

## 📅 Using Scheduled Notifications

### Setting up a schedule:

1. **Choose your day and time:**
   ```
   /schedule lunes 15:30
   ```
   This will send you parking updates every Monday at 3:30 PM (CDMX time)

2. **Create a daily notification:**
   ```
   /schedule diario 9:00
   ```
   Get updates every day at 9:00 AM

3. **Multiple schedules:**
   You can create multiple schedules for different days/times:
   ```
   /schedule lunes 8:00
   /schedule miércoles 14:00
   /schedule viernes 18:00
   ```

### Managing your schedules:

1. **View all schedules:**
   ```
   /listschedules
   ```
   Returns a numbered list of your schedules

2. **Remove a schedule:**
   ```
   /removeschedule 1
   ```
   Removes the first schedule from your list

### Notification format:

When the scheduled time arrives, you'll receive:
```
🔔 Actualización Programada

🅿️ Parking Status - AVAILABLE 🟢

📊 Occupied: 15/35 spaces
✅ Available: 20/35 spaces

🕐 Last updated: 02/10/2025 15:00:00
📡 System status: 🟢 Connected
```

## 🛠️ Development

### Local testing (without Docker):

```bash
cd telegram_bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_token"
export MQTT_BROKER="localhost"
export MQTT_PORT="1883"

# Run the bot
python telegram_bot.py
```

### Files:

- `telegram_bot.py` - Main bot service script with scheduling support
- `requirements.txt` - Python dependencies (includes APScheduler)
- `Dockerfile` - Container definition
- `data/schedules.json` - Persistent storage for user schedules (auto-created)
- `README.md` - This file

## 📊 Response Format

When users request parking status, they receive:

```
🅿️ Parking Status - AVAILABLE 🟢

📊 Occupied: 15/35 spaces
✅ Available: 20/35 spaces

🕐 Last updated: 02/10/2025 14:30:45
📡 System status: 🟢 Connected
```

Status indicators:
- 🟢 **AVAILABLE** - More than 5 spaces available
- 🟡 **ALMOST FULL** - 5 or fewer spaces available
- 🔴 **FULL** - No spaces available (35/35 occupied)

## 🔍 Troubleshooting

### Bot not responding:
```bash
# Check if container is running
docker ps | grep telegram-bot

# View logs for errors
docker-compose logs telegram-bot

# Verify MQTT connection
docker-compose logs telegram-bot | grep "MQTT connected"
```

### MQTT not receiving updates:
```bash
# Test MQTT topic manually
mosquitto_sub -h localhost -p 1883 -t "estacionamiento/total"
```

### Invalid bot token:
- Verify token in `.env` file matches the one from @BotFather
- Check for extra spaces or quotes in the token
- Restart the container after changing `.env`

### Schedules not persisting:
```bash
# Check if data directory exists
ls -la telegram_bot/data/

# Check if schedules.json exists
cat telegram_bot/data/schedules.json

# Verify volume mount
docker inspect telegram-bot | grep Mounts -A 10
```

### Scheduled notifications not firing:
```bash
# Check scheduler logs
docker-compose logs telegram-bot | grep "Added scheduler job"

# Verify timezone
docker exec telegram-bot date

# Test immediate notification
# Use a time 1 minute from now
```

## 📝 Logging

The bot logs important events:
- MQTT connection status
- Parking count updates
- Received Telegram messages
- Schedule creation/deletion
- Scheduler job execution
- Errors and exceptions

All logs are visible via `docker-compose logs -f telegram-bot`

## 🔒 Security Notes

- The bot token in `.env` is sensitive - keep it secure
- The `.env` file should not be committed to version control
- Consider adding `.env` to `.gitignore` if not already present
- Users can only read parking data, not modify it
- No authentication is required for users (public bot)
- User schedules are stored locally and not shared between users
- Schedule data contains only chat_id, day, time - no personal information

## 📈 Future Enhancements

Possible improvements:
- ✅ **Scheduled notifications** (IMPLEMENTED!)
- Support for multiple parking zones/segments
- Historical data and statistics
- Threshold-based notifications (alert when parking becomes available)
- Admin commands for authorized users
- Integration with payment systems
- One-time scheduled notifications (specific date/time)
- Timezone selection per user
