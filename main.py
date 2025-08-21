import uvicorn
import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.errors import setup_exception_handlers
from config import settings
import socketio
from app.services.socketio import sio

# Import robot WebSocket client
from robot_websocket_client import start_robot_websocket_client, stop_robot_websocket_client


# --- Create FastAPI App ---
# Initialize FastAPI app with title and OpenAPI URL
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Set up exception handlers
setup_exception_handlers(app)

# Serve static files (HTML demo)
try:
    app.mount("/static", StaticFiles(directory="."), name="static")
except Exception:
    # If static files can't be mounted, create a simple route for the demo
    pass

@app.get("/")
async def root():
    """Serve the WebRTC demo page."""
    if os.path.exists("webrtc_demo.html"):
        return FileResponse("webrtc_demo.html")
    else:
        return {"message": "WebRTC demo not found. Please ensure webrtc_demo.html exists in the root directory."}

@app.get("/webrtc_demo.html")
async def webrtc_demo():
    """Serve the WebRTC demo page directly."""
    if os.path.exists("webrtc_demo.html"):
        return FileResponse("webrtc_demo.html")
    else:
        return {"message": "WebRTC demo not found. Please ensure webrtc_demo.html exists in the root directory."}

@app.get("/webrtc_3d_pointcloud_demo.html")
async def webrtc_3d_pointcloud_demo():
    """Serve the 3D point cloud demo page directly."""
    if os.path.exists("webrtc_3d_pointcloud_demo.html"):
        return FileResponse("webrtc_3d_pointcloud_demo.html")
    else:
        return {"message": "3D point cloud demo not found. Please ensure webrtc_3d_pointcloud_demo.html exists in the root directory."}

@app.get("/test_3d_viewer_debug.html")
async def test_3d_viewer_debug():
    """Serve the 3D point cloud debug test page."""
    if os.path.exists("test_3d_viewer_debug.html"):
        return FileResponse("test_3d_viewer_debug.html")
    else:
        return {"message": "3D viewer debug test not found."}


# --- Combine FastAPI and Socket.IO into a single ASGI App ---
# Mount the Socket.IO app (`sio`) onto the FastAPI app (`app`)
# The result `combined_app` is what Uvicorn will run.
combined_app = socketio.ASGIApp(socketio_server=sio, other_asgi_app=app, socketio_path='socket')

if __name__ == "__main__":
    # Start the robot WebSocket client in the background
    async def start_services():
        # Start robot WebSocket client
        robot_task = asyncio.create_task(start_robot_websocket_client())
        
        # Start FastAPI server
        config = uvicorn.Config("main:combined_app", host="0.0.0.0", port=8000, reload=False, log_level="debug")
        server = uvicorn.Server(config)
        await server.serve()
        
        # Cleanup
        await stop_robot_websocket_client()
        robot_task.cancel()
    
    try:
        asyncio.run(start_services())
    except KeyboardInterrupt:
        print("Shutting down...")
        asyncio.run(stop_robot_websocket_client())
