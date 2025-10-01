# Stream Analytics Setup for Estacionamiento RPi

## Your IoT Hub Configuration
- **IoT Hub**: `solipsis-hub.azure-devices.net`
- **Device ID**: `estacionamiento-rpi`
- **Status**: ✅ Connected (based on your .env file)

## Quick Start - Basic Query

Here's the simplest query to start seeing your parking data:

```sql
SELECT
    deviceId,
    eventType,
    totalCars,
    timestamp,
    occupancyRate,
    status,
    System.Timestamp() as ProcessedTime
INTO
    [parking-output]  -- Change this to your output name
FROM
    [iot-hub-input]   -- Change this to your IoT Hub input name
WHERE
    deviceId = 'estacionamiento-rpi'
```

## Stream Analytics Job Setup Steps

### 1. Create Stream Analytics Job
```bash
# In Azure Portal:
# 1. Create new Stream Analytics Job
# 2. Choose your subscription and resource group
# 3. Select region close to your IoT Hub
```

### 2. Configure Input
- **Input Type**: IoT Hub
- **Input Alias**: `iot-hub-input` (or whatever you prefer)
- **IoT Hub**: Select `solipsis-hub`
- **Endpoint**: Messaging
- **Shared Access Policy**: iothubowner (or service)
- **Consumer Group**: Leave default or create new
- **Event Serialization**: JSON
- **Encoding**: UTF-8

### 3. Configure Output
Choose one or more outputs:

**Option A: Azure SQL Database**
```sql
-- Table structure needed:
CREATE TABLE ParkingEvents (
    deviceId NVARCHAR(50),
    eventType NVARCHAR(20),
    totalCars INT,
    timestamp DATETIME2,
    occupancyRate FLOAT,
    status NVARCHAR(20),
    processedTime DATETIME2
);
```

**Option B: Blob Storage**
- Container: `parking-data`
- Path Pattern: `{date}/{time}/parking-events`
- Format: JSON

**Option C: Power BI** (for real-time dashboards)
- Dataset Name: `parking-realtime`
- Table Name: `parking-events`

### 4. Test Your Setup

**Test Query** (copy and paste into Stream Analytics Query editor):
```sql
SELECT
    deviceId,
    eventType,
    totalCars,
    timestamp,
    occupancyRate,
    status
INTO
    [your-output-name]
FROM
    [your-input-name]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND totalCars IS NOT NULL
```

## Expected Data Format

Your Raspberry Pi will send this JSON structure:

```json
{
  "deviceId": "estacionamiento-rpi",
  "eventType": "entry",
  "totalCars": 15,
  "timestamp": "2025-10-01T14:30:00.123Z",
  "location": "parking_lot_main",
  "capacity": 35,
  "occupancyRate": 42.86,
  "status": "available"
}
```

## Useful Queries for Different Use Cases

### Real-time Dashboard Query
```sql
SELECT
    totalCars,
    occupancyRate,
    status,
    timestamp,
    System.Timestamp() as ProcessedTime
INTO
    [dashboard-output]
FROM
    [iot-hub-input]
WHERE
    deviceId = 'estacionamiento-rpi'
```

### Alert on Full Capacity
```sql
SELECT
    deviceId,
    totalCars,
    'PARKING_FULL' as AlertType,
    timestamp
INTO
    [alerts-output]
FROM
    [iot-hub-input]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND totalCars >= 35
    AND eventType IN ('entry', 'setfull')
```

### Hourly Statistics
```sql
SELECT
    System.Timestamp() as WindowEnd,
    COUNT(*) as EventCount,
    MAX(totalCars) as PeakOccupancy,
    AVG(CAST(occupancyRate as float)) as AvgOccupancy
INTO
    [hourly-stats]
FROM
    [iot-hub-input]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit')
GROUP BY
    TumblingWindow(hour, 1)
```

## Testing the Integration

### 1. Start Your Raspberry Pi System
```bash
cd /home/estacionamientog/PARKING_PI3
docker-compose up -d
```

### 2. Monitor IoT Hub Messages
```bash
# Using Azure CLI
az iot hub monitor-events --hub-name solipsis-hub --device-id estacionamiento-rpi
```

### 3. Simulate Events
```bash
# Send test messages to trigger IoT Hub events
mosquitto_pub -h 10.244.134.153 -t deepstream/car_count -m "entry"
mosquitto_pub -h 10.244.134.153 -t deepstream/car_count -m "exit"
```

### 4. Check Stream Analytics
- View job metrics in Azure Portal
- Check output sinks for processed data
- Monitor any errors in Activity Log

## Troubleshooting

**No data in Stream Analytics?**
1. Check IoT Hub is receiving messages: Azure Portal > IoT Hub > Metrics
2. Verify input configuration matches your IoT Hub name
3. Check query syntax and device ID spelling
4. Ensure output sink is properly configured

**Connection issues?**
1. Verify Raspberry Pi internet connectivity
2. Check IoT Hub connection string in .env file
3. Look at Docker logs: `docker-compose logs pi3-subscriber`

Your system should now be sending data to Stream Analytics every time a car enters/exits or every 5 seconds for periodic updates!