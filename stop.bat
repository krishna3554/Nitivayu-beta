@echo off
setlocal enabledelayedexpansion

:: Switch to script's directory
cd /d "%~dp0"

echo ===============================================================================
echo                NITIVAYU - Civic Innovation Pipeline
echo                         Stopping Services
echo ===============================================================================
echo.

:: 1. Check Docker daemon
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Docker Desktop is not responding or already stopped.
    echo.
    pause
    exit /b 0
)

:: 2. Stop Docker Compose services
echo [INFO] Stopping all Nitivayu containers...
docker compose down

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Encountered an error while shutting down containers.
    echo.
    pause
    exit /b 1
)

echo.
echo ===============================================================================
echo                  ALL NITIVAYU SERVICES STOPPED
echo ===============================================================================
echo [INFO] Containers and networks have been stopped gracefully.
echo [INFO] Database and workflow persistent data volumes have been preserved.
echo.
echo To restart services at any time, run: start.bat
echo ===============================================================================
echo.
pause
