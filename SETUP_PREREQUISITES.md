# 📋 Setup Prerequisites

Complete guide for installing all required software and tools for Adaptive IDS v2.0.

---

## 🖥️ System Requirements

### Minimum Requirements

| Component | Specification |
|-----------|--------------|
| **OS** | Windows 10/11, macOS 10.15+, Ubuntu 20.04+ |
| **RAM** | 8GB (16GB recommended) |
| **Storage** | 10GB free space |
| **CPU** | 4 cores (8 cores recommended) |
| **Network** | Internet connection for initial setup |

### Recommended for Production

| Component | Specification |
|-----------|--------------|
| **RAM** | 16GB+ |
| **Storage** | 50GB+ SSD |
| **CPU** | 8+ cores |
| **GPU** | NVIDIA GPU with CUDA support (optional, for faster ML inference) |

---

## 🔧 Required Software

### 1. Docker Desktop

**Purpose**: Container orchestration for all services

**Minimum Version**: 24.0+

**Installation**:

#### Windows
1. Download: https://www.docker.com/products/docker-desktop
2. Run the installer
3. **IMPORTANT**: Enable WSL2 backend during installation
4. Restart your computer
5. Verify installation:
   ```cmd
   docker --version
   docker compose version
   ```

#### macOS
1. Download: https://www.docker.com/products/docker-desktop
2. Drag Docker to Applications folder
3. Open Docker Desktop
4. Verify installation:
   ```bash
   docker --version
   docker compose version
   ```

#### Linux (Ubuntu/Debian)
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

**Docker Configuration**:
- **Memory**: Allocate at least 4GB (8GB recommended)
- **CPUs**: Allocate at least 2 CPUs (4+ recommended)
- **Disk**: Allocate at least 20GB

Go to: Docker Desktop → Settings → Resources

---

### 2. Git

**Purpose**: Version control and repository cloning

**Minimum Version**: 2.0+

**Installation**:

#### Windows
1. Download: https://git-scm.com/download/win
2. Run installer with default options
3. Verify:
   ```cmd
   git --version
   ```

#### macOS
```bash
# Install via Homebrew (recommended)
brew install git

# Or download from: https://git-scm.com/download/mac

# Verify
git --version
```

#### Linux
```bash
sudo apt-get update
sudo apt-get install git

# Verify
git --version
```

**Configuration**:
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

### 3. Python

**Purpose**: Backend development and scripts

**Minimum Version**: 3.12+

**Installation**:

#### Windows
1. Download: https://www.python.org/downloads/
2. Run installer
3. **IMPORTANT**: Check "Add Python to PATH"
4. Verify:
   ```cmd
   python --version
   pip --version
   ```

#### macOS
```bash
# Install via Homebrew (recommended)
brew install python@3.12

# Or download from: https://www.python.org/downloads/

# Verify
python3 --version
pip3 --version
```

#### Linux
```bash
sudo apt-get update
sudo apt-get install python3.12 python3-pip python3-venv

# Verify
python3 --version
pip3 --version
```

**Create Virtual Environment** (Recommended):
```bash
# Navigate to project directory
cd adaptive-ids-v-2.0

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

---

### 4. Node.js

**Purpose**: Frontend development and build tools

**Minimum Version**: 18+

**Installation**:

#### Windows
1. Download: https://nodejs.org/en/download/
2. Run installer (choose LTS version)
3. Verify:
   ```cmd
   node --version
   npm --version
   ```

#### macOS
```bash
# Install via Homebrew (recommended)
brew install node@18

# Or download from: https://nodejs.org/

# Verify
node --version
npm --version
```

#### Linux
```bash
# Using NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node --version
npm --version
```

**Install Frontend Dependencies**:
```bash
cd frontend
npm install
```

---

## 🔌 Optional Software

### 5. Npcap (Windows Only)

**Purpose**: Live network packet capture

**Installation** (Windows):
1. Download: https://npcap.com/#download
2. Run installer
3. **IMPORTANT**: Check "Install Npcap in WinPcap API-compatible Mode"
4. Verify by running: `tshark -D` (after installing Wireshark)

---

### 6. Wireshark/Tshark

**Purpose**: Network analysis and packet capture testing

**Installation**:

#### Windows
1. Download: https://www.wireshark.org/download.html
2. Run installer (include Tshark)
3. Verify:
   ```cmd
   tshark -v
   tshark -D  # List network interfaces
   ```

#### macOS
```bash
brew install --cask wireshark

# Or download from: https://www.wireshark.org/download.html

# Verify
tshark -v
```

#### Linux
```bash
sudo apt-get install tshark wireshark

# Allow non-root capture
sudo usermod -aG wireshark $USER
newgrp wireshark

