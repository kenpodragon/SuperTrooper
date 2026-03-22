/**
 * batchApply.ts — Batch apply orchestration in the background service worker.
 * Opens job URLs one at a time, waits for submission signal or skip, then advances.
 *
 * Enhanced with: queue management (pause, resume, skip, priority reorder),
 * progress tracking, and rate limiting.
 */

const STORAGE_KEY = "batch_state";

type JobStatus = "pending" | "in_progress" | "completed" | "skipped" | "failed";

interface BatchJob {
  id: number;
  url: string;
  status: JobStatus;
  priority: number; // lower = higher priority
  startedAt?: number;
  completedAt?: number;
  errorMessage?: string;
}

interface BatchProgress {
  total: number;
  completed: number;
  failed: number;
  skipped: number;
  pending: number;
  inProgress: number;
  startedAt: number;
  elapsedMs: number;
}

interface BatchState {
  jobs: BatchJob[];
  currentIndex: number;
  running: boolean;
  paused: boolean;
  activeTabId?: number;
  delayMs: number; // rate limiting delay between applications
  progress: BatchProgress;
  startedAt: number;
}

// --- Storage helpers ---

async function getState(): Promise<BatchState | null> {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return stored[STORAGE_KEY] || null;
}

async function setState(state: BatchState): Promise<void> {
  // Recalculate progress before saving
  state.progress = computeProgress(state);
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
}

async function clearState(): Promise<void> {
  await chrome.storage.local.remove(STORAGE_KEY);
}

function computeProgress(state: BatchState): BatchProgress {
  const jobs = state.jobs;
  const completed = jobs.filter((j) => j.status === "completed").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const skipped = jobs.filter((j) => j.status === "skipped").length;
  const inProgress = jobs.filter((j) => j.status === "in_progress").length;
  const pending = jobs.filter((j) => j.status === "pending").length;

  return {
    total: jobs.length,
    completed,
    failed,
    skipped,
    pending,
    inProgress,
    startedAt: state.startedAt,
    elapsedMs: Date.now() - state.startedAt,
  };
}

// --- Notify popup ---

function notifyPopup(jobId: number, status: JobStatus, index: number): void {
  chrome.runtime
    .sendMessage({
      type: "BATCH_JOB_STATUS",
      data: { jobId, status, index },
    })
    .catch(() => {}); // Popup may be closed
}

function notifyBatchComplete(progress: BatchProgress): void {
  chrome.runtime
    .sendMessage({ type: "BATCH_COMPLETE", data: progress })
    .catch(() => {});
}

function notifyProgressUpdate(progress: BatchProgress): void {
  chrome.runtime
    .sendMessage({ type: "BATCH_PROGRESS", data: progress })
    .catch(() => {});
}

// --- Rate limiting helper ---

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// --- Core batch logic ---

