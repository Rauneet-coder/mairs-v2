#!/usr/bin/env python3
"""CLI tool to test the MAIRS v2 multi-agent pipeline directly."""

import asyncio
import argparse
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI

from api.models import PipelineState
from integrations.prometheus_client import PrometheusClient
from agents.monitor_agent import MonitorAgent
from agents.historian_agent import HistorianAgent
from agents.rca_agent import RCAAgent
from agents.resolver_agent import ResolverAgent
from agents.auto_healer_agent import AutoHealerAgent
from agents.capacity_planner_agent import CapacityPlannerAgent
from agents.notifier_agent import NotifierAgent
from agents.pipeline import create_pipeline

# Mocks in case of missing LLM configuration or offline environment
class MockLLMChatCompletions:
    def __init__(self, mode):
        self.mode = mode

    async def create(self, model, messages, temperature=0.1, max_tokens=1000, **kwargs):
        class MockChoiceMessage:
            def __init__(self, content):
                self.content = content
        class MockChoice:
            def __init__(self, content):
                self.message = MockChoiceMessage(content)
        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]

        sys_prompt = messages[0]["content"] if messages else ""
        
        if "monitoring" in sys_prompt or "Analyze incoming system metrics" in sys_prompt:
            # Monitor agent mock
            content = json.dumps({
                "severity": "CRITICAL",
                "service": "database-primary",
                "component": "connection-pool",
                "anomaly": "Database connection pool exhaustion detected. High error rate on write queries.",
                "business_impact": "high"
            })
        elif "root cause analyst" in sys_prompt:
            # RCA agent mock
            content = json.dumps({
                "trigger": {
                    "description": "Stripe API timeouts causing write pool saturation",
                    "timestamp": datetime.utcnow().isoformat(),
                    "evidence": "error_rate_percent = 12.5%"
                },
                "propagation": [
                    {"step": 1, "event": "Write pool connection limit reached", "service": "database-primary", "lag_seconds": 0},
                    {"step": 2, "event": "API timeout on payments checkout", "service": "payments-api", "lag_seconds": 15}
                ],
                "impact": {
                    "affected_services": ["database-primary", "payments-api"],
                    "estimated_users_affected": 1250,
                    "blast_radius": "moderate"
                },
                "root_cause_category": "resource_exhaustion",
                "confidence": 0.90,
                "similar_incident_ref": "INC-2024-001"
            })
        elif "generating resolution runbooks" in sys_prompt or "resolution agent" in sys_prompt:
            # Resolver agent mock
            content = json.dumps({
                "steps": [
                    {
                        "step": 1,
                        "action": "Check database connection pool utilization",
                        "command": "psql -c 'SELECT count(*) FROM pg_stat_activity;'",
                        "duration_minutes": 1,
                        "historical_ref": "INC-2024-001",
                        "auto_executable": False
                    },
                    {
                        "step": 2,
                        "action": "Flush cache-layer eviction policy",
                        "command": "redis-cli -h cache-layer FLUSHDB",
                        "duration_minutes": 2,
                        "historical_ref": "INC-2024-002",
                        "auto_executable": True
                    },
                    {
                        "step": 3,
                        "action": "Restart affected database-primary pods",
                        "command": "kubectl rollout restart deployment/database-primary",
                        "duration_minutes": 5,
                        "historical_ref": "INC-2024-003",
                        "auto_executable": True
                    }
                ],
                "estimated_resolution_minutes": 8,
                "confidence": 0.85
            })
        else:
            content = "{}"
        
        return MockResponse(content)

class MockChat:
    def __init__(self, completions):
        self.completions = completions

class MockLLM:
    def __init__(self, mode="fast"):
        completions = MockLLMChatCompletions(mode)
        self.chat = MockChat(completions)
        self.completions = completions

