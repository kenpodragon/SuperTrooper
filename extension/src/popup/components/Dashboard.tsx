import { usePipeline, useHealth } from "../hooks/useBackend";

export default function Dashboard() {
  const { health } = useHealth();
  const { pipeline, loading } = usePipeline();

  if (!health?.connected) {
    return (
      <div className="p-4 text-center">
        <div className="text-st-red text-3xl mb-3">⚡</div>
        <h2 className="text-lg font-bold text-st-text mb-2">Backend Offline</h2>
        <p className="text-sm text-st-muted mb-4">
          SuperTroopers backend is not running. Start Docker:
        </p>
        <code className="block bg-st-surface text-st-green text-xs p-3 rounded font-mono">
          cd code && docker compose up -d
        </code>
      </div>
    );
  }

  if (loading || !pipeline) {
    return (
      <div className="p-4 text-center text-st-muted">
        <div className="animate-pulse">Loading pipeline...</div>
      </div>
    );
  }

  const stats = [
    { label: "Saved", value: pipeline.saved || 0, color: "text-st-muted" },
    { label: "Applied", value: pipeline.applied || 0, color: "text-blue-400" },
    { label: "Interviewing", value: pipeline.interviewing || 0, color: "text-yellow-400" },
    { label: "Offered", value: pipeline.offered || 0, color: "text-st-green" },
  ];

  return (
    <div className="p-4">
      <h2 className="text-sm font-bold text-st-green mb-3 tracking-wider uppercase">
        &gt; Pipeline
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-st-surface rounded p-3 border border-st-border">
            <div className={`text-2xl font-bold font-mono ${s.color}`}>{s.value}</div>
            <div className="text-xs text-st-muted mt-1">{s.label}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 bg-st-surface rounded p-3 border border-st-border">
        <div className="text-2xl font-bold font-mono text-st-text">
          {(pipeline.saved || 0) + (pipeline.applied || 0) + (pipeline.interviewing || 0) + (pipeline.offered || 0)}
        </div>
        <div className="text-xs text-st-muted mt-1">Total Active</div>
      </div>
    </div>
  );
}
