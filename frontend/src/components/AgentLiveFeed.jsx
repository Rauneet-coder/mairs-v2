import React from "react";

const AGENT_META = {
  monitor: { name: "Monitor Agent", icon: "👁️", desc: "Analyzing system telemetry & metrics" },
  historian: { name: "Historian Agent", icon: "📚", desc: "Searching ChromaDB for past incident resolutions" },
  rca: { name: "RCA Agent", icon: "🔬", desc: "Constructing causal root-cause propagation chain" },
  resolver: { name: "Resolver Agent", icon: "🛠️", desc: "Generating mitigation runbook & safe CLI commands" },
  healer: { name: "Auto-Healer Agent", icon: "🏥", desc: "Executing automated healing actions (dry-run)" },
  notifier: { name: "Notifier Agent", icon: "📢", desc: "Dispatching alerts & annotating dashboards" }
};

export default function AgentLiveFeed({ events, activeAgent }) {
  return (
    <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800 rounded-xl p-6 shadow-2xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-ping"></span>
          Multi-Agent Reasoning Chain
        </h2>
        <span className="text-xs text-slate-400 font-mono">Real-time WebSocket feed</span>
      </div>

      <div className="relative border-l border-slate-800 ml-4 pl-8 space-y-8">
        {Object.entries(AGENT_META).map(([key, meta]) => {
          const status = events[key]?.status || "idle";
          const data = events[key]?.data;
          
          let statusColor = "border-slate-800 bg-slate-950 text-slate-500";
          let pulseEffect = "";
          
          if (status === "running") {
            statusColor = "border-purple-500 bg-purple-950/30 text-purple-400 shadow-[0_0_15px_rgba(168,85,247,0.4)]";
            pulseEffect = "animate-pulse";
          } else if (status === "done") {
            statusColor = "border-emerald-500 bg-emerald-950/30 text-emerald-400";
          } else if (status === "error") {
            statusColor = "border-rose-500 bg-rose-950/30 text-rose-400";
          }

          return (
            <div key={key} className={`relative transition-all duration-300 ${status === "running" ? "scale-[1.01]" : ""}`}>
              {/* Node Icon Circle */}
              <div className={`absolute -left-14 top-0.5 w-11 h-11 rounded-full border-2 flex items-center justify-center text-lg ${statusColor} ${pulseEffect} transition-all duration-300 z-10`}>
                {meta.icon}
              </div>

              {/* Node Content */}
              <div className={`p-4 rounded-lg border transition-all duration-300 ${
                status === "running" 
                  ? "bg-purple-950/10 border-purple-500/30 shadow-lg"
                  : status === "done"
                  ? "bg-slate-900/30 border-slate-800/80"
                  : "bg-slate-950/20 border-transparent text-slate-500"
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <h3 className={`font-semibold ${status === "idle" ? "text-slate-500" : "text-white"}`}>
                    {meta.name}
                  </h3>
                  <span className={`text-xs font-mono px-2 py-0.5 rounded uppercase ${
                    status === "running" ? "bg-purple-500/20 text-purple-300" :
                    status === "done" ? "bg-emerald-500/20 text-emerald-300" :
                    status === "error" ? "bg-rose-500/20 text-rose-300" :
                    "bg-slate-800 text-slate-600"
                  }`}>
                    {status}
                  </span>
                </div>
                
                <p className="text-sm text-slate-400 mb-2">{meta.desc}</p>

                {/* Streamed Agent Output */}
                {status === "running" && (
                  <div className="text-xs font-mono bg-black/40 p-2.5 rounded border border-purple-950/30 text-purple-300/90 flex items-center gap-2">
                    <svg className="animate-spin h-3.5 w-3.5 text-purple-400" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Executing thoughts...
                  </div>
                )}

                {status === "done" && data && (
                  <div className="mt-3 text-xs font-mono bg-emerald-950/10 border border-emerald-900/30 p-3 rounded-md text-emerald-300 space-y-1">
                    {key === "monitor" && (
                      <>
                        <div>🎯 Severity: <span className="font-bold text-white">{data.severity}</span></div>
                        <div>🔌 Affected Service: <span className="text-slate-300">{data.service}</span></div>
                        <div>⚠️ Anomaly: <span className="text-slate-300">"{data.anomaly}"</span></div>
                      </>
                    )}
                    {key === "historian" && (
                      <>
                        <div>📁 Past Similar Incidents Matched: <span className="font-bold text-white">{data.match_count}</span></div>
                        {data.top_match && <div>🏷️ Best Match: <span className="text-slate-300">{data.top_match}</span></div>}
                      </>
                    )}
                    {key === "rca" && (
                      <>
                        <div>🔍 Root Cause: <span className="font-bold text-white">"{data.root_cause}"</span></div>
                        <div>📊 Confidence: <span className="text-slate-300">{(data.confidence * 100).toFixed(0)}%</span></div>
                        <div>🕸️ Chain Steps: <span className="text-slate-300">{data.propagation_steps} hops</span></div>
                      </>
                    )}
                    {key === "resolver" && (
                      <>
                        <div>📖 Mitigation Steps: <span className="font-bold text-white">{data.steps} action items</span></div>
                        <div>⏱️ Estimated TTR: <span className="text-slate-300">{data.ttr} minutes</span></div>
                        <div>🎯 Confidence: <span className="text-slate-300">{(data.confidence * 100).toFixed(0)}%</span></div>
                      </>
                    )}
                    {key === "healer" && (
                      <>
                        <div>🩹 Healing Steps Attempted: <span className="font-bold text-white">{data.actions_taken}</span></div>
                        <div>📈 Metric Improvement: <span className="text-emerald-400">+{data.improvement}%</span></div>
                        <div>🛡️ Operation Mode: <span className="text-amber-400">{data.dry_run ? "Dry-Run" : "Production"}</span></div>
                      </>
                    )}
                    {key === "notifier" && (
                      <>
                        <div>💬 Dispatch: <span className="font-bold text-white">Slack Hook Sent ({data.slack_sent ? "Yes" : "No"})</span></div>
                        <div>📌 Annotation: <span className="text-slate-300">Grafana marked</span></div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
