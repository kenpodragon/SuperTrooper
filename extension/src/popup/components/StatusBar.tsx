import { useHealth } from "../hooks/useBackend";

export default function StatusBar() {
  const { health, loading, refresh } = useHealth();
  const connected = health?.connected ?? false;

  return (
    <div className="flex items-center justify-between px-3 py-2 bg-st-surface border-b border-st-border">
      <div className="flex items-center gap-2">
        <div
          className={`w-2.5 h-2.5 rounded-full ${
            loading ? "bg-yellow-400 animate-pulse" : connected ? "bg-st-green" : "bg-st-red"
          }`}
        />
        <span className="text-xs text-st-muted">
          {loading ? "Connecting..." : connected ? "Backend Online" : "Backend Offline"}
        </span>
      </div>
      <button
        onClick={refresh}
        className="text-xs text-st-muted hover:text-st-green transition-colors"
        title="Refresh connection"
      >
        ↻
      </button>
    </div>
  );
}
