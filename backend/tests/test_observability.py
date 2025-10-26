"""
Test Observability Setup
Validates that Prometheus metrics and OTEL tracing are working correctly.
"""

import sys
import requests
import time
from typing import List, Dict, Any

# Terminal colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class ObservabilityTester:
    """Tests observability infrastructure."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.prometheus_url = "http://localhost:9090"
        self.grafana_url = "http://localhost:3000"
        self.jaeger_url = "http://localhost:16686"
        self.otel_url = "http://localhost:8888"
        
        # Service endpoints
        self.services = {
            "Backend API": "http://localhost:5001",
            "Model Service": "http://localhost:8000",
        }
    
    def log(self, message: str, level: str = "info"):
        """Log message with color."""
        colors = {
            "info": BLUE,
            "success": GREEN,
            "warning": YELLOW,
            "error": RED
        }
        color = colors.get(level, RESET)
        print(f"{color}[{level.upper()}]{RESET} {message}")
    
    def test_service_health(self, name: str, url: str, health_endpoint: str = "/health") -> bool:
        """Test if service is healthy."""
        try:
            response = requests.get(f"{url}{health_endpoint}", timeout=5)
            if response.status_code == 200:
                self.log(f"✓ {name} is healthy", "success")
                return True
            else:
                self.log(f"✗ {name} returned status {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"✗ {name} is not accessible: {e}", "error")
            return False
    
    def test_metrics_endpoint(self, name: str, url: str) -> bool:
        """Test if /metrics endpoint is accessible."""
        try:
            response = requests.get(f"{url}/metrics", timeout=5)
            if response.status_code == 200:
                # Check for Prometheus format
                if "# HELP" in response.text or "# TYPE" in response.text:
                    metric_count = response.text.count("\n")
                    self.log(f"✓ {name} /metrics endpoint working ({metric_count} lines)", "success")
                    return True
                else:
                    self.log(f"✗ {name} /metrics not in Prometheus format", "error")
                    return False
            else:
                self.log(f"✗ {name} /metrics returned status {response.status_code}", "error")
                return False
        except Exception as e:
            self.log(f"✗ {name} /metrics not accessible: {e}", "error")
            return False
    
    def test_prometheus(self) -> bool:
        """Test Prometheus is running and scraping."""
        try:
            # Check Prometheus health
            response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            if response.status_code != 200:
                self.log("✗ Prometheus is not healthy", "error")
                return False
            
            self.log("✓ Prometheus is running", "success")
            
            # Check targets
            response = requests.get(f"{self.prometheus_url}/api/v1/targets", timeout=5)
            if response.status_code == 200:
                data = response.json()
                active_targets = data.get("data", {}).get("activeTargets", [])
                up_count = sum(1 for t in active_targets if t.get("health") == "up")
                total_count = len(active_targets)
                
                self.log(f"✓ Prometheus has {up_count}/{total_count} targets up", 
                        "success" if up_count == total_count else "warning")
                
                # List targets
                for target in active_targets:
                    job = target.get("labels", {}).get("job", "unknown")
                    health = target.get("health", "unknown")
                    status = "✓" if health == "up" else "✗"
                    level = "info" if health == "up" else "warning"
                    self.log(f"  {status} {job}: {health}", level)
                
                return up_count > 0
            else:
                self.log("✗ Failed to get Prometheus targets", "error")
                return False
                
        except Exception as e:
            self.log(f"✗ Prometheus not accessible: {e}", "error")
            return False
    
    def test_grafana(self) -> bool:
        """Test Grafana is running and configured."""
        try:
            # Check Grafana health
            response = requests.get(f"{self.grafana_url}/api/health", timeout=5)
            if response.status_code != 200:
                self.log("✗ Grafana is not healthy", "error")
                return False
            
            self.log("✓ Grafana is running", "success")
            
            # Check datasources (requires auth)
            response = requests.get(
                f"{self.grafana_url}/api/datasources",
                auth=("admin", "admin"),
                timeout=5
            )
            
            if response.status_code == 200:
                datasources = response.json()
                self.log(f"✓ Grafana has {len(datasources)} datasource(s)", "success")
                
                for ds in datasources:
                    name = ds.get("name", "unknown")
                    ds_type = ds.get("type", "unknown")
                    self.log(f"  - {name} ({ds_type})", "info")
                
                return True
            else:
                self.log("✗ Failed to get Grafana datasources", "warning")
                return True  # Grafana is still running
                
        except Exception as e:
            self.log(f"✗ Grafana not accessible: {e}", "error")
            return False
    
    def test_jaeger(self) -> bool:
        """Test Jaeger is running."""
        try:
            response = requests.get(f"{self.jaeger_url}/api/services", timeout=5)
            if response.status_code == 200:
                services = response.json()
                service_count = len(services.get("data", []))
                self.log(f"✓ Jaeger is running ({service_count} services)", "success")
                
                if service_count > 0:
                    self.log(f"  Services: {', '.join(services.get('data', []))}", "info")
                
                return True
            else:
                self.log("✗ Jaeger API not responding", "error")
                return False
        except Exception as e:
            self.log(f"✗ Jaeger not accessible: {e}", "error")
            return False
    
    def test_otel_collector(self) -> bool:
        """Test OTEL Collector is running."""
        try:
            # Check health endpoint
            response = requests.get(f"http://localhost:13133/", timeout=5)
            if response.status_code == 200:
                self.log("✓ OTEL Collector is running", "success")
            else:
                self.log("✗ OTEL Collector health check failed", "error")
                return False
            
            # Check metrics endpoint
            response = requests.get(f"{self.otel_url}/metrics", timeout=5)
            if response.status_code == 200:
                self.log("✓ OTEL Collector metrics endpoint working", "success")
                return True
            else:
                self.log("✗ OTEL Collector metrics not accessible", "warning")
                return True  # Still counts as working
                
        except Exception as e:
            self.log(f"✗ OTEL Collector not accessible: {e}", "error")
            return False
    
    def test_metrics_values(self) -> bool:
        """Test that metrics contain expected values."""
        try:
            # Query for any IDS metrics
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": 'ids_service_health'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("data", {}).get("result", [])
                
                if result:
                    self.log(f"✓ Found {len(result)} service health metrics", "success")
                    for r in result:
                        service = r.get("metric", {}).get("service", "unknown")
                        value = r.get("value", [None, "0"])[1]
                        status = "healthy" if value == "1" else "unhealthy"
                        level = "success" if value == "1" else "warning"
                        self.log(f"  - {service}: {status}", level)
                    return True
                else:
                    self.log("✗ No IDS metrics found in Prometheus", "warning")
                    self.log("  (Services may need to expose metrics)", "info")
                    return False
            else:
                self.log("✗ Failed to query Prometheus", "error")
                return False
                
        except Exception as e:
            self.log(f"✗ Failed to query metrics: {e}", "error")
            return False
    
    def run_all_tests(self):
        """Run all observability tests."""
        print("\n" + "="*60)
        print("ADAPTIVE IDS - OBSERVABILITY VALIDATION")
        print("="*60 + "\n")
        
        # Test infrastructure services
        self.log("Testing Observability Infrastructure...", "info")
        print()
        
        tests = [
            ("Prometheus", lambda: self.test_prometheus()),
            ("Grafana", lambda: self.test_grafana()),
            ("Jaeger", lambda: self.test_jaeger()),
            ("OTEL Collector", lambda: self.test_otel_collector()),
        ]
        
        infra_results = []
        for name, test_func in tests:
            result = test_func()
            infra_results.append(result)
            print()
        
        # Test application services
        self.log("Testing Application Services...", "info")
        print()
        
        service_results = []
        for name, url in self.services.items():
            # Backend API uses /api/health instead of /health
            health_endpoint = "/api/health" if "Backend" in name else "/health"
            health = self.test_service_health(name, url, health_endpoint)
            metrics = self.test_metrics_endpoint(name, url)
            service_results.append(health and metrics)
            print()
        
        # Test metrics collection
        self.log("Testing Metrics Collection...", "info")
        print()
        metrics_working = self.test_metrics_values()
        print()
        
        # Summary
        print("="*60)
        print("SUMMARY")
        print("="*60)
        
        infra_passed = sum(infra_results)
        service_passed = sum(service_results)
        total_tests = len(infra_results) + len(service_results) + 1
        total_passed = infra_passed + service_passed + (1 if metrics_working else 0)
        
        self.log(f"Infrastructure: {infra_passed}/{len(infra_results)} tests passed", 
                "success" if infra_passed == len(infra_results) else "warning")
        self.log(f"Services: {service_passed}/{len(service_results)} tests passed",
                "success" if service_passed == len(service_results) else "warning")
        self.log(f"Metrics: {'Working' if metrics_working else 'Not detected'}",
                "success" if metrics_working else "info")
        
        print()
        
        if total_passed == total_tests:
            self.log("✓ All observability components are working!", "success")
            print("\nAccess dashboards at:")
            print(f"  - Grafana: {self.grafana_url} (admin/admin)")
            print(f"  - Prometheus: {self.prometheus_url}")
            print(f"  - Jaeger: {self.jaeger_url}")
            return True
        else:
            self.log(f"✗ {total_tests - total_passed} component(s) need attention", "warning")
            print("\nTroubleshooting:")
            print("  1. Ensure all services are running: docker compose ps")
            print("  2. Check logs: docker compose logs [service-name]")
            print("  3. Verify network connectivity")
            return False


def main():
    """Main entry point."""
    tester = ObservabilityTester()
    
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}[ERROR]{RESET} Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
