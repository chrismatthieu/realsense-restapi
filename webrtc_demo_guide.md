# RealSense WebRTC Demo Guide

## Overview

This demo demonstrates how to use the RealSense REST API's WebRTC functionality to stream video from a RealSense camera to a web browser in real-time.

## Components

### 1. RealSense REST API Server
- **Location**: `main.py`
- **Port**: 8000
- **Features**: 
  - Device management
  - Stream control
  - WebRTC session management
  - Socket.IO for metadata streaming

### 2. WebRTC HTML Demo Client
- **Location**: `webrtc_demo.html`
- **Features**:
  - Interactive web interface
  - Real-time video streaming
  - Connection status monitoring
  - Logging of WebRTC events

### 3. Python Test Script
- **Location**: `test_webrtc_api.py`
- **Features**:
  - API endpoint testing
  - WebRTC session lifecycle demonstration
  - Error handling examples

## Getting Started

### Prerequisites
1. RealSense camera connected (D435I, D415, etc.)
2. Python 3.8+ with virtual environment
3. Modern web browser with WebRTC support

### Setup Steps

1. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start the API Server**:
   ```bash
   source venv/bin/activate
   python main.py
   ```
   The server will start on `http://localhost:8000`

3. **Access the API Documentation**:
   Open `http://localhost:8000/docs` in your browser to explore the API endpoints.

### Testing the WebRTC API

1. **Run the Python Test**:
   ```bash
   source venv/bin/activate
   python test_webrtc_api.py
   ```
   This will test all WebRTC endpoints and show the complete workflow.

2. **Use the HTML Demo**:
   - Open `http://localhost:8000` or `http://localhost:8000/webrtc_demo.html` in your browser
   - Set the API URL to `http://localhost:8000/api`
   - Enter your device ID (e.g., `844212070924`)
   - Select stream type (color, depth, infrared)
   - Click "Start Stream"

## WebRTC Workflow

### 1. Device Discovery
```bash
GET /api/devices/
```
Returns list of connected RealSense devices.

### 2. Start Streaming
```bash
POST /api/devices/{device_id}/stream/start
{
  "configs": [
    {
      "sensor_id": "844212070924-sensor-0",
      "stream_type": "depth",
      "format": "z16",
      "resolution": {"width": 640, "height": 480},
      "framerate": 30
    }
  ]
}
```

### 3. Create WebRTC Offer
```bash
POST /api/webrtc/offer
{
  "device_id": "844212070924",
  "stream_types": ["depth"]
}
```
Returns session ID and SDP offer.

### 4. Process WebRTC Answer
```bash
POST /api/webrtc/answer
{
  "session_id": "session-uuid",
  "sdp": "v=0\r\no=-...",
  "type": "answer"
}
```

### 5. Exchange ICE Candidates
```bash
POST /api/webrtc/ice-candidates
{
  "session_id": "session-uuid",
  "candidate": "candidate:0 1 UDP...",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}
```

### 6. Monitor Session Status
```bash
GET /api/webrtc/sessions/{session_id}
```

### 7. Close Session
```bash
DELETE /api/webrtc/sessions/{session_id}
```

## Supported Stream Types

### Depth Stream
- **Sensor**: Stereo Module
- **Format**: z16
- **Resolutions**: 1280x720, 848x480, 640x480, etc.
- **Use Case**: 3D reconstruction, obstacle detection

### Color Stream
- **Sensor**: RGB Camera
- **Format**: rgb8, bgr8, yuyv
- **Resolutions**: 1920x1080, 1280x720, 640x480, etc.
- **Use Case**: Video streaming, computer vision

### Infrared Streams
- **Sensor**: Stereo Module
- **Stream Types**: infrared-1, infrared-2
- **Format**: y16, y8
- **Resolutions**: 1280x800, 1280x720, 848x480, etc.
- **Use Case**: Low-light conditions, depth processing

## Troubleshooting

### Common Issues

1. **Device Not Found**:
   - Check if RealSense camera is connected
   - Verify device ID in API response
   - Ensure camera drivers are installed

2. **Stream Start Fails**:
   - Check sensor ID format: `{device_id}-sensor-{index}`
   - Verify stream type is supported by the sensor
   - Note: Infrared streams are named `infrared-1` and `infrared-2`, not just `infrared`
   - Check resolution and framerate compatibility

3. **WebRTC Connection Fails**:
   - Ensure browser supports WebRTC
   - Check network connectivity
   - Verify ICE server configuration

4. **Video Not Displaying**:
   - Check browser console for errors
   - Verify video element permissions
   - Ensure WebRTC session is established

### Debug Commands

```bash
# Check device status
curl http://localhost:8000/api/devices/

# Check stream status
curl http://localhost:8000/api/devices/{device_id}/stream/status

# Test WebRTC endpoints
python test_webrtc_api.py
```

## Advanced Features

### Socket.IO Integration
The API also supports Socket.IO for real-time metadata streaming:
- Frame metadata
- Point cloud data
- Motion sensor data

### Multiple Streams
You can create WebRTC sessions with multiple stream types:
```json
{
  "device_id": "844212070924",
  "stream_types": ["color", "depth"]
}
```

### Custom ICE Servers
Configure STUN/TURN servers in `config.py` for NAT traversal.

## Performance Considerations

- **Resolution**: Lower resolutions (640x480) provide better performance
- **Framerate**: 30 FPS is recommended for real-time applications
- **Network**: WebRTC works best on local networks or with proper TURN servers
- **Browser**: Chrome and Firefox have the best WebRTC support

## Next Steps

1. **Custom Applications**: Use the API endpoints to build your own applications
2. **Multiple Cameras**: Extend the demo to support multiple RealSense devices
3. **Advanced Processing**: Add computer vision processing to the video streams
4. **Mobile Support**: Test WebRTC streaming on mobile devices
5. **Cloud Deployment**: Deploy the API server to cloud platforms

## API Documentation

For complete API documentation, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **OpenAPI Spec**: `http://localhost:8000/api/openapi.json`

## Support

- **RealSense SDK**: https://github.com/IntelRealSense/librealsense
- **WebRTC**: https://webrtc.org/
- **FastAPI**: https://fastapi.tiangolo.com/
