# RealSense Signaling Server

A Node.js/Express signaling server that handles WebRTC signaling between the React client and Python RealSense API server.

## Features

- **WebRTC Signaling**: Handles offer/answer exchange and ICE candidate negotiation
- **Session Management**: Tracks WebRTC sessions and device connections
- **Real-time Communication**: Uses Socket.IO for real-time bidirectional communication
- **Device Control**: Manages RealSense device streams and point cloud processing
- **Error Handling**: Comprehensive error handling and logging

## Architecture

```
React Client ←→ Signaling Server ←→ Python RealSense API
     ↑              ↑                    ↑
  WebRTC         Socket.IO           REST API
  Signaling      Real-time           Device Control
```

## Installation

1. Navigate to the server directory:
```bash
cd realsense-react-client/server
```

2. Install dependencies:
```bash
npm install
```

## Configuration

The server can be configured using environment variables:

- `PYTHON_API_URL`: URL of the Python RealSense API server (default: `http://localhost:8000/api`)
- `SIGNALING_PORT`: Port for the signaling server (default: `3001`)

Example:
```bash
export PYTHON_API_URL=http://192.168.1.100:8000/api
export SIGNALING_PORT=3001
```

## Usage

### Development Mode
```bash
npm run dev
```

### Production Mode
```bash
npm start
```

## API Endpoints

### Health Check
- `GET /health` - Server health status

### Device Discovery
- `GET /devices` - Get available RealSense devices

### Statistics
- `GET /stats` - Get server statistics (sessions, devices, connections)

## Socket.IO Events

### Client → Server

#### WebRTC Session Management
- `create-session` - Create a new WebRTC session
  ```javascript
  {
    deviceId: "844212070924",
    streamTypes: ["color", "depth"]
  }
  ```

- `answer` - Send WebRTC answer
  ```javascript
  {
    sessionId: "session-uuid",
    answer: { sdp: "...", type: "answer" }
  }
  ```

- `ice-candidate` - Send ICE candidate
  ```javascript
  {
    sessionId: "session-uuid",
    candidate: { candidate: "...", sdpMid: "...", sdpMLineIndex: 0 }
  }
  ```

- `close-session` - Close WebRTC session
  ```javascript
  {
    sessionId: "session-uuid"
  }
  ```

#### Device Control
- `start-device-stream` - Start device stream
  ```javascript
  {
    deviceId: "844212070924",
    configs: [{ stream_type: "depth", format: "z16", ... }]
  }
  ```

- `stop-device-stream` - Stop device stream
  ```javascript
  {
    deviceId: "844212070924"
  }
  ```

- `activate-pointcloud` - Activate/deactivate point cloud processing
  ```javascript
  {
    deviceId: "844212070924",
    enabled: true
  }
  ```

#### Point Cloud Data
- `get-pointcloud-data` - Get point cloud data
  ```javascript
  {
    deviceId: "844212070924"
  }
  ```

### Server → Client

#### WebRTC Session Events
- `session-created` - Session created successfully
- `session-error` - Session error occurred
- `session-closed` - Session closed successfully
- `answer-received` - Answer received from server
- `ice-candidate-received` - ICE candidate received from server

#### Device Control Events
- `device-stream-started` - Device stream started
- `device-stream-stopped` - Device stream stopped
- `device-stream-error` - Device stream error
- `pointcloud-activated` - Point cloud processing activated/deactivated
- `pointcloud-data` - Point cloud data received
- `pointcloud-error` - Point cloud error

## Session Management

The server maintains session state for:
- Active WebRTC sessions
- Device stream references
- Socket connections

Sessions are automatically cleaned up when:
- Client disconnects
- Session is explicitly closed
- Server restarts

## Error Handling

The server provides detailed error information:
- HTTP status codes
- Error messages
- Stack traces (in development)
- Socket.IO error events

## Logging

The server logs:
- Connection events
- Session creation/closure
- WebRTC signaling
- Device operations
- Errors and warnings

## Security Considerations

- CORS is enabled for development
- Input validation on all endpoints
- Session isolation
- Rate limiting (can be added)

## Deployment

### Local Development
```bash
npm run dev
```

### Production
```bash
npm start
```

### Docker (optional)
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3001
CMD ["npm", "start"]
```

## Troubleshooting

### Connection Issues
1. Check if Python API server is running
2. Verify CORS settings
3. Check network connectivity
4. Review server logs

### WebRTC Issues
1. Verify STUN server configuration
2. Check firewall settings
3. Review ICE candidate exchange
4. Monitor connection state changes

### Session Issues
1. Check session cleanup
2. Verify device availability
3. Review stream configuration
4. Monitor memory usage

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License
