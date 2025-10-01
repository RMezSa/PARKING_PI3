"""
Simplified Azure IoT Hub client for sending parking data to Stream Analytics
Using synchronous approach to avoid threading issues
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import threading
import time

try:
    from azure.iot.device import IoTHubDeviceClient, Message
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

class SimpleParkingIoTHubClient:
    """
    Simplified IoT Hub client for sending parking events to Azure Stream Analytics
    Uses synchronous operations to avoid threading issues
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize the IoT Hub client
        
        Args:
            connection_string: Azure IoT Hub device connection string
        """
        self.connection_string = connection_string
        self.client = None
        self.is_connected = False
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        
        if not AZURE_AVAILABLE:
            self.logger.error("Azure IoT Device SDK not available. Install with: pip install azure-iot-device")
            return
            
    def connect(self) -> bool:
        """
        Connect to IoT Hub (synchronous)
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        with self._lock:
            try:
                if not AZURE_AVAILABLE:
                    self.logger.error("Azure IoT Device SDK not available")
                    return False
                    
                self.logger.info("Connecting to IoT Hub...")
                self.client = IoTHubDeviceClient.create_from_connection_string(
                    self.connection_string
                )
                
                # Connect synchronously (this might block)
                self.client.connect()
                self.is_connected = True
                self.logger.info("Successfully connected to Azure IoT Hub")
                return True
                
            except Exception as e:
                self.logger.error(f"Error connecting to IoT Hub: {e}")
                self.is_connected = False
                return False
    
    def disconnect(self):
        """Disconnect from IoT Hub"""
        with self._lock:
            if self.client and self.is_connected:
                try:
                    self.client.disconnect()
                    self.is_connected = False
                    self.logger.info("Disconnected from IoT Hub")
                except Exception as e:
                    self.logger.error(f"Error disconnecting from IoT Hub: {e}")
    
    def send_parking_event(self, event_type: str, total_cars: int, 
                          timestamp: Optional[str] = None) -> bool:
        """
        Send parking event to IoT Hub for Stream Analytics processing
        
        Args:
            event_type: Type of event ('entry', 'exit', 'reset', 'setfull', 'periodic')
            total_cars: Current total number of cars
            timestamp: Event timestamp (ISO format), if None current time is used
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        if not AZURE_AVAILABLE:
            self.logger.warning("Azure IoT SDK not available - skipping IoT Hub send")
            return False
            
        with self._lock:
            # Check connection status
            if not self.is_connected or not self.client:
                self.logger.warning("Not connected to IoT Hub, attempting to connect...")
                if not self.connect():
                    return False
            
            try:
                if timestamp is None:
                    timestamp = datetime.utcnow().isoformat() + "Z"
                
                # Create message payload for Stream Analytics
                message_data = {
                    "deviceId": "estacionamiento-rpi",
                    "eventType": event_type,
                    "totalCars": total_cars,
                    "timestamp": timestamp,
                    "location": "parking_lot_main",
                    "capacity": 35,
                    "occupancyRate": round((total_cars / 35) * 100, 2),
                    "status": self._get_parking_status(total_cars)
                }
                
                # Convert to JSON string
                message_json = json.dumps(message_data)
                
                # Create IoT Hub message
                message = Message(message_json)
                
                # Add message properties for routing/filtering
                message.custom_properties["eventType"] = event_type
                message.custom_properties["deviceType"] = "parking_sensor"
                message.content_type = "application/json"
                message.content_encoding = "utf-8"
                
                # Send message synchronously
                self.client.send_message(message)
                
                self.logger.info(f"Sent parking event to IoT Hub: {event_type}, total: {total_cars}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error sending message to IoT Hub: {e}")
                # Reset connection on error
                self.is_connected = False
                return False
    
    def _get_parking_status(self, total_cars: int) -> str:
        """
        Get parking status based on car count
        
        Args:
            total_cars: Current number of cars
            
        Returns:
            str: Parking status ('available', 'nearly_full', 'full')
        """
        if total_cars >= 35:
            return "full"
        elif total_cars >= 30:
            return "nearly_full"
        else:
            return "available"