import json
import asyncio
from datetime import datetime, timezone
from openai import AsyncOpenAI
from api.models import CapacityReport, CapacityForecast

THRESHOLDS = {
    "error_rate_percent": 5.0,
    "latency_p99_ms": 2000.0,
    "cpu_utilization_percent": 85.0,
    "memory_utilization_percent": 90.0,
    "active_connections": 500.0
}


class CapacityPlannerAgent:
    SYSTEM_PROMPT = """
You are an SRE capacity planning agent. Predict service threshold breaches.

Respond ONLY as valid JSON. No markdown.
{
  "forecasts": [
    {
      "service": "service-name",
      "metric": "metric-name",
      "current_value": 72.1,
      "threshold": 85.0,
      "predicted_breach_hours": 18.5,
      "trend": "increasing",
      "confidence": 0.78,
      "recommendation": "Scale connection pool by 40% within 12 hours"
    }
  ]
}

Include ONLY services predicted to breach within 48 hours.
Recommendations must be specific with quantity and timeframe.
Return empty list if no breaches predicted.
"""

    def __init__(self, llm_client: AsyncOpenAI, model: str):
        self.llm = llm_client
        self.model = model

    def _calc_trend(self, values: list[float], step_seconds: int) -> tuple[str, float, float]:
        if len(values) < 3:
            return ("stable", values[-1] if values else 0.0, 0.0)

        diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        avg_diff = sum(diffs) / len(diffs)
        volatility = max(diffs) - min(diffs)

        if volatility > abs(avg_diff) * 3:
            trend = "volatile"
        elif avg_diff > 0.5:
            trend = "increasing"
        elif avg_diff < -0.5:
            trend = "decreasing"
        else:
            trend = "stable"

        # Project value over the next 48 hours using the actual step granularity
        hours_per_step = step_seconds / 3600.0
        steps_48h = 48.0 / hours_per_step if hours_per_step > 0 else 0.0
        projected_48h = values[-1] + avg_diff * steps_48h

        # Estimate hours until threshold breach (linear extrapolation)
        # We need the threshold value to compute this; return 0.0 for now and compute outside
        return (trend, projected_48h, avg_diff)

    async def run_forecast(self, prometheus) -> CapacityReport:
        services = ["payments-api", "auth-service", "database-primary", "database-gateway", "cache-layer"]
        trend_summary = []

        # Fetch all time-series concurrently to avoid blocking the event loop
        async def fetch_one(service: str, metric: str, threshold: float):
            try:
                ts = await prometheus.get_time_series(metric, service, hours=24)
                if len(ts) < 3:
                    return None

                values = [p["value"] for p in ts]
                current = values[-1]

                if current < threshold * 0.5:
                    return None

                # Determine step size from timestamps (last two points)
                if len(ts) >= 2:
                    step_seconds = int(ts[-1]["timestamp"] - ts[-2]["timestamp"])
                else:
                    step_seconds = 300

                trend, projected, avg_diff = self._calc_trend(values, step_seconds)
                if projected > threshold or current > threshold * 0.7:
                    # Linear extrapolation: hours_to_breach = (threshold - current) / (avg_diff per step * steps_per_hour)
                    hours_per_step = step_seconds / 3600.0
                    rate_per_hour = avg_diff / hours_per_step if hours_per_step > 0 else 0.0
                    if rate_per_hour > 0:
                        hours_to_breach = (threshold - current) / rate_per_hour
                    else:
                        hours_to_breach = float("inf")
                    return {
                        "service": service,
                        "metric": metric,
                        "current_value": current,
                        "threshold": threshold,
                        "projected_48h": projected,
                        "trend": trend,
                        "hours_to_breach": hours_to_breach
                    }
            except Exception as e:
                print(f"CapacityPlanner: failed to fetch {metric} for {service}: {e}")
            return None

        tasks = [
            asyncio.create_task(fetch_one(service, metric, threshold))
            for service in services
            for metric, threshold in THRESHOLDS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                print(f"CapacityPlanner: unhandled exception in fetch task: {res}")
                continue
            if res is not None:
                trend_summary.append(res)

        if not trend_summary:
            return CapacityReport(forecasts=[])

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(trend_summary)}
        ]

        try:
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:].strip()
                content = content.strip()

            data = json.loads(content)
            forecasts = [CapacityForecast(**f) for f in data["forecasts"]]
            return CapacityReport(forecasts=forecasts)
        except Exception as e:
            print(f"CapacityPlanner: LLM parsing failed: {e}")
            return CapacityReport(forecasts=[])
