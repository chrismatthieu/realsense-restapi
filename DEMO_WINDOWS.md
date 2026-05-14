# Running the Demo on Windows

## 1. One-time setup (already done if you followed the assistant)

```powershell
cd C:\Users\cmatthie\Projects\realsense-restapi
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# If pip fails on aiortc/av, install manually: pip install av --only-binary=:all: then pip install "aiortc>=1.14"
```

## 2. Verify the camera is detected

```powershell
.\venv\Scripts\Activate.ps1
python check_camera.py
```

You should see at least one device with a serial number. If you see "Found 0", see the troubleshooting tips printed by the script.

## 3. Start the API server

If PowerShell blocks script execution, use the venv's Python directly (no activation needed):

```powershell
.\venv\Scripts\python.exe main.py
```

Or run `run_server.bat`. Alternatively, allow scripts for this session then activate:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\venv\Scripts\Activate.ps1
python main.py
```

Leave this terminal open. You should see:
- `Uvicorn running on http://0.0.0.0:8000`
- A message about connecting to the cloud server (port 3001) is optional; the browser demo works without it.

## 4. Open the demo in your browser

- **WebRTC video demo:** http://localhost:8000/webrtc_demo.html  
- **3D point cloud demo:** http://localhost:8000/webrtc_3d_pointcloud_demo.html  
- **API docs:** http://localhost:8000/docs  

In the WebRTC demo:
1. Click **Discover Devices** to fill in your camera’s device ID.
2. Choose a stream type (e.g. Color) and click **Start WebRTC Session**.
3. Allow the page to use the camera if prompted; video should appear.

## Optional: full stack (React + cloud signaling)

For the React viewer and cloud signaling (e.g. multiple clients):

1. **Terminal 1 – API:** `python main.py`
2. **Terminal 2 – Signaling:** `cd realsense-react-client\server && node cloud-signaling-server.js`
3. **Terminal 3 – React:** `cd realsense-react-client && npm start`  
   Then open http://localhost:3000
