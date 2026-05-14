import io from 'socket.io-client';

class CloudSignalingService {
  constructor() {
    this.socket = null;
    this.cloudUrl = process.env.REACT_APP_CLOUD_URL || 'http://localhost:3001';
    this.isConnected = false;
    this.availableRobots = [];
    this.eventListeners = new Map();
    this.clientId = this.generateClientId();
  }

  connect() {
    return new Promise((resolve, reject) => {
      if (this.socket && this.isConnected) {
        console.log('🌐 Already connected to cloud signaling server');
        resolve();
        return;
      }

      console.log(`🌐 Connecting to cloud signaling server: ${this.cloudUrl}`);
      
      this.socket = io(this.cloudUrl, {
        transports: ['websocket'],
        timeout: 10000,
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
      });

      this.socket.on('connect', () => {
        console.log('✅ Connected to cloud signaling server');
        this.isConnected = true;
        
        // Register as client
        this.socket.emit('client-register', { clientId: this.clientId });
        resolve();
      });

      this.socket.on('available-robots', (robots) => {
        this.availableRobots = robots;
        console.log('🤖 Available robots:', robots);
        this.emitEvent('available-robots', robots);
      });

      this.socket.on('robot-available', (robot) => {
        this.availableRobots.push(robot);
        console.log('🤖 Robot available:', robot);
        this.emitEvent('robot-available', robot);
      });

      this.socket.on('robot-unavailable', (robot) => {
        this.availableRobots = this.availableRobots.filter(r => r.robotId !== robot.robotId);
        console.log('🤖 Robot unavailable:', robot);
        this.emitEvent('robot-unavailable', robot);
      });

      this.socket.on('webrtc-offer', (data) => {
        console.log('📤 Received WebRTC offer:', data);
        this.emitEvent('webrtc-offer', data);
      });

      this.socket.on('ice-candidate', (data) => {
        console.log('🧊 Received ICE candidate:', data);
        this.emitEvent('ice-candidate', data);
      });

      this.socket.on('session-error', (error) => {
        console.error('❌ Session error:', error);
        this.emitEvent('session-error', error);
      });

      this.socket.on('session-closed', (data) => {
        console.log('🗑️ Session closed:', data);
        this.emitEvent('session-closed', data);
      });

      this.socket.on('connect_error', (error) => {
        console.error('❌ Cloud connection error:', error);
        this.isConnected = false;
        reject(error);
      });

      this.socket.on('disconnect', (reason) => {
        console.log('❌ Disconnected from cloud server:', reason);
        this.isConnected = false;
        this.emitEvent('disconnected', { reason });
      });

      this.socket.on('reconnect', (attemptNumber) => {
        console.log(`🔄 Reconnected to cloud server (attempt ${attemptNumber})`);
        this.isConnected = true;
        this.emitEvent('reconnected', { attemptNumber });
      });

      // Timeout for connection
      setTimeout(() => {
        if (!this.isConnected) {
          reject(new Error('Connection timeout'));
        }
      }, 10000);
    });
  }

  disconnect() {
    if (this.socket && this.isConnected) {
      console.log('🛑 Disconnecting from cloud signaling server');
      this.socket.disconnect();
      this.socket = null;
      this.isConnected = false;
    } else {
      console.log('🛑 Already disconnected from cloud signaling server');
    }
  }

