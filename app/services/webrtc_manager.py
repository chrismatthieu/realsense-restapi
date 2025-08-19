import asyncio
import uuid
import weakref
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer
from aiortc.mediastreams import VideoStreamTrack
from av import VideoFrame
from app.core.errors import RealSenseError
from app.core.config import get_settings
from app.models.webrtc import WebRTCSession, WebRTCStatus

class RealSenseVideoTrack(VideoStreamTrack):
    """Video track that captures frames from RealSense camera."""

    def __init__(self, realsense_manager, device_id, stream_type, session_id=None):
        super().__init__()
        self.realsense_manager = realsense_manager
        self.device_id = device_id
        self.stream_type = stream_type
        self.session_id = session_id
        self._start = time.time()
        self._frame_count = 0
        self._last_frame_time = time.time()

    async def recv(self):
        try:
            # Get frame from RealSense
            frame_data = self.realsense_manager.get_latest_frame(self.device_id, self.stream_type)

            # Convert to RGB format if necessary
            if len(frame_data.shape) == 3 and frame_data.shape[2] == 3:
                # Already RGB, no conversion needed
                img = frame_data
            else:
                # Convert to RGB
                img = cv2.cvtColor(frame_data, cv2.COLOR_BGR2RGB)
            
            # Create VideoFrame
            video_frame = VideoFrame.from_ndarray(img, format="rgb24")

            # Set frame timestamp
            pts, time_base = await self.next_timestamp()
            video_frame.pts = pts
            video_frame.time_base = time_base

            # Update frame statistics
            self._frame_count += 1
            self._last_frame_time = time.time()

            return video_frame
        except Exception as e:
            # On error, return a black frame
            width, height = 640, 480  # Default size
            img = np.zeros((height, width, 3), dtype=np.uint8)
            video_frame = VideoFrame.from_ndarray(img, format="rgb24")
            pts, time_base = await self.next_timestamp()
            video_frame.pts = pts
            video_frame.time_base = time_base

            print(f"Error getting frame for session {self.session_id}: {str(e)}")
            return video_frame

