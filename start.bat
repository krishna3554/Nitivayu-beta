@echo off
setlocal enabledelayedexpansion

:: Switch to script's directory
cd /d "%~dp0"

echo ===============================================================================
echo                NITIVAYU - Civic Innovation Pipeline
echo                         Starting Services
echo ===============================================================================
echo.

:: 1. Check if installation has been performed
if not exist ".installed" (
    echo [WARN] Nitivayu installation has not been run yet on this machine.
    echo [INFO] Running installation.bat is recommended for the first-time setup.
    echo.
    set /p RUN_INSTALL="Do you want to run installation.bat now? (Y/n): "
    if /i not "!RUN_INSTALL!"=="n" (
        call installation.bat
        if %errorlevel% neq 0 exit /b %errorlevel%
    )
)

:: 2. Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy ".env.example" ".env" >nul
    ) else (
        echo [ERROR] .env file not found. Please create .env before starting.
        pause
        exit /b 1
    )
)

:: 3. Check Docker daemon
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop is not running.
    echo Please start Docker Desktop and wait until it is ready, then run start.bat again.
    echo.
    pause
    exit /b 1
)

:: 4. Start Docker Compose services
echo [INFO] Launching Nitivayu containers in background mode...
docker compose up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start one or more containers.
    echo Check container logs with: docker compose logs
    echo.
    pause
    exit /b 1
)

echo.
echo ===============================================================================
echo                 NITIVAYU SERVICES ARE NOW RUNNING!
echo ===============================================================================
echo.
echo   [Web Client]   Frontend UI:          http://localhost:3000
echo   [API Backend]  FastAPI & Swagger:    http://localhost:8000/docs
echo   [Workflow]     Temporal Web UI:      http://localhost:8233
echo   [Database]     PostgreSQL 16 Vector: localhost:5432
echo.
echo Useful Commands:
echo   - Follow live container logs:  docker compose logs -f
echo   - Check container status:      docker compose ps
echo   - Stop all services:           stop.bat
echo.
echo ===============================================================================
echo.

set /p SHOW_LOGS="Do you want to attach and follow live logs now? (y/N): "
if /i "!SHOW_LOGS!"=="y" (
    echo [INFO] Attaching to container logs. Press Ctrl+C to detach (services stay running).
    echo.
    docker compose logs -f
)

exit /b 0
