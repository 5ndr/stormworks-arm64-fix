@echo off
rem =======================================================================
rem Stormworks: Build and Rescue - Mesa D3D12 Launcher for Windows on ARM64
rem =======================================================================

echo Starting Stormworks with Mesa D3D12 Gallium translation layer...

rem Route OpenGL calls through Mesa Gallium to Direct3D 12 natively
set GALLIUM_DRIVER=d3d12
set MESA_LOADER_DRIVER_OVERRIDE=d3d12

rem Optional Mesa debugging (uncomment if troubleshooting)
rem set MESA_DEBUG=1
rem set MESA_LOG_LEVEL=debug

start "" "%~dp0stormworks64.exe"
