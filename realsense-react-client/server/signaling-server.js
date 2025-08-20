const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');
const axios = require('axios');

class SignalingServer {
  constructor() {
    this.app = express();
    this.server = http.createServer(this.app);
    this.io = socketIo(this.server, {
      cors: {
        origin: "http://localhost:3000",
        methods: ["GET", "POST"]
      }
    });
    
    // Configuration
    this.pythonApiUrl = process.env.PYTHON_API_URL || 'http://localhost:8000/api';
    this.port = process.env.SIGNALING_PORT || 3001;
    
    // Session storage
    this.sessions = new Map(); // sessionId -> session data
    this.deviceSessions = new Map(); // deviceId -> Set of sessionIds
    
    this.setupMiddleware();
    this.setupSocketHandlers();
  }

  setupMiddleware() {
    this.app.use(cors());
    this.app.use(express.json());
    
    // Health check endpoint
    this.app.get('/health', (req, res) => {
      res.json({ status: 'ok', timestamp: new Date().toISOString() });
    });
    
    // Device discovery endpoint
    this.app.get('/devices', async (req, res) => {
      try {
        const response = await axios.get(`${this.pythonApiUrl}/devices/`);
        res.json(response.data);
      } catch (error) {
        console.error('Error fetching devices:', error.message);
        res.status(500).json({ error: 'Failed to fetch devices' });
      }
    });
  }

