# RealSense React Web Client

A modern React.js web application for connecting to RealSense cameras via WebRTC and viewing 3D point clouds.

## Features

- **WebRTC Video Streaming**: Real-time video streaming from RealSense cameras
- **3D Point Cloud Viewer**: Interactive 3D visualization using Three.js
- **Multi-Client Support**: Multiple browsers can connect simultaneously
- **Stream Type Selection**: Color, Depth, Infrared-1, Infrared-2 streams
- **Modern UI**: Responsive design with real-time status updates
- **Cloud Deployable**: Can be deployed to any cloud platform
- **Signaling Server**: Dedicated Node.js server for WebRTC signaling and device control

## Architecture

```
┌─────────────────┐    WebRTC     ┌──────────────────┐    REST API    ┌─────────────────┐
│   React Client  │ ◄──────────► │ Signaling Server │ ◄──────────► │ Python API      │
│   (Browser)     │   Socket.IO  │   (Node.js)      │              │   (FastAPI)      │
└─────────────────┘              └──────────────────┘              └─────────────────┘
        │                                 │                                 │
        │                                 │                                 │
        ▼                                 ▼                                 ▼
   WebRTC Streams                 Session Management                RealSense Camera
   Video/Point Cloud              Device Control                    Hardware Interface
```

### Components

1. **React Client** (`http://localhost:3000`)
   - WebRTC peer connection management
   - Video stream display
   - 3D point cloud visualization
   - User interface

2. **Signaling Server** (`http://localhost:3001`)
   - WebRTC offer/answer exchange
   - ICE candidate negotiation
   - Session management
   - Device control proxy

3. **Python API Server** (`http://localhost:8000`)
   - RealSense camera interface
   - WebRTC stream generation
   - Point cloud processing
   - Device discovery

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- Python RealSense REST API server running (see main project README)

## Installation

### Prerequisites
- Node.js 16+ and npm
- Python RealSense API server running on `http://localhost:8000`

### Option 1: Quick Start (Recommended)
Use the development startup script that runs both the signaling server and React app:

```bash
# Make the script executable (first time only)
chmod +x start-dev.sh

# Start the development environment
./start-dev.sh
```

This will:
- Check if the Python API server is running
- Start the signaling server on port 3001
- Start the React development server on port 3000
- Open your browser to `http://localhost:3000`

### Option 2: Manual Start
If you prefer to start services manually:

1. **Install dependencies:**
```bash
npm install
cd server && npm install && cd ..
```

2. **Start the signaling server:**
```bash
cd server
npm start
```

3. **In a new terminal, start the React app:**
```bash
npm start
```

4. **Open your browser:**
Navigate to `http://localhost:3000`

## Configuration

### API URL
By default, the app connects to `http://localhost:8000/api`. You can change this in the UI or modify the default value in the components.

### For Production Deployment

1. Build the app:
```bash
npm run build
```

2. Deploy the `build` folder to your web server or cloud platform.

3. Update the API URL to point to your deployed Python REST API server.

## Usage

### WebRTC Demo
1. Navigate to the WebRTC Demo page
2. Click "Discover Devices" to find connected RealSense cameras
3. Select a stream type (Color, Depth, Infrared-1, Infrared-2)
4. Click "Start WebRTC Session" to begin streaming
5. View the video stream in the video player

### 3D Point Cloud Demo
1. Navigate to the 3D Point Cloud page
2. Click "Discover Devices" to find connected RealSense cameras
3. Click "Start 3D Viewer" to begin 3D visualization
4. Use mouse controls to navigate the 3D scene:
   - Left click + drag: Rotate
   - Right click + drag: Pan
   - Scroll wheel: Zoom
   - R key: Reset camera

## Deployment Options

### Netlify
1. Connect your GitHub repository to Netlify
2. Set build command: `npm run build`
3. Set publish directory: `build`
4. Add environment variable for API URL if needed

### Vercel
1. Connect your GitHub repository to Vercel
2. Vercel will automatically detect it's a React app
3. Deploy with default settings

### AWS S3 + CloudFront
1. Build the app: `npm run build`
2. Upload `build` folder to S3 bucket
3. Configure CloudFront distribution
4. Set up CORS if needed

### Docker
```dockerfile
FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## API Configuration

The React app communicates with the Python REST API server. Make sure:

1. The Python server is running and accessible
2. CORS is properly configured for cross-origin requests
3. WebRTC endpoints are working correctly
4. Point cloud data endpoint is available

## Troubleshooting

### Connection Issues
- Check if the Python API server is running
- Verify the API URL is correct
- Check browser console for CORS errors
- Ensure WebRTC is supported in your browser

### 3D Viewer Issues
- Make sure Three.js is properly loaded
- Check if WebGL is supported in your browser
- Verify point cloud data is being received

### Build Issues
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check for version conflicts in package.json
- Ensure all dependencies are compatible

## Development

### Project Structure
```
src/
├── components/          # Reusable components
├── pages/              # Page components
│   ├── WebRTCDemo.js   # WebRTC streaming page
│   └── PointCloudDemo.js # 3D point cloud page
├── App.js              # Main app component
├── App.css             # Main styles
└── index.js            # App entry point
```

### Adding New Features
1. Create new components in `src/components/`
2. Add new pages in `src/pages/`
3. Update routing in `App.js`
4. Add styles in `App.css`

## License

This project is part of the RealSense REST API project.
