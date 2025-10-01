-- ============================================
-- Azure Stream Analytics Queries for Parking System
-- IoT Hub: solipsis-hub.azure-devices.net
-- Device: estacionamiento-rpi
-- ============================================

-- ============================================
-- 1. BASIC QUERY - View All Parking Events
-- ============================================
-- This query shows all incoming parking events with processed timestamp
SELECT
    deviceId,
    eventType,
    totalCars,
    timestamp as EventTimestamp,
    System.Timestamp() as ProcessedTimestamp,
    location,
    capacity,
    occupancyRate,
    status
INTO
    [AllParkingEvents]  -- Replace with your output alias
FROM
    [YourIoTHubInput]   -- Replace with your IoT Hub input alias
WHERE
    deviceId = 'estacionamiento-rpi'

-- ============================================
-- 2. REAL-TIME OCCUPANCY MONITORING
-- ============================================
-- Shows current parking status with latest total count
SELECT
    deviceId,
    location,
    totalCars,
    capacity,
    occupancyRate,
    status,
    timestamp as LastUpdate,
    System.Timestamp() as ProcessedTime
INTO
    [CurrentOccupancy]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType != 'periodic'  -- Exclude periodic updates for cleaner data

-- ============================================
-- 3. ENTRY/EXIT EVENTS ONLY
-- ============================================
-- Track only actual car movements (entries and exits)
SELECT
    deviceId,
    eventType,
    totalCars,
    timestamp,
    System.Timestamp() as ProcessedTime,
    CASE 
        WHEN eventType = 'entry' THEN 1
        WHEN eventType = 'exit' THEN -1
        ELSE 0
    END as CarCountChange
INTO
    [ParkingMovements]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit')

-- ============================================
-- 4. ALERTING QUERY - High Occupancy Alert
-- ============================================
-- Triggers when parking lot reaches 85% capacity (30+ cars)
SELECT
    deviceId,
    location,
    totalCars,
    capacity,
    occupancyRate,
    status,
    timestamp,
    'HIGH_OCCUPANCY' as AlertType,
    'Parking lot is nearly full' as AlertMessage
INTO
    [HighOccupancyAlerts]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND totalCars >= 30
    AND eventType IN ('entry', 'exit', 'setfull')  -- Only on actual changes

-- ============================================
-- 5. FULL CAPACITY ALERT
-- ============================================
-- Triggers when parking lot reaches full capacity
SELECT
    deviceId,
    location,
    totalCars,
    capacity,
    status,
    timestamp,
    'FULL_CAPACITY' as AlertType,
    'Parking lot is at full capacity' as AlertMessage,
    System.Timestamp() as ProcessedTime
INTO
    [FullCapacityAlerts]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND totalCars >= 35
    AND eventType IN ('entry', 'setfull')

-- ============================================
-- 6. WINDOWED AGGREGATION - Hourly Statistics
-- ============================================
-- Calculate hourly parking statistics using tumbling window
SELECT
    deviceId,
    location,
    System.Timestamp() as WindowEnd,
    COUNT(*) as TotalEvents,
    SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) as TotalEntries,
    SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END) as TotalExits,
    MAX(totalCars) as PeakOccupancy,
    MIN(totalCars) as MinimumOccupancy,
    AVG(CAST(occupancyRate as float)) as AvgOccupancyRate
INTO
    [HourlyStatistics]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit')
GROUP BY
    deviceId, location, TumblingWindow(hour, 1)

-- ============================================
-- 7. SLIDING WINDOW - Recent Activity (15 minutes)
-- ============================================
-- Monitor recent parking activity in a sliding 15-minute window
SELECT
    deviceId,
    location,
    System.Timestamp() as WindowEnd,
    COUNT(*) as RecentEvents,
    SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) as RecentEntries,
    SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END) as RecentExits,
    MAX(totalCars) as CurrentOccupancy
INTO
    [RecentActivity]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit')
GROUP BY
    deviceId, location, SlidingWindow(minute, 15)

-- ============================================
-- 8. STATUS CHANGE DETECTION
-- ============================================
-- Detect when parking status changes (available -> nearly_full -> full)
SELECT
    deviceId,
    location,
    totalCars,
    status,
    LAG(status) OVER (LIMIT DURATION(hour, 1)) as PreviousStatus,
    timestamp,
    System.Timestamp() as ProcessedTime,
    CASE 
        WHEN LAG(status) OVER (LIMIT DURATION(hour, 1)) != status 
        THEN 'STATUS_CHANGED'
        ELSE 'NO_CHANGE'
    END as ChangeDetected
INTO
    [StatusChanges]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit', 'reset', 'setfull')

-- ============================================
-- 9. DAILY SUMMARY QUERY
-- ============================================
-- Generate end-of-day summary statistics
SELECT
    deviceId,
    location,
    System.Timestamp() as SummaryDate,
    COUNT(*) as TotalDailyEvents,
    SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) as DailyEntries,
    SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END) as DailyExits,
    MAX(totalCars) as DailyPeakOccupancy,
    AVG(CAST(occupancyRate as float)) as AvgDailyOccupancy,
    MAX(CASE WHEN status = 'full' THEN 1 ELSE 0 END) as ReachedCapacity
INTO
    [DailySummary]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit')
GROUP BY
    deviceId, location, TumblingWindow(day, 1)

-- ============================================
-- 10. ANOMALY DETECTION - Unusual Activity
-- ============================================
-- Detect unusual patterns (e.g., too many entries without exits)
SELECT
    deviceId,
    location,
    System.Timestamp() as WindowEnd,
    COUNT(*) as TotalEvents,
    SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) as Entries,
    SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END) as Exits,
    ABS(SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) - 
        SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END)) as EntryExitDifference,
    CASE 
        WHEN ABS(SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) - 
                 SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END)) > 5 
        THEN 'ANOMALY_DETECTED'
        ELSE 'NORMAL'
    END as AnomalyStatus
INTO
    [AnomalyDetection]
FROM
    [YourIoTHubInput]
WHERE
    deviceId = 'estacionamiento-rpi'
    AND eventType IN ('entry', 'exit')
GROUP BY
    deviceId, location, TumblingWindow(hour, 1)
HAVING
    ABS(SUM(CASE WHEN eventType = 'entry' THEN 1 ELSE 0 END) - 
        SUM(CASE WHEN eventType = 'exit' THEN 1 ELSE 0 END)) > 5

-- ============================================
-- SETUP INSTRUCTIONS:
-- ============================================
-- 1. Replace [YourIoTHubInput] with your actual IoT Hub input name
-- 2. Replace output aliases (e.g., [AllParkingEvents]) with your output sinks
-- 3. Adjust time windows based on your needs
-- 4. Configure outputs in Azure Portal (SQL Database, Blob Storage, etc.)
-- 5. Start the Stream Analytics job
-- ============================================