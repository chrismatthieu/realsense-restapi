#!/usr/bin/env python3
"""
Test script to reproduce and fix stream switching issues.
This script tests switching between different stream types to identify the problem.
"""

import asyncio
import aiohttp
import json
import time
import sys

class StreamSwitchingTest:
    def __init__(self, api_url: str = "http://localhost:8000/api"):
        self.api_url = api_url
        self.device_id = None
        self.session_id = None
        
    async def discover_devices(self):
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
    
    async def create_webrtc_session(self, stream_types):
        """Create a WebRTC session with specified stream types."""
        async with aiohttp.ClientSession() as session:
            payload = {
                "device_id": self.device_id,
                "stream_types": stream_types
            }
            async with session.post(f"{self.api_url}/webrtc/offer", json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Failed to create session: {response.status}")
                result = await response.json()
                return result
    
    async def close_session(self, session_id):
        """Close a WebRTC session."""
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{self.api_url}/webrtc/sessions/{session_id}") as response:
                if response.status != 200:
                    print(f"Warning: Failed to close session {session_id}: {response.status}")
                else:
                    print(f"✅ Closed session {session_id}")
    
    async def get_sessions(self):
        """Get current sessions."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/sessions") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get sessions: {response.status}")
                return await response.json()
    
    async def get_stream_references(self):
        """Get current stream references."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/stream-references") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get stream references: {response.status}")
                return await response.json()
    
    async def test_stream_switching(self):
        """Test switching between different stream types."""
        print("🎯 Testing Stream Switching")
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
            
            # Step 2: Test Color stream
            print(f"\n2. Testing Color stream...")
            result = await self.create_webrtc_session(["color"])
            self.session_id = result["session_id"]
            print(f"✅ Created color session: {self.session_id}")
            
            # Check sessions and references
            sessions = await self.get_sessions()
            references = await self.get_stream_references()
            print(f"   📊 Sessions: {len(sessions)}")
            print(f"   📊 Stream references: {references.get('stream_references', {})}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Step 3: Close color session
            print(f"\n3. Closing color session...")
            await self.close_session(self.session_id)
            self.session_id = None
            
            # Check sessions and references after closing
            sessions = await self.get_sessions()
            references = await self.get_stream_references()
            print(f"   📊 Sessions after close: {len(sessions)}")
            print(f"   📊 Stream references after close: {references.get('stream_references', {})}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Step 4: Test Depth stream
            print(f"\n4. Testing Depth stream...")
            result = await self.create_webrtc_session(["depth"])
            self.session_id = result["session_id"]
            print(f"✅ Created depth session: {self.session_id}")
            
            # Check sessions and references
            sessions = await self.get_sessions()
            references = await self.get_stream_references()
            print(f"   📊 Sessions: {len(sessions)}")
            print(f"   📊 Stream references: {references.get('stream_references', {})}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Step 5: Close depth session
            print(f"\n5. Closing depth session...")
            await self.close_session(self.session_id)
            self.session_id = None
            
            # Check sessions and references after closing
            sessions = await self.get_sessions()
            references = await self.get_stream_references()
            print(f"   📊 Sessions after close: {len(sessions)}")
            print(f"   📊 Stream references after close: {references.get('stream_references', {})}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Step 6: Test Point Cloud stream
            print(f"\n6. Testing Point Cloud stream...")
            result = await self.create_webrtc_session(["pointcloud"])
            self.session_id = result["session_id"]
            print(f"✅ Created pointcloud session: {self.session_id}")
            
            # Check sessions and references
            sessions = await self.get_sessions()
            references = await self.get_stream_references()
            print(f"   📊 Sessions: {len(sessions)}")
            print(f"   📊 Stream references: {references.get('stream_references', {})}")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Step 7: Close pointcloud session
            print(f"\n7. Closing pointcloud session...")
            await self.close_session(self.session_id)
            self.session_id = None
            
            # Check sessions and references after closing
            sessions = await self.get_sessions()
            references = await self.get_stream_references()
            print(f"   📊 Sessions after close: {len(sessions)}")
            print(f"   📊 Stream references after close: {references.get('stream_references', {})}")
            
            print(f"\n✅ Stream switching test completed!")
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            raise
        finally:
            # Clean up any remaining session
            if self.session_id:
                try:
                    await self.close_session(self.session_id)
                except:
                    pass

async def main():
    """Main test function."""
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = "http://localhost:8000/api"
    
    test = StreamSwitchingTest(api_url)
    
    try:
        await test.test_stream_switching()
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
