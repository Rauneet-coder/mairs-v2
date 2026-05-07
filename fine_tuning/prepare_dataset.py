#!/usr/bin/env python3
"""Prepare fine-tuning dataset from incidents JSON.

Reads incidents from data/incidents.json, creates three training examples
per incident (RCA, runbook, capacity), writes:
- fine_tuning/dataset/training.jsonl
- fine_tuning/dataset/train.jsonl
- fine_tuning/dataset/val.jsonl
- fine_tuning/dataset/test.jsonl
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


RANDOM_SEED = 42


def _pick(incident: Dict[str, Any], keys: Sequence[str], default: str = "unknown") -> str:
    """Return first non-empty value from candidate keys as string."""
    for key in keys:
        if key in incident and incident[key] not in (None, "", []):
            value = incident[key]
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=True)
            return str(value)
    return default


def _pick_json_like(incident: Dict[str, Any], keys: Sequence[str], default_obj: Any) -> str:
    """Return a JSON string for a structured field."""
    for key in keys:
        if key in incident and incident[key] not in (None, ""):
            value = incident[key]
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return json.dumps(parsed, ensure_ascii=True)
                except json.JSONDecodeError:
                    return value
            return json.dumps(value, ensure_ascii=True)
    return json.dumps(default_obj, ensure_ascii=True)


def to_format_a(incident: Dict[str, Any]) -> Dict[str, Any]:
    title = _pick(incident, ("title", "incident_title", "name"))
    description = _pick(incident, ("description", "metrics", "metric_summary"))
    similar_incidents = _pick(
        incident, ("similar_incidents", "historical_context", "related_incidents")
    )
    root_cause = _pick(incident, ("root_cause", "cause", "trigger"))
    propagation_chain = _pick(
        incident, ("propagation_chain", "blast_radius_chain", "propagation")
    )
    impact = _pick(incident, ("impact", "business_impact", "customer_impact"))
    confidence = _pick(incident, ("confidence", "rca_confidence"), default="0.5")

    return {
        "messages": [
            {"role": "system", "content": "You are an expert SRE root cause analyst."},
            {
                "role": "user",
                "content": (
                    f"Incident: {title}. Metrics: {description}. "
                    f"Historical context: {similar_incidents}"
                ),
            },
            {
                "role": "assistant",
                "content": (
                    f"Trigger: {root_cause}. Propagation: {propagation_chain}. "
                    f"Impact: {impact}. Confidence: {confidence}"
                ),
            },
        ]
    }


def to_format_b(incident: Dict[str, Any]) -> Dict[str, Any]:
    anomaly = _pick(incident, ("anomaly", "alert", "alert_summary"))
    root_cause = _pick(incident, ("root_cause", "cause", "trigger"))
    service = _pick(incident, ("service", "service_name", "affected_service"))
    runbook_json = _pick_json_like(
        incident,
        ("formatted_runbook_json", "runbook", "runbook_json"),
        default_obj={"steps": []},
    )

    return {
        "messages": [
            {"role": "system", "content": "You are a senior SRE generating resolution runbooks."},
            {
                "role": "user",
                "content": f"Alert: {anomaly}. Root cause: {root_cause}. Service: {service}.",
            },
            {"role": "assistant", "content": runbook_json},
        ]
    }


def to_format_c(incident: Dict[str, Any]) -> Dict[str, Any]:
    service = _pick(incident, ("service", "service_name", "affected_service"))
    metrics_trend = _pick(incident, ("metrics_trend", "trend_7d", "trend"))
    forecast_json = _pick_json_like(
        incident,
        ("forecast_json", "forecast", "capacity_forecast"),
        default_obj={"breach": False, "eta_hours": None},
    )

    return {
        "messages": [
            {"role": "system", "content": "You are an SRE capacity planning agent."},
            {"role": "user", "content": f"7-day trend for {service}: {metrics_trend}"},
            {"role": "assistant", "content": f"Predicted breach: {forecast_json}"},
        ]
    }


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")
            count += 1
    return count


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    input_path = root / "data" / "incidents.json"
    output_dir = root / "fine_tuning" / "dataset"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Missing input file: {input_path}")

    with input_path.open("r", encoding="utf-8") as fh:
        incidents = json.load(fh)

    if not isinstance(incidents, list):
        raise ValueError("Expected data/incidents.json to contain a JSON array of incidents.")

    examples: List[Dict[str, Any]] = []
    for incident in incidents:
        if not isinstance(incident, dict):
            continue
        examples.append(to_format_a(incident))
        examples.append(to_format_b(incident))
        examples.append(to_format_c(incident))

    random.Random(RANDOM_SEED).shuffle(examples)

    total = len(examples)
    train_end = int(total * 0.8)
    val_end = train_end + int(total * 0.1)

    train_rows = examples[:train_end]
    val_rows = examples[train_end:val_end]
    test_rows = examples[val_end:]

    all_path = output_dir / "training.jsonl"
    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"
    test_path = output_dir / "test.jsonl"

    _write_jsonl(all_path, examples)
    _write_jsonl(train_path, train_rows)
    _write_jsonl(val_path, val_rows)
    _write_jsonl(test_path, test_rows)

    print("Dataset preparation complete.")
    print(f"Input incidents: {len(incidents)}")
    print(f"Total examples (3x): {total}")
    print(f"Train examples (80%): {len(train_rows)}")
    print(f"Validation examples (10%): {len(val_rows)}")
    print(f"Test examples (10%): {len(test_rows)}")
    print(f"Output directory: {output_dir}")

    expected_total = len(incidents) * 3
    if total == expected_total:
        print("Integrity check: PASS")
    else:
        print(f"Integrity check: WARN (expected {expected_total}, got {total})")


if __name__ == "__main__":
    main()
