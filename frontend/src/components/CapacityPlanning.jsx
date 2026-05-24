import React from "react";

export default function CapacityPlanning({ capacityData }) {
  const forecasts = capacityData?.forecasts || [];

  return (
    <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
      <div className="flex items-center justify-between border-b border-slate-850 pb-4">
        <div>
          <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <span>📈</span> Predictive Capacity Planning
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Analyzing 24h metrics history to forecast service threshold breaches (48h window).
          </p>
        </div>
        <span className="text-xs text-slate-500 font-mono">
          Last evaluation: {capacityData?.generated_at ? new Date(capacityData.generated_at).toLocaleTimeString() : "Pending"}
        </span>
      </div>

      {forecasts.length === 0 ? (
        <div className="text-center p-8 bg-slate-950/20 border border-dashed border-slate-850 rounded-xl text-slate-500">
          🟢 All services operating with safe capacity margins. No predicted breaches within the next 48 hours.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {forecasts.map((forecast, idx) => {
            const ratio = (forecast.current_value / forecast.threshold) * 100;
            const isNearing = ratio >= 75;
            
            let trendEmoji = "➡️";
            let trendColor = "text-slate-400";
            if (forecast.trend === "increasing") {
              trendEmoji = "↗️";
              trendColor = "text-rose-400 font-semibold";
            } else if (forecast.trend === "decreasing") {
              trendEmoji = "↘️";
              trendColor = "text-emerald-400";
            }

            return (
              <div key={idx} className="bg-slate-950/40 rounded-xl p-5 border border-slate-850 hover:border-slate-800 transition-all duration-300">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{forecast.service}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 font-mono">
                        {forecast.metric}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Trend: <span className={trendColor}>{forecast.trend} {trendEmoji}</span> · Confidence: {(forecast.confidence * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-sm font-mono font-bold text-rose-400">
                      ⚡ Breach in {forecast.predicted_breach_hours.toFixed(1)} hrs
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">Estimated time to critical threshold</div>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="space-y-1.5 mb-4">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-slate-400">Current: {forecast.current_value.toFixed(1)}</span>
                    <span className="text-slate-500">Threshold: {forecast.threshold.toFixed(1)}</span>
                  </div>
                  <div className="h-2 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-850">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${isNearing ? "bg-rose-500" : "bg-purple-500"}`}
                      style={{ width: `${Math.min(100, ratio)}%` }}
                    />
                  </div>
                </div>

                {/* Recommendation Box */}
                <div className="bg-purple-950/10 border border-purple-900/30 p-3.5 rounded-lg flex items-start gap-3">
                  <span className="text-base text-purple-400 mt-0.5">💡</span>
                  <div>
                    <div className="text-xs font-semibold text-purple-300">SRE AI Upgrade Recommendation</div>
                    <div className="text-xs text-slate-300 mt-0.5 leading-relaxed">
                      {forecast.recommendation}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
