# MAIRS v2 — Execution & Architecture Plan

## 1. Best Ollama Models for this Task (192GB VRAM)

Since you have a beast of a machine with 192GB VRAM, you don't need to settle for small models. For multi-agent systems and coding tasks where strict JSON formatting and advanced reasoning are required, here are the absolute best models you can run in Ollama:

1. **`llama3.1:70b` (or `llama-3.3-70b` if available)**: The gold standard for open-source multi-agent reasoning. It follows tool-calling and JSON schemas incredibly well. This is highly recommended for the core agents (RCA, Resolver).
2. **`qwen2.5-coder:32b` / `qwen2.5:72b`**: The Qwen 2.5 series has state-of-the-art coding capabilities. The 32B Coder model is incredibly fast and beats most larger models at purely writing code and scripts.
3. **`command-r-plus` (104B)**: Specifically trained for RAG and tool-use (function calling). Excellent for agents that need to query the database and execute actions.
4. **`mixtral:8x22b` (141B)**: A MoE model that is incredibly fast for its size. Very capable of general reasoning and coding.

**Command to pull the best overall choice:**
```bash
ollama pull llama3.1:70b
ollama pull qwen2.5-coder:32b
```

---

## 2. Architecture Design: Multi-Agent Model

We will use **LangGraph** (or CrewAI/AutoGen, but LangGraph gives you the most control over the state) to manage the agents. The pipeline follows a state-machine pattern:

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
3. **UI Updates**: The React UI has an `AgentPanel` component that renders these steps dynamically, giving the judges the "wow" factor of seeing the agents think.

---

## 4. Testing Commands

You need a systematic way to test this without breaking production.

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

## 5. Master Prompt for Cursor/Windsurf

*Copy and paste the following prompt into Cursor/Windsurf's Composer (Ctrl/Cmd + I) to build the entire system.*

### **Prompt to Paste:**

```text
You are an expert AI architect and Full-Stack Developer. I need to build "MAIRS v2" (Multi-Agent Incident Response System). My backend uses FastAPI, LangGraph, and Ollama (llama3.1:70b). My frontend uses React, Vite, and TailwindCSS. 

Please generate the following file structure and code, step-by-step:

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
5. Create a `frontend/` directory (assume `npm create vite@latest . --template react` was run).
6. Create `frontend/src/App.jsx` with a premium dark-mode dashboard (bg-gray-900, text-white).
7. Create a `frontend/src/components/AgentLiveFeed.jsx` component that connects to `ws://localhost:8000/ws` and visually displays the agents "thinking" step-by-step (Monitor -> Historian -> RCA -> Resolver) with green checkmarks as they complete.
8. Create a `frontend/src/components/IncidentDetails.jsx` that displays the final Root Cause and Resolution Plan nicely formatted in Markdown.

**Phase 3: Integration & Testing**
9. Create `tests/simulate_incident.py` which sends a POST request to `http://localhost:8000/api/webhook` with a mock high CPU database payload to trigger the system.
10. Update `requirements.txt` to include `fastapi`, `uvicorn`, `websockets`, `langgraph`, `langchain-community`, `pydantic`.

Ensure the code relies on the `LLM_BASE_URL` from `.env` to connect to Ollama (e.g., http://localhost:11434/v1 using OpenAI compatibility in LangChain). Let's build this!
```
