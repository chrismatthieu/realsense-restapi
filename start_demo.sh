#!/bin/bash

echo "=== RealSense WebRTC Demo Startup ==="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1

# Check if RealSense camera is connected
echo "Checking for RealSense devices..."
python3 -c "
import pyrealsense2 as rs
ctx = rs.context()
devices = ctx.query_devices()
if len(devices) > 0:
    print(f'✅ Found {len(devices)} RealSense device(s):')
    for device in devices:
        print(f'   - {device.get_info(rs.camera_info.name)} (Serial: {device.get_info(rs.camera_info.serial_number)})')
else:
    print('❌ No RealSense devices found. Please connect a camera.')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "Please connect a RealSense camera and try again."
    exit 1
fi

echo ""
echo "Starting RealSense REST API server..."
echo "Server will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "To test the WebRTC demo:"
echo "1. Open http://localhost:8000 in your browser"
echo "2. Set API URL to: http://localhost:8000/api"
echo "3. Enter your device ID (shown above)"
echo "4. Select stream type and click 'Start Stream'"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
source venv/bin/activate
python main.py
