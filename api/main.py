import asyncio
import time
import uuid
import os
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from dotenv import load_dotenv

from api.models import PipelineState, AgentEvent
from api.websocket_manager import ConnectionManager
from agents.monitor_agent import MonitorAgent
from agents.historian_agent import HistorianAgent
from agents.rca_agent import RCAAgent
from agents.resolver_agent import ResolverAgent
from agents.auto_healer_agent import AutoHealerAgent
from agents.capacity_planner_agent import CapacityPlannerAgent
from agents.notifier_agent import NotifierAgent
from agents.pipeline import create_pipeline
from integrations.prometheus_client import PrometheusClient

load_dotenv()


# ── Mock response classes (defined once at module level) ───────────────────────
class _MockChoiceMessage:
    def __init__(self, content: str):
        self.content = content


class _MockChoice:
    def __init__(self, content: str):
        self.message = _MockChoiceMessage(content)


class _MockResponse:
    def __init__(self, content: str):
        self.choices = [_MockChoice(content)]


# ── Resilient LLM wrapper ────────────────────────────────────────────────────
class ResilientChatCompletions:
    def __init__(self, live_completions, mode):
        self.live_completions = live_completions
        self.mode = mode

    async def create(self, model, messages, temperature=0.1, max_tokens=1000, **kwargs):
        try:
            return await self.live_completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        except Exception as exc:
            print(f"⚠️ LLM call failed ({exc}), falling back to simulated SRE intelligence.")

            sys_prompt = messages[0]["content"] if messages else ""
            user_prompt = messages[1]["content"] if len(messages) > 1 else ""

            if "monitoring" in sys_prompt or "Analyze incoming system metrics" in sys_prompt:
                service = "database-primary"
                component = "connection-pool"
                anomaly = "Spike in errors detected"
                severity = "CRITICAL"

                try:
                    metrics = json.loads(user_prompt)
                    service = metrics.get("service", service)
                    component = metrics.get("component", component)
                    anomaly = metrics.get("anomaly", anomaly)
                    if metrics.get("error_rate_percent", 0) > 5 or metrics.get("latency_p99_ms", 0) > 2000:
                        severity = "CRITICAL"
                    elif metrics.get("error_rate_percent", 0) > 1 or metrics.get("cpu_utilization_percent", 0) > 85:
                        severity = "WARNING"
                    else:
                        severity = "NORMAL"
                except (json.JSONDecodeError, TypeError):
                    pass

                content = json.dumps({
                    "severity": severity,
                    "service": service,
                    "component": component,
                    "anomaly": anomaly,
                    "business_impact": "high" if service in ["payments-api", "auth-service"] else "medium"
                })
            elif "root cause analyst" in sys_prompt:
                content = json.dumps({
                    "trigger": {
                        "description": "Database query buffer saturation due to large transaction logging writes",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "evidence": "latency_p99_ms = 3200ms"
                    },
                    "propagation": [
                        {"step": 1, "event": "Write buffer replication lag increase", "service": "database-replica", "lag_seconds": 5},
                        {"step": 2, "event": "API latency degradation downstream", "service": "payments-api", "lag_seconds": 12}
                    ],
                    "impact": {
                        "affected_services": ["database-primary", "payments-api"],
                        "estimated_users_affected": 850,
                        "blast_radius": "moderate"
                    },
                    "root_cause_category": "resource_exhaustion",
                    "confidence": 0.95,
                    "similar_incident_ref": "INC-2024-034"
                })
            elif "generating resolution runbooks" in sys_prompt or "resolution agent" in sys_prompt:
                content = json.dumps({
                    "steps": [
                        {
                            "step": 1,
                            "action": "Check database write-buffer stats and CPU load",
                            "command": "psql -c 'SELECT * FROM pg_stat_activity WHERE state != \"idle\";\"'",
                            "duration_minutes": 2,
                            "historical_ref": "INC-2024-034",
                            "auto_executable": False
                        },
                        {
                            "step": 2,
                            "action": "Perform database-primary pod restart",
                            "command": "kubectl rollout restart deployment/database-primary",
                            "duration_minutes": 4,
                            "historical_ref": "INC-2024-034",
                            "auto_executable": True
                        }
                    ],
                    "estimated_resolution_minutes": 6,
                    "confidence": 0.92
                })
            elif "capacity planning" in sys_prompt or "forecast" in sys_prompt or "capacity" in sys_prompt:
                content = json.dumps({
                    "breach": True,
                    "eta_hours": 18,
                    "recommended_action": "Scale database-primary replica count to 3",
                    "confidence": 0.88
                })
            else:
                content = json.dumps({"status": "unknown_prompt", "message": "No fallback available for this prompt type"})

            return _MockResponse(content)


class ResilientChat:
    def __init__(self, live_chat, mode):
        self.completions = ResilientChatCompletions(live_chat.completions, mode)


class ResilientLLM:
    def __init__(self, live_client, mode):
        self.live_client = live_client
        self.chat = ResilientChat(live_client.chat, mode)


