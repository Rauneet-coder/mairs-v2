#!/usr/bin/env python3
"""Script to inject specific incident profiles into the MAIRS v2 alert endpoint."""

import argparse
import requests
import sys

PROFILES = {
    "database_timeout": {
        "service": "database-primary",
        "component": "connection-pool",
        "severity": "CRITICAL",
        "anomaly": "Write pool connection limit reached. Stripe checkout transactions timed out.",
        "metrics": {
            "error_rate_percent": 15.4,
            "latency_p99_ms": 3200,
            "cpu_utilization_percent": 89.5,
            "memory_utilization_percent": 74.0,
            "service_up": 1.0
        }
    },
    "high_cpu": {
        "service": "payments-api",
        "component": "transaction-logger",
        "severity": "WARNING",
        "anomaly": "High CPU utilization spike during billing worker processing queue.",
        "metrics": {
            "error_rate_percent": 2.8,
            "latency_p99_ms": 1150,
            "cpu_utilization_percent": 96.0,
            "memory_utilization_percent": 68.0,
            "service_up": 1.0
        }
    },
    "out_of_memory": {
        "service": "cache-layer",
        "component": "redis-cluster",
        "severity": "CRITICAL",
        "anomaly": "Out of memory. Eviction policy failed, cache requests failing with OOM error.",
        "metrics": {
            "error_rate_percent": 8.5,
            "latency_p99_ms": 1800,
            "cpu_utilization_percent": 72.0,
            "memory_utilization_percent": 98.5,
            "service_up": 0.0
        }
    }
}

def trigger(incident_type: str, endpoint: str):
    profile = PROFILES.get(incident_type)
    if not profile:
        print(f"❌ Unknown incident profile '{incident_type}'. Choose from: {list(PROFILES.keys())}")
        sys.exit(1)
        
    print(f"📡 Injecting incident profile: {incident_type.upper()}")
    print(f"  - Service: {profile['service']} [{profile['component']}]")
    print(f"  - Severity: {profile['severity']}")
    
    payload = {
        "metrics": {
            **profile["metrics"],
            "service": profile["service"],
            "component": profile["component"],
            "anomaly": profile["anomaly"]
        }
    }
    
    try:
        resp = requests.post(endpoint, json=payload, timeout=5)
        if resp.status_code == 200:
            result = resp.json()
            print("✅ Incident successfully triggered!")
            print(f"  - Pipeline ID: {result.get('pipeline_id')}")
            print(f"  - Status: {result.get('status')}")
        else:
            print(f"❌ Failed to trigger incident (HTTP {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ Error hitting endpoint: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger specific E2E simulated incident profiles.")
    parser.add_argument("--type", type=str, default="database_timeout", choices=list(PROFILES.keys()), help="Type of incident profile")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/alert", help="Backend incident alert endpoint")
    
    args = parser.parse_args()
    trigger(args.type, args.url)
