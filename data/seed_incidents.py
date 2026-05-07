#!/usr/bin/env python3
"""Generate synthetic SRE incidents and seed ChromaDB."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import chromadb


SERVICES = [
    "payments-api",
    "auth-service",
    "database-primary",
    "database-replica",
    "cdn-edge",
    "message-queue",
    "search-service",
    "notification-service",
    "api-gateway",
    "cache-layer",
]

ROOT_CAUSE_CATEGORIES = [
    "resource_exhaustion",
    "network",
    "deployment",
    "dependency",
    "data_corruption",
    "capacity",
]

ERROR_TRENDS = ["spike", "gradual_increase", "volatile", "flat_high"]
LATENCY_TRENDS = ["spike", "gradual_increase", "unstable", "recovered"]


def _rand_pct(low: float, high: float) -> float:
    return round(random.uniform(low, high), 2)


def _build_runbook(service: str, category: str) -> Dict[str, Any]:
    return {
        "title": f"Runbook for {service} ({category})",
        "steps": [
            {"order": 1, "action": "confirm_alert", "target": service},
            {"order": 2, "action": "check_logs", "target": service},
            {"order": 3, "action": "mitigate_and_verify", "target": service},
        ],
        "rollback": {"required": category in {"deployment", "data_corruption"}},
    }


def _build_forecast(service: str, category: str) -> Dict[str, Any]:
    breach = category in {"capacity", "resource_exhaustion"} or random.random() < 0.35
    return {
        "service": service,
        "breach": breach,
        "resource": random.choice(["cpu", "memory", "iops", "connections"]),
        "eta_hours": random.randint(2, 72) if breach else None,
        "confidence": _rand_pct(0.61, 0.97),
    }


def _build_incident(index: int) -> Dict[str, Any]:
    service = random.choice(SERVICES)
    dependency = random.choice([s for s in SERVICES if s != service])
    tertiary = random.choice([s for s in SERVICES if s not in {service, dependency}])
    category = random.choice(ROOT_CAUSE_CATEGORIES)
    auto_healable = random.random() < 0.40

    root_cause = f"{category.replace('_', ' ')} issue in {service}"
    propagation_chain = [
        f"{service} degraded",
        f"{dependency} timed out",
        f"{tertiary} failed",
    ]

    incident = {
        "incident_id": f"INC-{index + 1:04d}",
        "title": f"{service} incident {index + 1}",
        "service": service,
        "description": (
            f"Elevated latency and error rate observed in {service}; dependent "
            f"services experienced cascading failures."
        ),
        "anomaly": random.choice(
            [
                f"{service} p95 latency above SLO",
                f"{service} error budget burn spike",
                f"{service} saturation alert",
            ]
        ),
        "root_cause": root_cause,
        "root_cause_category": category,
        "propagation_chain": propagation_chain,
        "impact": random.choice(
            [
                "Checkout failures for active users",
                "Authentication delays across regions",
                "Intermittent API request failures",
                "Search indexing backlog and stale results",
            ]
        ),
        "confidence": _rand_pct(0.62, 0.98),
        "similar_incidents": random.choice(
            [
                "Past deployment caused identical timeout pattern.",
                "Previous capacity event triggered queue saturation.",
                "Historical network flap impacted upstream dependencies.",
            ]
        ),
        "auto_healable": auto_healable,
        "healing_actions": [
            {
                "action": random.choice(
                    [
                        "restart_pod",
                        "scale_replicas",
                        "flush_cache",
                        "failover_replica",
                    ]
                ),
                "target": service,
                "safe": random.random() < 0.8,
            }
        ],
        "time_series_features": {
            "error_rate_trend": random.choice(ERROR_TRENDS),
            "latency_trend": random.choice(LATENCY_TRENDS),
        },
        "metrics_trend": (
            f"error_rate={_rand_pct(1.8, 12.5)}%, "
            f"latency_p95={random.randint(220, 2200)}ms, "
            f"cpu={_rand_pct(45, 98)}%"
        ),
        "formatted_runbook_json": _build_runbook(service, category),
    }
    incident["forecast_json"] = _build_forecast(service, category)
    return incident


def _as_chroma_metadata(incident: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(incident)
    metadata["propagation_chain"] = json.dumps(incident["propagation_chain"], ensure_ascii=True)
    metadata["healing_actions"] = json.dumps(incident["healing_actions"], ensure_ascii=True)
    metadata["time_series_features"] = json.dumps(
        incident["time_series_features"], ensure_ascii=True
    )
    metadata["formatted_runbook_json"] = json.dumps(
        incident["formatted_runbook_json"], ensure_ascii=True
    )
    metadata["forecast_json"] = json.dumps(incident["forecast_json"], ensure_ascii=True)
    return metadata


def main() -> None:
    random.seed(42)

    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    incidents = [_build_incident(i) for i in range(500)]
    auto_healable_count = sum(1 for x in incidents if x["auto_healable"])

    incidents_path = data_dir / "incidents.json"
    with incidents_path.open("w", encoding="utf-8") as fh:
        json.dump(incidents, fh, indent=2, ensure_ascii=True)

    chroma_dir = root / "data" / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(name="incidents")

    collection.delete(where={})
    collection.add(
        ids=[str(uuid4()) for _ in incidents],
        documents=[
            (
                f"Incident: {x['title']}. Service: {x['service']}. "
                f"Root cause: {x['root_cause']}. Impact: {x['impact']}."
            )
            for x in incidents
        ],
        metadatas=[_as_chroma_metadata(x) for x in incidents],
    )

    print(f"Seeded {len(incidents)} incidents. {auto_healable_count} auto-healable.")


if __name__ == "__main__":
    main()
