/**
 * BatchQueue.tsx — Batch apply queue UI for queued saved jobs.
 * Popup component (React functional component).
 */

import { useState, useEffect, useCallback } from "react";
import type { SavedJob } from "@shared/types";

type JobQueueStatus = "pending" | "in_progress" | "completed" | "skipped" | "failed";

interface QueueItem {
  job: SavedJob;
  status: JobQueueStatus;
}

const STATUS_COLORS: Record<JobQueueStatus, string> = {
  pending: "text-st-muted",
  in_progress: "text-yellow-400",
  completed: "text-st-green",
  skipped: "text-blue-400",
  failed: "text-red-400",
};

async function fetchQueuedJobs(): Promise<SavedJob[]> {
  try {
    const res = await fetch("http://localhost:8055/api/saved-jobs?status=queued", {
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : data.jobs || [];
  } catch {
    return [];
  }
}

export default function BatchQueue() {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [currentIdx, setCurrentIdx] = useState(-1);

  const load = useCallback(async () => {
    setLoading(true);
    const jobs = await fetchQueuedJobs();
    setQueue(jobs.map((job) => ({ job, status: "pending" })));
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Listen for batch progress messages from background
  useEffect(() => {
    const handler = (message: { type: string; data?: { jobId: number; status: JobQueueStatus; index: number } }) => {
      if (message.type === "BATCH_JOB_STATUS" && message.data) {
        const { jobId, status, index } = message.data;
        setQueue((prev) =>
          prev.map((item) =>
            item.job.id === jobId ? { ...item, status } : item
          )
        );
        setCurrentIdx(index);
      }
      if (message.type === "BATCH_COMPLETE") {
        setRunning(false);
        setPaused(false);
        setCurrentIdx(-1);
      }
    };
    chrome.runtime.onMessage.addListener(handler);
    return () => chrome.runtime.onMessage.removeListener(handler);
  }, []);

  const handleStart = () => {
    if (queue.length === 0) return;
    const pendingIds = queue
      .filter((i) => i.status === "pending")
      .map((i) => i.job.id);
    if (pendingIds.length === 0) return;

    setRunning(true);
    setPaused(false);

    chrome.runtime.sendMessage({
      type: "BATCH_START",
      data: { jobIds: pendingIds },
    }).catch(console.error);
  };

  const handlePause = () => {
    setPaused(true);
    chrome.runtime.sendMessage({ type: "BATCH_PAUSE" }).catch(console.error);
  };

  const handleResume = () => {
    setPaused(false);
    chrome.runtime.sendMessage({ type: "BATCH_RESUME" }).catch(console.error);
  };

  const handleSkipCurrent = () => {
    chrome.runtime.sendMessage({ type: "BATCH_SKIP" }).catch(console.error);
  };

  const handleRemove = (jobId: number) => {
    setQueue((prev) => prev.filter((i) => i.job.id !== jobId));
  };

  const handleMoveUp = (idx: number) => {
    if (idx === 0) return;
    setQueue((prev) => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  };

  const pendingCount = queue.filter((i) => i.status === "pending").length;
  const completedCount = queue.filter((i) => i.status === "completed").length;

  if (loading) {
    return <div className="p-4 text-center text-st-muted text-sm animate-pulse">Loading...</div>;
  }

  return (
    <div className="p-2 space-y-2">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-xs font-bold text-st-green tracking-wider uppercase">
          &gt; Batch Apply
        </h2>
        <div className="text-[10px] text-st-muted font-mono">
          {completedCount}/{queue.length} done
        </div>
      </div>

      {queue.length === 0 && (
        <div className="p-4 text-center text-st-muted text-xs">
          <p>No jobs queued.</p>
          <p className="mt-1">Mark saved jobs as "queued" to add them here.</p>
        </div>
      )}

      {/* Controls */}
      {queue.length > 0 && (
        <div className="flex gap-2 px-1">
          {!running && (
            <button
              onClick={handleStart}
              disabled={pendingCount === 0}
              className="flex-1 py-1.5 text-[11px] font-mono border border-st-green text-st-green rounded hover:bg-st-green hover:text-st-bg transition disabled:opacity-40"
            >
              Start Batch ({pendingCount})
            </button>
          )}
          {running && !paused && (
            <>
              <button
                onClick={handlePause}
                className="flex-1 py-1.5 text-[11px] font-mono border border-yellow-400 text-yellow-400 rounded hover:bg-yellow-400 hover:text-st-bg transition"
              >
                Pause
              </button>
              <button
                onClick={handleSkipCurrent}
                className="flex-1 py-1.5 text-[11px] font-mono border border-st-border text-st-muted rounded hover:border-st-green hover:text-st-green transition"
              >
                Skip
              </button>
            </>
          )}
          {running && paused && (
            <button
              onClick={handleResume}
              className="flex-1 py-1.5 text-[11px] font-mono border border-st-green text-st-green rounded hover:bg-st-green hover:text-st-bg transition"
            >
              Resume
            </button>
          )}
          <button
            onClick={load}
            className="py-1.5 px-2 text-[11px] font-mono border border-st-border text-st-muted rounded hover:border-st-green hover:text-st-green transition"
            title="Refresh queue"
          >
            R
          </button>
        </div>
      )}

      {/* Queue list */}
      <div className="space-y-1.5 max-h-[320px] overflow-y-auto">
        {queue.map((item, idx) => {
          const isCurrent = idx === currentIdx;
          const statusColor = STATUS_COLORS[item.status];

          return (
            <div
              key={item.job.id}
              className={`bg-st-surface rounded p-2.5 border transition ${
                isCurrent ? "border-yellow-400" : "border-st-border"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="text-st-text text-[11px] font-semibold truncate">
                    {item.job.company}
                  </div>
                  <div className="text-st-muted text-[10px] truncate">{item.job.title}</div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <span className={`text-[10px] font-mono ${statusColor}`}>
                    {isCurrent ? "NOW" : item.status.toUpperCase()}
                  </span>
                  {item.status === "pending" && !running && (
                    <>
                      <button
                        onClick={() => handleMoveUp(idx)}
                        disabled={idx === 0}
                        className="text-[10px] text-st-muted hover:text-st-green disabled:opacity-30"
                        title="Move up"
                      >
                        ^
                      </button>
                      <button
                        onClick={() => handleRemove(item.job.id)}
                        className="text-[10px] text-st-muted hover:text-red-400"
                        title="Remove"
                      >
                        x
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
