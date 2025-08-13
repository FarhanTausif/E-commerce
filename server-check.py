#!/usr/bin/env python3
"""
E-commerce Application Server Health Check Script
Monitors the health of all services in the e-commerce stack
"""

import requests
import psycopg2
import json
import time
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import argparse

@dataclass
class HealthCheckResult:
    service: str
    status: str
    response_time: float
    message: str
    timestamp: str

class EcommerceHealthChecker:
    def __init__(self, config: Dict):
        self.config = config
        self.results = []

    def log_result(self, service: str, status: str, response_time: float, message: str):
        """Log a health check result"""
        result = HealthCheckResult(
            service=service,
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.now().isoformat()
        )
        self.results.append(result)

        # Color coding for console output
        color = "\033[92m" if status == "HEALTHY" else "\033[91m" if status == "UNHEALTHY" else "\033[93m"
        reset = "\033[0m"

        print(f"{color}[{status}]{reset} {service}: {message} ({response_time:.3f}s)")

    def check_spring_boot_health(self) -> bool:
        """Check Spring Boot application health"""
        service = "Spring Boot Backend"
        start_time = time.time()

        try:
            # Check actuator health endpoint
            health_url = f"{self.config['backend_url']}/actuator/health"
            response = requests.get(health_url, timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                health_data = response.json()
                if health_data.get("status") == "UP":
                    self.log_result(service, "HEALTHY", response_time, "Application is running")
                    return True
                else:
                    self.log_result(service, "UNHEALTHY", response_time, f"Health check failed: {health_data}")
                    return False
            else:
                self.log_result(service, "UNHEALTHY", response_time, f"HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            self.log_result(service, "UNHEALTHY", response_time, f"Connection error: {str(e)}")
            return False

    def check_api_endpoints(self) -> bool:
        """Check critical API endpoints"""
        endpoints = [
            ("/api/auth/health", "Authentication Service"),
            ("/api/products", "Product Service"),
            ("/api/categories", "Category Service")
        ]

        all_healthy = True

        for endpoint, service_name in endpoints:
            start_time = time.time()
            try:
                url = f"{self.config['backend_url']}{endpoint}"
                response = requests.get(url, timeout=5)
                response_time = time.time() - start_time

                if response.status_code in [200, 401]:  # 401 is expected for protected endpoints
                    self.log_result(service_name, "HEALTHY", response_time, "Endpoint accessible")
                else:
                    self.log_result(service_name, "UNHEALTHY", response_time, f"HTTP {response.status_code}")
                    all_healthy = False

            except requests.exceptions.RequestException as e:
                response_time = time.time() - start_time
                self.log_result(service_name, "UNHEALTHY", response_time, f"Connection error: {str(e)}")
                all_healthy = False

        return all_healthy

    def check_postgresql(self) -> bool:
        """Check PostgreSQL database connection"""
        service = "PostgreSQL Database"
        start_time = time.time()

        try:
            conn = psycopg2.connect(
                host=self.config['db_host'],
                port=self.config['db_port'],
                database=self.config['db_name'],
                user=self.config['db_user'],
                password=self.config['db_password'],
                connect_timeout=10
            )

            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()

            response_time = time.time() - start_time
            self.log_result(service, "HEALTHY", response_time, "Database connection successful")
            return True

        except Exception as e:
            response_time = time.time() - start_time
            self.log_result(service, "UNHEALTHY", response_time, f"Database error: {str(e)}")
            return False

    def check_elasticsearch(self) -> bool:
        """Check Elasticsearch cluster health"""
        service = "Elasticsearch"
        start_time = time.time()

        try:
            url = f"{self.config['elasticsearch_url']}/_cluster/health"
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get("status", "unknown")

                if status in ["green", "yellow"]:
                    self.log_result(service, "HEALTHY", response_time, f"Cluster status: {status}")
                    return True
                else:
                    self.log_result(service, "UNHEALTHY", response_time, f"Cluster status: {status}")
                    return False
            else:
                self.log_result(service, "UNHEALTHY", response_time, f"HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            self.log_result(service, "UNHEALTHY", response_time, f"Connection error: {str(e)}")
            return False

    def check_kibana(self) -> bool:
        """Check Kibana availability"""
        service = "Kibana"
        start_time = time.time()

        try:
            url = f"{self.config['kibana_url']}/api/status"
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time

            if response.status_code == 200:
                self.log_result(service, "HEALTHY", response_time, "Kibana is accessible")
                return True
            else:
                self.log_result(service, "UNHEALTHY", response_time, f"HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            self.log_result(service, "UNHEALTHY", response_time, f"Connection error: {str(e)}")
            return False

    def check_docker_services(self) -> bool:
        """Check if Docker services are running"""
        import subprocess

        services = ["ecommerce-postgres", "ecommerce-elasticsearch", "ecommerce-kibana"]
        all_running = True

        for service in services:
            start_time = time.time()
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                response_time = time.time() - start_time

                if result.returncode == 0 and "Up" in result.stdout:
                    self.log_result(f"Docker - {service}", "HEALTHY", response_time, "Container is running")
                else:
                    self.log_result(f"Docker - {service}", "UNHEALTHY", response_time, "Container not running")
                    all_running = False

            except Exception as e:
                response_time = time.time() - start_time
                self.log_result(f"Docker - {service}", "UNHEALTHY", response_time, f"Error: {str(e)}")
                all_running = False

        return all_running

    def run_full_health_check(self) -> Dict:
        """Run comprehensive health check on all services"""
        print("🔍 Starting E-commerce Application Health Check...")
        print("=" * 60)

        checks = [
            ("Docker Services", self.check_docker_services),
            ("PostgreSQL", self.check_postgresql),
            ("Elasticsearch", self.check_elasticsearch),
            ("Kibana", self.check_kibana),
            ("Spring Boot", self.check_spring_boot_health),
            ("API Endpoints", self.check_api_endpoints)
        ]

        overall_health = True

        for check_name, check_func in checks:
            print(f"\n📋 Checking {check_name}...")
            try:
                result = check_func()
                if not result:
                    overall_health = False
            except Exception as e:
                print(f"❌ Unexpected error in {check_name}: {str(e)}")
                overall_health = False

        # Summary
        print("\n" + "=" * 60)
        print("📊 HEALTH CHECK SUMMARY")
        print("=" * 60)

        healthy_count = sum(1 for r in self.results if r.status == "HEALTHY")
        total_count = len(self.results)

        print(f"Overall Status: {'✅ HEALTHY' if overall_health else '❌ UNHEALTHY'}")
        print(f"Services Checked: {total_count}")
        print(f"Healthy Services: {healthy_count}")
        print(f"Unhealthy Services: {total_count - healthy_count}")

        return {
            "overall_healthy": overall_health,
            "total_services": total_count,
            "healthy_services": healthy_count,
            "results": [
                {
                    "service": r.service,
                    "status": r.status,
                    "response_time": r.response_time,
                    "message": r.message,
                    "timestamp": r.timestamp
                }
                for r in self.results
            ]
        }

    def save_results_to_file(self, filename: str):
        """Save health check results to JSON file"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "overall_healthy": all(r.status == "HEALTHY" for r in self.results),
            "results": [
                {
                    "service": r.service,
                    "status": r.status,
                    "response_time": r.response_time,
                    "message": r.message,
                    "timestamp": r.timestamp
                }
                for r in self.results
            ]
        }

        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n💾 Results saved to {filename}")

def load_config(config_file: Optional[str] = None) -> Dict:
    """Load configuration from file or use defaults"""
    default_config = {
        "backend_url": "http://localhost:8080",
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "ecommerce",
        "db_user": "postgres",
        "db_password": "password",
        "elasticsearch_url": "http://localhost:9200",
        "kibana_url": "http://localhost:5601"
    }

    if config_file:
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                default_config.update(file_config)
        except FileNotFoundError:
            print(f"⚠️  Config file {config_file} not found, using defaults")
        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON in {config_file}, using defaults")

    return default_config

def main():
    parser = argparse.ArgumentParser(description="E-commerce Application Health Checker")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=60, help="Interval for continuous monitoring (seconds)")
    parser.add_argument("--quick", action="store_true", help="Run quick check (skip Docker services)")

    args = parser.parse_args()

    config = load_config(args.config)

    if args.continuous:
        print(f"🔄 Starting continuous monitoring (interval: {args.interval}s)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                checker = EcommerceHealthChecker(config)
                results = checker.run_full_health_check()

                if args.output:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{args.output}_{timestamp}.json"
                    checker.save_results_to_file(filename)

                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
    else:
        checker = EcommerceHealthChecker(config)

        if args.quick:
            # Skip Docker check for quick mode
            print("⚡ Quick health check mode")
            checker.check_postgresql()
            checker.check_elasticsearch()
            checker.check_spring_boot_health()
            checker.check_api_endpoints()
        else:
            results = checker.run_full_health_check()

        if args.output:
            checker.save_results_to_file(args.output)

        # Exit with error code if any service is unhealthy
        if not all(r.status == "HEALTHY" for r in checker.results):
            sys.exit(1)

if __name__ == "__main__":
    main()
