import json
import os
import random
import uuid
from datetime import datetime

# pyrefly: ignore [missing-import]
from chromadb import PersistentClient

# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

SERVICES = [
    "payments-api", "auth-service", "database-primary", "database-replica",
    "cdn-edge", "message-queue", "search-service", "notification-service",
    "api-gateway", "cache-layer"
]

COMPONENTS = {
    "payments-api": ["stripe-adapter", "transaction-logger", "billing-worker"],
    "auth-service": ["jwt-signer", "user-store", "session-manager"],
    "database-primary": ["connection-pool", "query-optimizer", "write-buffer"],
    "database-replica": ["read-pool", "replication-lag-monitor"],
    "cdn-edge": ["cache-invalidator", "waf-rules", "ssl-terminator"],
    "message-queue": ["broker", "dead-letter-queue", "consumer-group"],
    "search-service": ["indexer", "query-parser", "synonym-engine"],
    "notification-service": ["smtp-bridge", "push-gateway", "sms-provider"],
    "api-gateway": ["rate-limiter", "load-balancer", "cors-filter"],
    "cache-layer": ["redis-cluster", "eviction-policy", "key-serializer"]
}

CATEGORIES = ["resource_exhaustion", "network", "deployment", "dependency", "data_corruption", "capacity"]

def generate_incidents(count=500):
    incidents = []
    for i in range(1, count + 1):
        service = random.choice(SERVICES)
        component = random.choice(COMPONENTS[service])
        severity = "CRITICAL" if random.random() < 0.4 else "WARNING"
        auto_healable = random.random() < 0.4
        
        incident = {
            "id": f"INC-2024-{i:03d}",
            "title": f"{service} {component} error spike",
            "description": f"Observed a sharp increase in errors for {component} on {service}. System performance is degraded.",
            "root_cause": f"A recent change in {component} configuration caused unexpected resource pressure.",
            "propagation_chain": [
                f"{service} failure",
                f"downstream {random.choice(SERVICES)} timeouts",
                "increased user-facing 5xx errors"
            ],
            "resolution_steps": [
                f"Identify the problematic {component} instance",
                f"Review recent logs for {service}",
                "Perform a rolling restart of affected pods",
                "Verify system stability and error rates"
            ],
            "root_cause_category": random.choice(CATEGORIES),
            "severity": severity,
            "service": service,
            "component": component,
            "time_to_resolve_minutes": random.randint(5, 90),
            "auto_healable": auto_healable,
            "tags": ["sre", service.split('-')[0], component.split('-')[0]]
        }
        
        if auto_healable:
            incident["healing_actions"] = [
                {"action": "restart_pod", "target": service, "safe": True}
            ]
            if random.random() < 0.5:
                incident["healing_actions"].append({"action": "flush_cache", "target": "cache-layer", "safe": True})
        
        incidents.append(incident)
    return incidents

def seed():
    print("Generating incidents...")
    incidents = generate_incidents(500)
    
    os.makedirs("./data", exist_ok=True)
    with open("./data/incidents.json", "w") as f:
        json.dump(incidents, f, indent=2)
    
    print("Seeding ChromaDB...")
    client = PersistentClient(path="./data/chroma_db")
    try:
        client.delete_collection("incidents")
    except:
        pass
    collection = client.create_collection("incidents")
    
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    for incident in incidents:
        document = f"{incident['title']}. {incident['description']}. Root cause: {incident['root_cause']}"
        embedding = model.encode(document).tolist()
        metadata = {k: str(v) if isinstance(v, (list, dict, bool)) else v for k, v in incident.items()}
        collection.add(
            documents=[document],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[incident["id"]]
        )
    
    auto_healable_count = sum(1 for inc in incidents if inc["auto_healable"])
    print(f"Seeded {len(incidents)} incidents. {auto_healable_count} auto-healable. ChromaDB ready.")

if __name__ == "__main__":
    seed()
