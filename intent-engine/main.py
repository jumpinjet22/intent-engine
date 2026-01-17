#!/usr/bin/env python3
"""
Doorbell Intent Engine
Handles doorbell events from Frigate, processes with LLM, and responds via UniFi Protect talkback
"""

import asyncio
import logging
import os
import json
import signal
import sys

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from intent_engine import DoorbellIntentEngine
from config import Config

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DoorbellService:
    def __init__(self):
        self.config = Config()
        self.engine = None
        self.mqtt_client = None
        self.running = False
        self.loop = None
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing Doorbell Intent Engine...")

        if not self.loop:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("Event loop not set; MQTT callbacks will drop messages")
        
        # Initialize intent engine
        self.engine = DoorbellIntentEngine(self.config)
        await self.engine.initialize()
        
        # Setup MQTT client
        self.mqtt_client = mqtt.Client(client_id="doorbell-intent-engine")
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect

        # Give the engine access to MQTT for publishing intents/status
        self.engine.set_mqtt_client(self.mqtt_client)
        
        logger.info("Initialization complete")
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to Frigate events + optional manual triggers
            frigate_topic = self.config.mqtt_topic
            trigger_topic = self.config.mqtt_trigger_topic

            if frigate_topic:
                client.subscribe(frigate_topic)
                logger.info(f"Subscribed to {frigate_topic}")
            else:
                logger.warning("MQTT topic not set; skipping Frigate subscription")

            # This lets Home Assistant / Node-RED / ESP32 doorbell presses trigger the same flow
            if trigger_topic and trigger_topic != frigate_topic:
                client.subscribe(trigger_topic)
                logger.info(f"Subscribed to {trigger_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        logger.warning(f"Disconnected from MQTT broker: {rc}")
        
    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages from Frigate or a manual trigger topic"""
        try:
            payload = json.loads(msg.payload.decode())

            # Manual trigger path
            if msg.topic == self.config.mqtt_trigger_topic:
                logger.info(f"Processing manual trigger from {payload.get('source', 'unknown')}")
                if self.loop:
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self.handle_trigger(payload))
                    )
                else:
                    logger.warning("Event loop not set; dropping manual trigger message")
                return

            # Frigate event path
            if self.should_process_event(payload):
                logger.info(f"Processing event: {payload.get('type')} for camera {payload.get('after', {}).get('camera')}")
                if self.loop:
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self.handle_event(payload))
                    )
                else:
                    logger.warning("Event loop not set; dropping Frigate event")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)

    async def handle_trigger(self, trigger_payload: dict):
        """Handle a manual trigger (doorbell press, button, etc.)"""
        try:
            await self.engine.handle_trigger_event(trigger_payload)
        except Exception as e:
            logger.error(f"Error handling trigger event: {e}", exc_info=True)
    
    def should_process_event(self, event):
        """Determine if we should process this Frigate event"""
        # Check event type
        event_type = event.get('type')
        if event_type not in ['new', 'update']:
            return False
        
        # Get event details
        after = event.get('after', {})
        
        # Check if it's the right camera (selected via UI or FRIGATE_CAMERA)
        camera = (after.get('camera') or '').strip()
        selected = self.config.selected_frigate_camera
        if selected:
            # Frigate cameras are normally exact names
            if camera != selected:
                return False
        
        # Check for person detection
        label = after.get('label', '')
        if label != 'person':
            return False
        
        # Check if person is at the door (not just passing by)
        # You can add zone filtering here
        current_zones = after.get('current_zones', [])
        if 'entry' not in current_zones and 'door' not in current_zones:
            # If no zones configured, process all person detections
            if len(current_zones) > 0:
                return False
        
        # Avoid processing the same event multiple times
        if event_type == 'update':
            # Only process if person has been there for a bit
            stationary = after.get('stationary', False)
            if not stationary:
                return False
        
        return True
    
    async def handle_event(self, event):
        """Handle a doorbell event"""
        try:
            logger.info("Doorbell event triggered - processing...")
            await self.engine.handle_doorbell_event(event)
            logger.info("Event processing complete")
            
        except Exception as e:
            logger.error(f"Error handling doorbell event: {e}", exc_info=True)
    
    async def run(self):
        """Main service loop"""
        self.running = True
        
        # Connect to MQTT broker
        logger.info(f"Connecting to MQTT broker at {self.config.mqtt_host}:{self.config.mqtt_port}")
        self.mqtt_client.connect(self.config.mqtt_host, self.config.mqtt_port, 60)
        
        # Start MQTT loop in background
        self.mqtt_client.loop_start()
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down...")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.engine:
            await self.engine.cleanup()
        
        logger.info("Shutdown complete")


async def main():
    """Main entry point"""
    service = DoorbellService()
    service.loop = asyncio.get_running_loop()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(service.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await service.initialize()
        await service.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
