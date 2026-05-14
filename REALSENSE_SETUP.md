# RealSense + pyrealsense2 setup

## Use pyrealsense2-beta in this project

If you installed librealsense and want to use the latest Python bindings:

1. **Stop the API server** (and any other Python process using the camera).  
   Otherwise `pip install` can fail with **Access is denied** on `pyrealsense2*.pyd` (file is locked).

2. In this project's venv, install the beta package:
   ```powershell
   .\venv\Scripts\python.exe -m pip install pyrealsense2-beta --upgrade
   ```

3. Run the diagnostic:
   ```powershell
   .\venv\Scripts\python.exe find_camera.py
   ```

4. Restart the API server:
   ```powershell
   .\venv\Scripts\python.exe main.py
   ```

## If the camera still isn’t seen by Python

- **Confirm the SDK sees the device**  
  If you installed Intel RealSense SDK 2.0, run from a **new** Command Prompt (not PowerShell):
  ```cmd
  "C:\Program Files\Intel RealSense SDK 2.0\bin\rs-enumerate-devices.exe"
  ```
  If that path doesn’t exist, check `C:\Program Files (x86)\Intel RealSense SDK 2.0\bin\` or search for `rs-enumerate-devices.exe`.  
  If this lists your camera but `find_camera.py` still shows 0 devices, the issue is likely the Python bindings (version or environment).

- **Try another USB 3 port** and unplug/replug the camera after changing anything (SDK install, driver, port).

- **Python version**  
  Official pip wheels support Python 3.7–3.11. On 3.12+ you may need `pyrealsense2-beta` or a build from source; the diagnostic shows which module is loaded.
