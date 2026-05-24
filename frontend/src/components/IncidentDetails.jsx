import React from "react";

export default function IncidentDetails({ pipelineData }) {
  if (!pipelineData) {
    return (
      <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-8 text-center text-slate-500">
        📭 Select an active incident or trigger a mock incident below to inspect detailed resolution data.
      </div>
    );
  }

  const { rca_result, runbook, healing_result, raw_metrics } = pipelineData;

  return (
    <div className="space-y-6">
      {/* Root Cause Card */}
      {rca_result && (
        <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-850 pb-4 mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <span className="text-xl">🔬</span> Root Cause Analysis (RCA)
            </h2>
            <span className="text-xs px-2.5 py-1 rounded bg-purple-500/20 text-purple-300 font-mono border border-purple-500/30">
              Confidence: {(rca_result.confidence * 100).toFixed(0)}%
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className="bg-slate-950/40 p-4 rounded-lg border border-slate-850">
              <div className="text-xs text-slate-400 font-medium mb-1">Trigger Event</div>
              <div className="text-sm font-semibold text-white">
                {rca_result.trigger.description || "N/A"}
              </div>
              <div className="text-xs font-mono text-slate-500 mt-2">
                Evidence: {rca_result.trigger.evidence}
              </div>
            </div>

            <div className="bg-slate-950/40 p-4 rounded-lg border border-slate-850">
              <div className="text-xs text-slate-400 font-medium mb-1">Root Cause Category</div>
              <div className="text-sm font-semibold text-white capitalize">
                {rca_result.root_cause_category.replace("_", " ")}
              </div>
              {rca_result.similar_incident_ref && (
                <div className="text-xs text-purple-400 mt-2 font-mono">
                  Ref: {rca_result.similar_incident_ref}
                </div>
              )}
            </div>

            <div className="bg-slate-950/40 p-4 rounded-lg border border-slate-850">
              <div className="text-xs text-slate-400 font-medium mb-1">Impact & Blast Radius</div>
              <div className="text-sm font-semibold text-rose-400 uppercase">
                {rca_result.impact.blast_radius}
              </div>
              <div className="text-xs text-slate-500 mt-2 font-mono">
                {rca_result.impact.estimated_users_affected} users · {rca_result.impact.affected_services.length} services
              </div>
            </div>
          </div>

          {/* Causal Propagation Timeline */}
          {rca_result.propagation && rca_result.propagation.length > 0 && (
            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Causal Propagation Chain</h3>
              <div className="space-y-3">
                {rca_result.propagation.map((prop, idx) => (
                  <div key={idx} className="flex items-center gap-4 bg-slate-950/20 p-3 rounded-lg border border-slate-850/60">
                    <div className="w-6 h-6 rounded-full bg-slate-900 border border-slate-800 text-xs flex items-center justify-center text-slate-400 font-mono">
                      {prop.step}
                    </div>
                    <div className="flex-1">
                      <div className="text-sm text-white font-medium">{prop.event}</div>
                      <div className="text-xs text-slate-500">Service: <span className="text-slate-400 font-mono">{prop.service}</span></div>
                    </div>
                    {prop.lag_seconds > 0 && (
                      <div className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/25">
                        +{prop.lag_seconds}s lag
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Generated Runbook & Auto Healing */}
      {runbook && (
        <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-850 pb-4 mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <span className="text-xl">🛠️</span> Remediation Runbook
            </h2>
            <div className="text-xs text-slate-400 font-mono flex items-center gap-4">
              <span>⏱️ Est. TTR: <strong className="text-white">{runbook.estimated_resolution_minutes}m</strong></span>
              <span>🎯 Conf: <strong className="text-white">{(runbook.confidence * 100).toFixed(0)}%</strong></span>
            </div>
          </div>

          <div className="space-y-4">
            {runbook.steps.map((step) => {
              // Check if healer ran this step
              const healerAction = healing_result?.actions_log?.find(
                a => a.action.toLowerCase() === step.action.toLowerCase() ||
                     step.action.toLowerCase().includes(a.action.toLowerCase())
              );

              return (
                <div key={step.step} className="bg-slate-950/30 rounded-lg p-4 border border-slate-850 flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2.5">
                      <span className="w-5 h-5 rounded-full bg-slate-900 border border-slate-800 text-xs text-slate-300 font-mono flex items-center justify-center">
                        {step.step}
                      </span>
                      <h4 className="text-sm font-semibold text-white">{step.action}</h4>
                      {step.auto_executable && (
                        <span className="text-[10px] bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 px-2 py-0.5 rounded uppercase font-semibold font-mono tracking-wider">
                          Auto-Remedy
                        </span>
                      )}
                    </div>

                    {step.command && (
                      <div className="relative mt-2">
                        <pre className="text-xs font-mono bg-black/60 p-3 rounded border border-slate-900 text-purple-300/90 overflow-x-auto whitespace-pre">
                          {step.command}
                        </pre>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col items-end gap-1.5 justify-center md:min-w-[120px]">
                    <div className="text-xs text-slate-500 font-mono">{step.duration_minutes}m duration</div>
                    {healerAction && (
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                        healerAction.status === "success" 
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : healerAction.status === "skipped"
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                          : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                      }`}>
                        Auto-healed: {healerAction.status}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Healing Results block */}
          {healing_result && healing_result.actions_attempted > 0 && (
            <div className="mt-6 pt-5 border-t border-slate-850 bg-slate-950/10 rounded-lg p-4 border border-slate-850/60">
              <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-1.5">
                <span>🩹</span> Healing Outcome Log
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div className="flex justify-between p-3 bg-slate-900/30 rounded border border-slate-850">
                  <span className="text-xs text-slate-400">Remedial Actions:</span>
                  <span className="text-xs font-bold text-white">{healing_result.actions_succeeded} / {healing_result.actions_attempted} OK</span>
                </div>
                <div className="flex justify-between p-3 bg-slate-900/30 rounded border border-slate-850">
                  <span className="text-xs text-slate-400">Post-Heal Improvement:</span>
                  <span className="text-xs font-bold text-emerald-400">+{healing_result.improvement_percent}% recovery</span>
                </div>
              </div>

              <div className="space-y-2">
                {healing_result.actions_log.map((action, idx) => (
                  <div key={idx} className="text-xs font-mono bg-black/30 p-2.5 rounded border border-slate-900/80 text-slate-400 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-slate-200">🛠️ {action.action} (Target: {action.target})</span>
                      <span className={action.status === "success" ? "text-emerald-400" : "text-amber-400"}>{action.status.toUpperCase()}</span>
                    </div>
                    <div className="text-purple-300/80">{action.output}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
