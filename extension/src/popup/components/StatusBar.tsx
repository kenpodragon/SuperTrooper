import { useState, useEffect } from "react";
import { useHealth } from "../hooks/useBackend";
import { sendToBackground, MSG } from "@shared/messages";

interface BatchProgress {
  total: number;
  completed: number;
  failed: number;
  skipped: number;
  pending: number;
  inProgress: number;
}

interface BatchStateSnapshot {
  running: boolean;
  paused: boolean;
  progress: BatchProgress;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function StatusBar() {
  const { health, loading, refresh } = useHealth();
  const connected = health?.connected ?? false;
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [batchState, setBatchState] = useState<BatchStateSnapshot | null>(null);

  // Track last successful sync
  useEffect(() => {
    if (connected && !loading) {
      setLastSync(new Date());
    }
  }, [connected, loading]);

  // Poll batch state every 2 seconds when running
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    async function fetchBatch() {
      try {
        const state = await sendToBackground<BatchStateSnapshot | null>(
          MSG.BATCH_GET_STATE
        );
        setBatchState(state);
      } catch {
        setBatchState(null);
      }
    }

    fetchBatch();
    interval = setInterval(fetchBatch, 2000);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, []);

  // Listen for batch progress updates
  useEffect(() => {
    function handleMessage(msg: { type: string; data?: BatchProgress }) {
      if (msg.type === "BATCH_PROGRESS" || msg.type === "BATCH_JOB_STATUS") {
        sendToBackground<BatchStateSnapshot | null>(MSG.BATCH_GET_STATE)
          .then(setBatchState)
          .catch(() => {});
      }
      if (msg.type === "BATCH_COMPLETE") {
        setBatchState(null);
      }
    }
    chrome.runtime.onMessage.addListener(handleMessage);
    return () => chrome.runtime.onMessage.removeListener(handleMessage);
  }, []);

  const progress = batchState?.progress;
  const hasQueue = batchState && progress && progress.total > 0;

  return (
    <div className="px-3 py-2 bg-st-surface border-b border-st-border space-y-1.5">
      {/* Row 1: Connection status + last sync */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              loading
                ? "bg-yellow-400 animate-pulse"
                : connected
                  ? "bg-st-green"
                  : "bg-st-red"
            }`}
          />
          <span className="text-xs text-st-muted">
            {loading
              ? "Connecting..."
              : connected
                ? "Backend Online"
                : "Backend Offline"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {lastSync && (
            <span className="text-[10px] text-st-muted opacity-60">
              Synced {formatTime(lastSync)}
            </span>
          )}
          <button
            onClick={refresh}
            className="text-xs text-st-muted hover:text-st-green transition-colors"
            title="Refresh connection"
          >
            ↻
          </button>
        </div>
      </div>

      {/* Row 2: Batch queue status (only shown when active) */}
      {hasQueue && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div
              className={`w-2 h-2 rounded-full ${
                batchState.paused
                  ? "bg-yellow-400"
                  : "bg-blue-400 animate-pulse"
              }`}
            />
            <span className="text-[10px] text-st-muted">
              {batchState.paused ? "Queue paused" : "Applying..."}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[10px]">
            <span className="text-green-400">
              {progress.completed} done
            </span>
            {progress.failed > 0 && (
              <span className="text-red-400">{progress.failed} fail</span>
            )}
            {progress.skipped > 0 && (
              <span className="text-gray-400">{progress.skipped} skip</span>
            )}
            <span className="text-st-muted">
              {progress.pending} left
            </span>
          </div>
        </div>
      )}

      {/* Row 3: Progress bar (only when batch active) */}
      {hasQueue && (
        <div className="w-full bg-gray-700 rounded-full h-1">
          <div
            className={`h-1 rounded-full transition-all duration-300 ${
              batchState.paused ? "bg-yellow-400" : "bg-st-green"
            }`}
            style={{
              width: `${Math.round(((progress.completed + progress.failed + progress.skipped) / progress.total) * 100)}%`,
            }}
          />
        </div>
      )}
    </div>
  );
}
