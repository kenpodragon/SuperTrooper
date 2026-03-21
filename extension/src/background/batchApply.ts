/**
 * batchApply.ts — Batch apply orchestration in the background service worker.
 * Opens job URLs one at a time, waits for submission signal or skip, then advances.
 */

const STORAGE_KEY = "batch_state";

type JobStatus = "pending" | "in_progress" | "completed" | "skipped" | "failed";

interface BatchJob {
  id: number;
  url: string;
  status: JobStatus;
}

interface BatchState {
  jobs: BatchJob[];
  currentIndex: number;
  running: boolean;
  paused: boolean;
  activeTabId?: number;
}

// --- Storage helpers ---

async function getState(): Promise<BatchState | null> {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return stored[STORAGE_KEY] || null;
}

async function setState(state: BatchState): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
}

async function clearState(): Promise<void> {
  await chrome.storage.local.remove(STORAGE_KEY);
}

// --- Notify popup ---

function notifyPopup(jobId: number, status: JobStatus, index: number): void {
  chrome.runtime.sendMessage({
    type: "BATCH_JOB_STATUS",
    data: { jobId, status, index },
  }).catch(() => {}); // Popup may be closed
}

function notifyBatchComplete(): void {
  chrome.runtime.sendMessage({ type: "BATCH_COMPLETE" }).catch(() => {});
}

// --- Core batch logic ---

async function openNextJob(state: BatchState): Promise<void> {
  const { jobs, currentIndex } = state;

  // Find next pending job at or after currentIndex
  let nextIdx = currentIndex;
  while (nextIdx < jobs.length && jobs[nextIdx].status !== "pending") {
    nextIdx++;
  }

  if (nextIdx >= jobs.length) {
    // All done
    await clearState();
    notifyBatchComplete();
    return;
  }

  const job = jobs[nextIdx];
  jobs[nextIdx].status = "in_progress";

  // Open the job URL in a new tab
  let tab: chrome.tabs.Tab;
  try {
    tab = await chrome.tabs.create({ url: job.url, active: true });
  } catch (e) {
    jobs[nextIdx].status = "failed";
    notifyPopup(job.id, "failed", nextIdx);
    const updated: BatchState = { ...state, jobs, currentIndex: nextIdx + 1 };
    await setState(updated);
    await openNextJob(updated);
    return;
  }

  notifyPopup(job.id, "in_progress", nextIdx);

  const updated: BatchState = {
    ...state,
    jobs,
    currentIndex: nextIdx,
    activeTabId: tab.id,
  };
  await setState(updated);
}

// --- Public API ---

/**
 * Start a batch apply session with the given job IDs.
 * Fetches job URLs from backend and opens them one at a time.
 */
export async function startBatch(jobIds: number[]): Promise<void> {
  // Fetch job URLs from backend
  let jobsWithUrls: BatchJob[] = [];
  try {
    const res = await fetch("http://localhost:8055/api/saved-jobs", {
      headers: { "Content-Type": "application/json" },
    });
    if (res.ok) {
      const all = await res.json();
      const list = Array.isArray(all) ? all : all.jobs || [];
      jobsWithUrls = list
        .filter((j: { id: number; url: string }) => jobIds.includes(j.id))
        .map((j: { id: number; url: string }) => ({ id: j.id, url: j.url, status: "pending" as JobStatus }));
    }
  } catch {
    return;
  }

  if (jobsWithUrls.length === 0) return;

  const state: BatchState = {
    jobs: jobsWithUrls,
    currentIndex: 0,
    running: true,
    paused: false,
  };

  await setState(state);
  await openNextJob(state);
}

/**
 * Mark the current in-progress job as completed (called when submission detected).
 */
export async function markCurrentCompleted(): Promise<void> {
  const state = await getState();
  if (!state || !state.running) return;

  const { jobs, currentIndex } = state;
  if (jobs[currentIndex]?.status === "in_progress") {
    jobs[currentIndex].status = "completed";
    notifyPopup(jobs[currentIndex].id, "completed", currentIndex);
  }

  // Close the active tab
  if (state.activeTabId) {
    chrome.tabs.remove(state.activeTabId).catch(() => {});
  }

  const updated: BatchState = {
    ...state,
    jobs,
    currentIndex: currentIndex + 1,
    activeTabId: undefined,
  };

  await setState(updated);

  if (!state.paused) {
    await openNextJob(updated);
  }
}

/**
 * Skip the current job and move to the next.
 */
export async function skipCurrentJob(): Promise<void> {
  const state = await getState();
  if (!state || !state.running) return;

  const { jobs, currentIndex } = state;
  if (jobs[currentIndex]) {
    jobs[currentIndex].status = "skipped";
    notifyPopup(jobs[currentIndex].id, "skipped", currentIndex);
  }

  if (state.activeTabId) {
    chrome.tabs.remove(state.activeTabId).catch(() => {});
  }

  const updated: BatchState = {
    ...state,
    jobs,
    currentIndex: currentIndex + 1,
    activeTabId: undefined,
  };

  await setState(updated);
  await openNextJob(updated);
}

/**
 * Pause the batch (won't open next job after current completes).
 */
export async function pauseBatch(): Promise<void> {
  const state = await getState();
  if (!state) return;
  await setState({ ...state, paused: true });
}

/**
 * Resume a paused batch.
 */
export async function resumeBatch(): Promise<void> {
  const state = await getState();
  if (!state) return;
  const updated = { ...state, paused: false };
  await setState(updated);
  await openNextJob(updated);
}

/**
 * Get current batch state summary for the popup.
 */
export async function getBatchState(): Promise<BatchState | null> {
  return getState();
}
