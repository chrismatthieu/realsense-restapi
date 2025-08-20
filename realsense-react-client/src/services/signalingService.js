import io from 'socket.io-client';

class SignalingService {
  constructor() {
    this.socket = null;
    this.signalingUrl = process.env.REACT_APP_SIGNALING_URL || 'http://localhost:3001';
    this.isConnected = false;
    this.eventListeners = new Map();
  }

  connect() {
    return new Promise((resolve, reject) => {
      if (this.socket && this.isConnected) {
        resolve();
        return;
      }

      this.socket = io(this.signalingUrl, {
        transports: ['websocket', 'polling'],
        timeout: 10000,
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
      });

      this.socket.on('connect', () => {
        console.log('Connected to signaling server');
        this.isConnected = true;
        resolve();
      });

      this.socket.on('disconnect', () => {
        console.log('Disconnected from signaling server');
        this.isConnected = false;
      });

      this.socket.on('connect_error', (error) => {
        console.error('Signaling server connection error:', error);
        reject(error);
      });

      // Set up event listeners
      this.setupEventListeners();
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.isConnected = false;
    }
  }

  setupEventListeners() {
    // WebRTC session events
    this.socket.on('session-created', (data) => {
      this.emitEvent('session-created', data);
    });

    this.socket.on('session-error', (data) => {
      this.emitEvent('session-error', data);
    });

    this.socket.on('session-closed', (data) => {
      this.emitEvent('session-closed', data);
    });

    // WebRTC signaling events
    this.socket.on('answer-received', (data) => {
      this.emitEvent('answer-received', data);
    });

    this.socket.on('ice-candidate-received', (data) => {
      this.emitEvent('ice-candidate-received', data);
    });

    // Point cloud events
    this.socket.on('pointcloud-data', (data) => {
      this.emitEvent('pointcloud-data', data);
    });

    this.socket.on('pointcloud-error', (data) => {
      this.emitEvent('pointcloud-error', data);
    });

    this.socket.on('pointcloud-activated', (data) => {
      this.emitEvent('pointcloud-activated', data);
    });

    // Device stream events
    this.socket.on('device-stream-started', (data) => {
      this.emitEvent('device-stream-started', data);
    });

    this.socket.on('device-stream-stopped', (data) => {
      this.emitEvent('device-stream-stopped', data);
    });

    this.socket.on('device-stream-error', (data) => {
      this.emitEvent('device-stream-error', data);
    });
  }

  // Event listener management
  on(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  off(event, callback) {
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

  // WebRTC session management
  async createSession(deviceId, streamTypes) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Session creation timeout'));
      }, 10000);

      const onSessionCreated = (data) => {
        clearTimeout(timeout);
        this.off('session-created', onSessionCreated);
        this.off('session-error', onSessionError);
        resolve(data);
      };

      const onSessionError = (error) => {
        clearTimeout(timeout);
        this.off('session-created', onSessionCreated);
        this.off('session-error', onSessionError);
        reject(new Error(error.error || 'Failed to create session'));
      };

      this.on('session-created', onSessionCreated);
      this.on('session-error', onSessionError);

      this.socket.emit('create-session', { deviceId, streamTypes });
    });
  }

  async sendAnswer(sessionId, answer) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Answer processing timeout'));
      }, 10000);

      const onAnswerProcessed = () => {
        clearTimeout(timeout);
        this.off('answer-received', onAnswerProcessed);
        this.off('session-error', onSessionError);
        resolve();
      };

      const onSessionError = (error) => {
        clearTimeout(timeout);
        this.off('answer-received', onAnswerProcessed);
        this.off('session-error', onSessionError);
        reject(new Error(error.error || 'Failed to process answer'));
      };

      this.on('answer-received', onAnswerProcessed);
      this.on('session-error', onSessionError);

      this.socket.emit('answer', { sessionId, answer });
    });
  }

  async sendIceCandidate(sessionId, candidate) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('ICE candidate processing timeout'));
      }, 5000);

      const onIceProcessed = () => {
        clearTimeout(timeout);
        this.off('ice-candidate-received', onIceProcessed);
        this.off('session-error', onSessionError);
        resolve();
      };

      const onSessionError = (error) => {
        clearTimeout(timeout);
        this.off('ice-candidate-received', onIceProcessed);
        this.off('session-error', onSessionError);
        reject(new Error(error.error || 'Failed to process ICE candidate'));
      };

      this.on('ice-candidate-received', onIceProcessed);
      this.on('session-error', onSessionError);

      this.socket.emit('ice-candidate', { sessionId, candidate });
    });
  }

  async closeSession(sessionId) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Session closure timeout'));
      }, 5000);

      const onSessionClosed = (data) => {
        clearTimeout(timeout);
        this.off('session-closed', onSessionClosed);
        this.off('session-error', onSessionError);
        resolve(data);
      };

      const onSessionError = (error) => {
        clearTimeout(timeout);
        this.off('session-closed', onSessionClosed);
        this.off('session-error', onSessionError);
        reject(new Error(error.error || 'Failed to close session'));
      };

      this.on('session-closed', onSessionClosed);
      this.on('session-error', onSessionError);

      this.socket.emit('close-session', { sessionId });
    });
  }

  // Point cloud data
  async getPointCloudData(deviceId) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Point cloud data request timeout'));
      }, 10000);

      const onPointCloudData = (data) => {
        clearTimeout(timeout);
        this.off('pointcloud-data', onPointCloudData);
        this.off('pointcloud-error', onPointCloudError);
        resolve(data);
      };

      const onPointCloudError = (error) => {
        clearTimeout(timeout);
        this.off('pointcloud-data', onPointCloudData);
        this.off('pointcloud-error', onPointCloudError);
        reject(new Error(error.error || 'Failed to fetch point cloud data'));
      };

      this.on('pointcloud-data', onPointCloudData);
      this.on('pointcloud-error', onPointCloudError);

      this.socket.emit('get-pointcloud-data', { deviceId });
    });
  }

  // Device stream control
  async startDeviceStream(deviceId, configs) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Device stream start timeout'));
      }, 10000);

      const onStreamStarted = (data) => {
        clearTimeout(timeout);
        this.off('device-stream-started', onStreamStarted);
        this.off('device-stream-error', onStreamError);
        resolve(data);
      };

      const onStreamError = (error) => {
        clearTimeout(timeout);
        this.off('device-stream-started', onStreamStarted);
        this.off('device-stream-error', onStreamError);
        reject(new Error(error.error || 'Failed to start device stream'));
      };

      this.on('device-stream-started', onStreamStarted);
      this.on('device-stream-error', onStreamError);

      this.socket.emit('start-device-stream', { deviceId, configs });
    });
  }

  async stopDeviceStream(deviceId) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Device stream stop timeout'));
      }, 10000);

      const onStreamStopped = (data) => {
        clearTimeout(timeout);
        this.off('device-stream-stopped', onStreamStopped);
        this.off('device-stream-error', onStreamError);
        resolve(data);
      };

      const onStreamError = (error) => {
        clearTimeout(timeout);
        this.off('device-stream-stopped', onStreamStopped);
        this.off('device-stream-error', onStreamError);
        reject(new Error(error.error || 'Failed to stop device stream'));
      };

      this.on('device-stream-stopped', onStreamStopped);
      this.on('device-stream-error', onStreamError);

      this.socket.emit('stop-device-stream', { deviceId });
    });
  }

  async activatePointCloud(deviceId, enabled = true) {
    if (!this.isConnected) {
      throw new Error('Not connected to signaling server');
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Point cloud activation timeout'));
      }, 10000);

      const onPointCloudActivated = (data) => {
        clearTimeout(timeout);
        this.off('pointcloud-activated', onPointCloudActivated);
        this.off('pointcloud-error', onPointCloudError);
        resolve(data);
      };

      const onPointCloudError = (error) => {
        clearTimeout(timeout);
        this.off('pointcloud-activated', onPointCloudActivated);
        this.off('pointcloud-error', onPointCloudError);
        reject(new Error(error.error || 'Failed to activate point cloud'));
      };

      this.on('pointcloud-activated', onPointCloudActivated);
      this.on('pointcloud-error', onPointCloudError);

      this.socket.emit('activate-pointcloud', { deviceId, enabled });
    });
  }

  // Utility methods
  getConnectionStatus() {
    return this.isConnected;
  }

  getSocketId() {
    return this.socket ? this.socket.id : null;
  }
}

// Create a singleton instance
const signalingService = new SignalingService();

export default signalingService;
