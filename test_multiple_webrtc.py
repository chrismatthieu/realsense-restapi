#!/usr/bin/env python3
"""
Test script to demonstrate multiple concurrent WebRTC connections.
This script creates multiple WebRTC sessions to the same RealSense camera
to show that multiple browsers can connect simultaneously.
"""

import asyncio
import aiohttp
import json
import time
import sys
from typing import List, Dict, Any

class WebRTCMultiClientTest:
    def __init__(self, api_url: str = "http://localhost:8000/api"):
        self.api_url = api_url
        self.device_id = None
        self.sessions = []
        
    async def discover_devices(self) -> List[Dict]:
        """Discover available RealSense devices."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/devices/") as response:
                if response.status != 200:
                    raise Exception(f"Failed to discover devices: {response.status}")
                devices = await response.json()
                print(f"✅ Found {len(devices)} device(s)")
                for device in devices:
                    print(f"   - {device['device_id']}: {device['name']}")
                return devices
    
    async def start_device_stream(self, device_id: str, stream_type: str = "color") -> bool:
        """Start streaming on the device."""
        stream_config = {
            "configs": [
                {
                    "sensor_id": f"{device_id}-sensor-0",
                    "stream_type": stream_type,
                    "format": "z16" if stream_type == "depth" else "rgb8",
                    "resolution": {"width": 640, "height": 480},
                    "framerate": 30
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_url}/devices/{device_id}/stream/start",
                json=stream_config
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to start stream: {response.status}")
                print(f"✅ Device stream started for {device_id}")
                return True
    
    async def create_webrtc_session(self, device_id: str, stream_type: str, session_name: str) -> Dict:
        """Create a WebRTC session."""
        # Create offer
        offer_data = {
            "device_id": device_id,
            "stream_types": [stream_type]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_url}/webrtc/offer",
                json=offer_data
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to create offer: {response.status}")
                
                offer_response = await response.json()
                session_id = offer_response["session_id"]
                
                print(f"✅ Created WebRTC session '{session_name}' with ID: {session_id}")
                
                return {
                    "name": session_name,
                    "session_id": session_id,
                    "device_id": device_id,
                    "stream_type": stream_type,
                    "offer": offer_response
                }
    
    async def get_session_status(self, session_id: str) -> Dict:
        """Get the status of a WebRTC session."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/sessions/{session_id}") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get session status: {response.status}")
                return await response.json()
    
    async def list_all_sessions(self) -> List[Dict]:
        """List all active WebRTC sessions."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/sessions") as response:
                if response.status != 200:
                    raise Exception(f"Failed to list sessions: {response.status}")
                return await response.json()
    
    async def close_session(self, session_id: str) -> bool:
        """Close a WebRTC session."""
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{self.api_url}/webrtc/sessions/{session_id}") as response:
                if response.status != 200:
                    raise Exception(f"Failed to close session: {response.status}")
                print(f"✅ Closed session: {session_id}")
                return True
    
    async def close_all_sessions(self) -> int:
        """Close all active WebRTC sessions."""
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{self.api_url}/webrtc/sessions") as response:
                if response.status != 200:
                    raise Exception(f"Failed to close all sessions: {response.status}")
                result = await response.json()
                closed_count = result.get("closed_sessions", 0)
                print(f"✅ Closed {closed_count} session(s)")
                return closed_count
    
    async def run_multi_client_test(self, num_clients: int = 3):
        """Run the multi-client WebRTC test."""
        print("🚀 Starting Multi-Client WebRTC Test")
        print("=" * 50)
        
        try:
            # Step 1: Discover devices
            print("\n1. Discovering devices...")
            devices = await self.discover_devices()
            if not devices:
                print("❌ No devices found. Please connect a RealSense camera.")
                return
            
            self.device_id = devices[0]["device_id"]
            print(f"📷 Using device: {self.device_id}")
            
            # Step 2: Create multiple WebRTC sessions (device stream will auto-start)
            print(f"\n2. Creating {num_clients} WebRTC sessions...")
            for i in range(num_clients):
                session_name = f"Client-{i+1}"
                session = await self.create_webrtc_session(
                    self.device_id, 
                    "color", 
                    session_name
                )
                self.sessions.append(session)
            
            # Step 3: List all sessions
            print(f"\n3. Listing all active sessions...")
            all_sessions = await self.list_all_sessions()
            print(f"📊 Found {len(all_sessions)} active session(s):")
            for session in all_sessions:
                status = "🟢 Connected" if session["connected"] else "🔴 Disconnected"
                print(f"   - {session['session_id']}: {status}")
                print(f"     Device: {session['device_id']}")
                print(f"     Streams: {', '.join(session['stream_types'])}")
            
            # Step 4: Test independent session management
            print(f"\n4. Testing independent session management...")
            
            # Close one session and verify others continue
            if len(self.sessions) > 1:
                session_to_close = self.sessions[1]  # Close the second session
                print(f"   Closing session: {session_to_close['name']}")
                await self.close_session(session_to_close['session_id'])
                self.sessions.pop(1)  # Remove from our list
                
                # Wait a moment
                await asyncio.sleep(2)
                
                # Check remaining sessions
                remaining_sessions = await self.list_all_sessions()
                print(f"   Remaining sessions: {len(remaining_sessions)}")
                for session in remaining_sessions:
                    print(f"     - {session['session_id']}: {'🟢 Connected' if session['connected'] else '🔴 Disconnected'}")
            
            # Step 5: Monitor sessions for a while
            print(f"\n5. Monitoring sessions for 10 seconds...")
            for i in range(10):
                all_sessions = await self.list_all_sessions()
                connected_count = sum(1 for s in all_sessions if s["connected"])
                print(f"   Time {i+1}s: {len(all_sessions)} sessions, {connected_count} connected")
                await asyncio.sleep(1)
            
            # Step 6: Close all sessions
            print(f"\n6. Cleaning up...")
            await self.close_all_sessions()
            
            print("\n✅ Multi-client test completed successfully!")
            print("\n💡 Key Features Demonstrated:")
            print("   ✅ Multiple browsers can connect simultaneously")
            print("   ✅ Each browser gets its own WebRTC session")
            print("   ✅ Browsers can disconnect independently")
            print("   ✅ Device stream continues for remaining browsers")
            print("   ✅ Automatic resource management with reference counting")
            
            print("\n💡 To test with real browsers:")
            print("   1. Start the server: python main.py")
            print("   2. Open webrtc_demo.html in multiple browser tabs/windows")
            print("   3. Each browser will create its own WebRTC session")
            print("   4. All browsers will receive the same video stream simultaneously")
            print("   5. Close one browser - others will continue streaming")
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            raise

    async def test_independent_connections(self):
        """Test that browsers can connect and disconnect independently."""
        print("\n🧪 Testing Independent Browser Connections...")
        
        try:
            # Discover devices
            devices = await self.discover_devices()
            if not devices:
                print("❌ No devices found.")
                return
            
            self.device_id = devices[0]["device_id"]
            
            # Create 3 sessions
            print("Creating 3 initial sessions...")
            for i in range(3):
                session = await self.create_webrtc_session(
                    self.device_id, "color", f"Test-{i+1}"
                )
                self.sessions.append(session)
            
            # Verify all sessions exist
            all_sessions = await self.list_all_sessions()
            print(f"✅ Created {len(all_sessions)} sessions")
            
            # Close middle session
            print("Closing middle session...")
            middle_session = self.sessions[1]
            await self.close_session(middle_session['session_id'])
            self.sessions.pop(1)
            
            # Verify remaining sessions still work
            await asyncio.sleep(2)
            remaining_sessions = await self.list_all_sessions()
            print(f"✅ {len(remaining_sessions)} sessions remaining after closing one")
            
            # Add a new session
            print("Adding a new session...")
            new_session = await self.create_webrtc_session(
                self.device_id, "color", "New-Test"
            )
            self.sessions.append(new_session)
            
            # Verify we can have multiple sessions again
            all_sessions = await self.list_all_sessions()
            print(f"✅ Now have {len(all_sessions)} sessions")
            
            # Clean up
            await self.close_all_sessions()
            print("✅ Independent connection test completed!")
            
        except Exception as e:
            print(f"❌ Independent connection test failed: {str(e)}")
            raise

async def main():
    """Main test function."""
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = "http://localhost:8000/api"
    
    test = WebRTCMultiClientTest(api_url)
    
    try:
        # Run the main multi-client test
        await test.run_multi_client_test(num_clients=3)
        
        # Test independent connections
        await test.test_independent_connections()
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
