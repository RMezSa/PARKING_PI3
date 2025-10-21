#!/bin/bash

# Script to get Docker container logs
# Usage: ./get_docker_logs.sh <container-name> <number-of-lines>

CONTAINER_NAME="$1"
NUM_LINES="${2:-25}"  # Default to 25 lines if not specified

# Validate inputs
if [ -z "$CONTAINER_NAME" ]; then
    echo "Error: Container name is required"
    echo "Usage: $0 <container-name> <number-of-lines>"
    echo "Available containers: mosquitto-broker, pi3-subscriber, webpanel, telegram-bot"
    exit 1
fi

# Validate number of lines
if ! [[ "$NUM_LINES" =~ ^[0-9]+$ ]] || [ "$NUM_LINES" -lt 1 ] || [ "$NUM_LINES" -gt 1000 ]; then
    echo "Error: Number of lines must be between 1 and 1000"
    exit 1
fi

# Valid container names
VALID_CONTAINERS=("mosquitto-broker" "pi3-subscriber" "webpanel" "telegram-bot")

# Check if container name is valid
if [[ ! " ${VALID_CONTAINERS[@]} " =~ " ${CONTAINER_NAME} " ]]; then
    echo "Error: Invalid container name: $CONTAINER_NAME"
    echo "Available containers: ${VALID_CONTAINERS[*]}"
    exit 1
fi

# Determine if we need sudo (check if we have docker command)
if command -v docker &> /dev/null; then
    DOCKER_CMD="docker"
    # Check if we need sudo
    if ! docker ps &> /dev/null; then
        DOCKER_CMD="sudo docker"
    fi
else
    echo "Error: Docker command not found"
    exit 1
fi

# Check if container exists and is running
if ! $DOCKER_CMD ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Check if container exists but is stopped
    if $DOCKER_CMD ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Error: Container '$CONTAINER_NAME' exists but is not running"
        exit 1
    else
        echo "Error: Container '$CONTAINER_NAME' does not exist"
        exit 1
    fi
fi

# Get logs from the container
$DOCKER_CMD logs --tail "$NUM_LINES" "$CONTAINER_NAME" 2>&1

exit 0
