#!/bin/bash

# Cloud Development Startup Script
# This script starts all components for the robot-to-cloud WebSocket architecture

set -e

echo "🚀 Starting Cloud Development Environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${RED}Port $1 is already in use${NC}"
        return 1
    fi
    return 0
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${BLUE}Waiting for $service_name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}$service_name is ready!${NC}"
            return 0
        fi
        
        echo -e "${YELLOW}Attempt $attempt/$max_attempts - $service_name not ready yet...${NC}"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}$service_name failed to start within $max_attempts attempts${NC}"
    return 1
}

# Kill any existing processes
echo -e "${YELLOW}Cleaning up existing processes...${NC}"
pkill -f "python main.py" || true
pkill -f "node.*cloud-signaling-server.js" || true
pkill -f "npm start" || true

# Wait a moment for processes to fully stop
sleep 2

# Check ports
echo -e "${BLUE}Checking ports...${NC}"
check_port 8000 || exit 1
check_port 3001 || exit 1
check_port 3000 || exit 1

# Start Cloud Signaling Server
echo -e "${BLUE}Starting Cloud Signaling Server...${NC}"
cd realsense-react-client/server
node cloud-signaling-server.js &
CLOUD_SERVER_PID=$!
cd ../..

# Wait for cloud server to start
sleep 3
wait_for_service "http://localhost:3001/health" "Cloud Signaling Server" || exit 1

# Start Python API Server with Robot WebSocket Client
echo -e "${BLUE}Starting Python API Server with Robot WebSocket Client...${NC}"
source venv/bin/activate
python main.py &
PYTHON_SERVER_PID=$!

# Wait for Python server to start
sleep 5
wait_for_service "http://localhost:8000/api/devices/" "Python API Server" || exit 1

# Start React Development Server
echo -e "${BLUE}Starting React Development Server...${NC}"
cd realsense-react-client
npm start &
REACT_SERVER_PID=$!
cd ..

# Wait for React server to start
sleep 10
wait_for_service "http://localhost:3000" "React Development Server" || exit 1

echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo -e "${BLUE}Services:${NC}"
echo -e "  🌐 Cloud Signaling Server: ${GREEN}http://localhost:3001${NC}"
echo -e "  🐍 Python API Server: ${GREEN}http://localhost:8000${NC}"
echo -e "  ⚛️  React App: ${GREEN}http://localhost:3000${NC}"
echo -e "  📊 Health Check: ${GREEN}http://localhost:3001/health${NC}"
echo -e "  🤖 Available Robots: ${GREEN}http://localhost:3001/robots${NC}"

echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    if [ ! -z "$CLOUD_SERVER_PID" ]; then
        kill $CLOUD_SERVER_PID 2>/dev/null || true
        echo -e "${GREEN}Cloud Signaling Server stopped${NC}"
    fi
    
    if [ ! -z "$PYTHON_SERVER_PID" ]; then
        kill $PYTHON_SERVER_PID 2>/dev/null || true
        echo -e "${GREEN}Python API Server stopped${NC}"
    fi
    
    if [ ! -z "$REACT_SERVER_PID" ]; then
        kill $REACT_SERVER_PID 2>/dev/null || true
        echo -e "${GREEN}React Development Server stopped${NC}"
    fi
    
    # Kill any remaining processes
    pkill -f "python main.py" || true
    pkill -f "node.*cloud-signaling-server.js" || true
    pkill -f "npm start" || true
    
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait
