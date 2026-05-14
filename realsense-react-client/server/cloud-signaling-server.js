const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');

class CloudSignalingServer {
  constructor() {
    this.app = express();
    this.server = http.createServer(this.app);
    this.io = socketIo(this.server, {
      cors: {
        origin: "*", // Allow all origins for cloud deployment
        methods: ["GET", "POST"]
      }
    });
    
    this.port = process.env.PORT || 3001;
    
    // Connection tracking
    this.robots = new Map(); // robotId -> socket
    this.clients = new Map(); // clientId -> socket
    this.sessions = new Map(); // sessionId -> session data
    
    this.setupMiddleware();
    this.setupSocketHandlers();
  }

  setupMiddleware() {
    this.app.use(cors());
    this.app.use(express.json());
    
    this.app.get('/health', (req, res) => {
      res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        robots: this.robots.size,
        clients: this.clients.size,
        sessions: this.sessions.size
      });
    });

    this.app.get('/robots', (req, res) => {
      const availableRobots = Array.from(this.robots.keys()).map(robotId => ({
        robotId,
        deviceInfo: this.getRobotDeviceInfo(robotId)
      }));
      res.json(availableRobots);
    });
    
    // Test endpoint to send a test event to the robot
    this.app.post('/test-robot', (req, res) => {
      const robotId = req.body.robotId || 'robot-844212070924';
      const robotSocket = this.robots.get(robotId);
      
      if (robotSocket) {
        console.log(`🧪 Sending test event to robot ${robotId}`);
        robotSocket.emit('test', { message: 'Hello from cloud server!', timestamp: new Date().toISOString() });
        res.json({ success: true, message: 'Test event sent to robot' });
      } else {
        res.status(404).json({ success: false, message: 'Robot not found' });
      }
    });
  }

  setupSocketHandlers() {
    this.io.on('connection', (socket) => {
      console.log(`New connection: ${socket.id}`);
      
      // Handle robot registration
      socket.on('robot-register', (data) => {
        const { robotId, deviceInfo } = data;
        console.log(`🤖 Robot registered: ${robotId}`);
        
        this.robots.set(robotId, socket);
        socket.robotId = robotId;
        socket.deviceInfo = deviceInfo;
        
        // Broadcast robot availability to all clients
        this.broadcastToClients('robot-available', {
          robotId,
          deviceInfo
        });
      });

      // Handle point cloud data responses (from robot to client)
      // socket.on('pointcloud-data', (data) => {
      //     console.log(`📡 Received pointcloud-data response from robot:`, data);
      //     // Forward to all clients (since we don't track which client requested it)
      //     this.broadcastToClients('pointcloud-data', data);
      //     console.log(`✅ pointcloud-data forwarded to clients`);
      // });

      // Handle point cloud error responses (from robot to client)
      socket.on('pointcloud-error', (data) => {
        console.log(`📡 Received pointcloud-error response from robot:`, data);
        // Forward to all clients (since we don't track which client requested it)
        this.broadcastToClients('pointcloud-error', data);
        console.log(`✅ pointcloud-error forwarded to clients`);
      });

      // Handle point cloud activation responses (from robot to client)
      socket.on('pointcloud-activated', (data) => {
        console.log(`📡 Received pointcloud-activated response from robot:`, data);
        // Forward to all clients
        this.broadcastToClients('pointcloud-activated', data);
        console.log(`✅ pointcloud-activated forwarded to clients`);
      });

      // Handle device stream responses (from robot to client)
      socket.on('device-stream-started', (data) => {
        console.log(`📡 Received device-stream-started response from robot:`, data);
        // Forward to all clients
        this.broadcastToClients('device-stream-started', data);
        console.log(`✅ device-stream-started forwarded to clients`);
      });

      socket.on('device-stream-stopped', (data) => {
        console.log(`📡 Received device-stream-stopped response from robot:`, data);
        // Forward to all clients
        this.broadcastToClients('device-stream-stopped', data);
        console.log(`✅ device-stream-stopped forwarded to clients`);
      });

      // Handle client registration
      socket.on('client-register', (data) => {
        const { clientId } = data;
        console.log(`👤 Client registered: ${clientId}`);
        
        this.clients.set(clientId, socket);
        socket.clientId = clientId;
        
        // Send available robots to new client
        const availableRobots = Array.from(this.robots.keys()).map(robotId => ({
          robotId,
          deviceInfo: this.getRobotDeviceInfo(robotId)
        }));
        socket.emit('available-robots', availableRobots);
      });

      // Handle WebRTC session creation (from client to robot)
      socket.on('create-session', (data) => {
        const { robotId, deviceId, streamTypes } = data;
        const robotSocket = this.robots.get(robotId);
        
        if (!robotSocket) {
          socket.emit('session-error', { error: 'Robot not available' });
          return;
        }

        const sessionId = this.generateSessionId();
        const sessionData = {
          sessionId,
          robotId,
          deviceId,
          streamTypes,
          clientSocket: socket,
          robotSocket: robotSocket,
          createdAt: new Date()
        };
        
        this.sessions.set(sessionId, sessionData);
        
        console.log(`📡 Creating session ${sessionId} for robot ${robotId}`);
        
        // Forward to robot
        robotSocket.emit('create-session', {
          sessionId,
          deviceId,
          streamTypes
        });
      });

      // Handle stream type switching (from client to robot)
      socket.on('switch-stream-type', (data) => {
        console.log(`📡 Received switch-stream-type event:`, data);
        const { sessionId, streamTypes } = data;
        const session = this.sessions.get(sessionId);
        
        if (!session) {
          console.log(`❌ Session not found for switch-stream-type: ${sessionId}`);
          socket.emit('stream-type-switch-error', { error: 'Session not found' });
          return;
        }

        console.log(`🔄 Switching stream type for session ${sessionId} to ${streamTypes}`);
        console.log(`📤 Forwarding switch-stream-type to robot:`, { sessionId, streamTypes });
        
        // Forward to robot
        session.robotSocket.emit('switch-stream-type', {
          sessionId,
          streamTypes
        });
        console.log(`✅ switch-stream-type forwarded to robot`);
      });

      // Handle point cloud data requests (from client to robot)
      // socket.on('get-pointcloud-data', (data) => {
      //     console.log(`📡 Received get-pointcloud-data event:`, data);
      //     const { deviceId } = data;
      //     
      //     // Find the robot that has this device
      //     const robotId = this.findRobotWithDevice(deviceId);
      //     if (!robotId) {
      //         console.log(`❌ No robot found with device ${deviceId}`);
      //         socket.emit('pointcloud-error', { error: `No robot found with device ${deviceId}` });
      //         return;
      //     }
      //     
      //     console.log(`🔄 Getting point cloud data for device ${deviceId} via robot ${robotId}`);
      //     
      //     // Forward to the robot
      //     const robotSocket = this.robots.get(robotId);
      //     if (robotSocket) {
      //         robotSocket.emit('get-pointcloud-data', { deviceId });
      //         console.log(`✅ get-pointcloud-data forwarded to robot`);
      //     } else {
      //         console.log(`❌ Robot ${robotId} not found`);
      //         socket.emit('pointcloud-error', { error: `Robot ${robotId} not available` });
      //     }
      // });

      // Handle point cloud activation (from client to robot)
      socket.on('activate-pointcloud', (data) => {
        console.log(`📡 Received activate-pointcloud event:`, data);
        const { deviceId, enabled = true } = data;

        let robotSocket = this.findRobotSocketByCameraDeviceId(deviceId);
        if (!robotSocket) {
          robotSocket = this.robots.get(`robot-${deviceId}`);
        }

        if (!robotSocket) {
          socket.emit('pointcloud-error', { error: 'Robot not found for device' });
          return;
        }

        const robotId = robotSocket.robotId || 'unknown';
        console.log(`🔄 ${enabled ? 'Activating' : 'Deactivating'} point cloud for device ${deviceId} via robot ${robotId}`);
        
        // Forward to robot
        robotSocket.emit('activate-pointcloud', { deviceId, enabled });
        console.log(`✅ activate-pointcloud forwarded to robot`);
      });

      // Handle device stream start (from client to robot)
      socket.on('start-device-stream', (data) => {
        console.log(`📡 Received start-device-stream event:`, data);
        const { deviceId, streamConfigs } = data;

        let robotSocket = this.findRobotSocketByCameraDeviceId(deviceId);
        if (!robotSocket) {
          robotSocket = this.robots.get(`robot-${deviceId}`);
        }

        if (!robotSocket) {
          socket.emit('pointcloud-error', { error: 'Robot not found for device' });
          return;
        }

        const robotId = robotSocket.robotId || 'unknown';
        console.log(`🔄 Starting device stream for ${deviceId} via robot ${robotId}`);
        
        // Forward to robot
        robotSocket.emit('start-device-stream', { deviceId, streamConfigs });
        console.log(`✅ start-device-stream forwarded to robot`);
      });

      // Handle device stream stop (from client to robot)
      socket.on('stop-device-stream', (data) => {
        console.log(`📡 Received stop-device-stream event:`, data);
        const { deviceId } = data;

        let robotSocket = this.findRobotSocketByCameraDeviceId(deviceId);
        if (!robotSocket) {
          robotSocket = this.robots.get(`robot-${deviceId}`);
        }

        if (!robotSocket) {
          socket.emit('pointcloud-error', { error: 'Robot not found for device' });
          return;
        }

        const robotId = robotSocket.robotId || 'unknown';
        console.log(`🔄 Stopping device stream for ${deviceId} via robot ${robotId}`);
        
        // Forward to robot
        robotSocket.emit('stop-device-stream', { deviceId });
        console.log(`✅ stop-device-stream forwarded to robot`);
      });

      // Offer / errors from robot → originating client (must forward session-error; otherwise client only hits 10s timeout)
      socket.on('session-error', (data) => {
        const sessionId = data && data.sessionId;
        if (!sessionId) {
          return;
        }
        const session = this.sessions.get(sessionId);
        if (session && session.robotSocket === socket) {
          console.log(`❌ Forwarding session-error for ${sessionId} to client`);
          session.clientSocket.emit('session-error', data);
          this.sessions.delete(sessionId);
        }
      });

      // Handle WebRTC offer (from robot to client)
      socket.on('webrtc-offer', (data) => {
        const { sessionId, offer } = data;
        const session = this.sessions.get(sessionId);
        
        if (session) {
          session.offer = offer;
          console.log(`📤 Forwarding offer for session ${sessionId}`);
          session.clientSocket.emit('webrtc-offer', { sessionId, offer });
        }
      });

      // Handle WebRTC answer (from client to robot)
      socket.on('webrtc-answer', (data) => {
        const { sessionId, answer } = data;
        const session = this.sessions.get(sessionId);
        
        if (session) {
          console.log(`📤 Forwarding answer for session ${sessionId}`);
          session.robotSocket.emit('webrtc-answer', { sessionId, answer });
        }
      });

      // Handle ICE candidates (bidirectional)
      socket.on('ice-candidate', (data) => {
        const { sessionId, candidate } = data;
        const session = this.sessions.get(sessionId);
        
        if (session) {
          // Forward to the other party
          if (socket === session.clientSocket) {
            session.robotSocket.emit('ice-candidate', { sessionId, candidate });
          } else {
            session.clientSocket.emit('ice-candidate', { sessionId, candidate });
          }
        }
      });

      // Handle session cleanup
      socket.on('close-session', (data) => {
        const { sessionId } = data;
        const session = this.sessions.get(sessionId);
        
        if (session) {
          console.log(`🗑️ Closing session ${sessionId}`);
          this.sessions.delete(sessionId);
          
          // Notify the other party
          if (socket === session.clientSocket) {
            session.robotSocket.emit('session-closed', { sessionId });
          } else {
            session.clientSocket.emit('session-closed', { sessionId });
          }
        }
      });

      // Handle disconnection
      socket.on('disconnect', () => {
        console.log(`❌ Connection lost: ${socket.id}`);
        
        if (socket.robotId) {
          console.log(`🤖 Robot disconnected: ${socket.robotId}`);
          this.robots.delete(socket.robotId);
          this.broadcastToClients('robot-unavailable', { robotId: socket.robotId });
        }
        
        if (socket.clientId) {
          console.log(`👤 Client disconnected: ${socket.clientId}`);
          this.clients.delete(socket.clientId);
        }
        
        // Clean up sessions
        for (const [sessionId, session] of this.sessions.entries()) {
          if (session.clientSocket === socket || session.robotSocket === socket) {
            console.log(`🗑️ Cleaning up session ${sessionId} due to disconnect`);
            this.sessions.delete(sessionId);
            
            // Notify the other party
            if (session.clientSocket === socket) {
              session.robotSocket.emit('session-closed', { sessionId });
            } else {
              session.clientSocket.emit('session-closed', { sessionId });
            }
          }
        }
      });
    });
  }

  broadcastToClients(event, data) {
    for (const clientSocket of this.clients.values()) {
      clientSocket.emit(event, data);
    }
  }

  getRobotDeviceInfo(robotId) {
    const robotSocket = this.robots.get(robotId);
    return robotSocket ? robotSocket.deviceInfo : { robotId, status: 'unknown' };
  }

  /**
   * Resolve the robot Socket.IO connection that owns a RealSense camera serial.
   * robotId (e.g. robot-abc123) is NOT robot-${deviceId}; deviceId is the camera serial from deviceInfo.
   */
  findRobotSocketByCameraDeviceId(cameraDeviceId) {
    if (!cameraDeviceId) return null;
    const want = String(cameraDeviceId);
    for (const [, robotSocket] of this.robots.entries()) {
      const d = robotSocket.deviceInfo && robotSocket.deviceInfo.deviceId;
      if (d != null && String(d) === want) {
        return robotSocket;
      }
    }
    return null;
  }

  generateSessionId() {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  }

  start() {
    this.server.listen(this.port, () => {
      console.log(`🚀 Cloud signaling server running on port ${this.port}`);
      console.log(`🌐 CORS enabled for all origins`);
      console.log(`🤖 Ready for robot and client connections`);
      console.log(`📊 Health check: http://localhost:${this.port}/health`);
      console.log(`🤖 Available robots: http://localhost:${this.port}/robots`);
    });
  }
}

module.exports = CloudSignalingServer;

// Start server if run directly
if (require.main === module) {
  const server = new CloudSignalingServer();
  server.start();
}
