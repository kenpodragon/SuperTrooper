import { useState, useEffect } from "react";
import { usePipeline, useHealth } from "../hooks/useBackend";

export default function Dashboard() {
  const { health } = useHealth();
  const { pipeline, loading } = usePipeline();

  const [unreadCount, setUnreadCount] = useState(0);
  useEffect(() => {
    fetch("http://localhost:8055/api/notifications?limit=50")
      .then((r) => r.json())
      .then((data) => {
        const list = data.notifications || data || [];
        setUnreadCount(list.filter((n: { read: boolean }) => !n.read).length);
      })
      .catch(() => {});
  }, []);

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

  const FRONTEND = "http://localhost:5175";

  const stats = [
    { label: "Saved", value: pipeline.saved || 0, color: "text-st-muted", path: "/saved-jobs" },
    { label: "Applied", value: pipeline.applied || 0, color: "text-blue-400", path: "/applications" },
    { label: "Interviewing", value: pipeline.interviewing || 0, color: "text-yellow-400", path: "/interviews" },
    { label: "Offered", value: pipeline.offered || 0, color: "text-st-green", path: "/applications?status=offered" },
  ];

  return (
    <div className="p-4">
      <h2 className="text-sm font-bold text-st-green mb-3 tracking-wider uppercase">
        &gt; Pipeline
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {stats.map((s) => (
          <button
            key={s.label}
            onClick={() => chrome.tabs.create({ url: `${FRONTEND}${s.path}` })}
            className="bg-st-surface rounded p-3 border border-st-border text-left hover:border-st-green transition-colors cursor-pointer"
          >
            <div className={`text-2xl font-bold font-mono ${s.color}`}>{s.value}</div>
            <div className="text-xs text-st-muted mt-1">{s.label}</div>
          </button>
        ))}
      </div>
      <button
        onClick={() => chrome.tabs.create({ url: `${FRONTEND}/applications` })}
        className="mt-3 w-full bg-st-surface rounded p-3 border border-st-border text-left hover:border-st-green transition-colors cursor-pointer"
      >
        <div className="text-2xl font-bold font-mono text-st-text">
          {(pipeline.saved || 0) + (pipeline.applied || 0) + (pipeline.interviewing || 0) + (pipeline.offered || 0)}
        </div>
        <div className="text-xs text-st-muted mt-1">Total Active</div>
      </button>
      {unreadCount > 0 && (
        <button
          onClick={() => chrome.tabs.create({ url: `${FRONTEND}/notifications` })}
          className="mt-3 w-full bg-st-surface rounded p-3 border border-st-border text-left hover:border-st-green transition-colors cursor-pointer flex items-center gap-2"
        >
          <span className="bg-st-green text-st-bg text-xs font-bold font-mono rounded-full w-5 h-5 flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
          <span className="text-xs text-st-text">new notifications</span>
        </button>
      )}
    </div>
  );
}
