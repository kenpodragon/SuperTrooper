import { detectPage, extractJobData } from "./detector";
import { injectSaveButton } from "./saveButton";
import { injectScoreOverlay, type ScoreOverlayHandle } from "./scoreOverlay";
import { MSG, sendToBackground } from "@shared/messages";
import type { JobExtraction, GapAnalysisResult } from "@shared/types";
import type { GapAnalysisResponse } from "@shared/messages";
import siteConfig from "@config/siteConfig.json";

let currentOverlay: ScoreOverlayHandle | null = null;
let lastProcessedUrl: string | null = null;

export async function processJobPage(): Promise<void> {
  const context = detectPage();
  console.log("[SuperTroopers] processJobPage called, context:", context.type, context.board);
  if (context.type !== "job_listing" || !context.board) return;

  // Avoid re-processing same URL (SPA nav can re-trigger)
  if (lastProcessedUrl === window.location.href) return;
  lastProcessedUrl = window.location.href;

  // Clean up previous overlay
  currentOverlay?.remove();
  currentOverlay = null;

  // Also remove any old save button
  document.getElementById("st-save-btn")?.remove();

  // Extract job data from DOM — retry with delay for SPA content loading
  const rawData = await waitForJobData(context.board);
  if (!rawData || !rawData.title) {
    console.warn("[SuperTroopers] Could not extract job data after retries");
    return;
  }

  // Map to JobExtraction type
  const job: JobExtraction = {
    title: rawData.title || "",
    company: rawData.company || "",
    location: rawData.location || null,
    salary: rawData.salary || null,
    description: rawData.description || "",
    url: rawData.url || window.location.href,
    source: rawData.source || context.board,
  };

  console.log(`[SuperTroopers] Job detected: ${job.title} at ${job.company}`);

  // Find injection anchor from siteConfig
  const anchor = findInjectionAnchor(context.board);
  if (anchor) {
    injectSaveButton(anchor, job);
  }

  // Run gap analysis if we have a description
  if (job.description && job.description.length > 50) {
    try {
      const resp = await sendToBackground<GapAnalysisResponse>(MSG.RUN_GAP_ANALYSIS, {
        jd_text: job.description,
        job_url: job.url,
      });
      if (resp?.result) {
        currentOverlay = injectScoreOverlay(resp.result);
        // Wire refresh handler
        currentOverlay.onRefresh(async () => {
          try {
            const refreshResp = await sendToBackground<GapAnalysisResponse>(MSG.RUN_GAP_ANALYSIS, {
              jd_text: job.description,
              job_url: job.url,
              force_refresh: true,
            });
            if (refreshResp?.result && currentOverlay) {
              currentOverlay.update(refreshResp.result);
            }
          } catch (e) {
            console.warn("[SuperTroopers] Refresh failed:", e);
          }
        });
      }
    } catch (e) {
      // Backend offline — no score overlay, button still works when online
      console.warn("[SuperTroopers] Gap analysis failed:", e);
    }
  }
}

async function waitForJobData(board: string, maxRetries = 8, delayMs = 500): Promise<Record<string, string> | null> {
  for (let i = 0; i < maxRetries; i++) {
    const data = extractJobData(board);
    if (data && data.title) {
      console.log(`[SuperTroopers] Job data extracted on attempt ${i + 1}`);
      return data;
    }
    console.log(`[SuperTroopers] Waiting for DOM... attempt ${i + 1}/${maxRetries}`);
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return null;
}

function findInjectionAnchor(board: string): Element | null {
  const boardConfig = (siteConfig.boards as Record<string, { saveButtonAnchor?: string }>)[board];
  if (boardConfig?.saveButtonAnchor) {
    const anchor = document.querySelector(boardConfig.saveButtonAnchor);
    if (anchor) return anchor;
  }
  // Fallback: first h1 on page
  return document.querySelector("h1");
}

export function resetProcessedUrl(): void {
  lastProcessedUrl = null;
}
