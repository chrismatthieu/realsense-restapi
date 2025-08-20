import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import axios from 'axios';

const PointCloudDemo = () => {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000/api');
  const [deviceId, setDeviceId] = useState('');
  const [isViewerRunning, setIsViewerRunning] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('Disconnected');
  const [pointCloudStatus, setPointCloudStatus] = useState('Stopped');
  const [vertexCount, setVertexCount] = useState(0);
  const [fps, setFps] = useState(0);
  
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
  const animationIdRef = useRef(null);
  const frameCountRef = useRef(0);
  const lastTimeRef = useRef(0);
  const hasInitializedCameraRef = useRef(false);

  const logMessage = useCallback((message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLog(prev => `[${timestamp}] ${message}\n${prev}`);
  }, []);

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
    if (!isViewerRunningRef.current || !deviceId) return;

    try {
      logMessage(`Fetching point cloud data for device: ${deviceId}`);
      const response = await axios.get(`${apiUrl}/webrtc/pointcloud-data/${deviceId}`);
      const data = response.data;

      logMessage(`Received data: ${JSON.stringify(data).substring(0, 200)}...`);
      logMessage(`Data type: ${typeof data}, vertices type: ${typeof data.vertices}`);

      if (!data.vertices || data.vertices.length === 0) {
        logMessage('No vertices data found');
        setPointCloudStatus('No data');
        return;
      }

      logMessage(`Vertices array length: ${data.vertices.length}`);
      
      // Handle different data formats
      let vertexArray;
      if (Array.isArray(data.vertices)) {
        // Direct array format
        vertexArray = data.vertices;
      } else if (typeof data.vertices === 'string') {
        // Base64 encoded format - skip for now
        logMessage('Received base64 encoded data, skipping this update');
        return;
      } else {
        logMessage('Unknown vertices format, skipping this update');
        return;
      }
      
      // Flatten the array and filter out NaN values
      const flatVertices = [];
      for (let i = 0; i < vertexArray.length; i++) {
        const vertex = vertexArray[i];
        if (Array.isArray(vertex) && vertex.length === 3) {
          const [x, y, z] = vertex;
          if (!isNaN(x) && !isNaN(y) && !isNaN(z) && 
              isFinite(x) && isFinite(y) && isFinite(z)) {
            flatVertices.push(x, y, z);
          }
        }
      }
      
      if (flatVertices.length === 0) {
        logMessage('No valid vertices found after filtering');
        return;
      }
      
      const vertices = new Float32Array(flatVertices);
      logMessage(`Valid vertices: ${flatVertices.length / 3}, filtered from ${vertexArray.length} input vertices`);
      
      // Debug: Show first few vertices
      if (flatVertices.length > 0) {
        logMessage(`First vertex: [${flatVertices[0]}, ${flatVertices[1]}, ${flatVertices[2]}]`);
        if (flatVertices.length >= 6) {
          logMessage(`Second vertex: [${flatVertices[3]}, ${flatVertices[4]}, ${flatVertices[5]}]`);
        }
      }
      
      setVertexCount(vertices.length / 3);

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
      geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
      logMessage(`Created geometry with ${geometry.attributes.position.count} vertices`);

      // Create material
      const material = new THREE.PointsMaterial({
        size: 0.01, // Smaller points
        color: 0x00ff00,
        transparent: true,
        opacity: 1.0, // Full opacity
        sizeAttenuation: true
      });
      logMessage('Created point cloud material');

      // Create point cloud
      const pointCloud = new THREE.Points(geometry, material);
      sceneRef.current.add(pointCloud);
      pointCloudRef.current = pointCloud;
      logMessage(`Added point cloud to scene. Scene children count: ${sceneRef.current.children.length}`);

      // Preserve camera state
      if (!hasInitializedCameraRef.current) {
        // Initial setup
        cameraRef.current.position.set(0, 0, 2);
        controlsRef.current.target.set(0, 0, 0);
        hasInitializedCameraRef.current = true;
        logMessage(`Initialized camera at position: ${cameraRef.current.position.x}, ${cameraRef.current.position.y}, ${cameraRef.current.position.z}`);
      } else {
        // Preserve user's view
        cameraRef.current.position.copy(currentCameraPosition);
        controlsRef.current.target.copy(currentTarget);
        logMessage(`Preserved camera at position: ${cameraRef.current.position.x}, ${cameraRef.current.position.y}, ${cameraRef.current.position.z}`);
      }

      setPointCloudStatus('Streaming');
      logMessage(`Updated point cloud with ${vertices.length / 3} vertices`);

    } catch (error) {
      logMessage(`Error updating point cloud: ${error.message}`);
      setPointCloudStatus('Error');
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
    if (!deviceId) {
      alert('Please enter a device ID');
      return;
    }

    try {
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

      // Automatically activate point cloud processing
      try {
        logMessage('Activating point cloud processing...');
        await axios.post(`${apiUrl}/devices/${deviceId}/point_cloud/activate`);
        logMessage('Point cloud processing activated');

        // Start a depth stream session to enable point cloud data
        logMessage('Starting depth stream session...');
        await axios.post(`${apiUrl}/devices/${deviceId}/stream/start`, {
          configs: [{
            sensor_id: `${deviceId}-sensor-0`,
            stream_type: 'depth',
            format: 'z16',
            resolution: { width: 640, height: 480 },
            framerate: 30
          }]
        });
        logMessage('Depth stream session started');

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

  const resetDevice = async () => {
    if (!deviceId) {
      alert('Please enter a device ID');
      return;
    }

    try {
      logMessage('Resetting device...');
      
      // Stop any active streams
      try {
        await axios.post(`${apiUrl}/devices/${deviceId}/stream/stop`);
        logMessage('Stopped active streams');
      } catch (error) {
        logMessage(`Warning: ${error.message}`);
      }
      
      // Deactivate point cloud processing
      try {
        await axios.post(`${apiUrl}/devices/${deviceId}/point_cloud/activate`, { enabled: false });
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

    // Reset camera initialization flag
    hasInitializedCameraRef.current = false;

    // Clean up depth session if it exists
    if (deviceId) {
      try {
        logMessage('Cleaning up depth session...');
        await axios.post(`${apiUrl}/devices/${deviceId}/stream/stop`);
        logMessage('Depth session cleaned up');
        
        // Also deactivate point cloud processing
        logMessage('Deactivating point cloud processing...');
        await axios.post(`${apiUrl}/devices/${deviceId}/point_cloud/activate`, { enabled: false });
        logMessage('Point cloud processing deactivated');
        
        // Wait a moment for cleanup to complete
        await new Promise(resolve => setTimeout(resolve, 500));
        
      } catch (error) {
        logMessage(`Warning: Failed to clean up depth session: ${error.message}`);
      }
    }

    logMessage('3D point cloud viewer stopped');
  };

  const discoverDevices = useCallback(async () => {
    try {
      logMessage('Discovering devices...');
      logMessage(`Making request to: ${apiUrl}/devices/`);
      
      const response = await axios.get(`${apiUrl}/devices/`);
      logMessage(`Response status: ${response.status}`);
      logMessage(`Response data: ${JSON.stringify(response.data)}`);
      
      const devices = response.data;
      
      if (devices.length > 0) {
        setDeviceId(devices[0].device_id);
        logMessage(`Found ${devices.length} device(s): ${devices.map(d => d.device_id).join(', ')}`);
      } else {
        logMessage('No devices found');
      }
    } catch (error) {
      logMessage(`Failed to discover devices: ${error.message}`);
      logMessage(`Error details: ${JSON.stringify(error.response?.data || error)}`);
    }
  }, [apiUrl, logMessage]);

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
    discoverDevices();
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
      if (deviceId) {
        // Clean up any active streams
        try {
          axios.post(`${apiUrl}/devices/${deviceId}/stream/stop`);
          axios.post(`${apiUrl}/devices/${deviceId}/point_cloud/activate`, { enabled: false });
        } catch (error) {
          // Ignore cleanup errors on unmount
        }
      }
    };
  }, [discoverDevices, handleKeyPress]);

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
          <label htmlFor="apiUrl">API URL:</label>
          <input
            type="text"
            id="apiUrl"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="Enter API URL"
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
        
        <div>
          <button onClick={discoverDevices} className="button">
            🔍 Discover Devices
          </button>
          <button 
            onClick={startPointCloudViewer} 
            className="button success"
            disabled={isViewerRunning}
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
          >
            🔄 Reset Device
          </button>
        </div>

        <div className="status info">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span><strong>Connection:</strong> {connectionStatus}</span>
            <span><strong>Point Cloud:</strong> {pointCloudStatus}</span>
            <span><strong>Vertices:</strong> {vertexCount.toLocaleString()}</span>
            <span><strong>FPS:</strong> {fps}</span>
          </div>
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
