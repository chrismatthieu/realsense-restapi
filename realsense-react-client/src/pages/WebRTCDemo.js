import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const WebRTCDemo = () => {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000/api');
  const [deviceId, setDeviceId] = useState('');
  const [streamType, setStreamType] = useState('color');
  const [status, setStatus] = useState('Ready to connect');
  const [statusType, setStatusType] = useState('info');
  const [log, setLog] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [streamRefs, setStreamRefs] = useState([]);
  
  const videoRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const sessionIdRef = useRef(null);
  const sessionRefreshIntervalRef = useRef(null);

  const logMessage = useCallback((message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLog(prev => `[${timestamp}] ${message}\n${prev}`);
  }, []);

  const updateStatus = useCallback((message, type = 'info') => {
    setStatus(message);
    setStatusType(type);
  }, []);

  const resetDevice = async () => {
    if (!deviceId) {
      updateStatus('Please enter a device ID', 'error');
      return;
    }

    try {
      logMessage('Performing hardware reset on device...');
      updateStatus('Resetting device...', 'info');
      
      // Try hardware reset first
      try {
        await axios.post(`${apiUrl}/devices/${deviceId}/hw_reset`);
        logMessage('Hardware reset completed');
      } catch (error) {
        logMessage(`Hardware reset failed: ${error.message}`);
      }
      
      // Wait for device to stabilize
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Try to discover devices again
      await discoverDevices();
      
      updateStatus('Device reset completed', 'success');
    } catch (error) {
      logMessage(`Failed to reset device: ${error.message}`);
      updateStatus(`Failed to reset device: ${error.message}`, 'error');
    }
  };

  const discoverDevices = useCallback(async () => {
    try {
      logMessage('Discovering devices...');
      updateStatus('Discovering devices...', 'info');
      
      logMessage(`Making request to: ${apiUrl}/devices/`);
      const response = await axios.get(`${apiUrl}/devices/`);
      logMessage(`Response status: ${response.status}`);
      logMessage(`Response data: ${JSON.stringify(response.data)}`);
      
      const devices = response.data;
      
      if (devices.length > 0) {
        setDeviceId(devices[0].device_id);
        logMessage(`Found ${devices.length} device(s): ${devices.map(d => d.device_id).join(', ')}`);
        updateStatus(`Found ${devices.length} device(s)`, 'success');
      } else {
        logMessage('No devices found');
        updateStatus('No devices found', 'error');
      }
    } catch (error) {
      logMessage(`Failed to discover devices: ${error.message}`);
      logMessage(`Error details: ${JSON.stringify(error.response?.data || error)}`);
      updateStatus(`Failed to discover devices: ${error.message}`, 'error');
    }
  }, [apiUrl, logMessage, updateStatus]);

  const startStream = async () => {
    if (!deviceId) {
      updateStatus('Please enter a device ID', 'error');
      return;
    }

    try {
      logMessage('Starting WebRTC stream...');
      updateStatus('Starting WebRTC stream...', 'info');
      
      logMessage(`Making WebRTC offer request to: ${apiUrl}/webrtc/offer`);
      logMessage(`Request payload: ${JSON.stringify({ device_id: deviceId, stream_types: [streamType] })}`);

      // Create WebRTC offer
      const offerResponse = await axios.post(`${apiUrl}/webrtc/offer`, {
        device_id: deviceId,
        stream_types: [streamType]
      });
      
      logMessage(`Offer response status: ${offerResponse.status}`);
      logMessage(`Offer response data: ${JSON.stringify(offerResponse.data)}`);

      const { session_id, sdp, type } = offerResponse.data;
      sessionIdRef.current = session_id;
      logMessage(`Created session: ${session_id}`);
      
      // Create the offer object from the API response
      const offer = { type, sdp };
      
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
            await axios.post(`${apiUrl}/webrtc/ice-candidates`, {
              session_id: session_id,
              candidate: event.candidate.candidate,
              sdpMid: event.candidate.sdpMid,
              sdpMLineIndex: event.candidate.sdpMLineIndex
            });
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

      // Send answer
      await axios.post(`${apiUrl}/webrtc/answer`, {
        session_id: session_id,
        sdp: answer.sdp,
        type: answer.type
      });

      setIsConnected(true);
      updateStatus('WebRTC stream connected', 'success');
      logMessage('WebRTC stream connected successfully');

      // Start session refresh
      startSessionRefresh();

                } catch (error) {
              logMessage(`Failed to start stream: ${error.message}`);
              if (error.response) {
                logMessage(`Error status: ${error.response.status}`);
                logMessage(`Error data: ${JSON.stringify(error.response.data)}`);
              }
              updateStatus(`Failed to start stream: ${error.message}`, 'error');
            }
  };

  const stopStream = async () => {
    try {
      if (sessionIdRef.current) {
        logMessage('Stopping WebRTC stream...');
        await axios.delete(`${apiUrl}/webrtc/sessions/${sessionIdRef.current}`);
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
      const [sessionsResponse, streamRefsResponse] = await Promise.all([
        axios.get(`${apiUrl}/webrtc/sessions`),
        axios.get(`${apiUrl}/webrtc/stream-references`)
      ]);

      setSessions(sessionsResponse.data);
      setStreamRefs(streamRefsResponse.data);
    } catch (error) {
      logMessage(`Failed to refresh sessions: ${error.message}`);
    }
  };

  const closeAllSessions = async () => {
    try {
      logMessage('Closing all sessions...');
      await axios.delete(`${apiUrl}/webrtc/sessions`);
      logMessage('All sessions closed');
      setSessions([]);
      setStreamRefs([]);
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
    discoverDevices();
    return () => {
      stopSessionRefresh();
    };
  }, [discoverDevices]);

  return (
    <div>
      <div className="container">
        <h2>🎥 RealSense WebRTC Multi-Client Demo</h2>
        <p>Connect to RealSense cameras via WebRTC for real-time video streaming</p>
        
        <div className="form-group">
          <label htmlFor="apiUrl">API URL:</label>
          <input
            type="text"
            id="apiUrl"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="http://localhost:8000/api"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="deviceId">Device ID:</label>
          <input
            type="text"
            id="deviceId"
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
            placeholder="e.g., 844212070924"
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="streamType">Stream Type:</label>
          <select
            id="streamType"
            value={streamType}
            onChange={(e) => setStreamType(e.target.value)}
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
          <button onClick={discoverDevices} className="button">
            🔍 Discover Devices
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
            🔄 Reset Device
          </button>
        </div>

        <div className={`status ${statusType}`}>
          {status}
        </div>
      </div>

      <div className="container">
        <h2>📊 Active Sessions</h2>
        <div className="sessions-panel">
          {sessions.length > 0 ? (
            <div>
              <h3>Active WebRTC Sessions ({sessions.length})</h3>
              {sessions.map((session, index) => (
                <p key={index}>
                  Session {index + 1}: {session.session_id} - {session.device_id} ({session.stream_types.join(', ')})
                </p>
              ))}
            </div>
          ) : (
            <div>
              <h3>No active sessions</h3>
              <p>Start a stream to see active WebRTC sessions here.</p>
            </div>
          )}
        </div>
      </div>

      <div className="container">
        <h2>🔗 Stream References</h2>
        <div className="sessions-panel">
          {streamRefs.length > 0 ? (
            <div>
              <h3>Active Stream References ({streamRefs.length})</h3>
              {streamRefs.map((ref, index) => (
                <p key={index}>
                  Device {ref.device_id}: {ref.stream_type} (refs: {ref.reference_count})
                </p>
              ))}
            </div>
          ) : (
            <div>
              <h3>No active stream references</h3>
              <p>No device streams are currently active.</p>
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
