import json
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
from api.models import AlertEvent, HistoricalMatch, Runbook, RunbookStep

class ResolverAgent:
    SYSTEM_PROMPT = """
You are a senior SRE resolution agent. Generate a precise, actionable runbook.

Respond ONLY as valid JSON. No markdown.
{
  "steps": [
    {
      "step": 1,
      "action": "Check database connection pool utilization",
      "command": "psql -c 'SELECT count(*) FROM pg_stat_activity;'",
      "duration_minutes": 1,
      "historical_ref": "INC-2024-023",
      "auto_executable": false
    }
  ],
  "estimated_resolution_minutes": 12,
  "confidence": 0.87
}

Rules:
- Exactly 5 to 8 steps
- Every action starts with a verb: Check, Run, Scale, Restart, Rollback, Flush, Verify, Monitor, Reset
- command is null if no specific CLI command applies
- historical_ref: cite the most relevant past incident for that step, null if none
- auto_executable true ONLY for: cache flush, connection pool reset, rate limit change
- confidence: 0.9 if top match similarity > 0.8, else 0.7 if > 0.6, else 0.5
- estimated_resolution_minutes: average TTR of top 2 historical matches
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
                if attempt == 2:
                    messages.append({"role": "user", "content": "Respond ONLY with valid JSON. No markdown. No text outside the JSON object."})
                await asyncio.sleep(1)
        raise ValueError("Failed to get valid JSON from LLM after 3 attempts")

    async def generate(self, alert: AlertEvent, matches: list[HistoricalMatch]) -> Runbook:
        avg_ttr = 15
        if len(matches) >= 2:
            avg_ttr = sum(m.time_to_resolve_minutes for m in matches[:2]) // 2
        elif matches:
            avg_ttr = matches[0].time_to_resolve_minutes
            
        prompt = (
            f"Current incident:\nService: {alert.service}\nComponent: {alert.component}\nAnomaly: {alert.anomaly}\n\n"
            f"Top historical matches:\n" + 
            "\n".join(f"- {m.incident_id}: {m.title}\n  Root cause: {m.root_cause}\n  Steps: {m.resolution_steps[:2]}" for m in matches[:3])
        )
        
        data = await self._call_llm(prompt)
        
        steps = [RunbookStep(**s) for s in data["steps"]]
        
        return Runbook(
            steps=steps,
            estimated_resolution_minutes=data.get("estimated_resolution_minutes", avg_ttr),
            confidence=data.get("confidence", 0.5),
            generated_at=datetime.utcnow()
        )
