from __future__ import annotations

from typing import Any

import httpx


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class GrafanaClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_annotation(self, alert: Any, pipeline_id: str) -> str:
        """
        POST /api/annotations
        Creates a Grafana annotation at incident start time.
        Tags: ["mairs", alert.severity, alert.service]
        Text: f"MAIRS: {alert.anomaly} | Pipeline: {pipeline_id}"
        Returns annotation ID.
        """
        severity = str(_field(alert, "severity", "unknown"))
        service = str(_field(alert, "service", "unknown"))
        anomaly = str(_field(alert, "anomaly", "incident detected"))
        start_time = _field(alert, "timestamp")

        try:
            time_ms = int(float(start_time) * 1000) if start_time is not None else None
        except (TypeError, ValueError):
            time_ms = None

        payload: dict[str, Any] = {
            "tags": ["mairs", severity, service],
            "text": f"MAIRS: {anomaly} | Pipeline: {pipeline_id}",
        }
        if time_ms is not None:
            payload["time"] = time_ms

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/annotations",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()
            body = response.json()

        annotation_id = body.get("id")
        if annotation_id is None:
            raise ValueError("Grafana create annotation response missing 'id'.")
        return str(annotation_id)

    async def resolve_annotation(self, annotation_id: str, runbook: Any):
        """
        PATCH /api/annotations/{id}
        Updates annotation with resolution info.
        Appends estimated TTR to annotation text.
        """
        est_ttr = _field(runbook, "estimated_ttr")
        if est_ttr is None:
            est_ttr = _field(runbook, "estimated_ttr_minutes")
        if est_ttr is None:
            est_ttr = _field(runbook, "estimated_ttr_mins", "unknown")

        summary = _field(runbook, "summary")
        if summary is None:
            summary = _field(runbook, "title")
        if summary is None:
            summary = "Resolution applied"

        resolution_time = _field(runbook, "resolved_at")
        try:
            time_end_ms = (
                int(float(resolution_time) * 1000) if resolution_time is not None else None
            )
        except (TypeError, ValueError):
            time_end_ms = None

        text = f"{summary} | Estimated TTR: {est_ttr}"
        payload: dict[str, Any] = {"text": text}
        if time_end_ms is not None:
            payload["timeEnd"] = time_end_ms
            payload["isRegion"] = True

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/api/annotations/{annotation_id}",
                headers=self._headers(),
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()
