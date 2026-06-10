import React, { useState, useEffect, useRef, useCallback } from "react";
import AgentLiveFeed from "./components/AgentLiveFeed";
import IncidentDetails from "./components/IncidentDetails";
import CapacityPlanning from "./components/CapacityPlanning";

const API_BASE = "http://localhost:8002";

export default function App() {
  const [activeTab, setActiveTab] = useState("incidents");
  const [incidents, setIncidents] = useState([]);
  const [activePipelineId, setActivePipelineId] = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [agentEvents, setAgentEvents] = useState({});
  const [capacityData, setCapacityData] = useState(null);
  const [isSimulating, setIsSimulating] = useState(null);

  const wsRef = useRef(null);

  // Fetch incidents list
  const fetchIncidents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/incidents?limit=15`);
      const data = await res.json();
      if (data && data.metadatas) {
        const list = data.metadatas.map((m, idx) => ({
          id: data.ids[idx],
          ...m,
          resolution_steps: typeof m.resolution_steps === "string" ? safeParseJSON(m.resolution_steps) : m.resolution_steps
        }));
        setIncidents(list);
      }
    } catch (err) {
      console.error("Error fetching incidents:", err);
    }
  }, []);

  // Fetch capacity forecasts
  const fetchCapacity = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/capacity`);
      const data = await res.json();
      setCapacityData(data);
    } catch (err) {
      console.error("Error fetching capacity:", err);
    }
  }, []);

  useEffect(() => {
    fetchIncidents();
    fetchCapacity();
    const interval = setInterval(() => {
      fetchIncidents();
      fetchCapacity();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchIncidents, fetchCapacity]);

  // Handle WebSocket Connection
  useEffect(() => {
    if (!activePipelineId) return;

    const oldWs = wsRef.current;
    if (oldWs) {
      oldWs.close();
    }

    setAgentEvents({});

    // Connect to backend websocket endpoint
    const ws = new WebSocket(`ws://localhost:8002/ws/pipeline/${activePipelineId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`Connected to WS for pipeline: ${activePipelineId}`);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        console.log("WS Event received:", payload);

        setAgentEvents((prev) => ({
          ...prev,
          [payload.agent]: payload
        }));

        // Poll backend to get the latest updated pipeline state
        fetchPipelineDetails(activePipelineId);
      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    ws.onclose = () => {
      console.log(`WebSocket closed for: ${activePipelineId}`);
    };

    return () => {
      ws.close();
    };
  }, [activePipelineId]);

  const fetchPipelineDetails = async (pipelineId) => {
    try {
      const res = await fetch(`${API_BASE}/api/pipeline/${pipelineId}`);
      const data = await res.json();
      if (data && data.status !== "running") {
        setPipelineData(data);
      }
    } catch (err) {
      console.error("Error fetching pipeline details:", err);
    }
  };

  // Trigger simulated incident
  const triggerMockIncident = async (profileType) => {
    setIsSimulating(profileType);
    try {
      const res = await fetch(`${API_BASE}/api/alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metrics: {
            error_rate_percent: profileType === "database_timeout" ? 15.4 : profileType === "out_of_memory" ? 8.5 : 2.8,
            latency_p99_ms: profileType === "database_timeout" ? 3200 : profileType === "out_of_memory" ? 1800 : 1150,
            cpu_utilization_percent: profileType === "high_cpu" ? 96.0 : 80.0,
            memory_utilization_percent: profileType === "out_of_memory" ? 98.5 : 60.0,
            service_up: profileType === "out_of_memory" ? 0.0 : 1.0,
            service: profileType === "database_timeout" ? "database-primary" : profileType === "out_of_memory" ? "cache-layer" : "payments-api",
            component: profileType === "database_timeout" ? "connection-pool" : profileType === "out_of_memory" ? "redis-cluster" : "transaction-logger",
            anomaly: profileType === "database_timeout" ? "Write pool connection limit reached. Stripe checkout transactions timed out."
                     : profileType === "out_of_memory" ? "Out of memory. Eviction policy failed."
                     : "High CPU utilization spike during billing worker processing queue."
          }
        })
      });

      const data = await res.json();
      if (data && data.pipeline_id) {
        setActivePipelineId(data.pipeline_id);
        setActiveTab("incidents");
        setPipelineData(null);
      }
    } catch (err) {
      console.error("Failed to inject incident:", err);
    } finally {
      setIsSimulating(null);
    }
  };

  function safeParseJSON(str) {
    try {
      return JSON.parse(str);
    } catch {
      return str;
    }
  }

  return (
    <div className="min-h-screen bg-[#0b0c10] text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-900 bg-[#0f1118]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(168,85,247,0.3)]">
              M
            </div>
            <div>
              <h1 className="text-md font-bold tracking-tight text-white m-0 leading-none">MAIRS v2</h1>
              <span className="text-[10px] text-purple-400 font-mono">Multi-Agent Incident Response System</span>
            </div>
          </div>

          <nav className="flex gap-1 bg-slate-950 p-1 rounded-lg border border-slate-900">
            <button
              onClick={() => setActiveTab("incidents")}
              className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 ${
                activeTab === "incidents"
                  ? "bg-purple-600 text-white shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              💼 E2E Incident Workspace
            </button>
            <button
              onClick={() => setActiveTab("capacity")}
              className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all duration-200 ${
                activeTab === "capacity"
                  ? "bg-purple-600 text-white shadow-md"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              📈 Capacity Planning
            </button>
          </nav>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">

        {/* Left Side: Simulation Controls & Seeding status */}
        <section className="lg:col-span-4 space-y-6">
          <div className="bg-[#0f1118]/80 backdrop-blur-md border border-slate-900 rounded-xl p-5 shadow-lg">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-4 flex items-center gap-2">
              <span>🩺</span> System Health Summary
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between text-xs py-2 border-b border-slate-850">
                <span className="text-slate-400">Agent API Server:</span>
                <span className="text-emerald-400 font-semibold font-mono flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ONLINE
                </span>
              </div>
              <div className="flex justify-between text-xs py-2 border-b border-slate-850">
                <span className="text-slate-400">ChromaDB Incidents:</span>
                <span className="text-purple-400 font-mono font-semibold">{incidents.length} items seeded</span>
              </div>
              <div className="flex justify-between text-xs py-2">
                <span className="text-slate-400">Default Model:</span>
                <span className="text-slate-300 font-mono">Qwen 2.5 Coder / Llama 3.1</span>
              </div>
            </div>
          </div>

          <div className="bg-[#0f1118]/80 backdrop-blur-md border border-slate-900 rounded-xl p-5 shadow-lg space-y-4">
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-1">🎯 Inject Simulated Failure</h2>
              <p className="text-[11px] text-slate-400">Trigger full LangGraph multi-agent remediation workspace.</p>
            </div>

            <div className="space-y-2.5 pt-2">
              <button
                onClick={() => triggerMockIncident("database_timeout")}
                disabled={isSimulating !== null}
                className="w-full text-left px-4 py-3 rounded-lg border border-slate-850 bg-slate-950/40 hover:bg-purple-950/10 hover:border-purple-500/40 transition-all duration-300 group flex justify-between items-center"
              >
                <div>
                  <div className="text-xs font-semibold text-white group-hover:text-purple-300">Database Timeout Failure</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Write saturation & Stripe checkout logs</div>
                </div>
                <span className="text-slate-600 group-hover:text-purple-400 text-xs">🚀</span>
              </button>

              <button
                onClick={() => triggerMockIncident("out_of_memory")}
                disabled={isSimulating !== null}
                className="w-full text-left px-4 py-3 rounded-lg border border-slate-850 bg-slate-950/40 hover:bg-purple-950/10 hover:border-purple-500/40 transition-all duration-300 group flex justify-between items-center"
              >
                <div>
                  <div className="text-xs font-semibold text-white group-hover:text-purple-300">Redis Cache OOM</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Eviction policy crash & system offline</div>
                </div>
                <span className="text-slate-600 group-hover:text-purple-400 text-xs">🚀</span>
              </button>

              <button
                onClick={() => triggerMockIncident("high_cpu")}
                disabled={isSimulating !== null}
                className="w-full text-left px-4 py-3 rounded-lg border border-slate-850 bg-slate-950/40 hover:bg-purple-950/10 hover:border-purple-500/40 transition-all duration-300 group flex justify-between items-center"
              >
                <div>
                  <div className="text-xs font-semibold text-white group-hover:text-purple-300">Payments API Error Spike</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Queue processor bottleneck & latency</div>
                </div>
                <span className="text-slate-600 group-hover:text-purple-400 text-xs">🚀</span>
              </button>
            </div>
          </div>

          <div className="bg-[#0f1118]/80 backdrop-blur-md border border-slate-900 rounded-xl p-5 shadow-lg">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider mb-3">📁 Historical Seeded Incidents</h2>
            <div className="max-h-[220px] overflow-y-auto pr-1 space-y-2 scroller">
              {incidents.slice(0, 5).map((inc) => (
                <div key={inc.id} className="p-3 bg-slate-950/40 border border-slate-850 rounded-lg text-xs">
                  <div className="flex justify-between font-mono text-[10px] text-purple-400 mb-1">
                    <span>{inc.id}</span>
                    <span className={inc.severity === "CRITICAL" ? "text-rose-400" : "text-amber-400"}>{inc.severity}</span>
                  </div>
                  <div className="font-semibold text-white truncate">{inc.title}</div>
                  <div className="text-slate-400 truncate mt-1">{inc.root_cause}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Right Side: Dynamic Workspace Area */}
        <section className="lg:col-span-8">
          {activeTab === "incidents" ? (
            <div className="space-y-6">

              {/* Agent live thought feed */}
              {activePipelineId ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <AgentLiveFeed events={agentEvents} />
                  </div>
                  <div>
                    <IncidentDetails pipelineData={pipelineData} />
                  </div>
                </div>
              ) : (
                <div className="bg-[#0f1118]/80 backdrop-blur-md border border-slate-900 rounded-xl p-12 text-center shadow-lg space-y-4">
                  <div className="text-5xl">🌌</div>
                  <h3 className="text-lg font-bold text-white">E2E Resolution Workspace</h3>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    Select or trigger a simulated system incident using the side panel to view full real-time reasoning graph compilation.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div>
              <CapacityPlanning capacityData={capacityData} />
            </div>
          )}
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-[#0f1118]/60 py-6 text-center text-xs text-slate-500 font-mono">
        🤖 MAIRS v2 · DeepMind Advanced Multi-Agent Response Telemetry
      </footer>
    </div>
  );
}
