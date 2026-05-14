@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"

if exist "%ProgramFiles%\nodejs\node.exe" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "PATH=%ProgramFiles(x86)%\nodejs;%PATH%"
if exist "%LocalAppData%\Microsoft\WinGet\Links\node.exe" set "PATH=%LocalAppData%\Microsoft\WinGet\Links;%PATH%"
if exist "%LocalAppData%\Programs\node\node.exe" set "PATH=%LocalAppData%\Programs\node;%PATH%"
if exist "%UserProfile%\scoop\apps\nodejs\current\node.exe" set "PATH=%UserProfile%\scoop\apps\nodejs\current;%PATH%"
if defined NVM_SYMLINK if exist "%NVM_SYMLINK%\node.exe" set "PATH=%NVM_SYMLINK%;%PATH%"
if exist "%UserProfile%\.volta\bin\node.exe" set "PATH=%UserProfile%\.volta\bin;%PATH%"

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js not found. Install from https://nodejs.org ^(LTS^), add Node to PATH, or use a standard install path.
  echo Tip: nvm-windows: set NVM_SYMLINK to your active Node folder so node.exe is found here.
  pause
  exit /b 1
)

for /f "delims=" %%i in ('where node') do (
  set "NODE_EXE=%%i"
  goto :node_path_done
)
:node_path_done
echo Using Node: %NODE_EXE%
where npm >nul 2>&1
if errorlevel 1 (
  echo npm not found. Ensure Node.js includes npm and is on PATH.
  pause
  exit /b 1
)
echo Starting three windows: cloud signaling -^> Python API -^> React...
echo Ensure venv is set up ^(pip install -r requirements.txt^).
echo.

start "RealSense Cloud (3001)" /D "%ROOT%realsense-react-client\server" cmd /k node cloud-signaling-server.js
timeout /t 2 /nobreak >nul

start "RealSense API (8000)" /D "%ROOT%" cmd /k "set CLOUD_SIGNALING_URL=http://localhost:3001&& ""%ROOT%venv\Scripts\python.exe"" main.py"
timeout /t 4 /nobreak >nul

set "REACT_APP_CLOUD_URL=http://localhost:3001"
start "RealSense React (3000)" /D "%ROOT%realsense-react-client" cmd /k npm start

echo.
echo When React shows "Compiled", open http://localhost:3000
echo   WebRTC demo is the home route "/".
echo Cloud health: http://localhost:3001/health
echo Robots list:  http://localhost:3001/robots
echo API docs:     http://localhost:8000/docs
echo.
pause
