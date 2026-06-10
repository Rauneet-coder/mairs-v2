#!/usr/bin/env python3
"""Prometheus mock exporter simulating 10 microservices."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, start_http_server
import math
import random
import time


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

UPDATE_SECONDS = 15
INCIDENT_EVERY_SECONDS = 180
INCIDENT_DURATION_SECONDS = 120
RECOVERY_DURATION_SECONDS = 90


# Metric definitions.
HTTP_REQUEST_DURATION = Gauge(
    "http_request_duration_seconds",
    "HTTP request duration in seconds by service and quantile.",
    ["service", "quantile"],
)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests by service and status code.",
    ["service", "status_code"],
)
ERROR_RATE_PERCENT = Gauge(
    "error_rate_percent",
    "Service error percentage.",
    ["service"],
)
CPU_UTILIZATION_PERCENT = Gauge(
    "cpu_utilization_percent",
    "Service CPU utilization percentage.",
    ["service"],
)
MEMORY_UTILIZATION_PERCENT = Gauge(
    "memory_utilization_percent",
    "Service memory utilization percentage.",
    ["service"],
)
ACTIVE_CONNECTIONS = Gauge(
    "active_connections",
    "Service active connection count.",
    ["service"],
)
SERVICE_UP = Gauge(
    "service_up",
    "Service availability (1 up, 0 down).",
    ["service"],
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _stable_hash(s: str) -> int:
    """Deterministic hash for reproducible behavior across Python runs."""
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def make_baselines() -> dict[str, dict[str, float]]:
    baselines: dict[str, dict[str, float]] = {}
    for service in SERVICES:
        p50_ms = random.uniform(30, 90)
        p90_ms = p50_ms * random.uniform(1.8, 2.8)
        p99_ms = p90_ms * random.uniform(1.7, 3.2)
        baselines[service] = {
            "rps": random.uniform(35, 220),
            "error_rate": random.uniform(0.08, 1.8),
            "cpu": random.uniform(35, 72),
            "memory": random.uniform(42, 78),
            "connections": random.uniform(180, 1600),
            "p50_ms": p50_ms,
            "p90_ms": p90_ms,
            "p99_ms": p99_ms,
        }
    return baselines


def main() -> None:
    random.seed()
    start_http_server(9200)
    print("Mock exporter running on :9200")

    baselines = make_baselines()

    incident_service: str | None = None
    incident_started_at = 0.0
    last_incident_injected_at = 0.0

    while True:
        now = time.time()

        # Inject one incident every 3 minutes when no active incident/recovery exists.
        if incident_service is None and (now - last_incident_injected_at) >= INCIDENT_EVERY_SECONDS:
            incident_service = random.choice(SERVICES)
            incident_started_at = now
            last_incident_injected_at = now
            print(f"[incident] injected into {incident_service}")

        for service in SERVICES:
            base = baselines[service]
            phase = "normal"
            incident_elapsed = 0.0
            recovery_progress = 1.0
            is_incident_service = service == incident_service

            if is_incident_service:
                incident_elapsed = now - incident_started_at
                if incident_elapsed <= INCIDENT_DURATION_SECONDS:
                    phase = "incident"
                elif incident_elapsed <= (INCIDENT_DURATION_SECONDS + RECOVERY_DURATION_SECONDS):
                    phase = "recovery"
                    recovery_progress = (
                        incident_elapsed - INCIDENT_DURATION_SECONDS
                    ) / RECOVERY_DURATION_SECONDS
                else:
                    phase = "normal"
                    incident_service = None

            # Gentle periodicity + random noise.
            seasonal = 1.0 + 0.08 * math.sin(now / 90.0 + _stable_hash(service) % 31)
            rps = clamp(base["rps"] * seasonal + random.uniform(-8, 8), 5, 500)

            p50_ms = clamp(base["p50_ms"] * seasonal + random.uniform(-4, 6), 15, 350)
            p90_ms = clamp(base["p90_ms"] * seasonal + random.uniform(-8, 12), 20, 900)
            p99_ms = clamp(base["p99_ms"] * seasonal + random.uniform(-15, 20), 25, 1600)

            error_rate = clamp(base["error_rate"] + random.uniform(-0.2, 0.35), 0.01, 5.0)
            cpu = clamp(base["cpu"] + random.uniform(-2.0, 3.5), 8, 99)
            memory = clamp(base["memory"] + random.uniform(-1.5, 2.2), 12, 99)
            connections = int(clamp(base["connections"] * seasonal + random.uniform(-40, 45), 10, 15000))
            up = 1.0

            if phase == "incident":
                error_rate = random.uniform(8.0, 15.0)
                p99_ms = random.uniform(2000, 4000)
                p90_ms = clamp(p90_ms * random.uniform(1.8, 2.5), 300, 2500)
                p50_ms = clamp(p50_ms * random.uniform(1.2, 1.7), 80, 700)
                cpu = clamp(cpu + random.uniform(12, 24), 20, 99)
                memory = clamp(memory + random.uniform(8, 18), 20, 99)
                connections = int(clamp(connections * random.uniform(0.75, 1.35), 10, 20000))
                if random.random() < 0.22:
                    up = 0.0
            elif phase == "recovery":
                # Smoothly decay from incident severity back to baseline.
                incident_err = random.uniform(8.0, 15.0)
                incident_p99 = random.uniform(2000, 4000)
                alpha = clamp(recovery_progress, 0.0, 1.0)
                error_rate = (1 - alpha) * incident_err + alpha * error_rate
                p99_ms = (1 - alpha) * incident_p99 + alpha * p99_ms
                p90_ms = (1 - alpha) * (p90_ms * 2.0) + alpha * p90_ms
                p50_ms = (1 - alpha) * (p50_ms * 1.4) + alpha * p50_ms
                cpu = (1 - alpha) * min(99, cpu + 16) + alpha * cpu
                memory = (1 - alpha) * min(99, memory + 10) + alpha * memory
                if random.random() < 0.08:
                    up = 0.0

            HTTP_REQUEST_DURATION.labels(service=service, quantile="0.50").set(p50_ms / 1000.0)
            HTTP_REQUEST_DURATION.labels(service=service, quantile="0.90").set(p90_ms / 1000.0)
            HTTP_REQUEST_DURATION.labels(service=service, quantile="0.99").set(p99_ms / 1000.0)

            request_count = int(rps * UPDATE_SECONDS)
            success_count = int(request_count * (1.0 - (error_rate / 100.0)))
            error_count = max(0, request_count - success_count)
            HTTP_REQUESTS_TOTAL.labels(service=service, status_code="200").inc(success_count)
            HTTP_REQUESTS_TOTAL.labels(service=service, status_code="500").inc(error_count)

            ERROR_RATE_PERCENT.labels(service=service).set(error_rate)
            CPU_UTILIZATION_PERCENT.labels(service=service).set(cpu)
            MEMORY_UTILIZATION_PERCENT.labels(service=service).set(memory)
            ACTIVE_CONNECTIONS.labels(service=service).set(connections)
            SERVICE_UP.labels(service=service).set(up)

        time.sleep(UPDATE_SECONDS)


if __name__ == "__main__":
    main()
