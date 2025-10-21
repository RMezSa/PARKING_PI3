#!/bin/bash

# Docker Compose restart script for PARKING_PI3
# This script handles docker compose down/up operations

COMPOSE_DIR="/home/estacionamientog/PARKING_PI3"
LOG_FILE="/home/estacionamientog/PARKING_PI3/docker-restart-cron.log"

# GPIO BCM pins for the semaforo LEDs
LED_VERDE_BCM=26
LED_AMARILLO_BCM=19
LED_ROJO_BCM=13

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to turn off all semaforo LEDs
turn_off_semaforo() {
    log_message "Turning off semaforo LEDs..."
    
    # Wait a moment for containers to fully release GPIO pins
    sleep 2
    
    # Run the Python script to turn off LEDs
    if python3 "${COMPOSE_DIR}/turn_off_leds.py" 2>&1 | tee -a "$LOG_FILE"; then
        log_message "Semaforo LEDs turned off successfully"
    else
        log_message "Warning: Failed to turn off LEDs, attempting alternative method..."
        # Alternative method using sysfs if Python fails
        for pin in ${LED_VERDE_BCM} ${LED_AMARILLO_BCM} ${LED_ROJO_BCM}; do
            echo "$pin" > /sys/class/gpio/unexport 2>/dev/null || true
            echo "$pin" > /sys/class/gpio/export 2>/dev/null || true
            echo "out" > /sys/class/gpio/gpio${pin}/direction 2>/dev/null || true
            echo "0" > /sys/class/gpio/gpio${pin}/value 2>/dev/null || true
        done
        log_message "LEDs turned off using sysfs method"
    fi
}

# Change to the docker-compose directory
cd "$COMPOSE_DIR" || exit 1

# Check the operation argument
case "$1" in
    down)
        log_message "Starting docker compose down..."
        sudo docker compose down 2>&1 | tee -a "$LOG_FILE"
        log_message "Docker compose down completed."
        turn_off_semaforo
        ;;
    up)
        log_message "Starting docker compose up..."
        sudo docker compose up -d 2>&1 | tee -a "$LOG_FILE"
        log_message "Docker compose up completed."
        ;;
    *)
        log_message "ERROR: Invalid argument. Use 'down' or 'up'"
        exit 1
        ;;
esac

exit 0
