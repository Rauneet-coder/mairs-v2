import asyncio
import time
import uuid
import os
from datetime import datetime
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
from integrations.prometheus_client import PrometheusClient # Assuming this exists or mocked

load_dotenv()

app = FastAPI(title="MAIRS v2 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# LLM Config
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:4000/v1")
LLM_BASE_URL_FINETUNED = os.getenv("LLM_BASE_URL_FINETUNED")
fast_llm = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="na")
smart_llm = AsyncOpenAI(base_url=LLM_BASE_URL_FINETUNED or LLM_BASE_URL, api_key="na")
fast_model = os.getenv("LLM_MODEL_FAST", "qwen2.5-coder:32b")
smart_model = os.getenv("LLM_MODEL_FINETUNED", fast_model)

# Managers
ws_manager = ConnectionManager()
prometheus = PrometheusClient(base_url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"))

# Agents
monitor = MonitorAgent(fast_llm, fast_model)
historian = HistorianAgent()
rca = RCAAgent(smart_llm, smart_model)
resolver = ResolverAgent(smart_llm, smart_model)
healer = AutoHealerAgent(dry_run=True)
capacity = CapacityPlannerAgent(smart_llm, smart_model)
notifier = NotifierAgent()

# Pipeline
compiled_pipeline = create_pipeline(monitor, historian, rca, resolver, healer, capacity, notifier, ws_manager, prometheus)

pipeline_store: dict[str, dict] = {}
app.state.latest_forecast = {"forecasts": []}

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
    pipeline_store[pipeline_id] = result

async def capacity_loop():
    while True:
        try:
            report = await capacity.run_forecast(prometheus)
            app.state.latest_forecast = report.model_dump()
        except Exception as e:
            print(f"Capacity forecast error: {e}")
        await asyncio.sleep(6 * 3600) # 6 hours

@app.on_event("startup")
async def startup_event():
    # Start monitor polling
    asyncio.create_task(monitor.start_polling(prometheus, lambda m: run_pipeline(m, str(uuid.uuid4()))))
    # Start capacity planning
    asyncio.create_task(capacity_loop())

@app.get("/api/health")
async def health():
    count = 0
    try:
        count = historian.collection.count()
    except: pass
    return {
        "status": "ok",
        "model": fast_model,
        "timestamp": time.time(),
        "chroma_incidents": count
    }

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
    except:
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
