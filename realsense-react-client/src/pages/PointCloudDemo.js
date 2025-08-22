import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import cloudSignalingService from '../services/cloudSignalingService';

const PointCloudDemo = () => {
  const [robots, setRobots] = useState([]);
  const [selectedRobot, setSelectedRobot] = useState('');
  const [isViewerRunning, setIsViewerRunning] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('Disconnected');
  const [sessionId, setSessionId] = useState(null);
  const [pointCloudStatus, setPointCloudStatus] = useState('Stopped');
  const [vertexCount, setVertexCount] = useState(0);
  const [fps, setFps] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  
  // Use ref to track running state for intervals
  const isViewerRunningRef = useRef(false);
  const updateIntervalRef = useRef(null);
  const [log, setLog] = useState('');

  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const pointCloudRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const animationIdRef = useRef(null);
  const frameCountRef = useRef(0);
  const lastTimeRef = useRef(0);
  const hasInitializedCameraRef = useRef(false);

  const logMessage = useCallback((message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLog(prev => `[${timestamp}] ${message}\n${prev}`);
  }, []);

  const discoverRobots = async () => {
    try {
      logMessage('🔍 Discovering available robots...');
      const availableRobots = await cloudSignalingService.getAvailableRobots();
      setRobots(availableRobots);
      logMessage(`✅ Found ${availableRobots.length} robot(s): ${availableRobots.map(r => r.robotId).join(', ')}`);
    } catch (error) {
      logMessage(`❌ Failed to discover robots: ${error.message}`);
    }
  };

  const connectToCloud = async () => {
    try {
      logMessage('🌐 Connecting to cloud signaling server...');
      await cloudSignalingService.connect();
      setIsConnected(true);
      setConnectionStatus('Connected');
      logMessage('✅ Connected to cloud signaling server');
      
      // Discover robots after connecting
      await discoverRobots();
    } catch (error) {
      logMessage(`❌ Failed to connect to cloud: ${error.message}`);
      setConnectionStatus('Connection Failed');
    }
  };

  const initThreeJS = () => {
    if (!canvasRef.current) return;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(
      75,
      canvasRef.current.clientWidth / canvasRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0, 5);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ 
      canvas: canvasRef.current,
      antialias: true 
    });
    renderer.setSize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    rendererRef.current = renderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = false;
    controls.minDistance = 0.1;
    controls.maxDistance = 100;
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);

    // Grid helper
    const gridHelper = new THREE.GridHelper(10, 10);
    scene.add(gridHelper);

    // Axes helper
    const axesHelper = new THREE.AxesHelper(1);
    scene.add(axesHelper);

    logMessage('Three.js initialized');
  };

  const updatePointCloud = async () => {
    // This function is now deprecated - point cloud data comes through WebRTC data channels
    if (!isViewerRunningRef.current || !selectedRobot) return;
    
    // Just log that we're using WebRTC data channels now
    if (Math.random() < 0.1) { // Only log occasionally to avoid spam
      logMessage('📡 Point cloud data now comes through WebRTC data channels');
    }
  };

  const animate = (currentTime) => {
    if (!isViewerRunningRef.current) return;

    animationIdRef.current = requestAnimationFrame(animate);

    // Calculate FPS
    frameCountRef.current++;
    if (currentTime - lastTimeRef.current >= 1000) {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
      lastTimeRef.current = currentTime;
    }

    // Update controls
    if (controlsRef.current) {
      controlsRef.current.update();
    }

    // Render
    if (rendererRef.current && sceneRef.current && cameraRef.current) {
      rendererRef.current.render(sceneRef.current, cameraRef.current);
      // Debug: Log rendering info every 60 frames (about once per second)
      if (frameCountRef.current % 60 === 0) {
        logMessage(`Rendering frame. Scene children: ${sceneRef.current.children.length}, Point cloud: ${pointCloudRef.current ? 'Present' : 'Missing'}`);
      }
    }
  };

  const startPointCloudViewer = async () => {
    if (!selectedRobot) {
      alert('Please select a robot first');
      return;
    }

    try {
      const deviceId = selectedRobot.replace('robot-', '');
      
      // Initialize Three.js if not already done
      if (!sceneRef.current) {
        initThreeJS();
      }

      // Clear existing point cloud
      if (pointCloudRef.current) {
        sceneRef.current.remove(pointCloudRef.current);
        pointCloudRef.current.geometry.dispose();
        pointCloudRef.current.material.dispose();
        pointCloudRef.current = null;
      }

      setIsViewerRunning(true);
      isViewerRunningRef.current = true;
      setConnectionStatus('Connected');
      setPointCloudStatus('Activating...');
      logMessage('Starting 3D point cloud viewer...');

      // Start a WebRTC session for depth stream to enable point cloud data
      try {
        logMessage('Starting WebRTC depth stream session...');
        const sessionData = await cloudSignalingService.createSession(selectedRobot, deviceId, ['depth']);
        const newSessionId = sessionData.sessionId;
        const offer = sessionData.offer;
        setSessionId(newSessionId);
        logMessage(`WebRTC depth session created: ${newSessionId}`);

        // Create RTCPeerConnection
        const pc = new RTCPeerConnection({
          iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });
        peerConnectionRef.current = pc;

        // Handle ICE candidates
        pc.onicecandidate = async (event) => {
          if (event.candidate) {
            try {
              await cloudSignalingService.sendIceCandidate(newSessionId, event.candidate);
            } catch (error) {
              logMessage(`Failed to send ICE candidate: ${error.message}`);
            }
          }
        };

        // Handle connection state changes
        pc.onconnectionstatechange = () => {
          logMessage(`📡 Peer connection state: ${pc.connectionState}`);
        };

        // Handle ICE connection state changes
        pc.oniceconnectionstatechange = () => {
          logMessage(`🧊 ICE connection state: ${pc.iceConnectionState}`);
        };

        // Set remote description
        await pc.setRemoteDescription(new RTCSessionDescription(offer));

        // Create answer
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

                // Send answer via cloud server
        logMessage(`Sending answer for session: ${newSessionId}`);
        await cloudSignalingService.sendAnswer(newSessionId, answer);
        
        // Activate point cloud processing
        logMessage('Activating point cloud processing...');
        await cloudSignalingService.activatePointCloud(deviceId, true);
        logMessage('Point cloud processing activated');

        // Setup WebRTC data channel listener
        logMessage('Setting up WebRTC data channel listener...');
        setupWebRTCDataChannel(newSessionId);

      } catch (error) {
        logMessage(`Warning: ${error.message}`);
      }

      // Start animation loop
      animate(0);

      // Start point cloud updates
      updateIntervalRef.current = setInterval(() => {
        if (isViewerRunningRef.current) {
          updatePointCloud();
        } else {
          clearInterval(updateIntervalRef.current);
        }
      }, 1000);

      logMessage('3D point cloud viewer started successfully');

    } catch (error) {
      logMessage(`Failed to start 3D viewer: ${error.message}`);
      setConnectionStatus('Error');
      setPointCloudStatus('Error');
    }
  };

  // State for chunked message reassembly
  const [chunkedMessages, setChunkedMessages] = useState(new Map());

  const handleChunkedPointCloudData = (chunkData) => {
    const { message_id, chunk_index, total_chunks, is_last_chunk, vertices } = chunkData;
    
    logMessage(`📡 Received chunk ${chunk_index + 1}/${total_chunks} for message ${message_id} with ${vertices.length} vertices`);
    
    // Get or create message buffer for this message ID
    setChunkedMessages(prev => {
      const newMessages = new Map(prev);
      
      if (!newMessages.has(message_id)) {
        newMessages.set(message_id, {
          allVertices: [],
          receivedChunks: 0,
          totalChunks: total_chunks,
          totalVertices: chunkData.total_vertices
        });
      }
      
      const messageBuffer = newMessages.get(message_id);
      messageBuffer.allVertices.push(...vertices);
      messageBuffer.receivedChunks++;
      
      // Check if we have all chunks
      if (messageBuffer.receivedChunks === total_chunks) {
        logMessage(`📡 All chunks received for message ${message_id}, updating point cloud with ${messageBuffer.allVertices.length} vertices`);
        logMessage(`📡 Data sample: ${JSON.stringify(messageBuffer.allVertices.slice(0, 3))}`);
        
        // Update the point cloud with the complete data
        updatePointCloudWithData(messageBuffer.allVertices);
        
        // Update status to active
        setPointCloudStatus('Active');
        
        // Remove the message buffer
        newMessages.delete(message_id);
      }
      
      return newMessages;
    });
  };

  const setupWebRTCDataChannel = (sessionId) => {
    try {
      // Get the WebRTC peer connection from the ref
      const peerConnection = peerConnectionRef.current;
      
      if (!peerConnection) {
        logMessage('❌ No peer connection available for data channel');
        return;
      }

      // Listen for data channel from the server
      peerConnection.ondatachannel = (event) => {
        const dataChannel = event.channel;
        logMessage(`📡 Data channel received: ${dataChannel.label} (state: ${dataChannel.readyState})`);
        
        if (dataChannel.label === 'pointcloud-data') {
          logMessage('📡 WebRTC data channel opened for point cloud data');
          
          dataChannel.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              logMessage(`📡 Raw data received: ${JSON.stringify(data).substring(0, 200)}...`);
              
              // Handle heartbeat messages to keep connection alive
              if (data.type === 'heartbeat') {
                logMessage(`💓 Received heartbeat for session ${data.session_id}`);
                return;
              }
              
              if (data.type === 'pointcloud-data' && data.vertices) {
                // Check if this is a chunked message
                if (data.chunk_info) {
                  // Handle chunked point cloud data
                  handleChunkedPointCloudData(data);
                } else {
                  // Handle single message (small data)
                  logMessage(`📡 Received point cloud data: ${data.vertices.length} vertices`);
                  logMessage(`📡 Data sample: ${JSON.stringify(data.vertices.slice(0, 3))}`);
                  updatePointCloudWithData(data.vertices);
                }
              }
            } catch (error) {
              logMessage(`❌ Error parsing data channel message: ${error.message}`);
            }
          };

          dataChannel.onclose = () => {
            logMessage('📡 WebRTC data channel closed');
          };

          dataChannel.onerror = (error) => {
            logMessage(`❌ WebRTC data channel error: ${error.message}`);
          };
        }
      };

      logMessage('✅ WebRTC data channel setup complete');

    } catch (error) {
      logMessage(`❌ Error setting up WebRTC data channel: ${error.message}`);
    }
  };

  const updatePointCloudWithData = (vertices) => {
    try {
      if (!vertices || vertices.length === 0) {
        logMessage('No vertices data received');
        return;
      }

      // Flatten the array and filter out NaN values
      const flatVertices = [];
      let validCount = 0;
      let invalidCount = 0;
      
      for (let i = 0; i < vertices.length; i++) {
        const vertex = vertices[i];
        if (Array.isArray(vertex) && vertex.length === 3) {
          const [x, y, z] = vertex;
          if (!isNaN(x) && !isNaN(y) && !isNaN(z) && 
              isFinite(x) && isFinite(y) && isFinite(z)) {
            flatVertices.push(x, y, z);
            validCount++;
          } else {
            invalidCount++;
          }
        } else {
          invalidCount++;
        }
      }
      
      logMessage(`Data processing: ${validCount} valid vertices, ${invalidCount} invalid vertices`);
      
      if (flatVertices.length === 0) {
        logMessage('No valid vertices found after filtering');
        return;
      }
      
      const vertexArray = new Float32Array(flatVertices);
      logMessage(`Valid vertices: ${flatVertices.length / 3}, filtered from ${vertices.length} input vertices`);
      
      setVertexCount(vertexArray.length / 3);

      // Store current camera state
      const currentCameraPosition = cameraRef.current.position.clone();
      const currentTarget = controlsRef.current.target.clone();

      // Remove existing point cloud
      if (pointCloudRef.current) {
        sceneRef.current.remove(pointCloudRef.current);
        pointCloudRef.current.geometry.dispose();
        pointCloudRef.current.material.dispose();
      }

      // Create new geometry
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(vertexArray, 3));
      logMessage(`Created geometry with ${geometry.attributes.position.count} vertices`);
      logMessage(`Geometry bounds: ${JSON.stringify(geometry.boundingBox)}`);

      // Create material
      const material = new THREE.PointsMaterial({
        size: 0.01,
        color: 0x00ff00,
        transparent: true,
        opacity: 1.0,
        sizeAttenuation: true
      });

      // Create point cloud
      const pointCloud = new THREE.Points(geometry, material);
      sceneRef.current.add(pointCloud);
      pointCloudRef.current = pointCloud;
      logMessage(`Added point cloud to scene. Scene children count: ${sceneRef.current.children.length}`);
      logMessage(`Point cloud visible: ${pointCloud.visible}, position: ${pointCloud.position.x}, ${pointCloud.position.y}, ${pointCloud.position.z}`);
      
      // Check if point cloud is in camera view
      const frustum = new THREE.Frustum();
      const matrix = new THREE.Matrix4().multiplyMatrices(cameraRef.current.projectionMatrix, cameraRef.current.matrixWorldInverse);
      frustum.setFromProjectionMatrix(matrix);
      
      const boundingBox = new THREE.Box3().setFromObject(pointCloud);
      const inView = frustum.intersectsBox(boundingBox);
      logMessage(`Point cloud in camera view: ${inView}, bounding box: ${JSON.stringify(boundingBox)}`);

      // Preserve camera state
      if (!hasInitializedCameraRef.current) {
        cameraRef.current.position.set(0, 0, 2);
        controlsRef.current.target.set(0, 0, 0);
        hasInitializedCameraRef.current = true;
        logMessage(`Camera initialized at position: ${cameraRef.current.position.x}, ${cameraRef.current.position.y}, ${cameraRef.current.position.z}`);
      } else {
        cameraRef.current.position.copy(currentCameraPosition);
        controlsRef.current.target.copy(currentTarget);
        logMessage(`Camera restored to position: ${cameraRef.current.position.x}, ${cameraRef.current.position.y}, ${cameraRef.current.position.z}`);
      }
      
      // Log camera frustum for debugging
      logMessage(`Camera near: ${cameraRef.current.near}, far: ${cameraRef.current.far}, fov: ${cameraRef.current.fov}`);

      setPointCloudStatus('Streaming');
      logMessage(`Updated point cloud with ${vertexArray.length / 3} vertices`);
      logMessage(`Scene now contains ${sceneRef.current.children.length} objects`);
      logMessage(`Point cloud visible: ${pointCloud.visible}, position: ${pointCloud.position.x}, ${pointCloud.position.y}, ${pointCloud.position.z}`);

    } catch (error) {
      logMessage(`Error updating point cloud with data: ${error.message}`);
      setPointCloudStatus('Error');
    }
  };

  const resetDevice = async () => {
    if (!selectedRobot) {
      alert('Please select a robot first');
      return;
    }

    try {
      const deviceId = selectedRobot.replace('robot-', '');
      logMessage('Resetting device...');
      
      // Close WebRTC session if exists
      if (sessionId) {
        try {
          await cloudSignalingService.closeSession(sessionId);
          logMessage('Closed WebRTC session');
        } catch (error) {
          logMessage(`Warning: ${error.message}`);
        }
      }
      
      // Deactivate point cloud processing
      try {
        await cloudSignalingService.activatePointCloud(deviceId, false);
        logMessage('Deactivated point cloud processing');
      } catch (error) {
        logMessage(`Warning: ${error.message}`);
      }
      
      // Wait for cleanup
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      logMessage('Device reset successfully - ready for WebRTC demo');
    } catch (error) {
      logMessage(`Failed to reset device: ${error.message}`);
    }
  };

  const stopPointCloudViewer = async () => {
    setIsViewerRunning(false);
    isViewerRunningRef.current = false;
    setConnectionStatus('Disconnected');
    setPointCloudStatus('Stopped');
    setVertexCount(0);
    setFps(0);

    if (animationIdRef.current) {
      cancelAnimationFrame(animationIdRef.current);
      animationIdRef.current = null;
    }

    // Clear update interval
    if (updateIntervalRef.current) {
      clearInterval(updateIntervalRef.current);
      updateIntervalRef.current = null;
    }

    // Clear existing point cloud
    if (pointCloudRef.current) {
      sceneRef.current.remove(pointCloudRef.current);
      pointCloudRef.current.geometry.dispose();
      pointCloudRef.current.material.dispose();
      pointCloudRef.current = null;
    }

    // Close WebRTC peer connection
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
      logMessage('Closed WebRTC peer connection');
    }

    // Reset camera initialization flag
    hasInitializedCameraRef.current = false;

    // Clean up WebRTC session if it exists
    if (sessionId) {
      try {
        logMessage('Cleaning up WebRTC session...');
        await cloudSignalingService.closeSession(sessionId);
        logMessage('WebRTC session cleaned up');
    
        // Also deactivate point cloud processing
        logMessage('Deactivating point cloud processing...');
        const deviceId = selectedRobot.replace('robot-', '');
        await cloudSignalingService.activatePointCloud(deviceId, false);
        logMessage('Point cloud processing deactivated');
    
        // Wait a moment for cleanup to complete
        await new Promise(resolve => setTimeout(resolve, 500));
    
      } catch (error) {
        logMessage(`Warning: Failed to clean up WebRTC session: ${error.message}`);
      }
    }
    
    // Clear session ID
    setSessionId(null);

    logMessage('3D point cloud viewer stopped');
  };



  const handleKeyPress = useCallback((event) => {
    if (event.key === 'r' || event.key === 'R') {
      // Reset camera
      if (cameraRef.current && controlsRef.current) {
        cameraRef.current.position.set(0, 0, 2);
        controlsRef.current.target.set(0, 0, 0);
        hasInitializedCameraRef.current = true;
        logMessage('Camera reset to initial position');
      }
    }
  }, [logMessage]);

  useEffect(() => {
    // Initialize Three.js on component mount
    initThreeJS();

    // Connect to cloud server on mount
    connectToCloud();
    window.addEventListener('keydown', handleKeyPress);

    return () => {
      window.removeEventListener('keydown', handleKeyPress);
      if (animationIdRef.current) {
        cancelAnimationFrame(animationIdRef.current);
      }
      if (updateIntervalRef.current) {
        clearInterval(updateIntervalRef.current);
      }
      
      // Cleanup on unmount
      if (selectedRobot) {
        const deviceId = selectedRobot.replace('robot-', '');
        // Clean up any active streams
        try {
          cloudSignalingService.stopDeviceStream(deviceId);
          cloudSignalingService.activatePointCloud(deviceId, false);
        } catch (error) {
          // Ignore cleanup errors on unmount
        }
      }
      
      cloudSignalingService.disconnect();
    };
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current && cameraRef.current && rendererRef.current) {
        const width = canvasRef.current.clientWidth;
        const height = canvasRef.current.clientHeight;

        cameraRef.current.aspect = width / height;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.setSize(width, height);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div>
      <div className="container">
        <h2>🎯 RealSense 3D Point Cloud Viewer</h2>
        <p>Interactive 3D visualization of RealSense depth data</p>
        
        <div className="form-group">
          <label htmlFor="robotSelect">Select Robot:</label>
          <select
            id="robotSelect"
            value={selectedRobot}
            onChange={(e) => setSelectedRobot(e.target.value)}
            disabled={!isConnected}
          >
            <option value="">Select a robot...</option>
            {robots.map((robot) => (
              <option key={robot.robotId} value={robot.robotId}>
                {robot.robotId} - {robot.deviceInfo?.name || 'Unknown Device'}
              </option>
            ))}
          </select>
        </div>
        
        <div>
          <button onClick={discoverRobots} className="button" disabled={!isConnected}>
            🔍 Discover Robots
          </button>
          <button 
            onClick={startPointCloudViewer} 
            className="button success"
            disabled={isViewerRunning || !selectedRobot}
          >
            ▶️ Start 3D Viewer
          </button>
          <button 
            onClick={stopPointCloudViewer} 
            className="button danger"
            disabled={!isViewerRunning}
          >
            ⏹️ Stop Viewer
          </button>
          <button 
            onClick={resetDevice} 
            className="button warning"
            disabled={!selectedRobot}
          >
            🔄 Reset Device
          </button>
        </div>

        <div className="status info">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span><strong>Cloud Connection:</strong> {isConnected ? 'Connected' : 'Disconnected'}</span>
            <span><strong>Point Cloud:</strong> {pointCloudStatus}</span>
            <span><strong>Vertices:</strong> {vertexCount.toLocaleString()}</span>
            <span><strong>FPS:</strong> {fps}</span>
          </div>
        </div>
        <div className={`status ${isConnected ? 'success' : 'error'}`}>
          🌐 Cloud Signaling Server: {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      <div className="container">
        <h2>🎮 3D Viewer Controls</h2>
        <div className="sessions-panel">
          <h3>Mouse Controls:</h3>
          <ul>
            <li><strong>Left Click + Drag:</strong> Rotate camera around target</li>
            <li><strong>Right Click + Drag:</strong> Pan camera</li>
            <li><strong>Scroll Wheel:</strong> Zoom in/out</li>
            <li><strong>R Key:</strong> Reset camera to initial position</li>
          </ul>
        </div>
      </div>

      <div className="container">
        <h2>🎥 3D Point Cloud Viewer</h2>
        <div style={{ 
          background: 'rgba(0, 0, 0, 0.8)', 
          borderRadius: '15px', 
          padding: '20px', 
          height: '600px', 
          position: 'relative', 
          overflow: 'hidden' 
        }}>
          <canvas
            ref={canvasRef}
            style={{
              width: '100%',
              height: '100%',
              borderRadius: '10px',
              display: 'block'
            }}
          />
          {!isViewerRunning && (
            <div style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              fontSize: '18px',
              color: '#ffd700'
            }}>
              Click "Start 3D Viewer" to begin
            </div>
          )}
          {isViewerRunning && vertexCount > 0 && (
            <div style={{
              position: 'absolute',
              top: '20px',
              right: '20px',
              background: 'rgba(0, 0, 0, 0.7)',
              padding: '10px',
              borderRadius: '8px',
              fontSize: '14px',
              color: 'white'
            }}>
              Points: {vertexCount.toLocaleString()}
            </div>
          )}
        </div>
      </div>

      <div className="container">
        <h2>📝 Connection Log</h2>
        <div className="log">{log}</div>
      </div>
    </div>
  );
};

export default PointCloudDemo;
