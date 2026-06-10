import json
import asyncio
from datetime import datetime, timezone
from openai import AsyncOpenAI
from api.models import AlertEvent, HistoricalMatch, RCAResult, CausalStep, ImpactScope


class RCAAgent:
    SYSTEM_PROMPT = """
You are an expert SRE root cause analyst.
Analyze the incident, historical context, and time-series data to build a causal chain.

Respond ONLY as valid JSON. No markdown. No explanation outside the JSON.
{
  "trigger": {
    "description": "the exact initiating event",
    "timestamp": "ISO8601 or unknown",
    "evidence": "specific metric name and value from the data"
  },
  "propagation": [
    {"step": 1, "event": "what happened", "service": "service-name", "lag_seconds": 0},
    {"step": 2, "event": "downstream effect", "service": "service-name", "lag_seconds": 15}
  ],
  "impact": {
    "affected_services": ["service1"],
    "estimated_users_affected": 500,
    "blast_radius": "moderate"
  },
  "root_cause_category": "resource_exhaustion",
  "confidence": 0.85,
  "similar_incident_ref": "INC-2024-034"
}

Rules:
- propagation must have 2-5 steps minimum
- evidence must reference a real metric from the input
- confidence: 0.9 if top match similarity > 0.8, else 0.7 if > 0.6, else 0.5
- blast_radius: low=1 service, moderate=2-3, high=4-6, critical=7+
- similar_incident_ref: use the best historical match ID, null if none
"""

    def __init__(self, llm_client: AsyncOpenAI, model: str):
        self.llm = llm_client
        self.model = model

    async def _call_llm(self, prompt: str) -> dict:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(3):
            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1000
                )
                content = response.choices[0].message.content.strip()

                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:].strip()
                    content = content.strip()

                return json.loads(content)
            except Exception:
                if attempt < 2:
                    messages.append({"role": "user", "content": "Respond ONLY with valid JSON. No markdown. No text outside the JSON object."})
                    await asyncio.sleep(1)
                else:
                    raise ValueError("Failed to get valid JSON from LLM after 3 attempts")
        raise ValueError("Failed to get valid JSON from LLM after 3 attempts")

    async def analyze(self, alert: AlertEvent, matches: list[HistoricalMatch], time_series: list[dict]) -> RCAResult:
        prompt = (
            f"Current incident:\nService: {alert.service}\nComponent: {alert.component}\n"
            f"Anomaly: {alert.anomaly}\nSeverity: {alert.severity}\n\n"
            f"Top historical matches:\n" +
            "\n".join(f"- {m.incident_id}: {m.title} (similarity={m.similarity_score:.2f}, TTR={m.time_to_resolve_minutes}min)" for m in matches[:3]) +
            "\n\nRecent time-series (last 5 points): " + str(time_series[-5:] if time_series else [])
        )

        data = await self._call_llm(prompt)

        propagation = [CausalStep(**s) for s in data["propagation"]]
        impact = ImpactScope(**data["impact"])

        return RCAResult(
            trigger=data["trigger"],
            propagation=propagation,
            impact=impact,
            root_cause_category=data["root_cause_category"],
            confidence=data.get("confidence", 0.5),
            similar_incident_ref=data.get("similar_incident_ref"),
            analyzed_at=datetime.now(timezone.utc)
        )
