#!/usr/bin/env python3
"""
WebRTC API Test Script
This script demonstrates how to use the RealSense WebRTC API endpoints.
"""

import asyncio
import aiohttp
import json
import sys

# API Configuration
API_BASE_URL = "http://localhost:8000/api"
DEVICE_ID = "844212070924"  # Use the actual device ID found
STREAM_TYPE = "depth"

async def test_webrtc_api():
    """Test the WebRTC API endpoints."""
    
    async with aiohttp.ClientSession() as session:
        print("=== RealSense WebRTC API Test ===\n")
        
        # Step 1: First, let's check if the device is available
        print("1. Checking available devices...")
        try:
            async with session.get(f"{API_BASE_URL}/devices") as response:
                if response.status == 200:
                    devices = await response.json()
                    print(f"   Found {len(devices)} devices: {[d['device_id'] for d in devices]}")
                else:
                    print(f"   Error getting devices: {response.status}")
                    return
        except Exception as e:
            print(f"   Error connecting to API: {e}")
            return
        
        # Step 2: Start streaming on the device
        print("\n2. Starting stream on device...")
        stream_config = {
            "configs": [
                {
                    "sensor_id": "844212070924-sensor-0",  # Stereo Module sensor
                    "stream_type": STREAM_TYPE,
                    "format": "z16",
                    "resolution": {"width": 640, "height": 480},
                    "framerate": 30,
                }
            ]
        }
        
        try:
            async with session.post(f"{API_BASE_URL}/devices/{DEVICE_ID}/stream/start", 
                                  json=stream_config) as response:
                if response.status == 200:
                    print("   Stream started successfully")
                else:
                    print(f"   Error starting stream: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return
        except Exception as e:
            print(f"   Error starting stream: {e}")
            return
        
        # Step 3: Create WebRTC offer
        print("\n3. Creating WebRTC offer...")
        offer_request = {
            "device_id": DEVICE_ID,
            "stream_types": [STREAM_TYPE]
        }
        
        try:
            async with session.post(f"{API_BASE_URL}/webrtc/offer", 
                                  json=offer_request) as response:
                if response.status == 200:
                    offer_data = await response.json()
                    session_id = offer_data["session_id"]
                    print(f"   Offer created successfully")
                    print(f"   Session ID: {session_id}")
                    print(f"   SDP Type: {offer_data['type']}")
                    print(f"   SDP Length: {len(offer_data['sdp'])} characters")
                else:
                    print(f"   Error creating offer: {response.status}")
                    error_text = await response.text()
                    print(f"   Error details: {error_text}")
                    return
        except Exception as e:
            print(f"   Error creating offer: {e}")
            return
        
        # Step 4: Get session status
        print("\n4. Getting session status...")
        try:
            async with session.get(f"{API_BASE_URL}/webrtc/sessions/{session_id}") as response:
                if response.status == 200:
                    status = await response.json()
                    print(f"   Session Status:")
                    print(f"     - Device ID: {status['device_id']}")
                    print(f"     - Connected: {status['connected']}")
                    print(f"     - Streaming: {status['streaming']}")
                    print(f"     - Stream Types: {status['stream_types']}")
                else:
                    print(f"   Error getting session status: {response.status}")
        except Exception as e:
            print(f"   Error getting session status: {e}")
        
        # Step 5: Process a mock answer (for demonstration)
        print("\n5. Processing mock WebRTC answer...")
        mock_answer = {
            "session_id": session_id,
            "sdp": "v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\n",
            "type": "answer"
        }
        
        try:
            async with session.post(f"{API_BASE_URL}/webrtc/answer", 
                                  json=mock_answer) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   Answer processed successfully: {result['success']}")
                else:
                    print(f"   Error processing answer: {response.status}")
        except Exception as e:
            print(f"   Error processing answer: {e}")
        
        # Step 6: Add ICE candidate (for demonstration)
        print("\n6. Adding ICE candidate...")
        ice_candidate = {
            "session_id": session_id,
            "candidate": "candidate:0 1 UDP 2122260223 192.168.1.1 49152 typ host",
            "sdpMid": "0",
            "sdpMLineIndex": 0
        }
        
        try:
            async with session.post(f"{API_BASE_URL}/webrtc/ice-candidates", 
                                  json=ice_candidate) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   ICE candidate added successfully: {result['success']}")
                else:
                    print(f"   Error adding ICE candidate: {response.status}")
        except Exception as e:
            print(f"   Error adding ICE candidate: {e}")
        
        # Step 7: Close the session
        print("\n7. Closing WebRTC session...")
        try:
            async with session.delete(f"{API_BASE_URL}/webrtc/sessions/{session_id}") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   Session closed successfully: {result['success']}")
                else:
                    print(f"   Error closing session: {response.status}")
        except Exception as e:
            print(f"   Error closing session: {e}")
        
        # Step 8: Stop the stream
        print("\n8. Stopping stream...")
        try:
            async with session.post(f"{API_BASE_URL}/devices/{DEVICE_ID}/stream/stop") as response:
                if response.status == 200:
                    print("   Stream stopped successfully")
                else:
                    print(f"   Error stopping stream: {response.status}")
        except Exception as e:
            print(f"   Error stopping stream: {e}")
        
        print("\n=== Test completed ===")

async def test_api_documentation():
    """Test if the API documentation is accessible."""
    print("\n=== Testing API Documentation ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://localhost:8000/docs") as response:
                if response.status == 200:
                    print("✅ API documentation is accessible at http://localhost:8000/docs")
                else:
                    print(f"❌ API documentation not accessible: {response.status}")
        except Exception as e:
            print(f"❌ Error accessing API documentation: {e}")

async def main():
    """Main function to run all tests."""
    print("Starting RealSense WebRTC API tests...")
    
    # Test API documentation first
    await test_api_documentation()
    
    # Test WebRTC API
    await test_webrtc_api()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")
        sys.exit(1)
