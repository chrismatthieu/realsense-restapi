#!/usr/bin/env python3
"""
Test script to verify 3D point cloud viewer functionality.
This script tests the new 3D point cloud data endpoint and viewer.
"""

import asyncio
import aiohttp
import json
import time
import sys

class PointCloud3DTest:
    def __init__(self, api_url: str = "http://localhost:8000/api"):
        self.api_url = api_url
        self.device_id = None
        
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
    
    async def activate_point_cloud(self, device_id: str):
        """Activate point cloud processing for a device."""
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/devices/{device_id}/point_cloud/activate") as response:
                if response.status != 200:
                    raise Exception(f"Failed to activate point cloud: {response.status}")
                result = await response.json()
                print(f"✅ Activated point cloud processing for device {device_id}")
                return result
    
    async def get_point_cloud_data(self, device_id: str):
        """Get point cloud data from the 3D endpoint."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/webrtc/pointcloud-data/{device_id}") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get point cloud data: {response.status}")
                data = await response.json()
                return data
    
    async def run_3d_test(self):
        """Run the 3D point cloud viewer test."""
        print("🎯 Testing 3D Point Cloud Viewer")
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
            
            # Step 2: Activate point cloud processing
            print(f"\n2. Activating point cloud processing...")
            await self.activate_point_cloud(self.device_id)
            
            # Step 3: Test point cloud data endpoint
            print(f"\n3. Testing 3D point cloud data endpoint...")
            data = await self.get_point_cloud_data(self.device_id)
            
            if data["success"]:
                print(f"✅ Point cloud data retrieved successfully!")
                print(f"   📊 Vertex count: {data['vertex_count']}")
                print(f"   🕒 Timestamp: {data['timestamp']}")
                print(f"   📋 Frame number: {data['frame_number']}")
                
                # Show sample vertices
                if data.get("vertices") is not None and len(data["vertices"]) > 0:
                    print(f"\n   📍 Sample vertices (first 3):")
                    for i, vertex in enumerate(data["vertices"][:3]):
                        print(f"      Vertex {i+1}: X={vertex[0]:.3f}, Y={vertex[1]:.3f}, Z={vertex[2]:.3f}")
                
                # Step 4: Test multiple data fetches
                print(f"\n4. Testing real-time data updates...")
                for i in range(5):
                    data = await self.get_point_cloud_data(self.device_id)
                    if data["success"]:
                        print(f"   Frame {i+1}: {data['vertex_count']} vertices")
                    else:
                        print(f"   Frame {i+1}: No data available")
                    await asyncio.sleep(0.5)
                
                print(f"\n✅ 3D Point Cloud Viewer Test Completed Successfully!")
                print(f"\n🎮 Next Steps:")
                print(f"   1. Open webrtc_3d_pointcloud_demo.html in your browser")
                print(f"   2. Enter device ID: {self.device_id}")
                print(f"   3. Click 'Start 3D Viewer'")
                print(f"   4. Use mouse to rotate, pan, and zoom the 3D point cloud")
                print(f"   5. Press 'R' key to reset camera view")
                
            else:
                print(f"❌ Failed to get point cloud data: {data.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            raise

async def main():
    """Main test function."""
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        api_url = "http://localhost:8000/api"
    
    test = PointCloud3DTest(api_url)
    
    try:
        await test.run_3d_test()
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
