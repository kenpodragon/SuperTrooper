import { detectPage, extractJobData } from "./detector";
import { injectSaveButton } from "./saveButton";
import { injectScoreBadge } from "./scoreBadge";
import { MSG, sendToBackground } from "@shared/messages";
import type { JobExtraction, GapAnalysisResult } from "@shared/types";
import type { GapAnalysisResponse, McpStatusResponse } from "@shared/messages";
import siteConfig from "@config/siteConfig.json";

let lastProcessedUrl: string | null = null;

export async function processJobPage(): Promise<void> {
  const context = detectPage();
  console.log("[SuperTroopers] processJobPage called, context:", context.type, context.board);
  if (context.type !== "job_listing" || !context.board) return;

  // Avoid re-processing same URL (SPA nav can re-trigger)
  if (lastProcessedUrl === window.location.href) return;
  lastProcessedUrl = window.location.href;

  // Clean up previous injections
  document.getElementById("st-save-btn")?.remove();
  document.getElementById("st-score-badge")?.remove();

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

  // Wait for description to load (may arrive after title on SPA pages)
  if (!job.description || job.description.length <= 50) {
    const desc = await waitForDescription(context.board, 10, 600);
    if (desc) {
      job.description = desc;
    }
  }

  // Run Python keyword match (free/fast) if we have a description
  if (job.description && job.description.length > 50) {
    try {
      // Check cache first (might have an AI result from previous deep analysis)
      const cacheResp = await sendToBackground<GapAnalysisResponse & { error?: string }>(MSG.RUN_GAP_ANALYSIS, {
        jd_text: job.description,
        job_url: job.url,
        mode: "python",
      });

      if ((cacheResp as { error?: string })?.error) {
        console.warn("[SuperTroopers] Gap analysis error:", (cacheResp as { error: string }).error);
      }

      if (cacheResp?.result) {
        // Check if MCP is available for deep analysis button
        let mcpAvailable = false;
        try {
          const mcpResp = await sendToBackground<McpStatusResponse>(MSG.GET_MCP_STATUS);
          mcpAvailable = !!mcpResp?.available;
        } catch { /* default false */ }

        const scoreAnchor = document.getElementById("st-save-btn");
        if (scoreAnchor) {
          injectScoreBadge(scoreAnchor, cacheResp.result, mcpAvailable, async () => {
            // Deep analysis callback
            try {
              const aiResp = await sendToBackground<GapAnalysisResponse & { mcp_failed?: boolean }>(
                MSG.RUN_GAP_ANALYSIS,
                {
                  jd_text: job.description,
                  job_url: job.url,
                  mode: "ai",
                  force_refresh: true,
                }
              );
              return aiResp?.result || null;
            } catch {
              return null;
            }
          });
        }
      }
    } catch (e) {
      // Backend offline — no score, button still works when online
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

async function waitForDescription(board: string, maxRetries = 10, delayMs = 600): Promise<string | null> {
  const config = (siteConfig.boards as Record<string, { extractors: Record<string, { selector: string }> }>)[board];
  const descSelector = config?.extractors?.description?.selector;
  if (!descSelector) return null;

  for (let i = 0; i < maxRetries; i++) {
    const el = document.querySelector(descSelector);
    const text = el?.textContent?.trim() || "";
    if (text.length > 50) {
      console.log(`[SuperTroopers] Description found on attempt ${i + 1} (${text.length} chars)`);
      return text;
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  console.log("[SuperTroopers] Description not found after retries");
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
