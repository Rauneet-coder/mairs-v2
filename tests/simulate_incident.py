#!/usr/bin/env python3
"""Incident simulation client that posts a mock incident alert to the MAIRS backend."""

import argparse
import requests
import sys

def simulate(endpoint_url: str, service: str, severity: str, anomaly: str):
    print(f"📡 Sending mock incident alert to: {endpoint_url}")
    
    payload = {
        "metrics": {
            "error_rate_percent": 15.2 if severity == "CRITICAL" else 3.8,
            "latency_p99_ms": 3200 if severity == "CRITICAL" else 1250,
            "cpu_utilization_percent": 94.0,
            "memory_utilization_percent": 87.0,
            "service_up": 1.0,
            "service": service,
            "component": "connection-pool",
            "anomaly": anomaly
        }
    }
    
    try:
        response = requests.post(endpoint_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Incident injection successful!")
            print(f"🔗 Pipeline ID: {data.get('pipeline_id')}")
            print(f"🚦 Pipeline Status: {data.get('status')}")
            print(f"📈 Connect to WS at: ws://localhost:8000/ws/pipeline/{data.get('pipeline_id')}")
        else:
            print(f"❌ Failed to trigger incident. Server returned status {response.status_code}")
            print(response.text)
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger E2E simulated incident alert.")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/alert", help="Backend incident alert endpoint")
    parser.add_argument("--service", type=str, default="database-primary", help="Service name")
    parser.add_argument("--severity", type=str, default="CRITICAL", choices=["WARNING", "CRITICAL"], help="Severity status")
    parser.add_argument("--anomaly", type=str, default="High CPU write-buffer pressure causing connection-pool latency spikes", help="Description of anomaly")
    
    args = parser.parse_args()
    simulate(args.url, args.service, args.severity, args.anomaly)
