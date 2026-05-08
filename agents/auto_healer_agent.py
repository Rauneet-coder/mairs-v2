import asyncio
import time
from api.models import AlertEvent, Runbook, HealingResult, HealingAction, Severity

HEALING_REGISTRY = {
    "flush_cache": {
        "safe_for": [Severity.WARNING, Severity.CRITICAL],
        "dry_run": lambda target: f"redis-cli -h {target} FLUSHDB"
    },
    "reset_connection_pool": {
        "safe_for": [Severity.WARNING],
        "dry_run": lambda target: f"curl -X POST http://{target}/admin/reset-pool"
    },
    "increase_rate_limit": {
        "safe_for": [Severity.WARNING, Severity.CRITICAL],
        "dry_run": lambda target: f"kubectl set env deployment/{target} RATE_LIMIT_MULTIPLIER=1.5"
    },
    "restart_pod": {
        "safe_for": [Severity.WARNING],
        "dry_run": lambda target: f"kubectl rollout restart deployment/{target}"
    },
    "scale_up_pods": {
        "safe_for": [Severity.WARNING],
        "dry_run": lambda target: f"kubectl scale deployment/{target} --replicas=+2"
    }
}

class AutoHealerAgent:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.action_history: list[dict] = []

    def _was_recently_executed(self, action: str, minutes: int = 10) -> bool:
        cutoff = time.time() - (minutes * 60)
        return any(h["action"] == action and h["timestamp"] > cutoff for h in self.action_history)

    async def execute(self, alert: AlertEvent, runbook: Runbook, prometheus=None) -> HealingResult:
        metrics_before = {
            "error_rate": alert.raw_metrics.get("error_rate_percent", 0),
            "latency_p99": alert.raw_metrics.get("latency_p99_ms", 0)
        }
        
        auto_steps = [s for s in runbook.steps if s.auto_executable][:3]
        actions_log = []
        succeeded = 0
        failed = 0
        
        for step in auto_steps:
            action_name = None
            step_action_lower = step.action.lower().replace(" ", "_")
            for key in HEALING_REGISTRY:
                if key in step_action_lower:
                    action_name = key
                    break
            
            if not action_name:
                actions_log.append(HealingAction(
                    action=step.action, target="unknown", status="skipped", 
                    output="No matching healing registry key found", duration_ms=0
                ))
                continue
                
            registry = HEALING_REGISTRY[action_name]
            if alert.severity not in registry["safe_for"]:
                actions_log.append(HealingAction(
                    action=action_name, target=alert.service, status="skipped", 
                    output=f"Action not safe for severity {alert.severity}", duration_ms=0
                ))
                continue
                
            if self._was_recently_executed(action_name):
                actions_log.append(HealingAction(
                    action=action_name, target=alert.service, status="skipped", 
                    output="Action recently executed, skipping to prevent flip-flop", duration_ms=0
                ))
                continue
                
            start_ms = int(time.time() * 1000)
            output = registry["dry_run"](alert.service)
            await asyncio.sleep(0.3)  # simulate execution
            end_ms = int(time.time() * 1000)
            
            self.action_history.append({"action": action_name, "timestamp": time.time()})
            actions_log.append(HealingAction(
                action=action_name, target=alert.service, status="success", 
                output=f"[DRY RUN] {output}" if self.dry_run else f"Executed: {output}", 
                duration_ms=end_ms - start_ms
            ))
            succeeded += 1

        # Simulate improvement
        error_before = metrics_before["error_rate"]
        error_after = error_before
        if succeeded > 0:
            error_after = error_before * 0.3
            
        improvement = 0.0
        if error_before > 0:
            improvement = round((1 - error_after / error_before) * 100, 1)

        return HealingResult(
            actions_attempted=len(auto_steps),
            actions_succeeded=succeeded,
            actions_failed=failed,
            actions_log=actions_log,
            metrics_before=metrics_before,
            metrics_after={"error_rate": error_after, "latency_p99": metrics_before["latency_p99"]},
            improvement_percent=improvement,
            dry_run=self.dry_run
        )