async def run_test(alert_text: str, mock_llm: bool):
    print(f"\n🚀 Starting Agent Pipeline Test with alert concept: '{alert_text}'")
    
    load_dotenv()
    
    # Initialize Prometheus Client with dummy base URL
    prom_client = PrometheusClient(base_url="http://localhost:9090")
    
    # Check if we should use Mock LLM or live client
    llm_url = os.getenv("LLM_BASE_URL")
    if mock_llm or not llm_url:
        print("💡 Using MOCKED Local LLM responses for simulation.")
        fast_llm = MockLLM("fast")
        smart_llm = MockLLM("smart")
    else:
        print(f"📡 Using LIVE LLM Endpoint at: {llm_url}")
        fast_llm = AsyncOpenAI(base_url=llm_url, api_key="na")
        smart_llm = AsyncOpenAI(base_url=os.getenv("LLM_BASE_URL_FINETUNED") or llm_url, api_key="na")
        
    fast_model = os.getenv("LLM_MODEL_FAST", "qwen2.5-coder:32b")
    smart_model = os.getenv("LLM_MODEL_FINETUNED", fast_model)
    
    # Create agents
    monitor = MonitorAgent(fast_llm, fast_model)
    historian = HistorianAgent()
    rca = RCAAgent(smart_llm, smart_model)
    resolver = ResolverAgent(smart_llm, smart_model)
    healer = AutoHealerAgent(dry_run=True)
    capacity = CapacityPlannerAgent(smart_llm, smart_model)
    notifier = NotifierAgent()
    
    # Custom WebSocket Broadcast logger
    class MockWSManager:
        async def broadcast(self, pipeline_id: str, event):
            print(f"📡 [WS STREAM] Agent: {event.agent.upper()} | Status: {event.status.upper()} | Data: {event.data}")
            
    ws_manager = MockWSManager()
    
    # Create compiled StateGraph
    compiled_pipeline = create_pipeline(
        monitor, historian, rca, resolver, healer, capacity, notifier, ws_manager, prom_client
    )
    
    # Raw mock metrics simulating the triggered alert
    mock_metrics = {
        "error_rate_percent": 12.5,
        "latency_p99_ms": 2500,
        "cpu_utilization_percent": 91.0,
        "memory_utilization_percent": 88.0,
        "service_up": 1.0,
        "service": "database-primary",
        "component": "connection-pool",
        "anomaly": alert_text
    }
    
    state: PipelineState = {
        "raw_metrics": mock_metrics,
        "alert_event": None,
        "historical_matches": [],
        "rca_result": None,
        "runbook": None,
        "healing_result": None,
        "notification_sent": False,
        "pipeline_id": "test-pipeline-12345",
        "pipeline_start_time": time.time(),
        "error": None
    }
    
    print("\n--- Pipeline Node Execution Logs ---")
    result = await compiled_pipeline.ainvoke(state)
    print("------------------------------------\n")
    
    print("✅ Pipeline Completed!")
    print(f"⏱️  TTR Elapsed: {round(time.time() - state['pipeline_start_time'], 3)}s")
    if result.get("error"):
        print(f"❌ Error encountered: {result['error']}")
    else:
        print("\n📈 Root Cause Analysis:")
        if result["rca_result"]:
            print(f"  - Category: {result['rca_result'].root_cause_category}")
            print(f"  - Trigger: {result['rca_result'].trigger.get('description')}")
            print(f"  - Confidence: {result['rca_result'].confidence * 100}%")
        
        print("\n🛠️  Generated Remediation Runbook:")
        if result["runbook"]:
            print(f"  - Est. TTR: {result['runbook'].estimated_resolution_minutes} minutes")
            for step in result["runbook"].steps:
                print(f"    Step {step.step}: {step.action} (CMD: {step.command}) [Auto-Exec: {step.auto_executable}]")
        
        print("\n🏥 Auto-Healing Actions Executed (Dry-Run):")
        if result["healing_result"]:
            print(f"  - Succeeded: {result['healing_result'].actions_succeeded} | Failed: {result['healing_result'].actions_failed}")
            print(f"  - Performance Improvement: {result['healing_result'].improvement_percent}%")
            for action in result["healing_result"].actions_log:
                print(f"    - Action: {action.action} | Status: {action.status.upper()} | Output: {action.output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MAIRS v2 multi-agent workflow.")
    parser.add_argument("--mock-alert", type=str, default="High CPU Usage on Database", help="Mock alert name")
    parser.add_argument("--mock-llm", action="store_true", default=True, help="Force mock LLM outputs")
    args = parser.parse_args()
    
    asyncio.run(run_test(args.mock_alert, args.mock_llm))
