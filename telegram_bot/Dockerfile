FROM python:3.11-slim

WORKDIR /app

# Create data directory for persistent storage
RUN mkdir -p /app/data

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot script
COPY telegram_bot.py .

# Run the bot
CMD ["python", "-u", "telegram_bot.py"]