async function openNextJob(state: BatchState): Promise<void> {
  const { jobs, currentIndex, delayMs } = state;

  // Find next pending job by priority, then by position
  const pendingJobs = jobs
    .map((j, idx) => ({ ...j, originalIndex: idx }))
    .filter((j) => j.status === "pending")
    .sort((a, b) => a.priority - b.priority || a.originalIndex - b.originalIndex);

  if (pendingJobs.length === 0) {
    // All done
    const progress = computeProgress(state);
    await clearState();
    notifyBatchComplete(progress);
    return;
  }

  // Rate limiting: wait between applications
  if (delayMs > 0 && currentIndex > 0) {
    await delay(delayMs);
  }

  // Re-check if paused during delay
  const freshState = await getState();
  if (freshState?.paused) return;

  const nextJob = pendingJobs[0];
  const nextIdx = nextJob.originalIndex;
  const job = jobs[nextIdx];
  jobs[nextIdx].status = "in_progress";
  jobs[nextIdx].startedAt = Date.now();

  // Open the job URL in a new tab
  let tab: chrome.tabs.Tab;
  try {
    tab = await chrome.tabs.create({ url: job.url, active: true });
  } catch (e) {
    jobs[nextIdx].status = "failed";
    jobs[nextIdx].errorMessage =
      e instanceof Error ? e.message : "Failed to open tab";
    jobs[nextIdx].completedAt = Date.now();
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
  notifyProgressUpdate(computeProgress(updated));
}

// --- Public API ---

/**
 * Start a batch apply session with the given job IDs.
 * Fetches job URLs from backend and opens them one at a time.
 *
 * @param jobIds - IDs of saved jobs to apply to
 * @param options - Optional settings: delayMs (rate limit), priorities
 */
export async function startBatch(
  jobIds: number[],
  options?: { delayMs?: number; priorities?: Record<number, number> }
): Promise<void> {
  const delayMs = options?.delayMs ?? 3000; // default 3s between applications
  const priorities = options?.priorities ?? {};

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
        .map((j: { id: number; url: string }) => ({
          id: j.id,
          url: j.url,
          status: "pending" as JobStatus,
          priority: priorities[j.id] ?? 10, // default priority 10
        }));
    }
  } catch {
    return;
  }

  if (jobsWithUrls.length === 0) return;

  // Sort by priority initially
  jobsWithUrls.sort((a, b) => a.priority - b.priority);

  const now = Date.now();
  const state: BatchState = {
    jobs: jobsWithUrls,
    currentIndex: 0,
    running: true,
    paused: false,
    delayMs,
    startedAt: now,
    progress: {
      total: jobsWithUrls.length,
      completed: 0,
      failed: 0,
      skipped: 0,
      pending: jobsWithUrls.length,
      inProgress: 0,
      startedAt: now,
      elapsedMs: 0,
    },
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
    jobs[currentIndex].completedAt = Date.now();
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
  notifyProgressUpdate(computeProgress(updated));

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
    jobs[currentIndex].completedAt = Date.now();
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
  notifyProgressUpdate(computeProgress(updated));
  await openNextJob(updated);
}

/**
 * Pause the batch (won't open next job after current completes).
 */
export async function pauseBatch(): Promise<void> {
  const state = await getState();
  if (!state) return;
  await setState({ ...state, paused: true });
  notifyProgressUpdate(computeProgress({ ...state, paused: true }));
}

/**
 * Resume a paused batch.
 */
export async function resumeBatch(): Promise<void> {
  const state = await getState();
  if (!state) return;
  const updated = { ...state, paused: false };
  await setState(updated);

  // If no job is currently in progress, open the next one
  const hasInProgress = state.jobs.some((j) => j.status === "in_progress");
  if (!hasInProgress) {
    await openNextJob(updated);
  }
}

/**
 * Reorder job priority. Lower number = processed first.
 */
export async function reorderJob(
  jobId: number,
  newPriority: number
): Promise<void> {
  const state = await getState();
  if (!state) return;

  const job = state.jobs.find((j) => j.id === jobId);
  if (job && job.status === "pending") {
    job.priority = newPriority;
  }

  await setState(state);
}

/**
 * Update rate limiting delay.
 */
export async function setDelay(delayMs: number): Promise<void> {
  const state = await getState();
  if (!state) return;
  await setState({ ...state, delayMs: Math.max(0, delayMs) });
}

/**
 * Get current batch state summary for the popup.
 */
export async function getBatchState(): Promise<BatchState | null> {
  const state = await getState();
  if (state) {
    state.progress = computeProgress(state);
  }
  return state;
}

/**
 * Cancel the entire batch. Marks remaining pending jobs as skipped.
 */
export async function cancelBatch(): Promise<void> {
  const state = await getState();
  if (!state) return;

  for (const job of state.jobs) {
    if (job.status === "pending" || job.status === "in_progress") {
      job.status = "skipped";
      job.completedAt = Date.now();
    }
  }

  if (state.activeTabId) {
    chrome.tabs.remove(state.activeTabId).catch(() => {});
  }

  const progress = computeProgress(state);
  await clearState();
  notifyBatchComplete(progress);
}
