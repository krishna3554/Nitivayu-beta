@echo off
setlocal enabledelayedexpansion

:: Switch to script's directory
cd /d "%~dp0"

echo ===============================================================================
echo                NITIVAYU - Civic Innovation Pipeline
echo                     System Installation Script
echo ===============================================================================
echo.

:: 1. Check if installation has already been performed
if exist ".installed" (
    echo [INFO] Nitivayu is already installed on this system.
    echo [INFO] Installation flag found: .installed
    echo.
    set /p REINSTALL="Do you want to re-run the installation? (y/N): "
    if /i not "!REINSTALL!"=="y" (
        echo.
        echo [INFO] Skipping installation. You can run start.bat to launch Nitivayu.
        echo ===============================================================================
        pause
        exit /b 0
    )
    echo.
    echo [INFO] Proceeding with re-installation...
    echo.
)

:: 2. Check for Docker installation
echo [1/5] Checking prerequisites...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Docker is not installed or not in system PATH.
    echo Please install Docker Desktop for Windows: https://www.docker.com/products/docker-desktop/
    echo After installing, restart this script.
    echo.
    pause
    exit /b 1
)

:: Check if Docker daemon is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Docker Desktop is not running.
    echo Please start Docker Desktop and wait until it is fully initialized, then re-run this script.
    echo.
    pause
    exit /b 1
)

:: Check docker compose
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 'docker compose' is not available. Please ensure Docker Compose v2 is installed.
    echo.
    pause
    exit /b 1
)
echo [OK] Docker and Docker Compose detected and running.

:: 3. Configure Environment Variables
echo.
echo [2/5] Setting up environment configuration...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Created .env file from .env.example
        echo [NOTICE] If you have an OpenRouter API key, edit .env and update OPENROUTER_API_KEY.
    ) else (
        echo [WARN] .env.example not found. Creating default .env file...
        (
            echo OPENROUTER_API_KEY=your_openrouter_api_key_here
            echo OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
            echo OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
            echo POSTGRES_DB=nitivayu_db
            echo POSTGRES_USER=nitivayu_user
            echo POSTGRES_PASSWORD=nitivayu_secure_password
            echo JWT_SECRET=nitivayu_super_secret_jwt_key_2026
            echo LLM_CACHE=1
            echo TEMPORAL_HOST=temporal:7233
            echo TEMPORAL_NAMESPACE=default
        ) > ".env"
        echo [OK] Created default .env file.
    )
) else (
    echo [OK] Existing .env file found. Preserving current configuration.
)

:: 4. Verify/Create output directories
echo.
echo [3/5] Creating required output and cache directories...
if not exist "output\triage" mkdir "output\triage"
if not exist "output\sla" mkdir "output\sla"
if not exist "output\reports" mkdir "output\reports"
if not exist "output\audit" mkdir "output\audit"
if not exist "output\csr" mkdir "output\csr"
echo [OK] Output directories verified.

:: 5. Build Docker Containers
echo.
echo [4/5] Building Docker container images (this may take a few minutes)...
echo.
docker compose build
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Docker build failed. Please inspect the output above for error details.
    echo.
    pause
    exit /b 1
)
echo.
echo [OK] All Docker images built successfully.

:: 6. Mark installation as completed
echo.
echo [5/5] Finalizing installation...
echo Nitivayu Installation Timestamp: %DATE% %TIME% > ".installed"
echo Installation completed successfully on %COMPUTERNAME%. >> ".installed"

echo.
echo ===============================================================================
echo                    NITIVAYU INSTALLATION COMPLETE!
echo ===============================================================================
echo.
echo To launch the platform:
echo   - Run: start.bat
echo.
echo Service URLs once started:
echo   - Frontend UI:          http://localhost:3000
echo   - Backend API & Docs:   http://localhost:8000/docs
echo   - Temporal Workflow UI: http://localhost:8233
echo.
echo To stop all services:
echo   - Run: stop.bat
echo.
echo ===============================================================================
pause
