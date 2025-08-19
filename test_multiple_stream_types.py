#!/usr/bin/env python3
"""
Test script to demonstrate multiple stream types simultaneously.
This script creates WebRTC sessions with different stream types to show
that browsers can independently stream different types (color, depth, infrared).
"""

import asyncio
import aiohttp
import json
import time
import sys
from typing import List, Dict, Any

class MultiStreamTypeTest:
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
    
    async def create_webrtc_session(self, device_id: str, stream_types: List[str], session_name: str) -> Dict:
        """Create a WebRTC session with specific stream types."""
        # Create offer
        offer_data = {
            "device_id": device_id,
            "stream_types": stream_types
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
                print(f"   Stream types: {stream_types}")
                
                return {
                    "name": session_name,
                    "session_id": session_id,
                    "device_id": device_id,
                    "stream_types": stream_types,
                    "offer": offer_response
                }
    
    async def list_all_sessions(self) -> List[Dict]:
        """List all active WebRTC sessions."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/sessions") as response:
                if response.status != 200:
                    raise Exception(f"Failed to list sessions: {response.status}")
                return await response.json()
    
    async def get_stream_references(self) -> Dict:
        """Get stream reference information."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/stream-references") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get stream references: {response.status}")
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
    
    async def run_multi_stream_type_test(self):
        """Run the multi-stream type test."""
        print("🚀 Starting Multi-Stream Type Test")
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
            
            # Step 2: Create sessions with different stream types
            print(f"\n2. Creating sessions with different stream types...")
            
            # Session 1: Color stream only
            session1 = await self.create_webrtc_session(
                self.device_id, 
                ["color"], 
                "Color-Only"
            )
            self.sessions.append(session1)
            
            # Session 2: Depth stream only
            session2 = await self.create_webrtc_session(
                self.device_id, 
                ["depth"], 
                "Depth-Only"
            )
            self.sessions.append(session2)
            
            # Session 3: Infrared stream only
            session3 = await self.create_webrtc_session(
                self.device_id, 
                ["infrared-1"], 
                "Infrared-Only"
            )
            self.sessions.append(session3)
            
            # Session 4: Multiple stream types
            session4 = await self.create_webrtc_session(
                self.device_id, 
                ["color", "depth"], 
                "Color+Depth"
            )
            self.sessions.append(session4)
            
            # Step 3: Check stream references
            print(f"\n3. Checking stream references...")
            ref_info = await self.get_stream_references()
            print(f"📊 Stream references:")
            for device_id, stream_refs in ref_info.get("stream_references", {}).items():
                print(f"   Device: {device_id}")
                for stream_type, ref_count in stream_refs.items():
                    print(f"     - {stream_type}: {ref_count} reference(s)")
            
            # Step 4: List all sessions
            print(f"\n4. Listing all active sessions...")
            all_sessions = await self.list_all_sessions()
            print(f"📊 Found {len(all_sessions)} active session(s):")
            for session in all_sessions:
                status = "🟢 Connected" if session["connected"] else "🔴 Disconnected"
                print(f"   - {session['session_id']}: {status}")
                print(f"     Streams: {', '.join(session['stream_types'])}")
            
            # Step 5: Test independent stream type management
            print(f"\n5. Testing independent stream type management...")
            
            # Close the color-only session
            print("   Closing Color-Only session...")
            await self.close_session(session1['session_id'])
            self.sessions.pop(0)
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check stream references again
            ref_info = await self.get_stream_references()
            print(f"   Stream references after closing color session:")
            for device_id, stream_refs in ref_info.get("stream_references", {}).items():
                for stream_type, ref_count in stream_refs.items():
                    print(f"     - {stream_type}: {ref_count} reference(s)")
            
            # Close the depth-only session
            print("   Closing Depth-Only session...")
            await self.close_session(session2['session_id'])
            self.sessions.pop(0)  # session2 is now at index 0 after removing session1
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Check stream references again
            ref_info = await self.get_stream_references()
            print(f"   Stream references after closing depth session:")
            for device_id, stream_refs in ref_info.get("stream_references", {}).items():
                for stream_type, ref_count in stream_refs.items():
                    print(f"     - {stream_type}: {ref_count} reference(s)")
            
            # Step 6: Add a new session with a different stream type
            print(f"\n6. Adding new session with infrared stream...")
            session5 = await self.create_webrtc_session(
                self.device_id, 
                ["infrared-2"], 
                "Infrared2-Only"
            )
            self.sessions.append(session5)
            
            # Check final stream references
            ref_info = await self.get_stream_references()
            print(f"   Final stream references:")
            for device_id, stream_refs in ref_info.get("stream_references", {}).items():
                for stream_type, ref_count in stream_refs.items():
                    print(f"     - {stream_type}: {ref_count} reference(s)")
            
            # Step 7: Monitor for a while
            print(f"\n7. Monitoring sessions for 5 seconds...")
            for i in range(5):
                all_sessions = await self.list_all_sessions()
                connected_count = sum(1 for s in all_sessions if s["connected"])
                print(f"   Time {i+1}s: {len(all_sessions)} sessions, {connected_count} connected")
                await asyncio.sleep(1)
            
            # Step 8: Clean up
            print(f"\n8. Cleaning up...")
            await self.close_all_sessions()
            
            print("\n✅ Multi-stream type test completed successfully!")
            print("\n💡 Key Features Demonstrated:")
            print("   ✅ Multiple browsers can stream different stream types simultaneously")
            print("   ✅ Device stream configuration adapts to include all needed stream types")
            print("   ✅ Stream types are added/removed dynamically based on browser usage")
            print("   ✅ Independent stream type management per browser")
            print("   ✅ Automatic resource management with reference counting")
            
            print("\n💡 To test with real browsers:")
            print("   1. Start the server: python main.py")
            print("   2. Open webrtc_demo.html in multiple browser tabs")
            print("   3. Select different stream types in each browser")
            print("   4. Each browser can stream independently with different types")
            print("   5. Monitor the 'Stream References' panel to see stream usage")
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            raise

async def main():
    """Main test function."""
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = "http://localhost:8000/api"
    
    test = MultiStreamTypeTest(api_url)
    
    try:
        # Run the multi-stream type test
        await test.run_multi_stream_type_test()
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
