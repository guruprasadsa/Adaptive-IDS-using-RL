"""
Setup Validation Script
Verifies that the baseline environment is correctly configured.
"""
import os
import sys
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def check_mark(passed: bool) -> str:
    return f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"


def validate_folders():
    """Check that all required folders exist"""
    print("\n=== Validating Folder Structure ===")
    required_folders = [
        "backend/sensors",
        "backend/stream",
        "backend/model/service",
        "backend/alerting",
        "backend/schemas",
        "backend/api",
        "backend/db",
        "backend/tests",
        "backend/scripts",
    ]
    
    all_exist = True
    for folder in required_folders:
        path = Path(folder)
        exists = path.exists() and path.is_dir()
        print(f"{check_mark(exists)} {folder}")
        all_exist = all_exist and exists
    
    return all_exist


def validate_files():
    """Check that critical files exist"""
    print("\n=== Validating Critical Files ===")
    required_files = [
        "backend/requirements.txt",
        "backend/.env",
        "backend/Dockerfile",
        "backend/Dockerfile.model",
        "backend/model/service/app.py",
        "docker-compose.yml",
        "prompts.txt",
        "SETUP_GUIDE.md",
    ]
    
    all_exist = True
    for file in required_files:
        path = Path(file)
        exists = path.exists() and path.is_file()
        print(f"{check_mark(exists)} {file}")
        all_exist = all_exist and exists
    
    return all_exist


def validate_env_vars():
    """Check that required environment variables are defined in .env"""
    print("\n=== Validating Environment Variables ===")
    env_file = Path("backend/.env")
    
    if not env_file.exists():
        print(f"{RED}✗{RESET} backend/.env not found")
        return False
    
    required_vars = [
        "KAFKA_BROKERS",
        "PACKETS_TOPIC",
        "FEATURES_TOPIC",
        "PRED_TOPIC",
        "PG_DSN",
    ]
    
    content = env_file.read_text()
    all_exist = True
    
    for var in required_vars:
        exists = var in content
        print(f"{check_mark(exists)} {var}")
        all_exist = all_exist and exists
    
    return all_exist


def validate_dependencies():
    """Check that key Python dependencies are in requirements.txt"""
    print("\n=== Validating Python Dependencies ===")
    req_file = Path("backend/requirements.txt")
    
    if not req_file.exists():
        print(f"{RED}✗{RESET} requirements.txt not found")
        return False
    
    required_deps = [
        "confluent-kafka",
        "pydantic",
        "pydantic-settings",
        "torch",
        "scikit-learn",
        "psycopg2-binary",
        "prometheus-client",
        "opentelemetry-api",
    ]
    
    content = req_file.read_text()
    all_exist = True
    
    for dep in required_deps:
        exists = dep in content
        print(f"{check_mark(exists)} {dep}")
        all_exist = all_exist and exists
    
    return all_exist


def validate_docker_compose():
    """Check docker-compose.yml structure"""
    print("\n=== Validating Docker Compose ===")
    compose_file = Path("docker-compose.yml")
    
    if not compose_file.exists():
        print(f"{RED}✗{RESET} docker-compose.yml not found")
        return False
    
    required_services = [
        "postgres",
        "kafka",
        "schema-registry",
        "backend",
        "model-service",
    ]
    
    content = compose_file.read_text()
    all_exist = True
    
    for service in required_services:
        exists = f"{service}:" in content
        print(f"{check_mark(exists)} Service: {service}")
        all_exist = all_exist and exists
    
    return all_exist


def check_docker_running():
    """Check if Docker is running"""
    print("\n=== Checking Docker ===")
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"{GREEN}✓{RESET} Docker Compose is available")
            print(f"  Version: {result.stdout.strip()}")
            return True
        else:
            print(f"{RED}✗{RESET} Docker Compose command failed")
            return False
    except FileNotFoundError:
        print(f"{RED}✗{RESET} Docker Compose not found in PATH")
        return False
    except Exception as e:
        print(f"{YELLOW}⚠{RESET} Could not verify Docker: {e}")
        return False


def main():
    print(f"\n{GREEN}╔═══════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║  Adaptive IDS Setup Validation           ║{RESET}")
    print(f"{GREEN}╚═══════════════════════════════════════════╝{RESET}")
    
    results = {
        "Folders": validate_folders(),
        "Files": validate_files(),
        "Environment Variables": validate_env_vars(),
        "Python Dependencies": validate_dependencies(),
        "Docker Compose": validate_docker_compose(),
        "Docker Running": check_docker_running(),
    }
    
    print(f"\n{GREEN}╔═══════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║  Summary                                  ║{RESET}")
    print(f"{GREEN}╚═══════════════════════════════════════════╝{RESET}\n")
    
    for check, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {check:.<35} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print(f"\n{GREEN}✓ All validation checks passed!{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Install Python dependencies: pip install -r backend/requirements.txt")
        print(f"  2. Start services: docker compose up -d")
        print(f"  3. Verify health: curl http://localhost:5001/api/health")
        print(f"  4. See SETUP_GUIDE.md for detailed instructions")
        return 0
    else:
        print(f"\n{RED}✗ Some validation checks failed.{RESET}")
        print(f"Please fix the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
