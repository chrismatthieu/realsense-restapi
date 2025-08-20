#!/bin/bash

# RealSense React Client Development Startup Script
# This script starts both the signaling server and React development server

echo "🚀 Starting RealSense React Client Development Environment..."

# Function to cleanup on exit
cleanup() {
    echo "🛑 Shutting down development environment..."
    kill $SIGNALING_PID $REACT_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if Python API server is running
echo "🔍 Checking Python API server..."
if ! curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "❌ Python API server is not running on http://localhost:8000"
    echo "Please start the Python API server first:"
    echo "  cd /path/to/realsense-restapi"
    echo "  python main.py"
    exit 1
fi
echo "✅ Python API server is running"

# Start signaling server
echo "📡 Starting signaling server..."
cd server
npm start &
SIGNALING_PID=$!
cd ..

# Wait a moment for signaling server to start
sleep 2

# Check if signaling server started successfully
if ! curl -s http://localhost:3001/health > /dev/null 2>&1; then
    echo "❌ Signaling server failed to start"
    kill $SIGNALING_PID 2>/dev/null
    exit 1
fi
echo "✅ Signaling server is running on http://localhost:3001"

# Start React development server
echo "⚛️  Starting React development server..."
npm start &
REACT_PID=$!

# Wait for React server to start
sleep 5

# Check if React server started successfully
if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "❌ React development server failed to start"
    kill $SIGNALING_PID $REACT_PID 2>/dev/null
    exit 1
fi
echo "✅ React development server is running on http://localhost:3000"

echo ""
echo "🎉 Development environment is ready!"
echo ""
echo "📱 React App:     http://localhost:3000"
echo "📡 Signaling:     http://localhost:3001"
echo "🐍 Python API:    http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user to stop
wait
