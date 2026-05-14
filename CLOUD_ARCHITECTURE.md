# 🤖 Robot-to-Cloud WebSocket Architecture

## Overview

This implementation provides a **robot-to-cloud WebSocket architecture** that enables React clients to connect to RealSense cameras running behind firewalls without requiring VPN or tunneling setup.

## 🏗️ Architecture

```
┌─────────────────┐    WebSocket    ┌──────────────────┐    WebSocket    ┌─────────────────┐
│   React Client  │ ◄──────────────► │  Cloud Server    │ ◄──────────────► │  Robot (Python) │
│                 │   (Inbound)     │  (Node.js)       │   (Outbound)     │                 │
│  - WebRTC P2P   │                 │  - Signaling     │                  │  - RealSense    │
│  - UI Controls  │                 │  - Bridge        │                  │  - WebRTC       │
└─────────────────┘                 └──────────────────┘                  └─────────────────┘
```

The robot process is **Python** (FastAPI + RealSense + aiortc). Node users can start the same stack with **`npx teleop`** after a one-time **`pip install teleopsh`** (or `pip install -e .` from this repo); see `packages/teleop/README.md`. The PyPI package is **`teleopsh`**; the npm CLI remains **`teleop`**.

### Key Benefits

✅ **Works behind firewalls** - Robot initiates outbound connection  
✅ **No VPN/tunneling needed** - Standard WebSocket connection  
✅ **Cloud-deployable** - React app can be deployed anywhere  
✅ **Scalable** - Multiple robots can connect to same cloud server  
✅ **Real-time** - WebSocket provides low-latency signaling  
✅ **WebRTC P2P** - Direct connection once established  

## 🚀 Quick Start

### 1. Start All Services

```bash
# Make script executable (first time only)
chmod +x start-cloud-dev.sh

# Start all services
./start-cloud-dev.sh
```

This will start:
- 🌐 Cloud Signaling Server (port 3001)
- 🐍 Python API Server with Robot WebSocket Client (port 8000)
- ⚛️ React Development Server (port 3000)

### 2. Access the Application

- **React App**: http://localhost:3000
- **Health Check**: http://localhost:3001/health
- **Available Robots**: http://localhost:3001/robots

## 📁 File Structure

```
realsense-restapi/
├── robot_websocket_client.py          # Robot WebSocket client
├── main.py                            # Updated with robot client
├── start-cloud-dev.sh                 # Startup script
├── env.example                        # Environment configuration
├── realsense-react-client/
│   ├── server/
│   │   └── cloud-signaling-server.js  # Cloud signaling server
│   └── src/
│       ├── services/
│       │   └── cloudSignalingService.js # React cloud service
│       └── pages/
│           └── WebRTCDemo.js          # Updated React component
└── CLOUD_ARCHITECTURE.md              # This documentation
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `env.example`:

```bash
# Robot Configuration
ROBOT_ID=robot-844212070924
CLOUD_SIGNALING_URL=ws://localhost:3001

# React Client Configuration
REACT_APP_CLOUD_URL=http://localhost:3001

# Python API Configuration
PYTHON_API_URL=http://localhost:8000/api
SIGNALING_PORT=3001
```

### Cloud Deployment

For cloud deployment, update the URLs:

```bash
# Production URLs
CLOUD_SIGNALING_URL=wss://your-cloud-server.com
REACT_APP_CLOUD_URL=https://your-cloud-server.com
```

## 🔄 How It Works

### 1. Robot Registration
1. Robot starts and connects to cloud server via WebSocket
2. Robot registers with device information
3. Cloud server broadcasts robot availability to all clients

### 2. Client Connection
1. React client connects to cloud server
2. Client receives list of available robots
3. Client can select a robot to connect to

### 3. WebRTC Session Creation
1. Client requests WebRTC session with selected robot
2. Cloud server forwards request to robot
3. Robot creates WebRTC offer using existing WebRTC manager
4. Offer is forwarded back through cloud server to client

### 4. WebRTC Negotiation
1. Client and robot exchange WebRTC offers/answers via cloud server
2. ICE candidates are exchanged bidirectionally
3. Direct P2P connection is established

### 5. Video Streaming
1. Once P2P connection is established, video streams directly
2. Cloud server is no longer involved in video data
3. Only signaling continues through cloud server

## 🛠️ Manual Startup

If you prefer to start services manually:

### 1. Start Cloud Signaling Server
```bash
cd realsense-react-client/server
node cloud-signaling-server.js
```

### 2. Start Python API Server
```bash
source venv/bin/activate
python main.py
```

### 3. Start React Development Server
```bash
cd realsense-react-client
npm start
```

## 🔍 Troubleshooting

### Common Issues

#### Robot Not Connecting to Cloud
- Check `CLOUD_SIGNALING_URL` environment variable
- Ensure cloud server is running on correct port
- Check firewall allows outbound WebSocket connections

#### React Client Not Connecting
- Check `REACT_APP_CLOUD_URL` environment variable
- Ensure cloud server is accessible from client
- Check browser console for connection errors

#### WebRTC Session Creation Fails
- Verify robot is registered with cloud server
- Check robot's RealSense camera is working
- Review robot logs for WebRTC errors

### Debug Commands

```bash
# Check cloud server health
curl http://localhost:3001/health

# List available robots
curl http://localhost:3001/robots

# Check Python API
curl http://localhost:8000/api/devices/

# View logs
tail -f robot_websocket_client.py.log
```

## 🌐 Cloud Deployment

### Deploy Cloud Server

1. **Deploy to your cloud provider** (AWS, GCP, Azure, etc.)
2. **Update environment variables** with production URLs
3. **Configure SSL/TLS** for secure WebSocket connections
4. **Set up monitoring** and logging

### Deploy React App

1. **Build production version**:
   ```bash
   cd realsense-react-client
   npm run build
   ```
2. **Deploy to static hosting** (Netlify, Vercel, etc.)
3. **Update environment variables** for production

### Robot Configuration

1. **Update robot environment** with cloud server URL
2. **Ensure outbound WebSocket access** is allowed
3. **Set up automatic restart** on connection failure

## 🔒 Security Considerations

- Use **WSS (WebSocket Secure)** in production
- Implement **authentication** for robot registration
- Add **rate limiting** to prevent abuse
- Use **environment variables** for sensitive configuration
- Consider **VPN** for additional security if needed

## 📈 Scaling

### Multiple Robots
- Each robot connects independently to cloud server
- Cloud server tracks all connected robots
- Clients can choose which robot to connect to

### Multiple Clients
- Cloud server handles multiple client connections
- Each WebRTC session is independent
- No interference between different sessions

### Load Balancing
- Deploy multiple cloud server instances
- Use load balancer to distribute connections
- Implement sticky sessions for WebSocket connections

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Create an issue with detailed information
4. Include environment details and error logs
