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
        self.response_queue = []  # Queue to store responses when disconnected
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
                transports=['websocket', 'polling']
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
            # Send any queued responses
            await self.send_queued_responses()
            
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
        # Point cloud data is now handled via WebRTC data channels, not Socket.IO
        # self.sio.on('get-pointcloud-data', self.handle_get_pointcloud_data_direct)
        self.sio.on('activate-pointcloud', self.handle_activate_pointcloud_direct)
        self.sio.on('start-device-stream', self.handle_start_device_stream_direct)
        self.sio.on('stop-device-stream', self.handle_stop_device_stream_direct)
        
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
        """Handle reconnection with exponential backoff"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff
            logger.info(f"🔄 Reconnecting in {delay} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
            
            await asyncio.sleep(delay)
            
            try:
                await self.sio.connect(
                    self.cloud_url,
                    wait_timeout=10,
                    transports=['websocket', 'polling']
                )
                self.connected = True
                self.reconnect_attempts = 0
                logger.info("✅ Successfully reconnected to cloud signaling server")
                return
            except Exception as e:
                logger.error(f"❌ Reconnection attempt {self.reconnect_attempts} failed: {e}")
                self.connected = False
        
        logger.error(f"❌ Failed to reconnect after {self.max_reconnect_attempts} attempts")
        # Reset for next connection attempt
        self.reconnect_attempts = 0
            
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

    async def send_queued_responses(self):
        """Send any queued responses when connection is restored."""
        if not self.response_queue:
            return
            
        logger.info(f"📤 Sending {len(self.response_queue)} queued responses")
        for event_type, data in self.response_queue:
            try:
                await self.sio.emit(event_type, data)
                logger.info(f"✅ Sent queued {event_type} response")
            except Exception as e:
                logger.error(f"❌ Failed to send queued {event_type} response: {e}")
        
        self.response_queue.clear()
        logger.info("✅ Cleared response queue")

    async def queue_response(self, event_type: str, data: dict):
        """Queue a response to be sent when connection is restored."""
        self.response_queue.append((event_type, data))
        logger.info(f"📥 Queued {event_type} response (queue size: {len(self.response_queue)})")
            
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
            
            from app.api.dependencies import get_webrtc_manager

            webrtc_manager = get_webrtc_manager()

            offer_response = await webrtc_manager.create_offer(device_id, stream_types, session_id)
            
            if offer_response:
                api_session_id, offer_dict = offer_response
                sdp = offer_dict["sdp"]
                sdp_type = offer_dict["type"]
                
                # Store session info
                self.sessions[session_id] = {
                    "deviceId": device_id,
                    "streamTypes": stream_types,
                    "apiSessionId": api_session_id,
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

        from app.api.dependencies import get_webrtc_manager

        webrtc_manager = get_webrtc_manager()

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
                from app.api.dependencies import get_webrtc_manager

                await get_webrtc_manager().process_answer(
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

        if session_id in self.sessions:
            try:
                session_data = self.sessions[session_id]
                from app.api.dependencies import get_webrtc_manager

                cand = data.get("candidate")
                if cand is None:
                    await get_webrtc_manager().add_ice_candidate(
                        session_data["apiSessionId"], None, None, 0
                    )
                    return
                if isinstance(cand, dict):
                    line = cand.get("candidate")
                    mid = cand.get("sdpMid")
                    mline = int(cand.get("sdpMLineIndex", 0) or 0)
                else:
                    line = str(cand) if cand else None
                    mid = data.get("sdpMid")
                    mline = int(data.get("sdpMLineIndex", 0) or 0)

                await get_webrtc_manager().add_ice_candidate(
                    session_data["apiSessionId"], line, mid, mline
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
                from app.api.dependencies import get_webrtc_manager

                await get_webrtc_manager().close_session(session_data["apiSessionId"])
                logger.info(f"✅ Closed WebRTC session {session_id}")
            except Exception as e:
                logger.error(f"❌ Error closing WebRTC session {session_id}: {e}")
            
            # Remove from local sessions
            del self.sessions[session_id]
        else:
            logger.warning(f"⚠️ Session {session_id} not found for cleanup")

    async def handle_get_pointcloud_data_direct(self, data: Dict[str, Any]):
        """Direct handler for get-pointcloud-data event."""
        logger.info(f"🎯 Direct get-pointcloud-data handler called with data: {data}")
        await self.handle_get_pointcloud_data(data)

    async def handle_get_pointcloud_data(self, data: Dict[str, Any]):
        """Handle point cloud data request."""
        try:
            device_id = data.get('deviceId')
            logger.info(f"📡 Requesting point cloud data for device {device_id}")
            
            # Get point cloud data from RealSense manager
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://localhost:8000/api/webrtc/pointcloud-data/{device_id}') as response:
                    if response.status == 200:
                        pointcloud_data = await response.json()
                        logger.info(f"✅ Retrieved point cloud data for device {device_id}")
                        # Point cloud data is now sent via WebRTC data channels, not Socket.IO
                        # if self.sio.connected:
                        #     await self.sio.emit('pointcloud-data', pointcloud_data)
                        # else:
                        #     logger.warning("⚠️ Socket.IO not connected, queuing point cloud data")
                        #     await self.queue_response('pointcloud-data', pointcloud_data)
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to get point cloud data: {error_text}")
                        # Point cloud errors are now handled via WebRTC data channels, not Socket.IO
                        # if self.sio.connected:
                        #     await self.sio.emit('pointcloud-error', {'error': f'Failed to get point cloud data: {error_text}'})
                        # else:
                        #     logger.warning("⚠️ Socket.IO not connected, queuing error")
                        #     await self.queue_response('pointcloud-error', {'error': f'Failed to get point cloud data: {error_text}'})
                        
        except Exception as e:
            logger.error(f"❌ Error getting point cloud data: {e}")
            # Point cloud errors are now handled via WebRTC data channels, not Socket.IO
            # if self.sio.connected:
            #     await self.sio.emit('pointcloud-error', {'error': f'Error getting point cloud data: {str(e)}'})
            # else:
            #     logger.warning("⚠️ Socket.IO not connected, queuing error")
            #     await self.queue_response('pointcloud-error', {'error': f'Error getting point cloud data: {str(e)}'})

    async def handle_activate_pointcloud_direct(self, data: Dict[str, Any]):
        """Direct handler for activate-pointcloud event."""
        logger.info(f"🎯 Direct activate-pointcloud handler called with data: {data}")
        await self.handle_activate_pointcloud(data)

    async def handle_activate_pointcloud(self, data: Dict[str, Any]):
        """Handle point cloud activation request."""
        try:
            device_id = data.get('deviceId')
            enabled = data.get('enabled', data.get('activate', True))
            logger.info(f"📡 {'Activating' if enabled else 'Deactivating'} point cloud for device {device_id}")
            
            # Activate/deactivate point cloud via RealSense manager
            import aiohttp
            async with aiohttp.ClientSession() as session:
                path = "activate" if enabled else "deactivate"
                async with session.post(
                    f"http://localhost:8000/api/devices/{device_id}/point_cloud/{path}",
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ {'Activated' if enabled else 'Deactivated'} point cloud for device {device_id}")
                        # Send back to cloud server
                        if self.sio.connected:
                            await self.sio.emit('pointcloud-activated', result)
                        else:
                            logger.warning("⚠️ Socket.IO not connected, queuing activation confirmation")
                            await self.queue_response('pointcloud-activated', result)
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to activate point cloud: {error_text}")
                        if self.sio.connected:
                            await self.sio.emit('pointcloud-error', {'error': f'Failed to activate point cloud: {error_text}'})
                        else:
                            logger.warning("⚠️ Socket.IO not connected, queuing error")
                            await self.queue_response('pointcloud-error', {'error': f'Failed to activate point cloud: {error_text}'})
                        
        except Exception as e:
            logger.error(f"❌ Error activating point cloud: {e}")
            if self.sio.connected:
                await self.sio.emit('pointcloud-error', {'error': f'Error activating point cloud: {str(e)}'})
            else:
                logger.warning("⚠️ Socket.IO not connected, queuing error")
                await self.queue_response('pointcloud-error', {'error': f'Error activating point cloud: {str(e)}'})

    async def handle_start_device_stream_direct(self, data: Dict[str, Any]):
        """Direct handler for start-device-stream event."""
        logger.info(f"🎯 Direct start-device-stream handler called with data: {data}")
        await self.handle_start_device_stream(data)

    async def handle_start_device_stream(self, data: Dict[str, Any]):
        """Handle device stream start request."""
        try:
            device_id = data.get('deviceId')
            stream_configs = data.get('streamConfigs', [])
            logger.info(f"🚀 Starting device stream for {device_id} with configs: {stream_configs}")
            
            # Call local API to start device stream
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://localhost:8000/api/devices/{device_id}/streams/start",
                    json={"stream_configs": stream_configs}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Device stream started: {result}")
                        # Forward success response back to client
                        await self.sio.emit('device-stream-started', {"deviceId": device_id, "result": result})
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to start device stream: {error_text}")
                        await self.sio.emit('pointcloud-error', {"error": f"Failed to start device stream: {error_text}"})
        except Exception as e:
            logger.error(f"❌ Error starting device stream: {str(e)}")
            await self.sio.emit('pointcloud-error', {"error": f"Error starting device stream: {str(e)}"})

    async def handle_stop_device_stream_direct(self, data: Dict[str, Any]):
        """Direct handler for stop-device-stream event."""
        logger.info(f"🎯 Direct stop-device-stream handler called with data: {data}")
        await self.handle_stop_device_stream(data)

    async def handle_stop_device_stream(self, data: Dict[str, Any]):
        """Handle device stream stop request."""
        try:
            device_id = data.get('deviceId')
            logger.info(f"⏹️ Stopping device stream for {device_id}")
            
            # Call local API to stop device stream
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://localhost:8000/api/devices/{device_id}/streams/stop"
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Device stream stopped: {result}")
                        # Forward success response back to client
                        await self.sio.emit('device-stream-stopped', {"deviceId": device_id, "result": result})
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to stop device stream: {error_text}")
                        await self.sio.emit('pointcloud-error', {"error": f"Failed to stop device stream: {error_text}"})
        except Exception as e:
            logger.error(f"❌ Error stopping device stream: {str(e)}")
            await self.sio.emit('pointcloud-error', {"error": f"Error stopping device stream: {str(e)}"})

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
    """Stop the robot WebSocket client and close aiohttp session to avoid 'Unclosed client session' warning."""
    global robot_client

    if not robot_client:
        return
    if robot_client.sio:
        logger.info("🛑 Stopping robot WebSocket client")
        try:
            await robot_client.sio.disconnect()
        except Exception as e:
            logger.debug("Disconnect: %s", e)
        robot_client.connected = False
        # Explicitly close engineio's aiohttp session (avoids "Unclosed client session" on shutdown)
        eio = getattr(robot_client.sio, "eio", None)
        if eio is not None:
            http = getattr(eio, "http", None)
            if http is not None and not getattr(http, "closed", True):
                try:
                    await http.close()
                except Exception:
                    pass

# For testing
if __name__ == "__main__":
    asyncio.run(start_robot_websocket_client())
