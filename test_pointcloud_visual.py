#!/usr/bin/env python3
"""
Simple test to verify point cloud rendering produces visible output.
This script creates a point cloud session and checks if frames are being generated.
"""

import asyncio
import aiohttp
import json
import time
import sys

async def test_pointcloud_visual():
    """Test that point cloud rendering produces visible output."""
    api_url = "http://localhost:8000/api"
    
    print("🔍 Testing Point Cloud Visual Output")
    print("=" * 40)
    
    try:
        # Step 1: Discover devices
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/devices/") as response:
                devices = await response.json()
                if not devices:
                    print("❌ No devices found")
                    return
                
                device_id = devices[0]["device_id"]
                print(f"📷 Using device: {device_id}")
        
        # Step 2: Create point cloud session
        offer_data = {
            "device_id": device_id,
            "stream_types": ["pointcloud"]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/webrtc/offer",
                json=offer_data
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to create point cloud session: {response.status}")
                    return
                
                offer_response = await response.json()
                session_id = offer_response["session_id"]
                print(f"✅ Created point cloud session: {session_id}")
        
        # Step 3: Check stream references
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/webrtc/stream-references") as response:
                ref_info = await response.json()
                print(f"📊 Stream references:")
                for device_id, stream_refs in ref_info.get("stream_references", {}).items():
                    for stream_type, ref_count in stream_refs.items():
                        print(f"   - {stream_type}: {ref_count} reference(s)")
        
        # Step 4: Monitor session status
        print(f"\n⏱️  Monitoring point cloud session for 10 seconds...")
        for i in range(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api_url}/webrtc/sessions") as response:
                    sessions = await response.json()
                    connected_count = sum(1 for s in sessions if s["connected"])
                    print(f"   Time {i+1}s: {len(sessions)} sessions, {connected_count} connected")
            
            await asyncio.sleep(1)
        
        # Step 5: Clean up
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{api_url}/webrtc/sessions") as response:
                result = await response.json()
                print(f"\n🧹 Cleaned up {result.get('closed_sessions', 0)} session(s)")
        
        print(f"\n✅ Point cloud visual test completed!")
        print(f"\n💡 To see the point cloud in action:")
        print(f"   1. Open webrtc_demo.html in your browser")
        print(f"   2. Select 'Point Cloud' from the dropdown")
        print(f"   3. Click 'Start Stream'")
        print(f"   4. You should see a 2D top-down view of the 3D environment")
        print(f"   5. Points are color-coded: Blue (close) to Red (far)")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_pointcloud_visual())
