r"""
Find RealSense camera: check SDK visibility and list Windows USB/Imaging devices.
Run:  venv\Scripts\python.exe find_camera.py
"""
import sys
import subprocess
import os

def run_powershell(cmd):
    """Run a PowerShell command and return (success, output)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return r.returncode == 0, (r.stdout or "").strip() + (r.stderr or "").strip()
    except Exception as e:
        return False, str(e)

def main():
    print("=" * 60)
    print("RealSense camera diagnostic")
    print("=" * 60)
    windows_saw_realsense = False

    # 1) What pyrealsense2 sees
    print("\n1. Pyrealsense2 (this app's SDK):")
    try:
        import pyrealsense2 as rs
        ctx = rs.context()
        devices = list(ctx.devices)
        print(f"   Found {len(devices)} device(s).")
        for i, dev in enumerate(devices):
            try:
                serial = dev.get_info(rs.camera_info.serial_number)
                name = dev.get_info(rs.camera_info.name)
                try:
                    port = dev.get_info(rs.camera_info.physical_port)
                    print(f"   [{i}] {name}  serial={serial}  physical_port={port}")
                except Exception:
                    print(f"   [{i}] {name}  serial={serial}")
            except Exception as e:
                print(f"   [{i}] Error: {e}")
        if not devices:
            print("   No devices seen by pyrealsense2.")
    except ImportError:
        print("   pyrealsense2 not installed (use this project's venv).")
    except Exception as e:
        print(f"   Error: {e}")
    else:
        try:
            pkg = getattr(rs, "__file__", "") or ""
            if "pyrealsense2_beta" in pkg or "pyrealsense2-beta" in pkg:
                print("   (using pyrealsense2-beta)")
            if pkg:
                print(f"   Loaded from: {pkg[:90]}..." if len(pkg) > 90 else f"   Loaded from: {pkg}")
        except Exception:
            pass

    # 2) What Windows sees: Imaging devices (Device Manager)
    print("\n2. Windows Device Manager - Imaging devices / Cameras:")
    ok, out = run_powershell(
        "Get-PnpDevice -Class Camera,Image 2>$null | "
        "Select-Object Status, Class, FriendlyName, InstanceId | Format-List"
    )
    if ok and out:
        if "RealSense" in out:
            windows_saw_realsense = True
        for line in out.splitlines():
            line = line.strip()
            if line:
                print("   ", line)
    else:
        # Fallback: any PnP device with "RealSense" or "Intel" in name
        ok2, out2 = run_powershell(
            "Get-PnpDevice | Where-Object { $_.FriendlyName -match 'RealSense|Intel.*Camera|D4[0-9][0-9]' } | "
            "Select-Object Status, FriendlyName | Format-Table -AutoSize"
        )
        if ok2 and out2:
            if "RealSense" in out2:
                windows_saw_realsense = True
            print("   (devices matching RealSense/Intel):")
            for line in out2.splitlines():
                print("   ", line)
        else:
            print("   (Could not list cameras; check Device Manager manually)")

    # 3) USB devices (vendor 8086 = Intel) – often where RealSense shows up
    print("\n3. USB devices (Intel vendor 8086):")
    ok, out = run_powershell(
        "Get-PnpDevice -Class USB 2>$null | "
        "Where-Object { $_.InstanceId -match 'VID_8086' } | "
        "Select-Object Status, FriendlyName, InstanceId | Format-List"
    )
    if ok and out:
        for line in out.splitlines():
            line = line.strip()
            if line:
                print("   ", line)
        if not out.strip():
            print("   No USB devices with vendor 8086 (Intel) found.")
    else:
        print("   (Could not list USB devices)")

    # 4) Suggest rs-enumerate-devices if SDK is installed
    print("\n4. Intel RealSense SDK tools:")
    sdk_paths = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Intel RealSense SDK 2.0", "bin", "rs-enumerate-devices.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Intel RealSense SDK 2.0", "bin", "rs-enumerate-devices.exe"),
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Intel RealSense SDK 2.0", "tools", "rs-enumerate-devices.exe"),
    ]
    found_tool = None
    for p in sdk_paths:
        if os.path.isfile(p):
            found_tool = p
            break
    if found_tool:
        print(f"   Found: {found_tool}")
        print("   Running it to see what the SDK reports...")
        try:
            r = subprocess.run([found_tool], capture_output=True, text=True, timeout=10)
            if r.stdout:
                for line in r.stdout.splitlines():
                    print("   ", line)
            if r.returncode != 0 and r.stderr:
                print("   stderr:", r.stderr[:500])
        except Exception as e:
            print("   Error running tool:", e)
    else:
        print("   rs-enumerate-devices.exe not found.")
        print("   Install 'Intel RealSense SDK 2.0' so Windows uses the correct driver.")
        print("   Download: https://github.com/IntelRealSense/librealsense/releases")

    print("\n" + "=" * 60)
    # If Windows showed RealSense but pyrealsense2 saw nothing, we need the SDK driver
    if not devices and windows_saw_realsense:
        print("Your camera IS visible in Windows (Imaging devices) but NOT to pyrealsense2.")
        print("Fix: Install 'Intel RealSense SDK 2.0' so the correct USB driver is used.")
        print("     https://github.com/IntelRealSense/librealsense/releases")
        print("     After installing, unplug and replug the camera, then run this script again.")
    print("What to try if the app still says 'No devices found':")
    print("  - Install or repair 'Intel RealSense SDK 2.0' (required for pyrealsense2 to see the camera).")
    print("  - Use a USB 3.0 port (blue). Try a different USB 3 port.")
    print("  - Unplug the camera, wait 5 seconds, plug it back in.")
    print("  - Close Intel RealSense Viewer or any other app using the camera.")
    print("=" * 60)

if __name__ == "__main__":
    main()
