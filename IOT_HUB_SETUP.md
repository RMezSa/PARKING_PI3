# Azure IoT Hub Integration Setup

This document explains how to set up and test the Azure IoT Hub integration for the parking system.

## Prerequisites

1. An Azure subscription with IoT Hub service
2. A device registered in your IoT Hub
3. The device connection string from Azure Portal

## Setup Instructions

### 1. Configure Environment Variables

Copy the template environment file and configure your IoT Hub connection string:

```bash
cp .env.template .env
```

Edit `.env` file and replace the placeholder with your actual IoT Hub device connection string:

```bash
IOT_HUB_CONNECTION_STRING=HostName=your-iot-hub.azure-devices.net;DeviceId=parking-pi3;SharedAccessKey=your-shared-access-key
```

### 2. Build and Run the System

Rebuild the Docker container to include the Azure IoT SDK:

```bash
docker-compose down
docker-compose build --no-cache pi3-subscriber
docker-compose up -d
```

### 3. Verify IoT Hub Connection

Check the logs to ensure successful connection to IoT Hub:

```bash
docker-compose logs -f pi3-subscriber
```

You should see messages like:
```
Successfully connected to Azure IoT Hub
```

## Data Format Sent to IoT Hub

Each parking event sends a JSON message to IoT Hub with the following structure:

```json
{
  "deviceId": "parking-pi3",
  "eventType": "entry|exit|reset|setfull|periodic",
  "totalCars": 15,
  "timestamp": "2024-10-01T12:34:56.789Z",
  "location": "parking_lot_main",
  "capacity": 35,
  "occupancyRate": 42.86,
  "status": "available|nearly_full|full"
}
```

### Event Types:
- **entry**: Car entered parking lot
- **exit**: Car exited parking lot  
- **reset**: Counter was reset to 0
- **setfull**: Counter was manually set to full (35)
- **periodic**: Regular status update (every 5 seconds)

### Message Properties:
- `eventType`: For message routing/filtering
- `deviceType`: Always "parking_sensor"
- `content_type`: "application/json"

## Stream Analytics Job Configuration

Configure your Stream Analytics job to consume messages from IoT Hub:

### Input Configuration:
- **Input Type**: IoT Hub
- **Event Serialization Format**: JSON
- **Encoding**: UTF-8

### Sample Query:
```sql
SELECT
    deviceId,
    eventType,
    totalCars,
    timestamp,
    location,
    capacity,
    occupancyRate,
    status,
    System.Timestamp() as ProcessedTime
INTO
    [YourOutputStream]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'parking-pi3'
```

### Filtering Examples:
```sql
-- Only entry/exit events
WHERE eventType IN ('entry', 'exit')

-- Only when parking lot is nearly full or full
WHERE status IN ('nearly_full', 'full')

-- Only significant changes (not periodic updates)
WHERE eventType != 'periodic'
```

## Testing the Integration

### 1. Simulate Parking Events

Use the web panel or MQTT client to send test messages:

```bash
# Entry event
mosquitto_pub -h localhost -t deepstream/car_count -m "entry"

# Exit event  
mosquitto_pub -h localhost -t deepstream/car_count -m "exit"

# Reset counter
mosquitto_pub -h localhost -t deepstream/car_count -m "reset"
```

### 2. Monitor IoT Hub Messages

Use Azure CLI or IoT Explorer to monitor messages:

```bash
# Using Azure CLI
az iot hub monitor-events --hub-name your-iot-hub --device-id parking-pi3
```

### 3. Check Stream Analytics Output

Verify that your Stream Analytics job is processing the messages and writing to your configured output (Azure SQL, Blob Storage, etc.).

## Troubleshooting

### Common Issues:

1. **Connection String Error**: Verify the connection string format and device exists in IoT Hub
2. **Network Issues**: Ensure the Raspberry Pi has internet access
3. **Authentication Failed**: Check device key and permissions
4. **Message Not Received**: Verify IoT Hub endpoint and device registration

### Debug Commands:

```bash
# Check container logs
docker-compose logs pi3-subscriber

# Test network connectivity
ping your-iot-hub.azure-devices.net

# Verify environment variables
docker-compose exec pi3-subscriber env | grep IOT_HUB
```

## Message Flow Architecture

```
MQTT Broker → subscriber.py → Azure IoT Hub → Stream Analytics → Output Sink
     ↑              ↓
   Car Detection   LED Status
   System         Update
```

The system maintains dual data paths:
1. **Local MQTT**: For real-time LED control and web panel updates
2. **Azure IoT Hub**: For cloud analytics and Stream Analytics processing

Both paths are triggered simultaneously when parking events occur, ensuring local responsiveness while enabling cloud-based analytics and reporting.