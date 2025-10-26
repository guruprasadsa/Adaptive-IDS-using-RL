"""
Setup verification for packet capture producer
Checks if all dependencies are installed and configured correctly.
"""

import sys
import subprocess
import os
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in backend directory
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"ℹ Loaded environment from: {env_path}")
    else:
        print(f"⚠ .env file not found at: {env_path}")
except ImportError:
    print("⚠ python-dotenv not installed, environment variables won't be loaded automatically")
except Exception as e:
    print(f"⚠ Error loading .env file: {e}")

def check_pyshark():
    """Check if pyshark is installed."""
    try:
        import pyshark
        try:
            version = pyshark.__version__
        except AttributeError:
            version = "installed"
        print(f"✓ pyshark {version}")
        return True
    except ImportError:
        print("✗ pyshark not installed")
        print("  Install with: pip install pyshark")
        return False

def check_confluent_kafka():
    """Check if confluent-kafka is installed."""
    try:
        import confluent_kafka
        print("✓ confluent-kafka installed (version {})".format(confluent_kafka.version()[0]))
        return True
    except ImportError:
        print("✗ confluent-kafka not installed")
        print("  Install with: pip install confluent-kafka")
        return False

def check_tshark():
    """Check if tshark is available."""
    try:
        result = subprocess.run(
            ['tshark', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ tshark available ({version_line})")
            return True
        else:
            print("✗ tshark not working properly")
            return False
    except FileNotFoundError:
        print("✗ tshark not found in PATH")
        print("  Install Wireshark from: https://www.wireshark.org/download.html")
        print("  Add to PATH: C:\\Program Files\\Wireshark")
        return False
    except Exception as e:
        print(f"✗ Error checking tshark: {e}")
        return False

def check_npcap():
    """Check if Npcap is installed (Windows only)."""
    if sys.platform != 'win32':
        print("ℹ Npcap check skipped (not Windows)")
        return True
    
    # Check if Npcap directory exists
    npcap_paths = [
        r"C:\Windows\System32\Npcap",
        r"C:\Program Files\Npcap"
    ]
    
    for path in npcap_paths:
        if os.path.exists(path):
            print(f"✓ Npcap directory found: {path}")
            return True
    
    print("✗ Npcap not found")
    print("  Download from: https://npcap.com/#download")
    print("  Enable 'WinPcap API-compatible Mode' during installation")
    return False

def check_env_variables():
    """Check if required environment variables are set."""
    required = ['KAFKA_BROKERS', 'PACKETS_TOPIC']
    optional = ['PCAP_IFACE', 'PCAP_FILTER']
    
    all_good = True
    for var in required:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}={value}")
        else:
            print(f"✗ {var} not set (required)")
            all_good = False
    
    for var in optional:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}={value}")
        else:
            print(f"ℹ {var} not set (optional)")
    
    return all_good

def list_interfaces():
    """Try to list available network interfaces."""
    try:
        result = subprocess.run(
            ['tshark', '-D'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("\nAvailable network interfaces:")
            print(result.stdout)
            return True
        else:
            print("\n✗ Could not list interfaces")
            return False
    except Exception as e:
        print(f"\n✗ Could not list interfaces: {e}")
        return False

def main():
    """Run all checks."""
    print("=" * 60)
    print("Packet Capture Producer Setup Verification")
    print("=" * 60)
    print()
    
    checks = {
        "Python packages": [],
        "Capture tools": [],
        "Environment": [],
    }
    
    # Python packages
    print("Checking Python packages...")
    checks["Python packages"].append(check_pyshark())
    checks["Python packages"].append(check_confluent_kafka())
    print()
    
    # Capture tools
    print("Checking capture tools...")
    checks["Capture tools"].append(check_tshark())
    if sys.platform == 'win32':
        checks["Capture tools"].append(check_npcap())
    print()
    
    # Environment
    print("Checking environment variables...")
    checks["Environment"].append(check_env_variables())
    print()
    
    # Try to list interfaces
    if all(checks["Capture tools"]):
        list_interfaces()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    all_passed = True
    for category, results in checks.items():
        passed = sum(results)
        total = len(results)
        status = "✓" if all(results) else "✗"
        print(f"{status} {category}: {passed}/{total} checks passed")
        if not all(results):
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("✓ All checks passed! You can run the packet producer.")
        print()
        print("Next steps:")
        print("  1. Start Kafka: docker compose up -d kafka")
        print("  2. Set PCAP_IFACE: set PCAP_IFACE=Wi-Fi")
        print("  3. Run producer: python -m sensors.pcap_producer")
        return 0
    else:
        print("✗ Some checks failed. Please install missing dependencies.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
