"""Quick script to verify RealSense cameras are visible to the SDK."""
import sys
try:
    import pyrealsense2 as rs
except ImportError:
    print("pyrealsense2 not installed. Activate venv and run: pip install pyrealsense2")
    sys.exit(1)

ctx = rs.context()
devices = list(ctx.devices)
print(f"Found {len(devices)} RealSense device(s)")
for i, dev in enumerate(devices):
    try:
        serial = dev.get_info(rs.camera_info.serial_number)
        name = dev.get_info(rs.camera_info.name)
        print(f"  [{i}] {name}  (serial: {serial})")
    except Exception as e:
        print(f"  [{i}] Error: {e}")
if not devices:
    print("\nTroubleshooting:")
    print("  - Ensure the camera is plugged in via USB 3.")
    print("  - Install Intel RealSense SDK 2.0 (librealsense) if needed.")
    print("  - Try unplugging and replugging the camera.")
    print("  - Close Intel RealSense Viewer or other apps using the camera.")
