#!/bin/bash

# Adaptive IDS v2.0 - Automated Setup Script for Unix/Linux/macOS
# This script automates the initial setup process

set -e  # Exit on error

echo "========================================"
echo "  Adaptive IDS v2.0 - Automated Setup"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}WARNING: Running as root is not recommended${NC}"
   echo ""
fi

# Step 1: Check Prerequisites
echo "[1/6] Checking prerequisites..."
echo ""

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

all_installed=true

check_command docker || all_installed=false
check_command git || all_installed=false
check_command python3 || all_installed=false
check_command node || all_installed=false

if [ "$all_installed" = false ]; then
    echo ""
    echo -e "${RED}ERROR: Missing required dependencies!${NC}"
    echo "Please install missing tools. See SETUP_PREREQUISITES.md"
    exit 1
fi

# Check Docker Compose
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✓${NC} docker compose is available"
elif docker-compose --version &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} Using legacy docker-compose (consider upgrading)"
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}✗${NC} docker compose is not available"
    all_installed=false
fi

if [ "$all_installed" = false ]; then
    exit 1
fi

echo ""
echo -e "${GREEN}All prerequisites are installed!${NC}"
echo ""

# Step 2: Setup Backend Environment
echo "[2/6] Setting up backend environment..."
echo ""

if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        echo -e "${GREEN}✓${NC} Created backend/.env from template"
        echo ""
        echo -e "${YELLOW}IMPORTANT: Please edit backend/.env and set:${NC}"
        echo "  - SECRET_KEY"
        echo "  - JWT_SECRET"
        echo ""
        echo "Generate secrets using:"
        echo "  python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
        echo ""
    else
        echo -e "${RED}ERROR: backend/.env.example not found!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} backend/.env already exists"
fi

# Step 3: Setup Frontend Environment
echo "[3/6] Setting up frontend environment..."
echo ""

if [ ! -f "frontend/.env.local" ]; then
    if [ -f "frontend/.env.example" ]; then
        cp frontend/.env.example frontend/.env.local
        echo -e "${GREEN}✓${NC} Created frontend/.env.local from template"
    else
        echo -e "${RED}ERROR: frontend/.env.example not found!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} frontend/.env.local already exists"
fi
echo ""

# Step 4: Install Python Dependencies (Optional)
echo "[4/6] Installing Python dependencies..."
echo ""
read -p "Do you want to install Python dependencies? (y/n): " install_python

if [[ "$install_python" =~ ^[Yy]$ ]]; then
    if [ -d "venv" ]; then
        echo -e "${GREEN}✓${NC} Virtual environment already exists"
    else
        echo "Creating virtual environment..."
        python3 -m venv venv
        echo -e "${GREEN}✓${NC} Virtual environment created"
    fi
    
    echo "Installing Python packages..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r backend/requirements.txt
    deactivate
    echo -e "${GREEN}✓${NC} Python dependencies installed"
else
    echo "⊘ Skipped Python dependencies installation"
fi
echo ""

# Step 5: Install Node Dependencies (Optional)
echo "[5/6] Installing Node.js dependencies..."
echo ""
read -p "Do you want to install Node.js dependencies? (y/n): " install_node

if [[ "$install_node" =~ ^[Yy]$ ]]; then
    cd frontend
    echo "Installing Node packages..."
    npm install
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Node dependencies installed"
    else
        echo -e "${RED}ERROR: Failed to install Node dependencies${NC}"
    fi
    cd ..
else
    echo "⊘ Skipped Node dependencies installation"
fi
echo ""

# Step 6: Start Docker Services
echo "[6/6] Starting Docker services..."
echo ""
read -p "Do you want to start Docker services now? (y/n): " start_docker

if [[ "$start_docker" =~ ^[Yy]$ ]]; then
    echo "Starting services with Docker Compose..."
    ${DOCKER_COMPOSE:-docker compose} up -d
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ All services started successfully!${NC}"
        echo ""
        echo "Waiting for services to initialize..."
        sleep 10
        
        echo ""
        echo "========================================"
        echo "  Setup Complete!"
        echo "========================================"
        echo ""
        echo "Services are now running:"
        echo "  - Frontend:    http://localhost:8080"
        echo "  - Backend API: http://localhost:5001"
        echo "  - Grafana:     http://localhost:3000"
        echo "  - Prometheus:  http://localhost:9090"
        echo ""
        echo "Default login: admin / admin123"
        echo ""
        echo "To view logs: docker compose logs -f"
        echo "To stop:      docker compose down"
        echo ""
    else
        echo -e "${RED}ERROR: Failed to start Docker services${NC}"
        echo "Check the error messages above"
        exit 1
    fi
else
    echo "⊘ Skipped starting Docker services"
    echo ""
    echo "To start services manually, run:"
    echo "  docker compose up -d"
    echo ""
fi

echo "Setup script completed!"
echo ""
echo "Next steps:"
echo "1. Edit backend/.env with your SECRET_KEY and JWT_SECRET"
echo "2. Start services: docker compose up -d"
echo "3. Access dashboard: http://localhost:8080"
echo ""
echo "For more information, see QUICK_START.md"
echo ""