class WebRTCManager:
    def __init__(self, realsense_manager):
        self.realsense_manager = realsense_manager
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        self.settings = get_settings()
        self.max_concurrent_sessions = 10  # Limit concurrent sessions
        self.session_timeout = 3600  # 1 hour timeout
        
        # Stream reference counting for independent browser management
        self.stream_references: Dict[str, Dict[str, int]] = {}  # device_id -> stream_type -> ref_count
        self.device_stream_configs: Dict[str, Dict[str, Any]] = {}  # device_id -> stream_config

        # Set up ICE servers for WebRTC
        self.ice_servers = []

        if self.settings.STUN_SERVER:
            self.ice_servers.append(RTCIceServer(urls=self.settings.STUN_SERVER))

        if self.settings.TURN_SERVER:
            self.ice_servers.append(
                RTCIceServer(
                    urls=self.settings.TURN_SERVER,
                    username=self.settings.TURN_USERNAME,
                    credential=self.settings.TURN_PASSWORD
                )
            )

    async def _ensure_device_stream(self, device_id: str, stream_types: List[str]) -> bool:
        """Ensure device stream is running for the requested stream types."""
        async with self.lock:
            # Initialize reference counting for this device if not exists
            if device_id not in self.stream_references:
                self.stream_references[device_id] = {}
            
            # Check if we need to start the device stream
            need_to_start_stream = False
            new_stream_configs = []
            
            # Validate stream types before processing
            valid_stream_types = ["color", "depth", "infrared-1", "infrared-2"]
            for stream_type in stream_types:
                if stream_type not in valid_stream_types:
                    raise RealSenseError(
                        status_code=400, 
                        detail=f"Invalid stream type: {stream_type}. Valid types are: {', '.join(valid_stream_types)}"
                    )
            
            for stream_type in stream_types:
                if stream_type not in self.stream_references[device_id]:
                    self.stream_references[device_id][stream_type] = 0
                    need_to_start_stream = True
                    
                    # Create stream config
                    stream_config = {
                        "sensor_id": f"{device_id}-sensor-0",
                        "stream_type": stream_type,
                        "format": "z16" if stream_type == "depth" else "y8" if stream_type.startswith("infrared") else "rgb8",
                        "resolution": {"width": 640, "height": 480},
                        "framerate": 30
                    }
                    new_stream_configs.append(stream_config)
                
                # Increment reference count
                self.stream_references[device_id][stream_type] += 1
            
            # Handle device stream configuration
            if need_to_start_stream:
                if device_id in self.device_stream_configs:
                    # Device is already streaming, we need to restart with new configuration
                    # Get existing configs and merge with new ones
                    existing_configs = self.device_stream_configs[device_id]["configs"]
                    
                    # Create a set of existing stream types to avoid duplicates
                    existing_stream_types = {config["stream_type"] for config in existing_configs}
                    
                    # Add new stream configs that don't already exist
                    for new_config in new_stream_configs:
                        if new_config["stream_type"] not in existing_stream_types:
                            existing_configs.append(new_config)
                    
                    # Update the device stream with merged configuration
                    try:
                        from app.models.stream import StreamConfig, Resolution
                        
                        # Convert all configs to StreamConfig objects
                        stream_configs = []
                        for config in existing_configs:
                            stream_config = StreamConfig(
                                sensor_id=config["sensor_id"],
                                stream_type=config["stream_type"],
                                format=config["format"],
                                resolution=Resolution(
                                    width=config["resolution"]["width"],
                                    height=config["resolution"]["height"]
                                ),
                                framerate=config["framerate"]
                            )
                            stream_configs.append(stream_config)
                        
                        # Stop current stream and restart with new configuration
                        self.realsense_manager.stop_stream(device_id)
                        self.realsense_manager.start_stream(device_id, stream_configs)
                        
                        # Update stored configuration
                        self.device_stream_configs[device_id] = {
                            "configs": existing_configs,
                            "started_at": time.time()
                        }
                        
                        print(f"Restarted device stream for {device_id} with {len(existing_configs)} stream types")
                    except Exception as e:
                        # Rollback reference counts on failure
                        for stream_type in stream_types:
                            if stream_type in self.stream_references[device_id]:
                                self.stream_references[device_id][stream_type] -= 1
                                if self.stream_references[device_id][stream_type] <= 0:
                                    del self.stream_references[device_id][stream_type]
                        raise RealSenseError(status_code=400, detail=f"Failed to restart device stream: {str(e)}")
                else:
                    # First time starting device stream
                    self.device_stream_configs[device_id] = {
                        "configs": new_stream_configs,
                        "started_at": time.time()
                    }
            
            return need_to_start_stream

    async def _decrement_stream_references(self, device_id: str, stream_types: List[str]):
        """Decrement reference counts and stop device stream if no more references."""
        async with self.lock:
            if device_id not in self.stream_references:
                return
            
            should_stop_device_stream = True
            removed_stream_types = []
            
            for stream_type in stream_types:
                if stream_type in self.stream_references[device_id]:
                    self.stream_references[device_id][stream_type] -= 1
                    
                    # If any stream type still has references, don't stop device stream
                    if self.stream_references[device_id][stream_type] > 0:
                        should_stop_device_stream = False
                    
                    # Clean up zero references
                    if self.stream_references[device_id][stream_type] <= 0:
                        del self.stream_references[device_id][stream_type]
                        removed_stream_types.append(stream_type)
            
            # If we removed stream types and device is still streaming, update configuration
            if removed_stream_types and device_id in self.device_stream_configs:
                try:
                    # Get current configuration and remove unused stream types
                    current_configs = self.device_stream_configs[device_id]["configs"]
                    updated_configs = [
                        config for config in current_configs 
                        if config["stream_type"] not in removed_stream_types
                    ]
                    
                    if updated_configs:
                        # Update device stream with remaining stream types
                        from app.models.stream import StreamConfig, Resolution
                        
                        stream_configs = []
                        for config in updated_configs:
                            stream_config = StreamConfig(
                                sensor_id=config["sensor_id"],
                                stream_type=config["stream_type"],
                                format=config["format"],
                                resolution=Resolution(
                                    width=config["resolution"]["width"],
                                    height=config["resolution"]["height"]
                                ),
                                framerate=config["framerate"]
                            )
                            stream_configs.append(stream_config)
                        
                        # Restart device stream with updated configuration
                        self.realsense_manager.stop_stream(device_id)
                        self.realsense_manager.start_stream(device_id, stream_configs)
                        
                        # Update stored configuration
                        self.device_stream_configs[device_id] = {
                            "configs": updated_configs,
                            "started_at": time.time()
                        }
                        
                        print(f"Updated device stream for {device_id} - removed {removed_stream_types}, now has {len(updated_configs)} stream types")
                    else:
                        # No more stream types, stop device stream
                        self.realsense_manager.stop_stream(device_id)
                        print(f"Stopped device stream for {device_id} - no more active stream types")
                        
                        # Clean up device references
                        del self.stream_references[device_id]
                        del self.device_stream_configs[device_id]
                        
                except Exception as e:
                    print(f"Error updating device stream configuration: {str(e)}")
            
            # If no more references for any stream type, stop device stream
            elif should_stop_device_stream and device_id in self.stream_references:
                if not any(self.stream_references[device_id].values()):
                    try:
                        # Stop the device stream
                        self.realsense_manager.stop_stream(device_id)
                        print(f"Stopped device stream for {device_id} - no more active sessions")
                        
                        # Clean up device references
                        del self.stream_references[device_id]
                        if device_id in self.device_stream_configs:
                            del self.device_stream_configs[device_id]
                    except Exception as e:
                        print(f"Error stopping device stream: {str(e)}")

    async def create_offer(self, device_id: str, stream_types: List[str]) -> Tuple[str, dict]:
        """Create a WebRTC offer for device streams."""
        # Check if we have too many active sessions
        async with self.lock:
            active_sessions = len([s for s in self.sessions.values() if s.get("connected", False)])
            if active_sessions >= self.max_concurrent_sessions:
                raise RealSenseError(
                    status_code=429, 
                    detail=f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached. Please wait for a session to close."
                )

        # Track if we need to rollback references on failure
        references_added = False
        session_id = None
        
        try:
            # Ensure device stream is running for requested stream types
            need_to_start_stream = await self._ensure_device_stream(device_id, stream_types)
            references_added = True
            
            if need_to_start_stream:
                # Start the device stream with the required configuration
                try:
                    from app.models.stream import StreamConfig, Resolution
                    
                    # Convert dictionary configs to StreamConfig objects
                    stream_configs = []
                    for config in self.device_stream_configs[device_id]["configs"]:
                        stream_config = StreamConfig(
                            sensor_id=config["sensor_id"],
                            stream_type=config["stream_type"],
                            format=config["format"],
                            resolution=Resolution(
                                width=config["resolution"]["width"],
                                height=config["resolution"]["height"]
                            ),
                            framerate=config["framerate"]
                        )
                        stream_configs.append(stream_config)
                    
                    self.realsense_manager.start_stream(device_id, stream_configs)
                    print(f"Started device stream for {device_id} with {len(stream_configs)} stream types")
                except Exception as e:
                    # Rollback reference counts on failure
                    await self._decrement_stream_references(device_id, stream_types)
                    references_added = False
                    raise RealSenseError(status_code=400, detail=f"Failed to start device stream: {str(e)}")

            # Verify device is streaming and requested stream types are available
            stream_status = self.realsense_manager.get_stream_status(device_id)
            if not stream_status.is_streaming:
                # Rollback reference counts if device is not streaming
                await self._decrement_stream_references(device_id, stream_types)
                references_added = False
                raise RealSenseError(status_code=400, detail=f"Device {device_id} is not streaming")

            # Verify requested stream types are available
            for stream_type in stream_types:
                if stream_type not in stream_status.active_streams:
                    # Rollback reference counts if stream type is not available
                    await self._decrement_stream_references(device_id, stream_types)
                    references_added = False
                    raise RealSenseError(status_code=400, detail=f"Stream type {stream_type} is not active")

            # Create peer connection
            pc = RTCPeerConnection(RTCConfiguration(iceServers=self.ice_servers))

            # Create session ID
            session_id = str(uuid.uuid4())

            # Add video tracks for each stream type
            video_tracks = []
            for stream_type in stream_types:
                video_track = RealSenseVideoTrack(self.realsense_manager, device_id, stream_type, session_id)
                pc.addTrack(video_track)
                video_tracks.append(video_track)

            # Set up connection state change handler
            async def on_connection_state_change():
                async with self.lock:
                    if session_id in self.sessions:
                        self.sessions[session_id]["connection_state"] = pc.connectionState
                        if pc.connectionState == "closed":
                            # Mark for cleanup
                            self.sessions[session_id]["should_cleanup"] = True

            pc.on("connectionstatechange", on_connection_state_change)

            # Create offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)

            # Store session
            async with self.lock:
                self.sessions[session_id] = {
                    "device_id": device_id,
                    "stream_types": stream_types,
                    "pc": pc,
                    "video_tracks": video_tracks,
                    "connected": False,
                    "connection_state": "new",
                    "created_at": time.time(),
                    "last_activity": time.time(),
                    "should_cleanup": False
                }

            # Schedule cleanup of unused sessions
            asyncio.create_task(self._cleanup_sessions())

            # Return session ID and offer
            return session_id, {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
            
        except Exception as e:
            # If we added references but failed later, roll them back
            if references_added:
                try:
                    await self._decrement_stream_references(device_id, stream_types)
                except Exception as rollback_error:
                    print(f"Error rolling back references: {str(rollback_error)}")
            
            # Re-raise the original exception
            raise e

    async def process_answer(self, session_id: str, sdp: str, type_: str) -> bool:
        """Process a WebRTC answer."""
        async with self.lock:
            if session_id not in self.sessions:
                raise RealSenseError(status_code=404, detail=f"Session {session_id} not found")

            session = self.sessions[session_id]
            pc = session["pc"]

            # Update last activity
            session["last_activity"] = time.time()

        # Set remote description
        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=type_))

            # Mark as connected
            async with self.lock:
                if session_id in self.sessions:
                    self.sessions[session_id]["connected"] = True
                    self.sessions[session_id]["last_activity"] = time.time()

            return True
        except Exception as e:
            raise RealSenseError(status_code=400, detail=f"Error processing answer: {str(e)}")

    async def add_ice_candidate(self, session_id: str, candidate: str, sdp_mid: str, sdp_mline_index: int) -> bool:
        """Add an ICE candidate to a session."""
        async with self.lock:
            if session_id not in self.sessions:
                raise RealSenseError(status_code=404, detail=f"Session {session_id} not found")

            session = self.sessions[session_id]
            pc = session["pc"]

            # Update last activity
            session["last_activity"] = time.time()

        # Add ICE candidate
        try:
            candidate_obj = RTCIceCandidate(
                component=1,
                foundation="0",
                ip="0.0.0.0",
                port=0,
                priority=0,
                protocol="udp",
                type="host",
                sdpMid=sdp_mid,
                sdpMLineIndex=sdp_mline_index
            )
            candidate_obj.candidate = candidate

            await pc.addIceCandidate(candidate_obj)
            return True
        except Exception as e:
            raise RealSenseError(status_code=400, detail=f"Error adding ICE candidate: {str(e)}")

    async def get_ice_candidates(self, session_id: str) -> List[dict]:
        """Get ICE candidates for a session."""
        async with self.lock:
            if session_id not in self.sessions:
                raise RealSenseError(status_code=404, detail=f"Session {session_id} not found")

            pc = self.sessions[session_id]["pc"]

        # ICE candidates would be sent via events in a real application
        # This is a placeholder for the API
        return []

    async def get_session(self, session_id: str) -> WebRTCStatus:
        """Get session status."""
        async with self.lock:
            if session_id not in self.sessions:
                raise RealSenseError(status_code=404, detail=f"Session {session_id} not found")

            session = self.sessions[session_id]
            pc = session["pc"]

        # Get WebRTC stats (if available)
        stats = None
        try:
            stats_dict = await pc.getStats()
            stats = {k: v.__dict__ for k, v in stats_dict.items()}
        except Exception:
            stats = None

        # Return session status
        return WebRTCStatus(
            session_id=session_id,
            device_id=session["device_id"],
            connected=session["connected"],
            streaming=session["connected"],
            stream_types=session["stream_types"],
            stats=stats
        )

    async def get_all_sessions(self) -> List[WebRTCStatus]:
        """Get status of all active sessions."""
        async with self.lock:
            sessions = []
            for session_id, session in self.sessions.items():
                try:
                    pc = session["pc"]
                    stats = None
                    try:
                        stats_dict = await pc.getStats()
                        stats = {k: v.__dict__ for k, v in stats_dict.items()}
                    except Exception:
                        stats = None

                    sessions.append(WebRTCStatus(
                        session_id=session_id,
                        device_id=session["device_id"],
                        connected=session["connected"],
                        streaming=session["connected"],
                        stream_types=session["stream_types"],
                        stats=stats
                    ))
                except Exception:
                    # Skip sessions that can't be queried
                    continue
            return sessions

    async def close_session(self, session_id: str) -> bool:
        """Close a WebRTC session."""
        async with self.lock:
            if session_id not in self.sessions:
                return False

            session = self.sessions[session_id]
            device_id = session["device_id"]
            stream_types = session["stream_types"]

        # Close peer connection
        try:
            await session["pc"].close()
        except Exception as e:
            print(f"Error closing peer connection for session {session_id}: {str(e)}")

        # Decrement stream references
        await self._decrement_stream_references(device_id, stream_types)

        # Remove session
        async with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
            return True

    async def close_all_sessions(self) -> int:
        """Close all active WebRTC sessions."""
        async with self.lock:
            session_ids = list(self.sessions.keys())

        closed_count = 0
        for session_id in session_ids:
            try:
                await self.close_session(session_id)
                closed_count += 1
            except Exception as e:
                print(f"Error closing session {session_id}: {str(e)}")

        return closed_count

    async def get_stream_reference_info(self) -> Dict[str, Any]:
        """Get information about stream references for debugging."""
        async with self.lock:
            return {
                "stream_references": self.stream_references.copy(),
                "device_stream_configs": {
                    device_id: {
                        "configs": config["configs"],
                        "started_at": config["started_at"]
                    }
                    for device_id, config in self.device_stream_configs.items()
                }
            }

    async def _cleanup_sessions(self):
        """Clean up old or disconnected sessions."""
        async with self.lock:
            now = time.time()
            session_ids = list(self.sessions.keys())

            for session_id in session_ids:
                session = self.sessions[session_id]

                # Remove sessions that should be cleaned up
                if session.get("should_cleanup", False):
                    try:
                        await session["pc"].close()
                    except Exception:
                        pass
                    
                    # Decrement stream references
                    device_id = session["device_id"]
                    stream_types = session["stream_types"]
                    await self._decrement_stream_references(device_id, stream_types)
                    
                    del self.sessions[session_id]
                    continue

                # Remove sessions older than timeout
                if now - session["created_at"] > self.session_timeout:
                    try:
                        await session["pc"].close()
                    except Exception:
                        pass
                    
                    # Decrement stream references
                    device_id = session["device_id"]
                    stream_types = session["stream_types"]
                    await self._decrement_stream_references(device_id, stream_types)
                    
                    del self.sessions[session_id]
                    continue

                # Remove sessions with no activity for 30 minutes
                if now - session["last_activity"] > 1800:  # 30 minutes
                    try:
                        await session["pc"].close()
                    except Exception:
                        pass
                    
                    # Decrement stream references
                    device_id = session["device_id"]
                    stream_types = session["stream_types"]
                    await self._decrement_stream_references(device_id, stream_types)
                    
                    del self.sessions[session_id]
                    continue

        # Schedule next cleanup
        await asyncio.sleep(60)  # Run cleanup every minute
        asyncio.create_task(self._cleanup_sessions())