  setupSocketHandlers() {
    this.io.on('connection', (socket) => {
      console.log(`Client connected: ${socket.id}`);
      
      // Handle WebRTC session creation
      socket.on('create-session', async (data) => {
        try {
          const { deviceId, streamTypes } = data;
          console.log(`Creating session for device ${deviceId} with streams: ${streamTypes.join(', ')}`);
          
          // Create WebRTC offer via Python API
          const offerResponse = await axios.post(`${this.pythonApiUrl}/webrtc/offer`, {
            device_id: deviceId,
            stream_types: streamTypes
          });
          
          const { session_id, sdp, type } = offerResponse.data;
          
          // Store session information
          const sessionData = {
            sessionId: session_id,
            deviceId,
            streamTypes,
            socketId: socket.id,
            offer: { sdp, type },
            iceCandidates: [],
            createdAt: new Date()
          };
          
          this.sessions.set(session_id, sessionData);
          
          // Track device sessions
          if (!this.deviceSessions.has(deviceId)) {
            this.deviceSessions.set(deviceId, new Set());
          }
          this.deviceSessions.get(deviceId).add(session_id);
          
          // Join socket room for this session
          socket.join(session_id);
          
          // Send offer back to client
          socket.emit('session-created', {
            sessionId: session_id,
            offer: { sdp, type }
          });
          
          console.log(`Session ${session_id} created successfully`);
          
        } catch (error) {
          console.error('Error creating session:', error.message);
          socket.emit('session-error', {
            error: 'Failed to create session',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle WebRTC answer
      socket.on('answer', async (data) => {
        try {
          const { sessionId, answer } = data;
          console.log(`Processing answer for session ${sessionId}`);
          
          const sessionData = this.sessions.get(sessionId);
          if (!sessionData) {
            throw new Error('Session not found');
          }
          
          // Send answer to Python API
          await axios.post(`${this.pythonApiUrl}/webrtc/answer`, {
            session_id: sessionId,
            sdp: answer.sdp,
            type: answer.type
          });
          
          // Broadcast to all clients in the session room
          socket.to(sessionId).emit('answer-received', { answer });
          
          console.log(`Answer processed for session ${sessionId}`);
          
        } catch (error) {
          console.error('Error processing answer:', error.message);
          socket.emit('session-error', {
            error: 'Failed to process answer',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle ICE candidates
      socket.on('ice-candidate', async (data) => {
        try {
          const { sessionId, candidate } = data;
          console.log(`Processing ICE candidate for session ${sessionId}`);
          
          const sessionData = this.sessions.get(sessionId);
          if (!sessionData) {
            throw new Error('Session not found');
          }
          
          // Send ICE candidate to Python API
          await axios.post(`${this.pythonApiUrl}/webrtc/ice-candidates`, {
            session_id: sessionId,
            candidate: candidate.candidate,
            sdpMid: candidate.sdpMid,
            sdpMLineIndex: candidate.sdpMLineIndex
          });
          
          // Broadcast to all clients in the session room
          socket.to(sessionId).emit('ice-candidate-received', { candidate });
          
        } catch (error) {
          console.error('Error processing ICE candidate:', error.message);
          socket.emit('session-error', {
            error: 'Failed to process ICE candidate',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle session cleanup
      socket.on('close-session', async (data) => {
        try {
          const { sessionId } = data;
          console.log(`Closing session ${sessionId}`);
          
          const sessionData = this.sessions.get(sessionId);
          if (!sessionData) {
            console.log(`Session ${sessionId} not found`);
            return;
          }
          
          // Remove from Python API
          await axios.delete(`${this.pythonApiUrl}/webrtc/sessions/${sessionId}`);
          
          // Clean up local session data
          this.sessions.delete(sessionId);
          
          // Remove from device sessions
          const deviceId = sessionData.deviceId;
          if (this.deviceSessions.has(deviceId)) {
            this.deviceSessions.get(deviceId).delete(sessionId);
            if (this.deviceSessions.get(deviceId).size === 0) {
              this.deviceSessions.delete(deviceId);
            }
          }
          
          // Leave socket room
          socket.leave(sessionId);
          
          socket.emit('session-closed', { sessionId });
          console.log(`Session ${sessionId} closed successfully`);
          
        } catch (error) {
          console.error('Error closing session:', error.message);
          socket.emit('session-error', {
            error: 'Failed to close session',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle point cloud data requests
      socket.on('get-pointcloud-data', async (data) => {
        try {
          const { deviceId } = data;
          console.log(`Fetching point cloud data for device ${deviceId}`);
          
          const response = await axios.get(`${this.pythonApiUrl}/webrtc/pointcloud-data/${deviceId}`);
          socket.emit('pointcloud-data', response.data);
          
        } catch (error) {
          console.error('Error fetching point cloud data:', error.message);
          socket.emit('pointcloud-error', {
            error: 'Failed to fetch point cloud data',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle device stream control
      socket.on('start-device-stream', async (data) => {
        try {
          const { deviceId, configs } = data;
          console.log(`Starting device stream for ${deviceId}`);
          
          const response = await axios.post(`${this.pythonApiUrl}/devices/${deviceId}/stream/start`, {
            configs
          });
          
          socket.emit('device-stream-started', response.data);
          
        } catch (error) {
          console.error('Error starting device stream:', error.message);
          socket.emit('device-stream-error', {
            error: 'Failed to start device stream',
            details: error.response?.data || error.message
          });
        }
      });
      
      socket.on('stop-device-stream', async (data) => {
        try {
          const { deviceId } = data;
          console.log(`Stopping device stream for ${deviceId}`);
          
          const response = await axios.post(`${this.pythonApiUrl}/devices/${deviceId}/stream/stop`);
          
          socket.emit('device-stream-stopped', response.data);
          
        } catch (error) {
          console.error('Error stopping device stream:', error.message);
          socket.emit('device-stream-error', {
            error: 'Failed to stop device stream',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle point cloud activation
      socket.on('activate-pointcloud', async (data) => {
        try {
          const { deviceId, enabled = true } = data;
          console.log(`${enabled ? 'Activating' : 'Deactivating'} point cloud for device ${deviceId}`);
          
          const response = await axios.post(`${this.pythonApiUrl}/devices/${deviceId}/point_cloud/activate`, {
            enabled
          });
          
          socket.emit('pointcloud-activated', response.data);
          
        } catch (error) {
          console.error('Error activating point cloud:', error.message);
          socket.emit('pointcloud-error', {
            error: 'Failed to activate point cloud',
            details: error.response?.data || error.message
          });
        }
      });
      
      // Handle disconnection
      socket.on('disconnect', () => {
        console.log(`Client disconnected: ${socket.id}`);
        
        // Clean up sessions for this socket
        for (const [sessionId, sessionData] of this.sessions.entries()) {
          if (sessionData.socketId === socket.id) {
            console.log(`Cleaning up session ${sessionId} due to disconnect`);
            this.sessions.delete(sessionId);
            
            // Remove from device sessions
            const deviceId = sessionData.deviceId;
            if (this.deviceSessions.has(deviceId)) {
              this.deviceSessions.get(deviceId).delete(sessionId);
              if (this.deviceSessions.get(deviceId).size === 0) {
                this.deviceSessions.delete(deviceId);
              }
            }
          }
        }
      });
    });
  }

  start() {
    this.server.listen(this.port, () => {
      console.log(`🚀 Signaling server running on port ${this.port}`);
      console.log(`📡 Python API URL: ${this.pythonApiUrl}`);
      console.log(`🌐 CORS enabled for: http://localhost:3000`);
    });
  }

  getStats() {
    return {
      sessions: this.sessions.size,
      devices: this.deviceSessions.size,
      connections: this.io.engine.clientsCount
    };
  }
}

// Start the server if this file is run directly
if (require.main === module) {
  const server = new SignalingServer();
  server.start();
  
  // Add stats endpoint
  server.app.get('/stats', (req, res) => {
    res.json(server.getStats());
  });
}

module.exports = SignalingServer;
