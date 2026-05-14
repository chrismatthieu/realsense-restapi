@echo off
setlocal
set "ROOT=%~dp0"

echo Stopping listeners on ports 3000 ^(React^), 3001 ^(cloud^), 8000 ^(API^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach ($p in 3000,3001,8000) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('Stopping PID ' + $_.OwningProcess + ' on port ' + $p); Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
echo Waiting for ports to release...
timeout /t 2 /nobreak >nul
echo.
call "%ROOT%start-full-demo-win.bat"
