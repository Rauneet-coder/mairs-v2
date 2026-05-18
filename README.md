# MAIRS v2 — Architecture & Execution Guide

Welcome to the Multi-Agent Incident Response System (MAIRS) v2 repository. This README serves as the complete execution plan and design guide, containing the architecture overview, recommended local models, testing commands, and the master prompt to build the system via your AI IDE.

## 1. Best Ollama Models for this Task (192GB VRAM)

Since you have a 192GB VRAM machine, you don't need to settle for small models. For multi-agent systems and coding tasks where strict JSON formatting and advanced reasoning are required, here are the absolute best models you can run via Ollama:

1. **`llama3.1:70b` (or `llama-3.3-70b`)**: The gold standard for open-source multi-agent reasoning. It follows tool-calling and JSON schemas incredibly well. Highly recommended for the core agents (RCA, Resolver).
2. **`qwen2.5-coder:32b` / `qwen2.5:72b`**: The Qwen 2.5 series has state-of-the-art coding capabilities. The 32B Coder model is incredibly fast and beats most larger models at purely writing code, scripts, and YAML files for resolutions.
3. **`command-r-plus` (104B)**: Specifically trained for RAG and tool-use (function calling). Excellent for agents that need to query the database and execute actions.
4. **`mixtral:8x22b` (141B)**: A highly capable MoE model that is fast for its size.

**Command to pull the recommended choices:**
```bash
ollama pull llama3.1:70b
ollama pull qwen2.5-coder:32b
```

---

## 2. Architecture Design: Multi-Agent Model

We use **LangGraph** to manage the agents. The pipeline follows a state-machine pattern:

1. **Monitor Agent**: Listens to Prometheus/Grafana alerts. When an alert triggers, it formats the data and passes it to the state graph.
2. **Historian Agent**: Takes the alert, queries ChromaDB for past similar incidents, and attaches the context to the state.
3. **RCA (Root Cause Analysis) Agent**: Analyzes the metrics + history to determine the root cause.
4. **Resolver & Auto-Healer Agent**: Generates the fix (e.g., a bash script, a kubernetes command, or configuration change) based on the RCA.
5. **Capacity & Notifier Agent**: Updates the runbook and sends the final RCA + Resolution to the frontend.

**Backend Framework:** `FastAPI` (Python)
- Serves as the API layer.
- Uses WebSockets to stream the agent's thought process to the frontend in real-time.

---

## 3. Architecture Design: Frontend to Backend

The frontend will be a sleek, dark-mode **React (Vite) + TailwindCSS** application.

**Communication Flow:**
1. **REST API**: Frontend fetches historical incidents and general stats from FastAPI endpoints (`/api/incidents`).
2. **WebSockets (Real-time)**: Frontend connects to `ws://localhost:8000/ws`. As the LangGraph multi-agent pipeline executes, it streams events (`agent_started`, `agent_thought`, `agent_finished`) over the WebSocket.
3. **UI Updates**: The React UI has an `AgentPanel` component that renders these steps dynamically, giving judges the "wow" factor of seeing the agents think in real-time.

---

## 4. Testing Commands

**Backend Tests:**
```bash
# Run the FastAPI server locally
uvicorn api.main:app --reload --port 8000

# Test the agents directly from CLI (bypassing HTTP)
python -m tests.test_agents --mock-alert "High CPU Usage on Database"
```

**Frontend Tests:**
```bash
cd frontend
npm run dev
```

**E2E Incident Simulation:**
```bash
# Triggers a mock incident to flow through Prometheus -> Backend -> Frontend
python -m monitoring.trigger_mock_incident --type "database_timeout"
```

---

## 5. Master Prompt for Cursor / Windsurf

*Copy and paste the following prompt into your AI IDE's Composer (Ctrl/Cmd + I) to build the entire system based on the existing structure.*

```text
You are an expert AI architect and Full-Stack Developer. I need to build out "MAIRS v2" (Multi-Agent Incident Response System) in my current workspace. My backend will use FastAPI, LangGraph, and Ollama (llama3.1:70b). My frontend will use React, Vite, and TailwindCSS. 

Please generate the following file structure and code, step-by-step, complementing my existing `data/`, `fine_tuning/`, and `monitoring/` directories:

**Phase 1: Multi-Agent Backend (Python/FastAPI)**
1. Create `api/main.py` with a FastAPI server. Include a `/ws` WebSocket endpoint that will stream agent progress, and a POST `/api/webhook` to receive mock Prometheus alerts.
2. Create `agents/state.py` defining a LangGraph `TypedDict` State that holds: `incident_data`, `historical_context`, `root_cause`, `resolution_plan`.
3. Create `agents/nodes.py` with 4 functions (LangGraph nodes):
   - `monitor_node`: Parses the incident.
   - `historian_node`: Mocks a vector search returning past similar incidents.
   - `rca_node`: Uses Ollama to generate a root cause analysis based on the incident and history.
   - `resolver_node`: Uses Ollama to generate a remediation script/action.
4. Create `agents/graph.py` that wires these nodes together using LangGraph `StateGraph`, compiles it, and includes a function that runs the graph and yields updates to the WebSocket.

**Phase 2: Frontend Dashboard (React/Tailwind)**
5. Scaffold a `frontend/` directory (run `npx create-vite@latest frontend --template react`).
6. Create `frontend/src/App.jsx` with a premium dark-mode dashboard (bg-gray-900, text-white).
7. Create a `frontend/src/components/AgentLiveFeed.jsx` component that connects to `ws://localhost:8000/ws` and visually displays the agents "thinking" step-by-step (Monitor -> Historian -> RCA -> Resolver) with green checkmarks as they complete.
8. Create a `frontend/src/components/IncidentDetails.jsx` that displays the final Root Cause and Resolution Plan formatted nicely.

**Phase 3: Integration & Testing**
9. Create `tests/simulate_incident.py` which sends a POST request to `http://localhost:8000/api/webhook` with a mock high CPU database payload to trigger the system.
10. Update `requirements.txt` to include `fastapi`, `uvicorn`, `websockets`, `langgraph`, `langchain-community`, `pydantic`.

Ensure the backend code relies on `LLM_BASE_URL` and `LLM_MODEL_FAST` from `.env` to connect to my local Ollama instance (e.g., http://localhost:11434/v1 using OpenAI compatibility in LangChain). Let's build this!
```
