import asyncio
import socketio
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RobotWebSocketClient:
    def __init__(self, cloud_url: str, robot_id: str):
        self.cloud_url = cloud_url
        self.robot_id = robot_id
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.sessions = {}  # sessionId -> session data
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        self.webrtc_manager = None  # Will be initialized when needed
        
    async def connect(self):
        """Connect to cloud signaling server"""
        try:
            logger.info(f"🤖 Connecting to cloud server: {self.cloud_url}")
            
            # Set up event handlers
            self.setup_event_handlers()
            
            # Connect to Socket.IO server with more robust options
            await self.sio.connect(
                self.cloud_url,
                wait_timeout=10,
                transports=['websocket']
            )
            self.connected = True
            self.reconnect_attempts = 0
            
            logger.info("✅ Connected to cloud signaling server")
            
            # Keep connection alive
            await self.sio.wait()
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to cloud: {e}")
            self.connected = False
            await self.handle_reconnect()
    
    def setup_event_handlers(self):
        """Set up Socket.IO event handlers"""
        
        @self.sio.event
        async def connect():
            logger.info("✅ Socket.IO connected")
            self.connected = True
            self.reconnect_attempts = 0
            await self.register_robot()
            
        @self.sio.event
        async def disconnect():
            logger.warning("⚠️ Socket.IO disconnected")
            self.connected = False
            # Don't immediately reconnect - let the main reconnection logic handle it
            logger.info("🔄 Disconnect detected, will reconnect via main logic")
            
        # Use direct event listeners instead of decorators
        self.sio.on('create-session', self.handle_create_session_direct)
        self.sio.on('switch-stream-type', self.handle_switch_stream_type_direct)
        self.sio.on('webrtc-answer', self.handle_webrtc_answer_direct)
        self.sio.on('ice-candidate', self.handle_ice_candidate_direct)
        
        @self.sio.event
        async def create_session(data):
            logger.info(f"📡 Received create-session event: {data}")
            try:
                await self.handle_create_session(data)
                logger.info(f"✅ Successfully handled create-session event for session {data.get('sessionId', 'unknown')}")
            except Exception as e:
                logger.error(f"❌ Error handling create-session event: {e}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                
        # Add a catch-all event listener for create-session specifically
        @self.sio.event
        async def create_session_alt(data):
            logger.info(f"📡 Received create-session-alt event: {data}")
            
        # Add a catch-all event listener for any event with 'session' in the name
        @self.sio.event
        async def session_event(data):
            logger.info(f"📡 Received session event: {data}")
            
        @self.sio.event
        async def webrtc_answer(data):
            await self.handle_webrtc_answer(data)
            
        @self.sio.event
        async def webrtc_answer_alt(data):
            await self.handle_webrtc_answer(data)
            
        @self.sio.event
        async def ice_candidate(data):
            await self.handle_ice_candidate(data)
            
        @self.sio.event
        async def ice_candidate_alt(data):
            await self.handle_ice_candidate(data)
            
        @self.sio.event
        async def session_closed(data):
            await self.handle_session_closed(data)
            
        # Add a general event listener to catch all events
        @self.sio.event
        async def message(data):
            logger.info(f"📨 Received general message event: {data}")
            
        # Add a catch-all event listener for debugging
        @self.sio.event
        async def any_event(event, data):
            logger.info(f"📨 Received event '{event}' with data: {data}")
            
        # Add a simple test event listener
        @self.sio.event
        async def test(data):
            logger.info(f"🧪 Received test event: {data}")
            
        # Add a simple ping event listener
        @self.sio.event
        async def ping(data):
            logger.info(f"🏓 Received ping event: {data}")
            await self.sio.emit('pong', {'response': 'pong'})
            
    async def handle_reconnect(self):
        """Handle reconnection logic"""
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = self.reconnect_delay * self.reconnect_attempts
            logger.info(f"🔄 Reconnecting in {delay} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
            await asyncio.sleep(delay)
            await self.connect()
        else:
            logger.error("❌ Max reconnection attempts reached. Stopping robot client.")
            
    async def register_robot(self):
        """Register this robot with the cloud server"""
        try:
            # Get device info from existing RealSense manager
            device_info = await self.get_device_info()
            
            await self.sio.emit('robot-register', {
                "robotId": self.robot_id,
                "deviceInfo": device_info
            })
            logger.info(f"🤖 Registered robot {self.robot_id} with cloud server")
            
        except Exception as e:
            logger.error(f"❌ Failed to register robot: {e}")
            
    async def get_device_info(self):
        """Get device information from RealSense manager"""
        try:
            # Use a simple approach - get device info from the API
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/api/devices/') as response:
                    if response.status == 200:
                        devices = await response.json()
                        if devices:
                            device = devices[0]  # Use first device
                            return {
                                "name": f"RealSense Robot {self.robot_id}",
                                "deviceId": device["device_id"],
                                "serialNumber": device["serial_number"],
                                "firmwareVersion": device["firmware_version"],
                                "sensors": device["sensors"],
                                "capabilities": ["color", "depth", "infrared", "pointcloud"],
                                "status": "available",
                                "lastSeen": datetime.now().isoformat()
                            }
            
            # Fallback if API call fails
            return {
                "name": f"RealSense Robot {self.robot_id}",
                "deviceId": "844212070924",  # Default device ID
                "capabilities": ["color", "depth", "infrared", "pointcloud"],
                "status": "available",
                "lastSeen": datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"❌ Failed to get device info: {e}")
            return {
                "name": f"RealSense Robot {self.robot_id}",
                "deviceId": "844212070924",  # Default device ID
                "capabilities": ["color", "depth", "infrared", "pointcloud"],
                "status": "available",
                "lastSeen": datetime.now().isoformat()
            }
            

            
    async def handle_create_session_direct(self, data):
        """Direct event handler for create-session (non-async)"""
        logger.info(f"🎯 Direct create-session handler called with data: {data}")
        try:
            await self.handle_create_session(data)
        except Exception as e:
            logger.error(f"❌ Error in direct create-session handler: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def handle_webrtc_answer_direct(self, data):
        """Direct event handler for webrtc-answer (non-async)"""
        logger.info(f"🎯 Direct webrtc-answer handler called with data: {data}")
        try:
            await self.handle_webrtc_answer(data)
        except Exception as e:
            logger.error(f"❌ Error in direct webrtc-answer handler: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def handle_ice_candidate_direct(self, data):
        """Direct event handler for ice-candidate (non-async)"""
        logger.info(f"🎯 Direct ice-candidate handler called with data: {data}")
        try:
            await self.handle_ice_candidate(data)
        except Exception as e:
            logger.error(f"❌ Error in direct ice-candidate handler: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")

    async def handle_switch_stream_type_direct(self, data):
        """Direct event handler for switch-stream-type (non-async)"""
        logger.info(f"🎯 Direct switch-stream-type handler called with data: {data}")
        try:
            await self.handle_switch_stream_type(data)
        except Exception as e:
            logger.error(f"❌ Error in direct switch-stream-type handler: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def handle_create_session(self, data: Dict[str, Any]):
        """Handle WebRTC session creation request"""
        logger.info(f"🔍 handle_create_session called with data: {data}")
        session_id = data["sessionId"]
        device_id = data["deviceId"]
        stream_types = data["streamTypes"]
        
        try:
            logger.info(f"📡 Creating WebRTC session {session_id} for streams: {stream_types}")
            
            # Import WebRTC manager and dependencies directly (this runs on the robot)
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            
            from app.services.webrtc_manager import WebRTCManager
            from app.api.dependencies import get_realsense_manager
            
            # Get the existing realsense manager instance
            realsense_manager = get_realsense_manager()
            
            # Create WebRTC offer using local WebRTC manager
            self.webrtc_manager = WebRTCManager(realsense_manager)
            offer_response = await self.webrtc_manager.create_offer(device_id, stream_types)
            
            if offer_response:
                api_session_id, offer_dict = offer_response
                sdp = offer_dict["sdp"]
                sdp_type = offer_dict["type"]
                
                # Store session info
                self.sessions[session_id] = {
                    "deviceId": device_id,
                    "streamTypes": stream_types,
                    "apiSessionId": api_session_id,
                    "webrtcManager": self.webrtc_manager,
                    "createdAt": datetime.now()
                }
                
                # Send offer back to cloud
                await self.sio.emit('webrtc-offer', {
                    "sessionId": session_id,
                    "offer": {
                        "sdp": sdp,
                        "type": sdp_type
                    }
                })
                logger.info(f"✅ WebRTC offer created for session {session_id}")
                
            else:
                raise Exception("Failed to create WebRTC offer")
                
        except Exception as e:
            logger.error(f"❌ Failed to create session {session_id}: {e}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            await self.sio.emit('session-error', {
                "sessionId": session_id,
                "error": str(e)
            })

    async def handle_switch_stream_type(self, data: Dict[str, Any]):
        """Handle stream type switching within an existing session"""
        cloud_session_id = data.get('sessionId')
        new_stream_types = data.get('streamTypes', [])
        
        if not cloud_session_id or not new_stream_types:
            logger.error(f"❌ Invalid switch-stream-type data: {data}")
            return

        logger.info(f"🔄 Switching stream types for session {cloud_session_id} to: {new_stream_types}")
        
        # Get the session data to find the API session ID
        session_data = self.sessions.get(cloud_session_id)
        if not session_data:
            logger.error(f"❌ Session {cloud_session_id} not found in local sessions")
            await self.sio.emit('stream-type-switch-error', {
                'sessionId': cloud_session_id,
                'error': 'Session not found'
            })
            return
        
        api_session_id = session_data.get('apiSessionId')
        if not api_session_id:
            logger.error(f"❌ API session ID not found for cloud session {cloud_session_id}")
            await self.sio.emit('stream-type-switch-error', {
                'sessionId': cloud_session_id,
                'error': 'API session ID not found'
            })
            return
        
        logger.info(f"🔄 Using API session ID {api_session_id} for stream type switch")
        
        # Get the WebRTC manager from the session data
        webrtc_manager = session_data.get('webrtcManager')
        if not webrtc_manager:
            logger.error(f"❌ WebRTC manager not found for cloud session {cloud_session_id}")
            await self.sio.emit('stream-type-switch-error', {
                'sessionId': cloud_session_id,
                'error': 'WebRTC manager not found'
            })
            return
        
        try:
            # Switch stream types in the existing session using API session ID
            success = await webrtc_manager.switch_stream_type(api_session_id, new_stream_types)
            
            if success:
                logger.info(f"✅ Successfully switched stream types for session {cloud_session_id}")
                await self.sio.emit('stream-type-switched', {
                    "sessionId": cloud_session_id,
                    "streamTypes": new_stream_types
                })
            else:
                logger.error(f"❌ Failed to switch stream types for session {cloud_session_id}")
                await self.sio.emit('stream-type-switch-error', {
                    "sessionId": cloud_session_id,
                    "error": "Failed to switch stream types"
                })
                
        except Exception as e:
            logger.error(f"❌ Error switching stream types for session {cloud_session_id}: {e}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            await self.sio.emit('stream-type-switch-error', {
                "sessionId": cloud_session_id,
                "error": str(e)
            })
            
    async def handle_webrtc_answer(self, data: Dict[str, Any]):
        """Handle WebRTC answer from client"""
        session_id = data["sessionId"]
        answer = data["answer"]
        
        if session_id in self.sessions:
            try:
                session_data = self.sessions[session_id]
                webrtc_manager = session_data["webrtcManager"]
                
                # Process answer using local WebRTC manager
                await webrtc_manager.process_answer(
                    session_data["apiSessionId"],
                    answer["sdp"],
                    answer["type"]
                )
                logger.info(f"✅ Processed WebRTC answer for session {session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to process answer for session {session_id}: {e}")
        else:
            logger.warning(f"⚠️ Session {session_id} not found for answer")
                
    async def handle_ice_candidate(self, data: Dict[str, Any]):
        """Handle ICE candidate from client"""
        session_id = data["sessionId"]
        candidate = data["candidate"]
        
        if session_id in self.sessions:
            try:
                session_data = self.sessions[session_id]
                webrtc_manager = session_data["webrtcManager"]
                
                # Add ICE candidate using local WebRTC manager
                await webrtc_manager.add_ice_candidate(
                    session_data["apiSessionId"],
                    candidate["candidate"],
                    candidate["sdpMid"],
                    candidate["sdpMLineIndex"]
                )
                logger.debug(f"✅ Added ICE candidate for session {session_id}")
            except Exception as e:
                logger.error(f"❌ Failed to add ICE candidate for session {session_id}: {e}")
        else:
            logger.warning(f"⚠️ Session {session_id} not found for ICE candidate")
            
    async def handle_session_closed(self, data: Dict[str, Any]):
        """Handle session closure notification"""
        session_id = data["sessionId"]
        
        if session_id in self.sessions:
            logger.info(f"🗑️ Cleaning up session {session_id}")
            # Clean up WebRTC session using local WebRTC manager
            try:
                session_data = self.sessions[session_id]
                webrtc_manager = session_data["webrtcManager"]
                
                # Close session using local WebRTC manager
                await webrtc_manager.close_session(session_data["apiSessionId"])
                logger.info(f"✅ Closed WebRTC session {session_id}")
            except Exception as e:
                logger.error(f"❌ Error closing WebRTC session {session_id}: {e}")
            
            # Remove from local sessions
            del self.sessions[session_id]
        else:
            logger.warning(f"⚠️ Session {session_id} not found for cleanup")

# Global robot client instance
robot_client = None

async def start_robot_websocket_client():
    """Start the robot WebSocket client"""
    global robot_client
    
    # Configuration
    cloud_url = os.getenv('CLOUD_SIGNALING_URL', 'http://localhost:3001')
    robot_id = os.getenv('ROBOT_ID', 'robot-844212070924')
    
    logger.info(f"🤖 Starting robot WebSocket client")
    logger.info(f"🌐 Cloud URL: {cloud_url}")
    logger.info(f"🆔 Robot ID: {robot_id}")
    
    robot_client = RobotWebSocketClient(cloud_url, robot_id)
    await robot_client.connect()

async def stop_robot_websocket_client():
    """Stop the robot WebSocket client"""
    global robot_client
    
    if robot_client and robot_client.sio:
        logger.info("🛑 Stopping robot WebSocket client")
        await robot_client.sio.disconnect()
        robot_client.connected = False

# For testing
if __name__ == "__main__":
    asyncio.run(start_robot_websocket_client())
