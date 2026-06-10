import asyncio
import time
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END, START
from api.models import PipelineState, AgentEvent


def create_pipeline(monitor, historian, rca_agent, resolver, healer, capacity, notifier, ws_manager, prometheus):

    async def _broadcast(pipeline_id, agent, status, data=None):
        if ws_manager:
            event = AgentEvent(agent=agent, status=status, timestamp=datetime.now(timezone.utc), data=data)
            await ws_manager.broadcast(pipeline_id, event)

    async def monitor_node(state: PipelineState) -> PipelineState:
        pid = state["pipeline_id"]
        await _broadcast(pid, "monitor", "running")
        try:
            alert = await monitor.analyze(state["raw_metrics"])
            state["alert_event"] = alert
            await _broadcast(pid, "monitor", "done", {
                "severity": alert.severity.value,
                "service": alert.service,
                "anomaly": alert.anomaly
            })
        except Exception as e:
            state["error"] = f"monitor: {str(e)}"
            await _broadcast(pid, "monitor", "error", {"error": str(e)})
        return state

    async def historian_node(state: PipelineState) -> PipelineState:
        pid = state["pipeline_id"]
        await _broadcast(pid, "historian", "running")
        try:
            matches = await historian.search(state["alert_event"])
            state["historical_matches"] = matches
            await _broadcast(pid, "historian", "done", {
                "match_count": len(matches),
                "top_match": matches[0].incident_id if matches else None
            })
        except Exception as e:
            state["error"] = f"historian: {str(e)}"
            await _broadcast(pid, "historian", "error", {"error": str(e)})
        return state

    async def rca_node(state: PipelineState) -> PipelineState:
        pid = state["pipeline_id"]
        await _broadcast(pid, "rca", "running")
        try:
            ts = await prometheus.get_time_series("error_rate_percent", state["alert_event"].service, hours=1)
            result = await rca_agent.analyze(state["alert_event"], state["historical_matches"], ts)
            state["rca_result"] = result
            await _broadcast(pid, "rca", "done", {
                "confidence": result.confidence,
                "propagation_steps": len(result.propagation),
                "root_cause": result.trigger.get("description")
            })
        except Exception as e:
            state["error"] = f"rca: {str(e)}"
            await _broadcast(pid, "rca", "error", {"error": str(e)})
        return state

    async def resolver_node(state: PipelineState) -> PipelineState:
        pid = state["pipeline_id"]
        await _broadcast(pid, "resolver", "running")
        try:
            runbook = await resolver.generate(state["alert_event"], state["historical_matches"])
            state["runbook"] = runbook
            await _broadcast(pid, "resolver", "done", {
                "steps": len(runbook.steps),
                "ttr": runbook.estimated_resolution_minutes,
                "confidence": runbook.confidence
            })
        except Exception as e:
            state["error"] = f"resolver: {str(e)}"
            await _broadcast(pid, "resolver", "error", {"error": str(e)})
        return state

    async def healer_node(state: PipelineState) -> PipelineState:
        pid = state["pipeline_id"]
        await _broadcast(pid, "healer", "running")
        try:
            result = await healer.execute(state["alert_event"], state["runbook"], prometheus)
            state["healing_result"] = result
            await _broadcast(pid, "healer", "done", {
                "actions_taken": result.actions_attempted,
                "dry_run": result.dry_run,
                "improvement": result.improvement_percent
            })
        except Exception as e:
            state["error"] = f"healer: {str(e)}"
            await _broadcast(pid, "healer", "error", {"error": str(e)})
        return state

    async def notifier_node(state: PipelineState) -> PipelineState:
        pid = state["pipeline_id"]
        await _broadcast(pid, "notifier", "running")
        try:
            slack_sent = await notifier.send(state["alert_event"], state["runbook"], state["rca_result"])
            await notifier.annotate_grafana(state["alert_event"], pid)
            state["notification_sent"] = slack_sent
            await _broadcast(pid, "notifier", "done", {"slack_sent": slack_sent})
        except Exception as e:
            state["error"] = f"notifier: {str(e)}"
            await _broadcast(pid, "notifier", "error", {"error": str(e)})
        return state

    def route_after_monitor(state: PipelineState) -> str:
        if state.get("error"):
            return END
        if state["alert_event"] and state["alert_event"].severity.value in ["WARNING", "CRITICAL"]:
            return "historian"
        return END

    def route_after_resolver(state: PipelineState) -> str:
        if state.get("error"):
            return "notifier"
        # Route both WARNING and CRITICAL through the healer.
        # The healer will skip unsafe actions based on severity.
        if state["alert_event"] and state["alert_event"].severity.value in ["WARNING", "CRITICAL"]:
            return "healer"
        return "notifier"

    workflow = StateGraph(PipelineState)

    workflow.add_node("monitor", monitor_node)
    workflow.add_node("historian", historian_node)
    workflow.add_node("rca", rca_node)
    workflow.add_node("resolver", resolver_node)
    workflow.add_node("healer", healer_node)
    workflow.add_node("notifier", notifier_node)

    workflow.add_edge(START, "monitor")
    workflow.add_conditional_edges("monitor", route_after_monitor)
    workflow.add_edge("historian", "rca")
    workflow.add_edge("rca", "resolver")
    workflow.add_conditional_edges("resolver", route_after_resolver)
    workflow.add_edge("healer", "notifier")
    workflow.add_edge("notifier", END)

    return workflow.compile()
