import { MSG, type Message } from "@shared/messages";
import type { SaveJobPayload, GapAnalysisPayload, CheckJobUrlPayload } from "@shared/messages";
import { checkHealth, getPipelineSummary, saveJob, checkJobUrl, getSavedJobs, runGapAnalysis, persistGapAnalysis } from "./api";
import { cacheGet } from "./cache";
import { getCachedGap, setCachedGap } from "./gapCache";

const KNOWN_TYPES = new Set(Object.values(MSG));

export function handleMessage(
  message: Message,
  _sender: chrome.runtime.MessageSender,
  sendResponse: (response: unknown) => void
): boolean {
  // Ignore messages from other extensions or unknown sources
  if (!message?.type || !KNOWN_TYPES.has(message.type)) return false;
  handleAsync(message).then(sendResponse);
  return true;
}

async function handleAsync(message: Message): Promise<unknown> {
  switch (message.type) {
    case MSG.HEALTH_CHECK: {
      const cached = await cacheGet("health");
      if (cached) return cached;
      const health = await checkHealth();
      return { ...health, timestamp: Date.now() };
    }

    case MSG.GET_PIPELINE: {
      const cached = await cacheGet("pipeline");
      if (cached) return cached;
      return await getPipelineSummary();
    }

    case MSG.GET_SETTINGS: {
      const result = await chrome.storage.local.get("settings");
      return result.settings || {};
    }

    case MSG.SAVE_SETTINGS: {
      await chrome.storage.local.set({ settings: message.data });
      return { ok: true };
    }

    case MSG.PAGE_CONTEXT: {
      console.log("[SuperTroopers] Page context:", message.data);
      return { ok: true };
    }

    case MSG.SAVE_JOB: {
      const { job } = message.data as SaveJobPayload;
      // Check duplicate first
      const dupeCheck = await checkJobUrl(job.url);
      if (dupeCheck.exists) {
        return { saved_job: dupeCheck.saved_job, already_existed: true };
      }
      const savedJob = await saveJob(job);
      // If we have a cached gap analysis, persist it linked to the new saved_job
      const cachedGap = await getCachedGap(job.url);
      if (cachedGap) {
        try { await persistGapAnalysis(savedJob.id, cachedGap); } catch { /* non-critical */ }
      }
      return { saved_job: savedJob, already_existed: false };
    }

    case MSG.RUN_GAP_ANALYSIS: {
      const { jd_text, job_url, force_refresh, saved_job_id } = message.data as GapAnalysisPayload;
      // Check cache unless force refresh
      if (!force_refresh) {
        const cached = await getCachedGap(job_url);
        if (cached) {
          return { result: cached, from_cache: true };
        }
      }
      // Run analysis via backend
      const result = await runGapAnalysis(jd_text);
      result.job_url = job_url;
      // Cache it
      await setCachedGap(job_url, result);
      // If linked to a saved job, persist to backend
      if (saved_job_id) {
        try { await persistGapAnalysis(saved_job_id, result); } catch { /* non-critical */ }
      }
      return { result, from_cache: false };
    }

    case MSG.CHECK_JOB_URL: {
      const { url } = message.data as CheckJobUrlPayload;
      return await checkJobUrl(url);
    }

    case MSG.GET_SAVED_JOBS: {
      const jobs = await getSavedJobs();
      return { jobs };
    }

    default:
      return { error: `Unknown message type: ${message.type}` };
  }
}
