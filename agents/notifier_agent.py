import os
import httpx
from datetime import datetime
from api.models import AlertEvent, Runbook, RCAResult

class NotifierAgent:
    def __init__(self, slack_webhook=None, grafana_url=None, grafana_key=None):
        self.slack_webhook = slack_webhook or os.getenv("SLACK_WEBHOOK_URL")
        self.grafana_url = grafana_url or os.getenv("GRAFANA_URL")
        self.grafana_key = grafana_key or os.getenv("GRAFANA_API_KEY")

    async def send(self, alert: AlertEvent, runbook: Runbook, rca: RCAResult = None) -> bool:
        emoji = "🟢"
        if alert.severity == "CRITICAL":
            emoji = "🔴"
        elif alert.severity == "WARNING":
            emoji = "🟡"
            
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {alert.severity} — {alert.service}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Anomaly:* {alert.anomaly}\n*Impact:* {alert.business_impact}"}
            }
        ]
        
        if rca and rca.propagation:
            chain = " → ".join([p.service for p in rca.propagation[:3]])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Root cause chain:* {chain}"}
            })
            
        if runbook.steps:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Top action:* {runbook.steps[0].action}\n*Est. resolution:* {runbook.estimated_resolution_minutes} min | *Confidence:* {int(runbook.confidence*100)}%"}
            })
            
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"MAIRS v2 · {alert.triggered_at.strftime('%H:%M:%S UTC')}"}]
        })

        if not self.slack_webhook:
            print(f"[Notifier] No webhook — would send: {alert.severity} for {alert.service}")
            return True
            
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(self.slack_webhook, json={"blocks": blocks})
                return resp.status_code == 200
            except:
                return False

    async def annotate_grafana(self, alert: AlertEvent, pipeline_id: str) -> str | None:
        if not self.grafana_key or not self.grafana_url:
            return None
            
        payload = {
            "time": int(alert.triggered_at.timestamp() * 1000),
            "tags": ["mairs", alert.severity.value.lower(), alert.service],
            "text": f"MAIRS: {alert.anomaly} | Pipeline: {pipeline_id}"
        }
        
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.post(
                    f"{self.grafana_url}/api/annotations",
                    headers={"Authorization": f"Bearer {self.grafana_key}"},
                    json=payload
                )
                if resp.status_code == 200:
                    return str(resp.json().get("id"))
            except:
                pass
        return None

    def format_jira_body(self, alert: AlertEvent, runbook: Runbook, rca: RCAResult = None) -> str:
        body = f"h1. MAIRS Incident Report: {alert.service}\n\n"
        body += f"*Severity:* {alert.severity}\n"
        body += f"*Service:* {alert.service}\n"
        body += f"*Component:* {alert.component}\n"
        body += f"*Anomaly:* {alert.anomaly}\n\n"
        
        if rca:
            body += "h2. Root Cause Analysis\n"
            body += f"*Category:* {rca.root_cause_category}\n"
            body += f"*Trigger:* {rca.trigger.get('description')}\n"
            body += f"*Confidence:* {int(rca.confidence*100)}%\n\n"
            
        body += "h2. Generated Runbook\n"
        for step in runbook.steps:
            body += f"#{step.action}\n"
            if step.command:
                body += f"{{code}}{step.command}{{code}}\n"
                
        body += f"\n*Estimated Resolution:* {runbook.estimated_resolution_minutes} minutes"
        return body
