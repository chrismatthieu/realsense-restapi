# RealSense REST API & 3D Point Cloud Viewer

A comprehensive RealSense camera management system featuring a standalone REST API server and an advanced ReactJS 3D point cloud viewer with cloud signaling capabilities.

## 🏗️ Project Architecture

This project consists of two main components:

1. **Standalone REST API Server** - FastAPI-based backend with WebRTC streaming
2. **ReactJS RealSense Viewer** - Frontend with 3D point cloud visualization and cloud signaling

### System Overview

```
┌─────────────────┐    WebRTC/Socket.IO    ┌──────────────────┐
│   React Client  │ ◄─────────────────────► │  Python API      │
│   (Port 3000)   │                        │  (Port 8000)     │
└─────────────────┘                        └──────────────────┘
         │                                         │
         │ Socket.IO                               │ RealSense
         │                                         │ Camera
         ▼                                         ▼
┌─────────────────┐                        ┌──────────────────┐
│ Cloud Signaling │                        │ RealSense D435i  │
│ Server          │                        │ Depth Camera      │
│ (Port 3001)     │                        └──────────────────┘
└─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** with virtual environment
- **Node.js 16+** and npm
- **Intel RealSense D435i** camera (or compatible)
- **Network connectivity** for multi-device access

### 1. Clone and Setup

```bash
git clone <repository-url>
cd realsense-restapi

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd realsense-react-client
npm install
cd ..
```

### 2. Start All Services

```bash
# Terminal 1: Start Python API Server
source venv/bin/activate
python main.py

# Terminal 2: Start Cloud Signaling Server
cd realsense-react-client/server
node cloud-signaling-server.js

# Terminal 3: Start React Client
cd realsense-react-client
npm start
```

### 3. Access the Application

- **Local access**: http://localhost:3000
- **Network access**: http://YOUR_IP_ADDRESS:3000

## 📋 Component Details

## 1. Standalone REST API Server

### Overview
A FastAPI-based server that provides RESTful endpoints for RealSense camera management, WebRTC streaming, and real-time data transmission.

### Key Features

#### 🔧 Device Management
- **Device Discovery**: List and manage connected RealSense devices
- **Device Information**: Get detailed device specs, firmware, and capabilities
- **Hardware Control**: Reset devices remotely
- **Sensor Management**: Configure individual sensors and options

#### 📡 Streaming Capabilities
- **REST-based Stream Control**: Start/stop streams with custom configurations
- **WebRTC Video Streaming**: Real-time RGB, depth, and infrared streaming
- **Socket.IO Data Streaming**: Real-time point cloud and metadata transmission

#### 🎯 WebRTC Implementation
- **Peer Connection Management**: Handle WebRTC offer/answer exchange
- **ICE Candidate Handling**: Manage network connectivity
- **Data Channel Support**: Efficient point cloud data transmission
- **Session Management**: Multiple concurrent streaming sessions

### API Endpoints

#### Device Management
```http
GET    /api/devices/                    # List all devices
GET    /api/devices/{device_id}         # Get device details
POST   /api/devices/{device_id}/reset   # Reset device
```

#### Stream Control
```http
POST   /api/devices/{device_id}/streams/start    # Start streaming
POST   /api/devices/{device_id}/streams/stop     # Stop streaming
GET    /api/devices/{device_id}/streams/status   # Get stream status
```

#### WebRTC Management
```http
POST   /api/webrtc/sessions/create      # Create WebRTC session
POST   /api/webrtc/sessions/{session_id}/offer   # Handle WebRTC offer
POST   /api/webrtc/sessions/{session_id}/answer  # Handle WebRTC answer
POST   /api/webrtc/sessions/{session_id}/ice     # Handle ICE candidates
```

#### Point Cloud Data
```http
GET    /api/devices/{device_id}/pointcloud       # Get point cloud data
POST   /api/webrtc/sessions/{session_id}/pointcloud/activate  # Activate point cloud
```

### Configuration

#### Environment Variables
```bash
# Cloud Signaling Server URL (for network access)
export CLOUD_SIGNALING_URL=http://YOUR_IP_ADDRESS:3001

