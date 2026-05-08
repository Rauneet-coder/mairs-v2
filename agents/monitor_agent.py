import json
import asyncio
import uuid
from datetime import datetime
from openai import AsyncOpenAI
from api.models import AlertEvent, Severity

class MonitorAgent:
    SYSTEM_PROMPT = """
You are a Site Reliability AI monitoring agent.
Analyze incoming system metrics to detect incidents.

Respond ONLY as valid JSON. No markdown. No explanation.
{
  "severity": "NORMAL" | "WARNING" | "CRITICAL",
  "service": "service name from input",
  "component": "specific component",
  "anomaly": "one precise sentence",
  "business_impact": "low" | "medium" | "high"
}

Classification rules:
- CRITICAL: error_rate_percent > 5 OR latency_p99_ms > 2000 OR service_up == 0
- WARNING: error_rate_percent 1-5 OR latency_p99_ms 1000-2000 OR cpu_utilization_percent > 85
- NORMAL: everything else
- business_impact: "high" for payments-api/auth-service, "medium" for database/queue services, "low" for rest
- Never invent services not in the input JSON
"""

    def __init__(self, llm_client: AsyncOpenAI, model: str):
        self.llm = llm_client
        self.model = model
        self.active_incidents: dict[str, AlertEvent] = {}

    async def _call_llm(self, metrics: dict) -> dict:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(metrics)}
        ]
        
        for attempt in range(3):
            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=300
                )
                content = response.choices[0].message.content.strip()
                
                # Strip markdown fences
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:].strip()
                    content = content.strip()
                
                return json.loads(content)
            except Exception as e:
                if attempt == 2:
                    messages.append({"role": "user", "content": "Respond ONLY with valid JSON. No markdown. No text outside the JSON object."})
                await asyncio.sleep(1)
        raise ValueError("Failed to get valid JSON from LLM after 3 attempts")

    async def analyze(self, metrics: dict) -> AlertEvent:
        data = await self._call_llm(metrics)
        return AlertEvent(
            id=str(uuid.uuid4()),
            severity=Severity(data["severity"]),
            service=data["service"],
            component=data["component"],
            anomaly=data["anomaly"],
            business_impact=data["business_impact"],
            triggered_at=datetime.utcnow(),
            raw_metrics=metrics
        )

    async def start_polling(self, prometheus_client, pipeline_runner, interval_seconds=15):
        while True:
            try:
                snapshot = await prometheus_client.get_current_metrics()
                for service_name, metrics in snapshot.items():
                    alert = await self.analyze(metrics)
                    
                    if alert.severity in [Severity.WARNING, Severity.CRITICAL]:
                        if service_name not in self.active_incidents:
                            self.active_incidents[service_name] = alert
                            asyncio.create_task(pipeline_runner(metrics))
                    elif alert.severity == Severity.NORMAL:
                        if service_name in self.active_incidents:
                            del self.active_incidents[service_name]
                            
            except Exception as e:
                print(f"Monitor polling error: {e}")
            
            await asyncio.sleep(interval_seconds)
