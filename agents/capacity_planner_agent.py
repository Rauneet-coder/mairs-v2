import json
import asyncio
from datetime import datetime
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

    def _calc_trend(self, values: list[float]) -> tuple[str, float]:
        if len(values) < 3:
            return ("stable", values[-1] if values else 0)
        
        diffs = [values[i+1] - values[i] for i in range(len(values) - 1)]
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
            
        projected_48h = values[-1] + avg_diff * 48
        return (trend, projected_48h)

    async def run_forecast(self, prometheus) -> CapacityReport:
        services = ["payments-api", "auth-service", "database-primary", "api-gateway", "cache-layer"]
        trend_summary = []
        
        for service in services:
            for metric, threshold in THRESHOLDS.items():
                try:
                    ts = await prometheus.get_time_series(metric, service, hours=24)
                    if len(ts) < 3:
                        continue
                        
                    values = [p["value"] for p in ts]
                    current = values[-1]
                    
                    if current < threshold * 0.5:
                        continue
                        
                    trend, projected = self._calc_trend(values)
                    if projected > threshold or current > threshold * 0.7:
                        trend_summary.append({
                            "service": service,
                            "metric": metric,
                            "current_value": current,
                            "threshold": threshold,
                            "projected_48h": projected,
                            "trend": trend
                        })
                except:
                    continue
                    
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
        except:
            return CapacityReport(forecasts=[])
