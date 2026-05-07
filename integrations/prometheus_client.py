from __future__ import annotations

import time
from typing import Any

import httpx


class PrometheusClient:
    def __init__(self, base_url: str):  # e.g. http://localhost:9090
        self.base_url = base_url.rstrip("/")

    async def _instant_query(self, client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
        response = await client.get(
            f"{self.base_url}/api/v1/query",
            params={"query": query},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return []
        data = payload.get("data", {})
        return data.get("result", [])

    async def get_current_metrics(self, service: str | None = None) -> dict:
        """
        Queries Prometheus instant query API for all MAIRS metrics.
        Returns dict of {service_name: {metric_name: value}}
        If service provided, filter to that service only.
        Uses httpx.AsyncClient.
        Queries: error_rate_percent, http_request_duration_seconds{quantile="0.99"},
                 cpu_utilization_percent, memory_utilization_percent, service_up
        """
        service_filter = f'{{service="{service}"}}' if service else ""
        latency_filter = (
            f'{{quantile="0.99",service="{service}"}}'
            if service
            else '{quantile="0.99"}'
        )
        queries = {
            "error_rate_percent": f"error_rate_percent{service_filter}",
            "http_request_duration_seconds_p99": (
                f"http_request_duration_seconds{latency_filter}"
            ),
            "cpu_utilization_percent": f"cpu_utilization_percent{service_filter}",
            "memory_utilization_percent": f"memory_utilization_percent{service_filter}",
            "service_up": f"service_up{service_filter}",
        }

        snapshots: dict[str, dict[str, float]] = {}
        async with httpx.AsyncClient() as client:
            for metric_name, query in queries.items():
                results = await self._instant_query(client, query)
                for item in results:
                    metric = item.get("metric", {})
                    service_name = metric.get("service")
                    value_pair = item.get("value", [])
                    if service_name is None or len(value_pair) < 2:
                        continue
                    try:
                        value = float(value_pair[1])
                    except (TypeError, ValueError):
                        continue

                    if service_name not in snapshots:
                        snapshots[service_name] = {}
                    snapshots[service_name][metric_name] = value

        if service is not None:
            return {service: snapshots.get(service, {})}
        return snapshots

    async def get_time_series(self, metric: str, service: str, hours: int = 24) -> list[dict]:
        """
        Queries /api/v1/query_range for time-series data.
        Returns list of {timestamp, value} dicts.
        Step: 60s for < 6h, 300s for < 24h, 3600s for > 24h.
        """
        if hours < 6:
            step_seconds = 60
        elif hours < 24:
            step_seconds = 300
        else:
            step_seconds = 3600

        end_ts = int(time.time())
        start_ts = end_ts - int(hours * 3600)
        query = f'{metric}{{service="{service}"}}'

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start_ts,
                    "end": end_ts,
                    "step": step_seconds,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()

        if payload.get("status") != "success":
            return []

        result = payload.get("data", {}).get("result", [])
        if not result:
            return []

        points = result[0].get("values", [])
        series: list[dict[str, float]] = []
        for timestamp, value in points:
            try:
                series.append({"timestamp": float(timestamp), "value": float(value)})
            except (TypeError, ValueError):
                continue
        return series

    async def get_all_services_snapshot(self) -> list[dict]:
        """
        Returns current metrics snapshot for ALL services.
        Used by Monitor Agent's polling loop.
        """
        metrics_by_service = await self.get_current_metrics()
        snapshot: list[dict[str, Any]] = []
        for service_name in sorted(metrics_by_service.keys()):
            row: dict[str, Any] = {"service": service_name}
            row.update(metrics_by_service[service_name])
            snapshot.append(row)
        return snapshot
