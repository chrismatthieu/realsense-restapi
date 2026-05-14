import asyncio
import uuid
import weakref
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import cv2
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer,
    RTCBundlePolicy,
)
from aiortc.mediastreams import VideoStreamTrack
from av import VideoFrame
from app.core.errors import RealSenseError
from app.core.config import get_settings
from app.models.webrtc import WebRTCSession, WebRTCStatus

def safe_convert_vertices(vertices):
    """Safely convert vertices to a Python list, handling NumPy arrays and other types."""
    if vertices is None:
        return []
    
    # If it's already a list, return it
    if isinstance(vertices, list):
        return vertices
    
    # If it's a NumPy array, convert to list
    if hasattr(vertices, 'tolist'):
        try:
            return vertices.tolist()
        except Exception as e:
            print(f"❌ Error converting NumPy array to list: {e}")
            return []
    
    # If it's a string, it's corrupted data
    if isinstance(vertices, str):
        print(f"❌ Vertices is a string (corrupted data), returning empty list")
        return []
    
    # Try to convert to list
    try:
        return list(vertices)
    except Exception as e:
        print(f"❌ Cannot convert vertices to list: {type(vertices)}, error: {e}")
        return []

def safe_len(vertices):
    """Safely get the length of vertices, handling NumPy arrays."""
    if vertices is None:
        return 0

    if isinstance(vertices, np.ndarray):
        if vertices.ndim >= 2 and vertices.shape[1] >= 3:
            return int(vertices.shape[0])
        if vertices.ndim == 1 and vertices.size % 3 == 0:
            return int(vertices.size // 3)
        return int(vertices.size)

    # Convert to list first if it's a NumPy array
    if hasattr(vertices, 'tolist') and not isinstance(vertices, np.ndarray):
        try:
            vertices = vertices.tolist()
        except Exception:
            return 0
    
    # Now it should be a list or similar
    try:
        return len(vertices)
    except Exception:
        return 0


def normalize_vertices_for_json(vertices):
    """Turn mixed numpy/list vertex rows into plain [[x,y,z], ...] for JSON + browser."""
    if not vertices:
        return []
    out = []
    for v in vertices:
        if v is None:
            continue
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            try:
                out.append([float(v[0]), float(v[1]), float(v[2])])
            except (TypeError, ValueError):
                continue
            continue
        if isinstance(v, np.ndarray) and v.size >= 3:
            try:
                a = np.asarray(v, dtype=np.float64).reshape(-1)[:3]
                out.append([float(a[0]), float(a[1]), float(a[2])])
            except Exception:
                continue
            continue
        if hasattr(v, "__iter__") and not isinstance(v, (str, bytes, dict)):
            try:
                t = list(v)
                if len(t) >= 3:
                    out.append([float(t[0]), float(t[1]), float(t[2])])
            except Exception:
                continue
    return out


def vertices_to_json_list(vertices_data: Any, max_vertices: int = 3000) -> list:
    """
    Build a small JSON-friendly [[x,y,z], ...] list for the data channel.

    RealSense depth clouds are often ~200k–300k points. The old path called
    ``.tolist()`` on the full ndarray then normalized every row in Python, which
    blocked the asyncio event loop for many seconds (or OOM), so nothing was
    ever sent despite the SCTP channel being open.
    """
    if vertices_data is None:
        return []
    max_vertices = max(1, int(max_vertices))

    # Already small list/tuple rows
    if isinstance(vertices_data, list):
        if len(vertices_data) <= max_vertices:
            return normalize_vertices_for_json(vertices_data)
        return normalize_vertices_for_json(vertices_data[:max_vertices])

    if isinstance(vertices_data, np.ndarray):
        v = np.ascontiguousarray(vertices_data)
        if v.dtype.names:
            try:
                names = list(v.dtype.names)[:3]
                v = np.stack([v[n].astype(np.float64, copy=False) for n in names], axis=-1)
            except Exception:
                v = np.ascontiguousarray(v.astype(np.float64))
        else:
            v = np.ascontiguousarray(v.astype(np.float64, copy=False))

        if v.ndim == 1:
            if v.size % 3 != 0 or v.size == 0:
                return normalize_vertices_for_json(safe_convert_vertices(vertices_data))
            v = v.reshape(-1, 3)
        elif v.ndim == 2:
            if v.shape[1] < 3:
                return []
            v = v[:, :3]
        else:
            return normalize_vertices_for_json(safe_convert_vertices(vertices_data))

        finite = np.isfinite(v).all(axis=1)
        v = v[finite]
        n = v.shape[0]
        if n == 0:
            return []
        if n > max_vertices:
            # Evenly spaced indices across the cloud (cheap vs random)
            idx = np.linspace(0, n - 1, max_vertices, dtype=np.int64)
            v = v[idx]
        return v.tolist()

    # Slow path for exotic iterators (keep small)
    conv = safe_convert_vertices(vertices_data)
    if len(conv) > max_vertices:
        conv = conv[:max_vertices]
    return normalize_vertices_for_json(conv)


def frame_to_rgb(frame_data: np.ndarray, stream_type: str) -> np.ndarray:
    """Convert RealSense frame arrays (grayscale, BGR, BGRA, or RGB) to RGB uint8 for VideoFrame."""
    if frame_data is None:
        raise ValueError("empty frame")

    if not frame_data.flags["C_CONTIGUOUS"]:
        frame_data = np.ascontiguousarray(frame_data)

    # Some librealsense / numpy paths expose get_data() as a 1D buffer
    if frame_data.ndim == 1:
        n = int(frame_data.size)
        reshaped = None
        for h, w in ((480, 640), (720, 1280), (480, 848), (800, 1280)):
            for c in (3, 4):
                if n == h * w * c:
                    reshaped = frame_data.reshape((h, w, c))
                    break
            if reshaped is not None:
                break
        if reshaped is None:
            raise ValueError(f"Cannot reshape 1D frame buffer of size {n} for stream {stream_type}")
        frame_data = reshaped

    if len(frame_data.shape) == 2:
        if frame_data.dtype == np.uint16:
            norm = cv2.normalize(frame_data, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            return cv2.cvtColor(norm, cv2.COLOR_GRAY2RGB)
        return cv2.cvtColor(frame_data, cv2.COLOR_GRAY2RGB)

    if len(frame_data.shape) == 3 and frame_data.shape[2] == 2:
        return cv2.cvtColor(frame_data[:, :, 0], cv2.COLOR_GRAY2RGB)

    if len(frame_data.shape) == 3 and frame_data.shape[2] == 4:
        # Colorized depth is often BGRA from librealsense get_data()
        return cv2.cvtColor(frame_data, cv2.COLOR_BGRA2RGB)

    if len(frame_data.shape) == 3 and frame_data.shape[2] == 3:
        # Color camera rgb8 is already RGB order; depth colorizer / IR pseudo-color often BGR.
        if stream_type == "color":
            return frame_data
        return cv2.cvtColor(frame_data, cv2.COLOR_BGR2RGB)

    raise ValueError(f"Unsupported frame shape {frame_data.shape} for stream {stream_type}")


def hardware_stream_keys_for_request(stream_types: List[str]) -> set:
    """Map logical WebRTC stream types to RealSense pipeline keys in active_streams / frame queues."""
    keys = set()
    for st in stream_types:
        if st == "pointcloud":
            keys.add("depth")
        else:
            keys.add(st)
    return keys


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

    def switch_stream_type(self, new_stream_type: str):
        """Switch the stream type for this video track."""
        print(f"🔄 Switching video track from {self.stream_type} to {new_stream_type}")
        self.stream_type = new_stream_type

    async def recv(self):
        try:
            # Get frame from RealSense
            frame_data = self.realsense_manager.get_latest_frame(self.device_id, self.stream_type)
            img = frame_to_rgb(frame_data, self.stream_type)
            
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

class PointCloudVideoTrack(VideoStreamTrack):
    """Video track that sends point cloud data for 3D rendering."""

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
            # Get frame from RealSense (this will be depth frame)
            frame_data = self.realsense_manager.get_latest_frame(self.device_id, "depth")
            
            # Temporarily disable metadata retrieval to avoid NumPy array errors
            # TODO: Re-enable once NumPy array issues are resolved
            # Get metadata separately to check for point cloud data
            # try:
            #     metadata = self.realsense_manager.get_latest_metadata(self.device_id, "depth")
            #     # Temporarily disable point cloud visualization to isolate NumPy array error
            #     # TODO: Re-enable once NumPy array issues are resolved
            #     # Check if point cloud data is available
            #     # if "point_cloud" in metadata and metadata["point_cloud"].get("vertices") is not None:
            #     #     vertices = metadata["point_cloud"]["vertices"]
            #     #     # Use safe_len to avoid NumPy array boolean context issues
            #     #     if safe_len(vertices) > 0:
            #     #         # Create a visualization frame with point cloud data encoded
            #     #         img = self._create_point_cloud_visualization(vertices)
            #     #     else:
            #     #         # Fallback to depth frame if no valid vertices
            #     #         img = frame_data
            #     # else:
            #     #     # Fallback to depth frame if no point cloud data
            #     img = frame_data
            # except Exception as e:
            #     # If metadata is not available, use depth frame
            #     print(f"Warning: Could not get metadata for point cloud: {str(e)}")
            #     img = frame_data
            img = frame_to_rgb(frame_data, "depth")
            
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

            print(f"Error getting point cloud frame for session {self.session_id}: {str(e)}")
            return video_frame

    def _create_point_cloud_visualization(self, vertices):
        """Create a visualization frame that encodes point cloud data for 3D rendering."""
        # Safely convert vertices to list
        vertices = safe_convert_vertices(vertices)
        
        if safe_len(vertices) == 0:
            # Return black image if no vertices
            return np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Create a visualization that shows point cloud info
        width, height = 640, 480
        img = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add text overlay with point cloud information
        text_lines = [
            f"Point Cloud: {safe_len(vertices)} vertices",
            "3D Interactive View Available",
            "Use mouse to rotate/zoom",
            "Loading 3D data..."
        ]
        
        y_offset = 50
        for i, line in enumerate(text_lines):
            y = y_offset + i * 30
            # Add text with white color
            cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add a simple 3D-like visualization (placeholder)
        # This will be replaced by the actual 3D rendering in the browser
        center_x, center_y = width // 2, height // 2
        radius = 100
        
        # Draw a circle to indicate 3D content
        cv2.circle(img, (center_x, center_y), radius, (0, 255, 255), 3)
        cv2.putText(img, "3D", (center_x - 20, center_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        return img

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
            valid_stream_types = ["color", "depth", "infrared-1", "infrared-2", "pointcloud"]
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
                    if stream_type == "pointcloud":
                        # For pointcloud, we only need the depth stream
                        stream_config = {
                            "sensor_id": f"{device_id}-sensor-0",
                            "stream_type": "depth",  # Use depth stream for pointcloud
                            "format": "z16",
                            "resolution": {"width": 640, "height": 480},
                            "framerate": 30
                        }
                    else:
                        stream_config = {
                            "sensor_id": f"{device_id}-sensor-0",
                            "stream_type": stream_type,
                            "format": "z16" if stream_type == "depth" else "y8" if stream_type.startswith("infrared") else "rgb8",
                            "resolution": {"width": 640, "height": 480},
                            "framerate": 30
                        }
                    new_stream_configs.append(stream_config)
                
                # Increment reference count
                if stream_type == "pointcloud":
                    # For pointcloud, increment both pointcloud and depth reference counts
                    if "pointcloud" not in self.stream_references[device_id]:
                        self.stream_references[device_id]["pointcloud"] = 0
                    if "depth" not in self.stream_references[device_id]:
                        self.stream_references[device_id]["depth"] = 0
                    self.stream_references[device_id]["pointcloud"] += 1
                    self.stream_references[device_id]["depth"] += 1
                else:
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
                        
                        # Enable point cloud when depth is streamed (WebRTC sends vertices on data channel)
                        if any(st == "pointcloud" for st in stream_types) or any(st == "depth" for st in stream_types):
                            self.realsense_manager.activate_point_cloud(device_id, True)
                        
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
                    try:
                        from app.models.stream import StreamConfig, Resolution
                        
                        # Convert configs to StreamConfig objects
                        stream_configs = []
                        for config in new_stream_configs:
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
                        
                        # Start the actual RealSense stream
                        print(f"Starting device stream for {device_id} with {len(stream_configs)} stream types")
                        self.realsense_manager.start_stream(device_id, stream_configs)
                        
                        # Enable point cloud when depth is streamed (WebRTC sends vertices on data channel)
                        if any(st == "pointcloud" for st in stream_types) or any(st == "depth" for st in stream_types):
                            self.realsense_manager.activate_point_cloud(device_id, True)
                        
                        # Store configuration after successful start
                        self.device_stream_configs[device_id] = {
                            "configs": new_stream_configs,
                            "started_at": time.time()
                        }
                        
                        print(f"Started device stream for {device_id} with {len(new_stream_configs)} stream types")
                    except Exception as e:
                        # Rollback reference counts on failure
                        for stream_type in stream_types:
                            if stream_type in self.stream_references[device_id]:
                                self.stream_references[device_id][stream_type] -= 1
                                if self.stream_references[device_id][stream_type] <= 0:
                                    del self.stream_references[device_id][stream_type]
                        raise RealSenseError(status_code=400, detail=f"Failed to start device stream: {str(e)}")
                    
                    # Small delay to prevent race conditions
                    await asyncio.sleep(0.05)
            
            return need_to_start_stream

    async def _decrement_stream_references(self, device_id: str, stream_types: List[str]):
        """Decrement reference counts and stop device stream if no more references."""
        async with self.lock:
            if device_id not in self.stream_references:
                return
            
            should_stop_device_stream = True
            removed_stream_types = []
            
            for stream_type in stream_types:
                if stream_type == "pointcloud":
                    # For pointcloud, decrement both pointcloud and depth reference counts
                    if "pointcloud" in self.stream_references[device_id]:
                        self.stream_references[device_id]["pointcloud"] -= 1
                        if self.stream_references[device_id]["pointcloud"] <= 0:
                            del self.stream_references[device_id]["pointcloud"]
                    
                    if "depth" in self.stream_references[device_id]:
                        self.stream_references[device_id]["depth"] -= 1
                        
                        # If depth still has references, don't stop device stream
                        if self.stream_references[device_id]["depth"] > 0:
                            should_stop_device_stream = False
                        
                        # Clean up zero references
                        if self.stream_references[device_id]["depth"] <= 0:
                            del self.stream_references[device_id]["depth"]
                            removed_stream_types.append("depth")
                elif stream_type in self.stream_references[device_id]:
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
                        
                        try:
                            # Stop current stream first
                            self.realsense_manager.stop_stream(device_id)
                            
                            # Wait a moment for cleanup
                            await asyncio.sleep(0.1)
                            
                            # Start new stream with updated configuration
                            self.realsense_manager.start_stream(device_id, stream_configs)
                            
                            # Point cloud vertices: keep on while any depth or pointcloud consumer exists
                            refs = self.stream_references.get(device_id, {})
                            depth_refs = int(refs.get("depth", 0) or 0)
                            pc_refs = int(refs.get("pointcloud", 0) or 0)
                            if depth_refs <= 0 and pc_refs <= 0:
                                self.realsense_manager.activate_point_cloud(device_id, False)
                            else:
                                self.realsense_manager.activate_point_cloud(device_id, True)
                            
                            # Update stored configuration
                            self.device_stream_configs[device_id] = {
                                "configs": updated_configs,
                                "started_at": time.time()
                            }
                        except Exception as e:
                            print(f"Error updating device stream configuration: {str(e)}")
                            # If update fails, try to restart with original configuration
                            try:
                                self.realsense_manager.stop_stream(device_id)
                                await asyncio.sleep(0.1)
                                # Restart with original configs
                                original_configs = []
                                for config in current_configs:
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
                                    original_configs.append(stream_config)
                                self.realsense_manager.start_stream(device_id, original_configs)
                            except Exception as restart_error:
                                print(f"Failed to restart with original configuration: {str(restart_error)}")
                        
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

    async def create_offer(self, device_id: str, stream_types: List[str], session_id: str = None) -> Tuple[str, dict]:
        """Create a WebRTC offer for device streams."""
        # Count all signaling + active PCs (half-open sessions used to be ignored and could pile up).
        async with self.lock:
            active_sessions = len(self.sessions)
            if active_sessions >= self.max_concurrent_sessions:
                raise RealSenseError(
                    status_code=429, 
                    detail=f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached. Please wait for a session to close."
                )

        # Re-use the same cloud session id: close any stale PC first (client retry / partial negotiate).
        if session_id:
            async with self.lock:
                stale = session_id in self.sessions
            if stale:
                await self.close_session(session_id)

        # Track if we need to rollback references on failure
        references_added = False
        
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
            # Add retry mechanism for stream activation
            max_retries = 5
            retry_delay = 0.5  # seconds
            
            for attempt in range(max_retries):
                stream_status = self.realsense_manager.get_stream_status(device_id)
                
                if not stream_status.is_streaming:
                    if attempt < max_retries - 1:
                        print(f"Device {device_id} not streaming yet, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        # Rollback reference counts if device is not streaming
                        await self._decrement_stream_references(device_id, stream_types)
                        references_added = False
                        raise RealSenseError(status_code=400, detail=f"Device {device_id} is not streaming after {max_retries} attempts")

                # Check if all requested stream types are available
                missing_streams = []
                for stream_type in stream_types:
                    if stream_type == "pointcloud":
                        # For pointcloud, check if depth stream is available
                        if "depth" not in stream_status.active_streams:
                            missing_streams.append("depth (required for pointcloud)")
                    elif stream_type not in stream_status.active_streams:
                        missing_streams.append(stream_type)
                
                if missing_streams:
                    if attempt < max_retries - 1:
                        print(f"Stream types {missing_streams} not active yet, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        # Rollback reference counts if stream types are not available
                        await self._decrement_stream_references(device_id, stream_types)
                        references_added = False
                        raise RealSenseError(status_code=400, detail=f"Stream types {missing_streams} are not active after {max_retries} attempts")
                
                # All streams are active, break out of retry loop
                print(f"All requested stream types are active after {attempt + 1} attempts")
                break

            # Create peer connection
            # MAX_BUNDLE + createDataChannel *after* addTrack so SCTP reuses the first media
            # transport's ICE/DTLS. Creating the channel first gives SCTP its own gatherer;
            # the browser then often completes video ICE but not SCTP, so the data channel
            # never opens and point cloud stays at 0 vertices.
            pc = RTCPeerConnection(
                RTCConfiguration(
                    iceServers=self.ice_servers,
                    bundlePolicy=RTCBundlePolicy.MAX_BUNDLE,
                )
            )

            # Use provided session ID or generate a new one
            if session_id is None:
                session_id = str(uuid.uuid4())

            # Add video tracks for each stream type (must exist before createDataChannel for bundling)
            video_tracks = []
            for stream_type in stream_types:
                if stream_type == "pointcloud":
                    # Use special point cloud video track
                    video_track = PointCloudVideoTrack(self.realsense_manager, device_id, stream_type, session_id)
                else:
                    # Use regular video track
                    video_track = RealSenseVideoTrack(self.realsense_manager, device_id, stream_type, session_id)
                pc.addTrack(video_track)
                video_tracks.append(video_track)

            # Create data channel for point cloud data when depth or pointcloud session is active
            data_channel = None
            if "depth" in stream_types or "pointcloud" in stream_types:
                # Negotiated id must match realsense-react-client PointCloudDemo.js (id: 0).
                # Some browsers never fire ondatachannel for aiortc's DCEP-open path while ICE is fine.
                data_channel = pc.createDataChannel(
                    "pointcloud-data",
                    negotiated=True,
                    id=0,
                )
                _loop = asyncio.get_running_loop()

                @data_channel.on("open")
                def on_open():
                    print(f"📡 Data channel opened for session {session_id}")
                    try:
                        _loop.create_task(self._send_point_cloud_data(session_id, device_id))
                    except Exception as e:
                        import traceback
                        print(f"❌ Failed to schedule point cloud sender: {e}\n{traceback.format_exc()}")
                
                @data_channel.on("close")
                def on_close():
                    print(f"📡 Data channel closed for session {session_id}")

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
                    "data_channel": data_channel,
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

            # Fallback: SCTP "open" can race with handler registration; start sender if channel already open
            async def _maybe_start_point_cloud_sender_delayed():
                await asyncio.sleep(0.5)
                async with self.lock:
                    s = self.sessions.get(session_id)
                    if not s or s.get("point_cloud_sender_running"):
                        return
                    dc = s.get("data_channel")
                    dev = s.get("device_id")
                    if not dc or not dev:
                        return
                    if getattr(dc, "readyState", None) != "open":
                        return
                    st = s.get("stream_types") or []
                    if "depth" not in st and "pointcloud" not in st:
                        return
                _loop = asyncio.get_running_loop()
                _loop.create_task(self._send_point_cloud_data(session_id, dev))

            asyncio.create_task(_maybe_start_point_cloud_sender_delayed())

            return True
        except Exception as e:
            raise RealSenseError(status_code=400, detail=f"Error processing answer: {str(e)}")

    async def add_ice_candidate(
        self,
        session_id: str,
        candidate: Optional[str],
        sdp_mid: Optional[str],
        sdp_mline_index: int,
    ) -> bool:
        """Add trickle ICE from the browser. Invalid host candidates prevented SCTP (data channels) from working."""
        from aiortc.sdp import candidate_from_sdp

        async with self.lock:
            if session_id not in self.sessions:
                raise RealSenseError(status_code=404, detail=f"Session {session_id} not found")

            session = self.sessions[session_id]
            pc = session["pc"]
            session["last_activity"] = time.time()

        try:
            if candidate is None or (isinstance(candidate, str) and not candidate.strip()):
                await pc.addIceCandidate(None)
                return True

            line = candidate.strip()
            if line.startswith("candidate:"):
                line = line[len("candidate:") :].lstrip()

            cand = candidate_from_sdp(line)
            cand.sdpMid = sdp_mid
            cand.sdpMLineIndex = int(sdp_mline_index)

            await pc.addIceCandidate(cand)
            return True
        except Exception as e:
            print(f"❌ Error adding ICE candidate: {e}")
            return False

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

    async def switch_stream_type(self, session_id: str, new_stream_types: List[str]) -> bool:
        """Switch stream types within an existing WebRTC session."""
        try:
            async with asyncio.timeout(10.0):  # 10 second timeout for entire operation
                # First, get session info while holding the lock
                async with self.lock:
                    if session_id not in self.sessions:
                        raise RealSenseError(status_code=404, detail=f"Session {session_id} not found")

                    session = self.sessions[session_id]
                    device_id = session["device_id"]
                    video_tracks = session["video_tracks"]
                    old_stream_types = session["stream_types"]

                    print(f"🔄 Switching stream types for session {session_id} from {old_stream_types} to {new_stream_types}")

                    # Update stream types in session first
                    session["stream_types"] = new_stream_types
                    session["last_activity"] = time.time()

                # Release lock before calling _ensure_device_stream to avoid deadlock
                print(f"🚀 Starting new device stream for {device_id} with types: {new_stream_types}")
                print(f"🔍 About to call _ensure_device_stream...")
                await self._ensure_device_stream(device_id, new_stream_types)
                print(f"✅ _ensure_device_stream completed")

                # Wait for new stream to be fully active
                max_retries = 5
                retry_delay = 0.2
                for attempt in range(max_retries):
                    stream_status = self.realsense_manager.get_stream_status(device_id)
                    active_streams = set(stream_status.active_streams)
                    required = hardware_stream_keys_for_request(new_stream_types)
                    
                    if required.issubset(active_streams):
                        print(f"✅ New stream types {new_stream_types} are active after {attempt + 1} attempts")
                        print(f"📊 Active streams: {active_streams}")
                        break
                    print(f"⏳ Waiting for new stream types to activate (attempt {attempt + 1}/{max_retries})")
                    print(f"📊 Current active streams: {active_streams}, waiting for hardware keys: {required}")
                    await asyncio.sleep(retry_delay)

                # Re-acquire lock to update video tracks and stream references
                async with self.lock:
                    # Now update the video track stream types so they request from the new stream
                    for i, track in enumerate(video_tracks):
                        if i < len(new_stream_types):
                            if hasattr(track, 'switch_stream_type'):
                                track.switch_stream_type(new_stream_types[i])
                                print(f"✅ Switched track {i} to stream type: {new_stream_types[i]}")

                    # Update stream references (remove old, add new)
                    for stream_type in old_stream_types:
                        if device_id in self.stream_references and stream_type in self.stream_references[device_id]:
                            self.stream_references[device_id][stream_type] -= 1
                            if self.stream_references[device_id][stream_type] <= 0:
                                del self.stream_references[device_id][stream_type]

                    for stream_type in new_stream_types:
                        if device_id not in self.stream_references:
                            self.stream_references[device_id] = {}
                        self.stream_references[device_id][stream_type] = self.stream_references[device_id].get(stream_type, 0) + 1

                print(f"✅ Successfully switched stream types for session {session_id}")
                return True
        except asyncio.TimeoutError:
            print(f"❌ Stream type switch timed out for session {session_id}")
            raise RealSenseError(status_code=500, detail="Stream type switch operation timed out")
        except Exception as e:
            print(f"❌ Error switching stream types for session {session_id}: {str(e)}")
            raise RealSenseError(status_code=500, detail=f"Failed to switch stream types: {str(e)}")

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

        # Decrement stream references with better error handling
        try:
            await self._decrement_stream_references(device_id, stream_types)
        except Exception as e:
            print(f"Error decrementing stream references for session {session_id}: {str(e)}")

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
        removed: List[Tuple[str, str, List[str], Any]] = []

        async with self.lock:
            now = time.time()
            session_ids = list(self.sessions.keys())

            for session_id in session_ids:
                session = self.sessions.get(session_id)
                if not session:
                    continue

                drop = False
                if session.get("should_cleanup", False):
                    drop = True
                elif now - session["created_at"] > self.session_timeout:
                    drop = True
                elif now - session["last_activity"] > 1800:
                    drop = True
                elif not session.get("connected", False) and (now - session["created_at"]) > 120:
                    drop = True

                if drop:
                    pc = session["pc"]
                    device_id = session["device_id"]
                    stream_types = session["stream_types"]
                    removed.append((session_id, device_id, stream_types, pc))
                    del self.sessions[session_id]

        for _sid, device_id, stream_types, pc in removed:
            try:
                await pc.close()
            except Exception:
                pass
            try:
                await self._decrement_stream_references(device_id, stream_types)
            except Exception as e:
                print(f"Error decrementing stream references during cleanup: {e}")

        await asyncio.sleep(60)
        asyncio.create_task(self._cleanup_sessions())

    async def _send_point_cloud_data(self, session_id: str, device_id: str):
        """Send point cloud data over WebRTC data channel"""
        import json
        import time
        
        try:
            print(f"🚀 Starting point cloud data transmission for session {session_id}")

            async with self.lock:
                session_data = self.sessions.get(session_id)
                if not session_data:
                    print(f"❌ Session {session_id} not found")
                    return
                if session_data.get("point_cloud_sender_running"):
                    print(f"📡 Point cloud sender already running for {session_id}, skipping duplicate start")
                    return
                data_channel = session_data.get("data_channel")
                if not data_channel:
                    print(f"❌ No data channel found for session {session_id}")
                    return
                session_data["point_cloud_sender_running"] = True

            # Prove SCTP path to browser immediately (heartbeat was only every 30s before).
            try:
                if data_channel.readyState == "open":
                    hb0 = {
                        "type": "heartbeat",
                        "timestamp": time.time(),
                        "session_id": session_id,
                    }
                    data_channel.send(json.dumps(hb0))
                    print(f"💓 Initial heartbeat sent for session {session_id}")
            except Exception as e:
                print(f"❌ Initial heartbeat failed for {session_id}: {e}")
            
            # Add keep-alive mechanism
            last_heartbeat = time.time()
            heartbeat_interval = 30  # Send heartbeat every 30 seconds
            last_no_vertices_log = 0.0
            
            while True:
                try:
                    # Check if session still exists
                    async with self.lock:
                        if session_id not in self.sessions:
                            print(f"📡 Session {session_id} no longer exists, stopping transmission")
                            break
                        session_data = self.sessions.get(session_id)
                        if not session_data:
                            break
                        data_channel = session_data.get("data_channel")
                        if not data_channel:
                            break
                    
                    # Send heartbeat to keep connection alive
                    current_time = time.time()
                    if current_time - last_heartbeat > heartbeat_interval:
                        if data_channel.readyState == "open":
                            try:
                                heartbeat_message = {
                                    "type": "heartbeat",
                                    "timestamp": current_time,
                                    "session_id": session_id
                                }
                                data_channel.send(json.dumps(heartbeat_message))
                                print(f"💓 Sent heartbeat for session {session_id}")
                                last_heartbeat = current_time
                            except Exception as heartbeat_error:
                                print(f"❌ Heartbeat error: {heartbeat_error}")
                                break
                    
                    try:
                        point_cloud_data = self.realsense_manager.get_latest_metadata(device_id, "depth")
                    except Exception:
                        await asyncio.sleep(0.05)
                        continue
                    
                    # Temporarily disable debug logging to avoid NumPy array boolean context issues
                    # TODO: Re-enable once NumPy array issues are resolved
                    # Debug logging
                    # if point_cloud_data is None:
                    #     print(f"📡 No point cloud data available for device {device_id}")
                    # elif not point_cloud_data.get("point_cloud"):
                    #     print(f"📡 Point cloud data has no point_cloud key: {point_cloud_data.keys()}")
                    # elif not point_cloud_data["point_cloud"].get("vertices"):
                    #     print(f"📡 Point cloud data has no vertices: {point_cloud_data['point_cloud'].keys()}")
                    # else:
                    #     vertices_count = safe_len(point_cloud_data['point_cloud']['vertices'])
                    #     print(f"📡 Got point cloud data with {vertices_count} vertices")
                    
                    # Re-enable point cloud data sending with proper NumPy array handling
                    # Break down the complex boolean expression to avoid NumPy array boolean context issues
                    if point_cloud_data is None:
                        await asyncio.sleep(0.02)
                        continue
                    
                    point_cloud = point_cloud_data.get("point_cloud")
                    if point_cloud is None:
                        nowm = time.monotonic()
                        if nowm - last_no_vertices_log > 3.0:
                            last_no_vertices_log = nowm
                            keys = (
                                list(point_cloud_data.keys())
                                if isinstance(point_cloud_data, dict)
                                else []
                            )
                            print(
                                f"📡 Session {session_id}: depth metadata has no point_cloud "
                                f"(keys={keys}, device={device_id})"
                            )
                        await asyncio.sleep(0.02)
                        continue
                    
                    vertices_data = point_cloud.get("vertices")
                    if vertices_data is None:
                        await asyncio.sleep(0.02)
                        continue
                    
                    vertices_count = safe_len(vertices_data)
                    if vertices_count <= 0:
                        nowm = time.monotonic()
                        if nowm - last_no_vertices_log > 3.0:
                            last_no_vertices_log = nowm
                            print(
                                f"📡 Session {session_id}: point_cloud.vertices empty or invalid "
                                f"(raw count={vertices_count}, device={device_id})"
                            )
                        await asyncio.sleep(0.02)
                        continue

                    # Wait until SCTP data channel is open — do not break while still "connecting"
                    if data_channel.readyState != "open":
                        await asyncio.sleep(0.02)
                        continue

                    # Send point cloud data through data channel (never full-res .tolist(); see vertices_to_json_list)
                    max_vertices = 3000
                    vertices = vertices_to_json_list(vertices_data, max_vertices=max_vertices)

                    if len(vertices) == 0:
                        await asyncio.sleep(0.02)
                        continue

                    if len(vertices) > max_vertices:
                        original_count = len(vertices)
                        vertices = vertices[:max_vertices]
                        print(f"📡 Limiting point cloud data to {max_vertices} vertices (original: {original_count})")

                    data_message = {
                        "type": "pointcloud-data",
                        "device_id": device_id,
                        "vertices": vertices,
                        "timestamp": time.time(),
                        "total_vertices": len(vertices),
                        "sent_vertices": len(vertices),
                    }

                    try:
                        max_vertices_per_chunk = 3000

                        if len(vertices) <= max_vertices_per_chunk:
                            json_data = json.dumps(data_message)
                            data_channel.send(json_data)
                            print(f"📡 Sent point cloud data: {len(vertices)} vertices (JSON size: {len(json_data)} bytes)")
                        else:
                            import uuid

                            message_id = str(uuid.uuid4())
                            total_chunks = (len(vertices) + max_vertices_per_chunk - 1) // max_vertices_per_chunk

                            print(f"📡 Sending large point cloud data in {total_chunks} chunks: {len(vertices)} vertices")

                            for chunk_index in range(total_chunks):
                                start_vertex = chunk_index * max_vertices_per_chunk
                                end_vertex = min(start_vertex + max_vertices_per_chunk, len(vertices))
                                chunk_vertices = vertices[start_vertex:end_vertex]

                                chunk_message = {
                                    "type": "pointcloud-data",
                                    "device_id": device_id,
                                    "vertices": chunk_vertices,
                                    "timestamp": time.time(),
                                    "total_vertices": len(vertices),
                                    "sent_vertices": len(chunk_vertices),
                                    "message_id": message_id,
                                    "chunk_index": chunk_index,
                                    "total_chunks": total_chunks,
                                    "is_last_chunk": chunk_index == total_chunks - 1,
                                    "chunk_info": True,
                                }

                                chunk_json = json.dumps(chunk_message)
                                data_channel.send(chunk_json)
                                print(f"📡 Sent chunk {chunk_index + 1}/{total_chunks} with {len(chunk_vertices)} vertices (JSON size: {len(chunk_json)} bytes)")
                                await asyncio.sleep(0.0001)

                            print(f"📡 Completed sending {total_chunks} chunks for message {message_id}")

                    except Exception as json_error:
                        print(f"❌ JSON serialization error: {json_error}")
                        vertices = normalize_vertices_for_json(vertices)[:1000]
                        data_message["vertices"] = vertices
                        data_message["sent_vertices"] = len(vertices)
                        json_data = json.dumps(data_message)
                        data_channel.send(json_data)
                        print(f"📡 Sent reduced point cloud data: {len(vertices)} vertices")
                    
                    # Wait before sending next update - increased to 30 FPS for smoother updates
                    await asyncio.sleep(0.033)  # ~30 FPS
                    
                except Exception as e:
                    print(f"❌ Error sending point cloud data: {str(e)}")
                    # Check if session still exists
                    async with self.lock:
                        if session_id not in self.sessions:
                            print(f"📡 Session {session_id} no longer exists, stopping transmission")
                            break
                    await asyncio.sleep(1)  # Wait longer on error
                    
        except Exception as e:
            print(f"❌ Error in point cloud data transmission: {str(e)}")
        finally:
            async with self.lock:
                if session_id in self.sessions:
                    self.sessions[session_id]["point_cloud_sender_running"] = False
            print(f"🛑 Stopped point cloud data transmission for session {session_id}")