# Verify
tshark -v
tshark -D
```

> 💡 **Note**: This is only needed if you want to capture live network traffic. The system works with simulated traffic by default.

---

### 7. CUDA Toolkit (For GPU Support)

**Purpose**: GPU acceleration for ML model inference

**Requirements**:
- NVIDIA GPU with CUDA compute capability 3.5+
- Latest NVIDIA drivers

**Installation**:
1. Check GPU compatibility: https://developer.nvidia.com/cuda-gpus
2. Download CUDA Toolkit 11.8+: https://developer.nvidia.com/cuda-downloads
3. Follow installation instructions for your OS
4. Verify:
   ```bash
   nvcc --version
   nvidia-smi
   ```

---

## 🔍 Verification Checklist

Before proceeding with the Quick Start, verify all installations:

```bash
# Check Docker
docker --version          # Should show 24.0+
docker compose version    # Should show v2.0+

# Check Git
git --version            # Should show 2.0+

# Check Python
python --version         # Should show 3.12+
pip --version            # Should show pip version

# Check Node.js
node --version           # Should show 18+
npm --version            # Should show npm version

# Optional: Check Tshark
tshark -v               # Should show Wireshark/TShark version

# Optional: Check CUDA
nvidia-smi              # Should show GPU information
```

---

## 📊 Resource Allocation

### Docker Desktop Settings

**Windows/macOS**:
1. Open Docker Desktop
2. Go to Settings → Resources
3. Configure:
   - **Memory**: 8GB (minimum 4GB)
   - **CPUs**: 4 (minimum 2)
   - **Disk**: 20GB
   - **Swap**: 2GB

**Linux**:
- Docker uses all available resources by default
- No additional configuration needed

---

## 🌐 Network Configuration

### Firewall Rules

Ensure the following ports are accessible:

| Port | Service | Protocol |
|------|---------|----------|
| 5001 | Backend API | HTTP |
| 8000 | Model Service | HTTP |
| 8080 | Frontend | HTTP |
| 3000 | Grafana | HTTP |
| 9090 | Prometheus | HTTP |
| 16686 | Jaeger UI | HTTP |
| 55432 | PostgreSQL | TCP |
| 9092 | Kafka | TCP |

**Windows Firewall**:
- Docker Desktop automatically configures firewall rules
- If issues occur, manually allow ports above

**Linux Firewall (UFW)**:
```bash
sudo ufw allow 5001/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 3000/tcp
```

---

## 🧪 Test Environment Setup

### Quick Test Script

Create a file `test-setup.sh` (Linux/macOS) or `test-setup.bat` (Windows):

**Linux/macOS**:
```bash
#!/bin/bash
echo "Testing Docker..."
docker --version && echo "✓ Docker OK" || echo "✗ Docker FAILED"

echo "Testing Git..."
git --version && echo "✓ Git OK" || echo "✗ Git FAILED"

echo "Testing Python..."
python3 --version && echo "✓ Python OK" || echo "✗ Python FAILED"

echo "Testing Node..."
node --version && echo "✓ Node.js OK" || echo "✗ Node.js FAILED"

echo "Testing Docker Compose..."
docker compose version && echo "✓ Docker Compose OK" || echo "✗ Docker Compose FAILED"

echo ""
echo "All required tools are installed!"
```

**Windows**:
```batch
@echo off
echo Testing Docker...
docker --version && echo ✓ Docker OK || echo ✗ Docker FAILED

echo Testing Git...
git --version && echo ✓ Git OK || echo ✗ Git FAILED

echo Testing Python...
python --version && echo ✓ Python OK || echo ✗ Python FAILED

echo Testing Node...
node --version && echo ✓ Node.js OK || echo ✗ Node.js FAILED

echo Testing Docker Compose...
docker compose version && echo ✓ Docker Compose OK || echo ✗ Docker Compose FAILED

echo.
echo All required tools are installed!
pause
```

Run the test:
```bash
# Linux/macOS
chmod +x test-setup.sh
./test-setup.sh

# Windows
test-setup.bat
```

---

## 🆘 Troubleshooting

### Docker Issues

**Problem**: Docker daemon not running
```bash
# Windows/macOS: Start Docker Desktop application
# Linux: Start Docker service
sudo systemctl start docker
```

**Problem**: WSL2 not enabled (Windows)
```bash
# Enable WSL2
wsl --install

# Set WSL2 as default
wsl --set-default-version 2
```

### Python Issues

**Problem**: `python` command not found (Linux/macOS)
```bash
# Use python3 instead, or create alias
alias python=python3
```

**Problem**: pip not installing packages
```bash
# Upgrade pip
python -m pip install --upgrade pip

# Use virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### Node Issues

**Problem**: npm install fails
```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

---

## ✅ Ready to Proceed

Once all prerequisites are installed and verified, you're ready to proceed with the [Quick Start Guide](./QUICK_START.md)!

**Next Steps**:
1. Clone the repository
2. Configure environment files
3. Start Docker services
4. Access the dashboard

---

## 📚 Additional Resources

- **Docker Documentation**: https://docs.docker.com/
- **Python Documentation**: https://docs.python.org/3/
- **Node.js Documentation**: https://nodejs.org/docs/
- **Git Documentation**: https://git-scm.com/doc

---

**Questions or Issues?** Check our [Troubleshooting Guide](./documentation/TROUBLESHOOTING_MODEL_SERVICE.md) or open an issue on GitHub.