  async createSession(robotId, deviceId, streamTypes) {
    return new Promise((resolve, reject) => {
      if (!this.isConnected) {
        reject(new Error('Not connected to cloud server'));
        return;
      }

      console.log(`📡 Creating session for robot ${robotId}, device ${deviceId}, streams: ${streamTypes}`);

      this.socket.emit('create-session', {
        robotId,
        deviceId,
        streamTypes
      });

      let settled = false;
      let timer = null;
      const done = (fn) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        fn();
      };

      const offerHandler = (data) => {
        done(() => {
          this.removeEventListener('webrtc-offer', offerHandler);
          this.removeEventListener('session-error', errorHandler);
          resolve(data);
        });
      };

      const errorHandler = (error) => {
        done(() => {
          this.removeEventListener('webrtc-offer', offerHandler);
          this.removeEventListener('session-error', errorHandler);
          reject(new Error(error.error || 'Failed to create session'));
        });
      };

      this.addEventListener('webrtc-offer', offerHandler);
      this.addEventListener('session-error', errorHandler);

      timer = setTimeout(() => {
        done(() => {
          this.removeEventListener('webrtc-offer', offerHandler);
          this.removeEventListener('session-error', errorHandler);
          reject(new Error('Session creation timeout'));
        });
      }, 30000);
    });
  }

  sendAnswer(sessionId, answer) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`📤 Sending WebRTC answer for session ${sessionId}`);
    this.socket.emit('webrtc-answer', { sessionId, answer });
  }

  sendIceCandidate(sessionId, candidate) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`🧊 Sending ICE candidate for session ${sessionId}`);
    this.socket.emit('ice-candidate', { sessionId, candidate });
  }

  closeSession(sessionId) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`🗑️ Closing session ${sessionId}`);
    this.socket.emit('close-session', { sessionId });
  }

  switchStreamType(sessionId, streamTypes) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`🔄 Switching stream type for session ${sessionId} to ${streamTypes}`);
    console.log(`📡 Emitting switch-stream-type event:`, { sessionId, streamTypes });
    this.socket.emit('switch-stream-type', { sessionId, streamTypes });
    console.log(`✅ switch-stream-type event emitted`);
  }

  getPointCloudData(deviceId) {
    return new Promise((resolve, reject) => {
      if (!this.isConnected) {
        reject(new Error('Not connected to cloud server'));
        return;
      }

      console.log(`📊 Requesting point cloud data for device ${deviceId}`);
      
      const timeout = setTimeout(() => {
        this.removeEventListener('pointcloud-data', dataHandler);
        this.removeEventListener('pointcloud-error', errorHandler);
        reject(new Error('Point cloud data request timeout'));
      }, 10000);

      const dataHandler = (data) => {
        clearTimeout(timeout);
        this.removeEventListener('pointcloud-data', dataHandler);
        this.removeEventListener('pointcloud-error', errorHandler);
        resolve(data);
      };

      const errorHandler = (error) => {
        clearTimeout(timeout);
        this.removeEventListener('pointcloud-data', dataHandler);
        this.removeEventListener('pointcloud-error', errorHandler);
        reject(new Error(error.error || 'Point cloud data request failed'));
      };

      this.addEventListener('pointcloud-data', dataHandler);
      this.addEventListener('pointcloud-error', errorHandler);

      this.socket.emit('get-pointcloud-data', { deviceId });
    });
  }

  activatePointCloud(deviceId, activate) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`🎯 ${activate ? 'Activating' : 'Deactivating'} point cloud for device ${deviceId}`);
    this.socket.emit('activate-pointcloud', { deviceId, enabled: activate, activate });
  }

  startDeviceStream(deviceId, streamConfigs) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`🚀 Starting device stream for ${deviceId} with configs:`, streamConfigs);
    this.socket.emit('start-device-stream', { deviceId, streamConfigs });
  }

  stopDeviceStream(deviceId) {
    if (!this.isConnected) {
      throw new Error('Not connected to cloud server');
    }

    console.log(`⏹️ Stopping device stream for ${deviceId}`);
    this.socket.emit('stop-device-stream', { deviceId });
  }

  getAvailableRobots() {
    return this.availableRobots;
  }

  getPeerConnection(sessionId) {
    // This method should return the WebRTC peer connection for the given session
    // For now, we'll need to access it from the WebRTC manager
    if (window.webrtcManager && window.webrtcManager.sessions && window.webrtcManager.sessions[sessionId]) {
      return window.webrtcManager.sessions[sessionId].pc;
    }
    return null;
  }

  addEventListener(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  removeEventListener(event, callback) {
    if (this.eventListeners.has(event)) {
      const listeners = this.eventListeners.get(event);
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  emitEvent(event, data) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
  }

  generateClientId() {
    return 'client-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  }

  getConnectionStatus() {
    return {
      isConnected: this.isConnected,
      cloudUrl: this.cloudUrl,
      clientId: this.clientId,
      availableRobots: this.availableRobots.length
    };
  }
}

// Create singleton instance
const cloudSignalingService = new CloudSignalingService();
export default cloudSignalingService;
