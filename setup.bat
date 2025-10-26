@echo off
REM Adaptive IDS v2.0 - Automated Setup Script for Windows
REM This script automates the initial setup process

echo ========================================
echo  Adaptive IDS v2.0 - Automated Setup
echo ========================================
echo.

REM Check if running as Administrator
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo WARNING: Not running as Administrator
    echo Some operations may fail without admin privileges
    echo.
    pause
)

REM Step 1: Check Prerequisites
echo [1/6] Checking prerequisites...
echo.

where docker >nul 2>&1
if %errorLevel% NEQ 0 (
    echo ERROR: Docker is not installed!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✓ Docker is installed

where git >nul 2>&1
if %errorLevel% NEQ 0 (
    echo ERROR: Git is not installed!
    echo Please install Git from: https://git-scm.com/downloads
    pause
    exit /b 1
)
echo ✓ Git is installed

where python >nul 2>&1
if %errorLevel% NEQ 0 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.12+ from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo ✓ Python is installed

where node >nul 2>&1
if %errorLevel% NEQ 0 (
    echo ERROR: Node.js is not installed!
    echo Please install Node.js 18+ from: https://nodejs.org/
    pause
    exit /b 1
)
echo ✓ Node.js is installed

echo.
echo All prerequisites are installed!
echo.

REM Step 2: Setup Backend Environment
echo [2/6] Setting up backend environment...
echo.

if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env"
        echo ✓ Created backend\.env from template
        echo.
        echo IMPORTANT: Please edit backend\.env and set:
        echo   - SECRET_KEY
        echo   - JWT_SECRET
        echo.
        echo Generate secrets using:
        echo   python -c "import secrets; print(secrets.token_urlsafe(32))"
        echo.
    ) else (
        echo ERROR: backend\.env.example not found!
        pause
        exit /b 1
    )
) else (
    echo ✓ backend\.env already exists
)

REM Step 3: Setup Frontend Environment
echo [3/6] Setting up frontend environment...
echo.

if not exist "frontend\.env.local" (
    if exist "frontend\.env.example" (
        copy "frontend\.env.example" "frontend\.env.local"
        echo ✓ Created frontend\.env.local from template
    ) else (
        echo ERROR: frontend\.env.example not found!
        pause
        exit /b 1
    )
) else (
    echo ✓ frontend\.env.local already exists
)
echo.

REM Step 4: Install Python Dependencies (Optional)
echo [4/6] Installing Python dependencies...
echo.
set /p install_python="Do you want to install Python dependencies? (y/n): "
if /i "%install_python%"=="y" (
    if exist "venv\" (
        echo ✓ Virtual environment already exists
    ) else (
        echo Creating virtual environment...
        python -m venv venv
        echo ✓ Virtual environment created
    )
    
    echo Installing Python packages...
    call venv\Scripts\activate.bat
    pip install -r backend\requirements.txt
    echo ✓ Python dependencies installed
    deactivate
) else (
    echo ⊘ Skipped Python dependencies installation
)
echo.

REM Step 5: Install Node Dependencies (Optional)
echo [5/6] Installing Node.js dependencies...
echo.
set /p install_node="Do you want to install Node.js dependencies? (y/n): "
if /i "%install_node%"=="y" (
    cd frontend
    echo Installing Node packages...
    call npm install
    if %errorLevel% EQU 0 (
        echo ✓ Node dependencies installed
    ) else (
        echo ERROR: Failed to install Node dependencies
    )
    cd ..
) else (
    echo ⊘ Skipped Node dependencies installation
)
echo.

REM Step 6: Start Docker Services
echo [6/6] Starting Docker services...
echo.
set /p start_docker="Do you want to start Docker services now? (y/n): "
if /i "%start_docker%"=="y" (
    echo Starting services with Docker Compose...
    docker compose up -d
    
    if %errorLevel% EQU 0 (
        echo.
        echo ✓ All services started successfully!
        echo.
        echo Waiting for services to initialize...
        timeout /t 10 /nobreak >nul
        
        echo.
        echo ========================================
        echo  Setup Complete!
        echo ========================================
        echo.
        echo Services are now running:
        echo   - Frontend:    http://localhost:8080
        echo   - Backend API: http://localhost:5001
        echo   - Grafana:     http://localhost:3000
        echo   - Prometheus:  http://localhost:9090
        echo.
        echo Default login: admin / admin123
        echo.
        echo To view logs: docker compose logs -f
        echo To stop:      docker compose down
        echo.
    ) else (
        echo ERROR: Failed to start Docker services
        echo Check the error messages above
        pause
        exit /b 1
    )
) else (
    echo ⊘ Skipped starting Docker services
    echo.
    echo To start services manually, run:
    echo   docker compose up -d
    echo.
)

echo Setup script completed!
echo.
echo Next steps:
echo 1. Edit backend\.env with your SECRET_KEY and JWT_SECRET
echo 2. Start services: docker compose up -d
echo 3. Access dashboard: http://localhost:8080
echo.
echo For more information, see QUICK_START.md
echo.
pause