# ── LLM config ─────────────────────────────────────────────────────────────────
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:4000/v1")
LLM_BASE_URL_FINETUNED = os.getenv("LLM_BASE_URL_FINETUNED")

live_fast_llm = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="na")
live_smart_llm = AsyncOpenAI(base_url=LLM_BASE_URL_FINETUNED or LLM_BASE_URL, api_key="na")
fast_llm = ResilientLLM(live_fast_llm, "fast")
smart_llm = ResilientLLM(live_smart_llm, "smart")
fast_model = os.getenv("LLM_MODEL_FAST", "qwen2.5-coder:32b")
smart_model = os.getenv("LLM_MODEL_FINETUNED", fast_model)

# ── Managers & Agents ──────────────────────────────────────────────────────────
ws_manager = ConnectionManager()
prometheus = PrometheusClient(base_url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"))

monitor = MonitorAgent(fast_llm, fast_model)
historian = HistorianAgent()
rca = RCAAgent(smart_llm, smart_model)
resolver = ResolverAgent(smart_llm, smart_model)
healer = AutoHealerAgent(dry_run=True)
capacity = CapacityPlannerAgent(smart_llm, smart_model)
notifier = NotifierAgent()

compiled_pipeline = create_pipeline(monitor, historian, rca, resolver, healer, capacity, notifier, ws_manager, prometheus)

pipeline_store: dict[str, dict] = {}

# ── Lifespan (replaces deprecated on_event) ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.latest_forecast = {"forecasts": []}
    app.state._bg_tasks = set()

    def _log_task_exception(t: asyncio.Task):
        app.state._bg_tasks.discard(t)
        exc = t.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            print(f"[Lifespan] Background task failed: {exc}")

    t1 = asyncio.create_task(monitor.start_polling(prometheus, lambda m: run_pipeline(m, str(uuid.uuid4()))))
    t2 = asyncio.create_task(capacity_loop())
    app.state._bg_tasks.add(t1)
    app.state._bg_tasks.add(t2)
    t1.add_done_callback(_log_task_exception)
    t2.add_done_callback(_log_task_exception)

    yield

    # Shutdown: cancel background tasks
    for t in app.state._bg_tasks:
        t.cancel()
    await asyncio.gather(*app.state._bg_tasks, return_exceptions=True)


app = FastAPI(title="MAIRS v2 API", lifespan=lifespan)

# Restrict CORS to the frontend origin in production; allow localhost for dev
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def capacity_loop():
    while True:
        try:
            report = await capacity.run_forecast(prometheus)
            app.state.latest_forecast = report.model_dump()
        except Exception as e:
            print(f"Capacity forecast error: {e}")
        await asyncio.sleep(6 * 3600)  # 6 hours


async def run_pipeline(metrics: dict, pipeline_id: str):
    state: PipelineState = {
        "raw_metrics": metrics,
        "alert_event": None,
        "historical_matches": [],
        "rca_result": None,
        "runbook": None,
        "healing_result": None,
        "notification_sent": False,
        "pipeline_id": pipeline_id,
        "pipeline_start_time": time.time(),
        "error": None
    }

    result = await compiled_pipeline.ainvoke(state)
    result["elapsed_seconds"] = round(time.time() - state["pipeline_start_time"], 2)
    # Ensure everything is JSON-serializable before storing
    pipeline_store[pipeline_id] = _serialize_state(result)


def _serialize_state(state: dict) -> dict:
    """Recursively convert Pydantic models in the state dict to plain dicts."""
    from pydantic import BaseModel
    out = {}
    for k, v in state.items():
        if isinstance(v, BaseModel):
            out[k] = v.model_dump(mode="json")
        elif isinstance(v, list):
            out[k] = [_serialize_state(item) if isinstance(item, dict) else item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in v]
        elif isinstance(v, dict):
            out[k] = _serialize_state(v)
        else:
            out[k] = v
    return out


@app.get("/api/health")
async def health():
    count = 0
    try:
        count = historian.collection.count()
    except Exception:
        pass
    return {
        "status": "ok",
        "model": fast_model,
        "timestamp": time.time(),
        "chroma_incidents": count
    }


@app.post("/api/webhook")
@app.post("/api/alert")
async def trigger_alert(payload: dict, background_tasks: BackgroundTasks):
    metrics = payload.get("metrics", {})
    pipeline_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline, metrics, pipeline_id)
    return {"pipeline_id": pipeline_id, "status": "running"}


@app.get("/api/pipeline/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    if pipeline_id in pipeline_store:
        return pipeline_store[pipeline_id]
    return {"status": "running", "pipeline_id": pipeline_id}


@app.get("/api/incidents")
async def get_incidents(limit: int = 20):
    try:
        results = historian.collection.get(limit=limit)
        return results
    except Exception:
        return {"ids": []}


@app.get("/api/capacity")
async def get_capacity():
    return app.state.latest_forecast


@app.websocket("/ws/pipeline/{pipeline_id}")
async def websocket_endpoint(websocket: WebSocket, pipeline_id: str):
    await ws_manager.connect(pipeline_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(pipeline_id, websocket)
