import React, { useState, useEffect, useRef, useCallback } from 'react';
import cloudSignalingService from '../services/cloudSignalingService';

const WebRTCDemo = () => {
  const [deviceId, setDeviceId] = useState('');
  const [streamType, setStreamType] = useState('color');
  const [status, setStatus] = useState('Ready to connect');
  const [statusType, setStatusType] = useState('info');
  const [log, setLog] = useState('');
  const [isConnected, setIsConnected] = useState(false);

  const [signalingConnected, setSignalingConnected] = useState(false);
  const [availableRobots, setAvailableRobots] = useState([]);
  const [selectedRobot, setSelectedRobot] = useState(null);
  
  const videoRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const sessionIdRef = useRef(null);
  const sessionRefreshIntervalRef = useRef(null);
  const connectionEstablishedRef = useRef(false);
  const cleanupCalledRef = useRef(false);

  const logMessage = useCallback((message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLog(prev => `[${timestamp}] ${message}\n${prev}`);
  }, []);

  const updateStatus = useCallback((message, type = 'info') => {
    setStatus(message);
    setStatusType(type);
  }, []);

  const resetDevice = async () => {
    if (!selectedRobot) {
      updateStatus('Please select a robot first', 'error');
      return;
    }

    try {
      logMessage('Refreshing robot connection...');
      updateStatus('Refreshing robot...', 'info');
      
      // Wait for robot to stabilize
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Try to discover robots again
      await discoverRobots();
      
      updateStatus('Robot refresh completed', 'success');
    } catch (error) {
      logMessage(`Failed to refresh robot: ${error.message}`);
      updateStatus(`Failed to refresh robot: ${error.message}`, 'error');
    }
  };

  const discoverRobots = useCallback(async () => {
    try {
      logMessage('Discovering available robots...');
      updateStatus('Discovering robots...', 'info');
      
      const robots = cloudSignalingService.getAvailableRobots();
      setAvailableRobots(robots);
      
      if (robots.length > 0) {
        setSelectedRobot(robots[0]);
        setDeviceId(robots[0].deviceInfo.deviceId);
        logMessage(`Found ${robots.length} robot(s): ${robots.map(r => r.robotId).join(', ')}`);
        updateStatus(`Found ${robots.length} robot(s)`, 'success');
      } else {
        logMessage('No robots available');
        updateStatus('No robots available', 'warning');
      }
    } catch (error) {
      logMessage(`Failed to discover robots: ${error.message}`);
      updateStatus(`Failed to discover robots: ${error.message}`, 'error');
    }
  }, [logMessage, updateStatus]);

  const startStream = async () => {
    if (!selectedRobot) {
      updateStatus('Please select a robot', 'error');
      return;
    }

    if (!signalingConnected) {
      updateStatus('Not connected to cloud server', 'error');
      return;
    }

    try {
      logMessage('Starting WebRTC stream...');
      updateStatus('Starting WebRTC stream...', 'info');
      
      logMessage(`Creating WebRTC session for robot: ${selectedRobot.robotId}, device: ${selectedRobot.deviceInfo.deviceId}, stream type: ${streamType}`);

      // Create WebRTC session via cloud server
      const sessionData = await cloudSignalingService.createSession(selectedRobot.robotId, selectedRobot.deviceInfo.deviceId, [streamType]);
      const { sessionId, offer } = sessionData;
      sessionIdRef.current = sessionId;
      logMessage(`Session created: ${sessionId}`);
      
      // Debug the offer object
      logMessage(`Offer object: ${JSON.stringify(offer)}`);
      logMessage(`Offer type: ${offer?.type}`);
      logMessage(`Offer sdp: ${offer?.sdp ? 'Present' : 'Missing'}`);

      // Create RTCPeerConnection
      const pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });
      peerConnectionRef.current = pc;

      // Handle incoming tracks
      pc.ontrack = (event) => {
        logMessage('Received remote track');
        if (videoRef.current) {
          videoRef.current.srcObject = event.streams[0];
        }
      };

      // Handle ICE candidates
      pc.onicecandidate = async (event) => {
        if (event.candidate) {
          try {
            await cloudSignalingService.sendIceCandidate(sessionId, event.candidate);
          } catch (error) {
            logMessage(`Failed to send ICE candidate: ${error.message}`);
          }
        }
      };

      // Validate offer before setting remote description
      if (!offer || !offer.type || !offer.sdp) {
        throw new Error(`Invalid offer received: ${JSON.stringify(offer)}`);
      }
      
      logMessage(`Setting remote description with type: ${offer.type}`);
      // Set remote description
      await pc.setRemoteDescription(new RTCSessionDescription(offer));

      // Create answer
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // Send answer via cloud server
      logMessage(`Sending answer for session: ${sessionId}`);
      await cloudSignalingService.sendAnswer(sessionId, answer);

      setIsConnected(true);
      updateStatus('WebRTC stream connected', 'success');
      logMessage('WebRTC stream connected successfully');

      // Start session refresh
      startSessionRefresh();

    } catch (error) {
      logMessage(`Failed to start stream: ${error.message}`);
      updateStatus(`Failed to start stream: ${error.message}`, 'error');
    }
  };

  const switchStreamType = async (newStreamType) => {
    logMessage(`🔍 switchStreamType called with: ${newStreamType}`);
    logMessage(`🔍 Session ID: ${sessionIdRef.current}, Connected: ${isConnected}`);
    
    if (!sessionIdRef.current || !isConnected) {
      logMessage('❌ No active session to switch');
      return;
    }

    try {
      logMessage(`🔄 Switching stream type to: ${newStreamType}`);
      updateStatus(`Switching to ${newStreamType}...`, 'info');
      
      // Switch stream type via cloud server
      logMessage(`📡 Calling cloudSignalingService.switchStreamType(${sessionIdRef.current}, [${newStreamType}])`);
      await cloudSignalingService.switchStreamType(sessionIdRef.current, [newStreamType]);
      
      // Update local state
      setStreamType(newStreamType);
      updateStatus(`Switched to ${newStreamType}`, 'success');
      logMessage(`✅ Successfully switched to ${newStreamType}`);
      
    } catch (error) {
      logMessage(`❌ Failed to switch stream type: ${error.message}`);
      updateStatus(`Failed to switch stream type: ${error.message}`, 'error');
    }
  };

  const stopStream = async () => {
    try {
      if (sessionIdRef.current) {
        logMessage('Stopping WebRTC stream...');
        await cloudSignalingService.closeSession(sessionIdRef.current);
        logMessage('WebRTC stream stopped');
      }

      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
      }

      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }

      setIsConnected(false);
      sessionIdRef.current = null;
      updateStatus('WebRTC stream stopped', 'info');
      stopSessionRefresh();

    } catch (error) {
      logMessage(`Failed to stop stream: ${error.message}`);
    }
  };

  const refreshSessions = async () => {
    try {
      // In cloud architecture, sessions are managed by the cloud server
      // We can get session info from the cloud signaling service
      logMessage('Session management handled by cloud server');
    } catch (error) {
      logMessage(`Failed to refresh sessions: ${error.message}`);
    }
  };

  const closeAllSessions = async () => {
    try {
      logMessage('Closing all sessions...');
      // Close current session if active
      if (sessionIdRef.current) {
        await cloudSignalingService.closeSession(sessionIdRef.current);
        sessionIdRef.current = null;
      }
      logMessage('All sessions closed');
    } catch (error) {
      logMessage(`Failed to close all sessions: ${error.message}`);
    }
  };

  const startSessionRefresh = () => {
    sessionRefreshIntervalRef.current = setInterval(refreshSessions, 2000);
  };

  const stopSessionRefresh = () => {
    if (sessionRefreshIntervalRef.current) {
      clearInterval(sessionRefreshIntervalRef.current);
      sessionRefreshIntervalRef.current = null;
    }
  };

  useEffect(() => {
    // Only connect once
    if (connectionEstablishedRef.current) {
      return;
    }
    
    connectionEstablishedRef.current = true;
    
    // Connect to cloud signaling server
    const connectToCloud = async () => {
      try {
        logMessage('Attempting to connect to cloud server...');
        await cloudSignalingService.connect();
        setSignalingConnected(true);
        logMessage('Connected to cloud server');
        
        // Set up event listeners
        cloudSignalingService.addEventListener('available-robots', (robots) => {
          logMessage(`Received ${robots.length} available robots`);
          setAvailableRobots(robots);
          // Only set selected robot if none is currently selected
          if (robots.length > 0) {
            setSelectedRobot(prev => {
              if (!prev) {
                const firstRobot = robots[0];
                setDeviceId(firstRobot.deviceInfo.deviceId);
                logMessage(`Auto-selected robot: ${firstRobot.robotId}`);
                return firstRobot;
              }
              return prev;
            });
          }
        });
        
        cloudSignalingService.addEventListener('robot-available', (robot) => {
          logMessage(`Robot available: ${robot.robotId}`);
          setAvailableRobots(prev => [...prev, robot]);
        });
        
        cloudSignalingService.addEventListener('robot-unavailable', (robot) => {
          logMessage(`Robot unavailable: ${robot.robotId}`);
          setAvailableRobots(prev => prev.filter(r => r.robotId !== robot.robotId));
          setSelectedRobot(prev => {
            if (prev && prev.robotId === robot.robotId) {
              return null;
            }
            return prev;
          });
        });
        
        cloudSignalingService.addEventListener('disconnected', (data) => {
          logMessage(`Disconnected from cloud server: ${data.reason}`);
          setSignalingConnected(false);
        });
        
        cloudSignalingService.addEventListener('reconnected', (data) => {
          logMessage(`Reconnected to cloud server (attempt ${data.attemptNumber})`);
          setSignalingConnected(true);
        });
        
      } catch (error) {
        logMessage(`Failed to connect to cloud server: ${error.message}`);
        setSignalingConnected(false);
      }
    };

    connectToCloud();
    
    // Cleanup function - only run on component unmount
    return () => {
      // Only cleanup if this is a real unmount, not a development mode re-run
      if (connectionEstablishedRef.current && !cleanupCalledRef.current) {
        cleanupCalledRef.current = true;
        logMessage('Component unmounting, cleaning up cloud connection...');
        stopSessionRefresh();
        cloudSignalingService.disconnect();
        connectionEstablishedRef.current = false;
      }
    };
  }, []); // Empty dependency array - only run once

  return (
    <div>
      <div className="container">
        <h2>🤖 Robot WebRTC Multi-Client Demo</h2>
        <p>Connect to robots with RealSense cameras via cloud WebRTC for real-time video streaming</p>
        

        
        <div className="form-group">
          <label htmlFor="robotSelect">Select Robot:</label>
          <select
            id="robotSelect"
            value={selectedRobot ? selectedRobot.robotId : ''}
            onChange={(e) => {
              const robot = availableRobots.find(r => r.robotId === e.target.value);
              setSelectedRobot(robot);
              if (robot) {
                setDeviceId(robot.deviceInfo.deviceId);
              }
            }}
            disabled={availableRobots.length === 0}
          >
            <option value="">No robots available</option>
            {availableRobots.map(robot => (
              <option key={robot.robotId} value={robot.robotId}>
                {robot.deviceInfo.name} (Device: {robot.deviceInfo.deviceId})
              </option>
            ))}
          </select>
          <small>Available robots: {availableRobots.length} | Selected device: {deviceId || 'None'}</small>
        </div>
        
        <div className="form-group">
          <label htmlFor="streamType">Stream Type:</label>
          <select
            id="streamType"
            value={streamType}
            onChange={(e) => {
              const newStreamType = e.target.value;
              setStreamType(newStreamType);
              
              // If we have an active session, switch stream type instead of creating new session
              if (isConnected && sessionIdRef.current) {
                logMessage(`🔄 Attempting to switch stream type from ${streamType} to ${newStreamType}`);
                logMessage(`Session ID: ${sessionIdRef.current}, Connected: ${isConnected}`);
                switchStreamType(newStreamType);
              } else {
                logMessage(`⚠️ Cannot switch stream type - Session: ${sessionIdRef.current}, Connected: ${isConnected}`);
              }
            }}
          >
            <option value="color">Color</option>
            <option value="depth">Depth</option>
            <option value="infrared-1">Infrared 1</option>
            <option value="infrared-2">Infrared 2</option>
          </select>
        </div>
        
        <div className="form-group">
          <p style={{ margin: '10px 0', padding: '10px', backgroundColor: '#e7f3ff', borderRadius: '4px', borderLeft: '4px solid #007bff' }}>
            <strong>🎯 3D Point Cloud Viewer:</strong> For interactive 3D point cloud visualization, 
            <a href="/pointcloud" style={{ color: '#007bff', textDecoration: 'none', fontWeight: 'bold', marginLeft: '5px' }}>
              click here to open the 3D Point Cloud Demo
            </a>
          </p>
        </div>
        
        <div>
          <button onClick={discoverRobots} className="button">
            🔍 Discover Robots
          </button>
          <button 
            onClick={startStream} 
            className="button"
            disabled={isConnected}
          >
            ▶️ Start WebRTC Session
          </button>
          <button 
            onClick={stopStream} 
            className="button danger"
            disabled={!isConnected}
          >
            ⏹️ Stop WebRTC Session
          </button>
          <button onClick={refreshSessions} className="button">
            🔄 Refresh Sessions
          </button>
          <button onClick={closeAllSessions} className="button danger">
            🗑️ Close All Sessions
          </button>
          <button onClick={resetDevice} className="button warning">
            🔄 Refresh Robot
          </button>
          <button 
            onClick={() => {
              logMessage('Manual connection test...');
              logMessage(`Cloud service connected: ${cloudSignalingService.getConnectionStatus().isConnected}`);
              logMessage(`Available robots: ${cloudSignalingService.getAvailableRobots().length}`);
            }} 
            className="button info"
          >
            🔍 Test Connection
          </button>
        </div>

        <div className={`status ${statusType}`}>
          {status}
        </div>
        <div className={`status ${signalingConnected ? 'success' : 'error'}`}>
          ☁️ Cloud Server: {signalingConnected ? 'Connected' : 'Disconnected'} | Robots: {availableRobots.length} | Service: {cloudSignalingService.getConnectionStatus().isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      <div className="container">
        <h2>📊 Cloud Sessions</h2>
        <div className="sessions-panel">
          {sessionIdRef.current ? (
            <div>
              <h3>Active WebRTC Session</h3>
              <p>Session ID: {sessionIdRef.current}</p>
              <p>Robot: {selectedRobot?.robotId || 'Unknown'}</p>
              <p>Device: {deviceId || 'Unknown'}</p>
              <p>Stream Type: {streamType}</p>
            </div>
          ) : (
            <div>
              <h3>No active sessions</h3>
              <p>Start a stream to establish a WebRTC session with a robot.</p>
            </div>
          )}
        </div>
      </div>

      <div className="container">
        <h2>🔗 Cloud Connection</h2>
        <div className="sessions-panel">
          {signalingConnected ? (
            <div>
              <h3>Cloud Server Status</h3>
              <p>✅ Connected to cloud signaling server</p>
              <p>🤖 Available robots: {availableRobots.length}</p>
              <p>📡 WebRTC sessions managed by cloud server</p>
            </div>
          ) : (
            <div>
              <h3>Cloud Server Status</h3>
              <p>❌ Not connected to cloud server</p>
              <p>Please check your connection to the cloud signaling server.</p>
            </div>
          )}
        </div>
      </div>

      <div className="container">
        <h2>🎥 Video Stream</h2>
        <div className="video-container">
          <div className={`video-wrapper ${isConnected ? 'active' : ''}`}>
            <h3>Current Stream</h3>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{ width: '100%', borderRadius: '8px', background: '#000' }}
            />
            <div className={`status ${isConnected ? 'success' : 'info'}`}>
              {isConnected ? 'Streaming' : 'No video stream'}
            </div>
          </div>
        </div>
      </div>

      <div className="container">
        <h2>📝 Connection Log</h2>
        <div className="log">{log}</div>
      </div>
    </div>
  );
};

export default WebRTCDemo;