# Robot ID (default: robot-844212070924)
export ROBOT_ID=your-robot-id

# API Server Port (default: 8000)
export API_PORT=8000
```

#### Starting the Server
```bash
# Basic startup
source venv/bin/activate
python main.py

# With custom configuration
CLOUD_SIGNALING_URL=http://192.168.0.43:3001 python main.py
```

### Testing the API

#### Interactive Documentation
Access the built-in OpenAPI (Swagger) UI at:
```
http://localhost:8000/docs
```

#### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio typeguard jinja2 pyyaml lark httpx

# Run tests
pytest tests/
```

## 2. ReactJS RealSense Viewer

### Overview
A modern React application providing a comprehensive 3D point cloud visualization interface with real-time streaming capabilities.

### Key Features

#### 🎮 3D Point Cloud Visualization
- **Real-time 3D Rendering**: Interactive Three.js-based point cloud display
- **Camera Controls**: Mouse-based camera manipulation (rotate, pan, zoom)
- **Performance Optimization**: Efficient vertex rendering and updates
- **Visual Feedback**: Real-time vertex count and FPS display

#### 🌐 WebRTC Integration
- **Data Channel Management**: Efficient point cloud data transmission
- **Chunked Data Handling**: Large dataset transmission via chunking
- **Connection Management**: Automatic reconnection and error handling
- **Session Management**: Multiple concurrent viewing sessions

#### 📊 Real-time Monitoring
- **Connection Status**: Live connection state monitoring
- **Data Flow Visualization**: Real-time data transmission metrics
- **Error Handling**: Comprehensive error reporting and recovery
- **Performance Metrics**: FPS, vertex count, and latency monitoring

### Application Structure

```
realsense-react-client/
├── src/
│   ├── pages/
│   │   ├── PointCloudDemo.js      # 3D point cloud viewer
│   │   ├── WebRTCDemo.js          # WebRTC streaming demo
│   │   └── MainViewer.js          # Main camera viewer
│   ├── services/
│   │   ├── cloudSignalingService.js  # Cloud signaling client
│   │   └── webrtcService.js          # WebRTC management
│   ├── components/
│   │   ├── ThreeJSViewer.js       # Three.js 3D renderer
│   │   └── ConnectionStatus.js    # Connection monitoring
│   └── utils/
│       └── pointCloudUtils.js     # Point cloud data processing
├── server/
│   └── cloud-signaling-server.js  # Cloud signaling server
└── public/
    └── index.html
```

### Configuration

#### Environment Variables
Create a `.env` file in `realsense-react-client/`:
```bash
# Cloud Signaling Server URL
REACT_APP_CLOUD_URL=http://YOUR_IP_ADDRESS:3001

# API Server URL
REACT_APP_API_URL=http://YOUR_IP_ADDRESS:8000
```

#### Network Access Setup
For multi-device access, configure the environment variables to use your machine's IP address:

```bash
# Example for IP 192.168.0.43
REACT_APP_CLOUD_URL=http://192.168.0.43:3001
REACT_APP_API_URL=http://192.168.0.43:8000
```

### Starting the Application

#### Development Mode
```bash
cd realsense-react-client
npm start
```

#### Production Build
```bash
cd realsense-react-client
npm run build
npm install -g serve
serve -s build -l 3000
```

## 3. Cloud Signaling Server

### Overview
A Node.js Socket.IO server that manages real-time communication between the Python API server and React clients.

### Key Features

#### 🔄 Session Management
- **Robot Registration**: Register and manage RealSense robot instances
- **Client Management**: Handle multiple concurrent client connections
- **Session Routing**: Route messages between robots and clients
- **Connection Monitoring**: Track connection health and status

#### 📡 Real-time Communication
- **WebRTC Signaling**: Handle WebRTC offer/answer exchange
- **Point Cloud Activation**: Manage point cloud streaming requests
- **Event Broadcasting**: Broadcast events to connected clients
- **Error Handling**: Graceful error handling and recovery

### Starting the Server
```bash
cd realsense-react-client/server
node cloud-signaling-server.js
```

## 🎯 Usage Examples

### 1. Basic Point Cloud Visualization

