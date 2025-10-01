"""
Synchronous Azure IoT Hub client for sending parking data to Stream Analytics
"""
import json
import logging
import threading
from datetime import datetime
from typing import Optional
from azure.iot.device import IoTHubDeviceClient, Message

class SynchronousIoTHubClient:
    """
    Synchronous IoT Hub client for sending parking events to Azure Stream Analytics
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
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """
        Connect to IoT Hub (synchronous)
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        with self.lock:
            try:
                if self.client is None:
                    self.logger.info("Creating IoT Hub client...")
                    self.client = IoTHubDeviceClient.create_from_connection_string(
                        self.connection_string
                    )
                
                if not self.is_connected:
                    self.logger.info("Connecting to IoT Hub...")
                    self.client.connect()
                    self.is_connected = True
                    self.logger.info("Successfully connected to Azure IoT Hub")
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error connecting to IoT Hub: {e}")
                self.is_connected = False
                return False
    
    def disconnect(self):
        """Disconnect from IoT Hub (synchronous)"""
        with self.lock:
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
        Send parking event to IoT Hub for Stream Analytics processing (synchronous)
        
        Args:
            event_type: Type of event ('entry', 'exit', 'reset', 'setfull', 'periodic')
            total_cars: Current total number of cars
            timestamp: Event timestamp (ISO format), if None current time is used
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        # Check connection
        if not self.is_connected:
            if not self.connect():
                return False
        
        try:
            if timestamp is None:
                timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Create message payload for Stream Analytics
            message_data = {
                "park": "g",                 # str: parking lot/device id
                "event": event_type,         # str: 'entry' | 'exit' | 'reset' | 'setfull' | 'periodic'
                "cars": total_cars,          # int: current total number of cars
                "time": timestamp,           # str (ISO-8601, UTC): e.g. "2025-10-01T18:34:21.123Z"
                "status": self._get_parking_status(total_cars)  # str: 'available' | 'nearly_full' | 'full'
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
            
            # Send message (synchronous)
            self.client.send_message(message)
            
            self.logger.info(f"Sent parking event to IoT Hub: {event_type}, total: {total_cars}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending message to IoT Hub: {e}")
            # Try to reconnect on next send
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

# Alias for backward compatibility
IoTHubManager = SynchronousIoTHubClient