1. **Start all services** (see Quick Start section)
2. **Open the application** at http://localhost:3000
3. **Navigate to "3D Point Cloud"** page
4. **Select your robot** from the dropdown
5. **Click "Start 3D Viewer"** to begin streaming
6. **Interact with the 3D view**:
   - **Left Click + Drag**: Rotate camera
   - **Right Click + Drag**: Pan camera
   - **Scroll Wheel**: Zoom in/out
   - **R Key**: Reset camera position

### 2. WebRTC Video Streaming

1. **Navigate to "WebRTC Demo"** page
2. **Select stream type** (RGB, Depth, Infrared)
3. **Click "Start Stream"** to begin WebRTC streaming
4. **View real-time video** in the browser

### 3. Network Access Setup

1. **Configure environment variables** with your IP address:
   ```bash
   # Python server
   export CLOUD_SIGNALING_URL=http://YOUR_IP:3001
   
   # React client (.env file)
   REACT_APP_CLOUD_URL=http://YOUR_IP:3001
   REACT_APP_API_URL=http://YOUR_IP:8000
   ```

2. **Restart all services** with new configuration
3. **Access from other devices** at http://YOUR_IP:3000

## 🔧 Troubleshooting

### Common Issues

#### Point Cloud Not Displaying
- **Check NumPy array errors**: Ensure proper data type conversion
- **Verify WebRTC connection**: Check browser console for connection errors
- **Monitor server logs**: Look for data transmission issues

#### Connection Issues
- **Firewall settings**: Ensure ports 3000, 3001, and 8000 are open
- **Network configuration**: Verify IP address settings
- **Service status**: Check all services are running

#### Performance Issues
- **Reduce vertex count**: Adjust `max_vertices` in WebRTC manager
- **Optimize update rate**: Modify FPS settings
- **Check network bandwidth**: Monitor data transmission rates

### Debug Mode

#### Enable Verbose Logging
```bash
# Python server
export LOG_LEVEL=DEBUG
python main.py

# React client
REACT_APP_DEBUG=true npm start
```

#### Monitor Network Traffic
```bash
# Check service status
lsof -i :8000 -i :3001 -i :3000

# Monitor WebRTC connections
netstat -an | grep :3001
```

## 📊 Performance Optimization

### Point Cloud Streaming
- **Chunked transmission**: Large datasets split into manageable chunks
- **Compression**: Efficient data serialization and transmission
- **Update rate control**: Configurable FPS for optimal performance

### WebRTC Optimization
- **ICE candidate optimization**: Efficient network path selection
- **Data channel buffering**: Smooth data transmission
- **Connection pooling**: Reuse connections for better performance

## 🔒 Security Considerations

### Network Security
- **Firewall configuration**: Restrict access to necessary ports
- **Network isolation**: Use VPN for remote access
- **Authentication**: Implement user authentication for production use

### Data Security
- **Encryption**: Enable HTTPS for production deployments
- **Access control**: Implement proper access controls
- **Data validation**: Validate all incoming data

## 📈 Future Enhancements

### Planned Features
- **Multi-camera support**: Simultaneous multiple camera streaming
- **Advanced filtering**: Real-time point cloud filtering and processing
- **Recording capabilities**: Save and replay point cloud sessions
- **Mobile support**: Responsive design for mobile devices
- **Authentication system**: User management and access control

### Performance Improvements
- **WebAssembly integration**: Faster point cloud processing
- **GPU acceleration**: Hardware-accelerated rendering
- **Compression algorithms**: Advanced data compression
- **Load balancing**: Distributed processing support

## 🤝 Contributing

### Development Setup
1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Add tests for new features**
5. **Submit a pull request**

### Code Standards
- **Python**: Follow PEP 8 guidelines
- **JavaScript**: Use ESLint configuration
- **Documentation**: Update README for new features
- **Testing**: Maintain test coverage

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Intel RealSense SDK**: For camera integration
- **Three.js**: For 3D visualization
- **Socket.IO**: For real-time communication
- **FastAPI**: For REST API framework
- **React**: For frontend framework

---

**For support and questions, please open an issue on the project repository.**