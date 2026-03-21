import siteConfig from "@config/siteConfig.json";
import type { PageContext } from "@shared/types";

interface BoardConfig {
  hostPattern: string;
  jobListingPaths: string[];
  extractors: Record<string, { selector: string; attribute: string }>;
}

export function detectPage(): PageContext {
  const url = window.location.href;
  const hostname = window.location.hostname;

  for (const [boardId, config] of Object.entries(siteConfig.boards as Record<string, BoardConfig>)) {
    if (!hostname.includes(config.hostPattern)) continue;

    const path = window.location.pathname;
    const search = window.location.search;
    const isJobListing = config.jobListingPaths.some((p) => path.includes(p));
    // LinkedIn collections/search pages with currentJobId are also job listings
    const hasJobIdParam = boardId === "linkedin" && search.includes("currentJobId=");

    if (isJobListing || hasJobIdParam) {
      return { url, type: "job_listing", board: boardId };
    }
  }

  return { url, type: "unknown" };
}

export function extractJobData(board: string): Record<string, string> | null {
  const config = (siteConfig.boards as Record<string, BoardConfig>)[board];
  if (!config?.extractors) return null;

  // For LinkedIn, scope extraction to the job detail panel (right side of split view)
  const scopeRoot = board === "linkedin"
    ? (document.querySelector(".jobs-search__job-details, .job-details-module, .jobs-details, .scaffold-layout__detail") || document)
    : document;

  console.log(`[SuperTroopers] Extraction scope: ${scopeRoot === document ? "document" : (scopeRoot as Element).className?.substring(0, 60)}`);

  const data: Record<string, string> = {};
  for (const [field, ext] of Object.entries(config.extractors)) {
    // LinkedIn location: find the first tvm__text span with actual location text (not "·" separators)
    if (board === "linkedin" && field === "location") {
      const spans = (scopeRoot as Element).querySelectorAll?.("span.tvm__text.tvm__text--low-emphasis") ||
                    document.querySelectorAll("span.tvm__text.tvm__text--low-emphasis");
      for (const span of Array.from(spans)) {
        const txt = (span as HTMLElement).textContent?.trim() || "";
        if (txt && txt !== "·" && txt.length > 1) {
          data[field] = txt;
          console.log(`[SuperTroopers] Extracted ${field}: ${txt.substring(0, 60)}`);
          break;
        }
      }
      if (!data[field]) {
        console.log(`[SuperTroopers] Missing ${field}: no tvm__text span with location text`);
      }
      continue;
    }

    const el = (scopeRoot as Element).querySelector?.(ext.selector) || document.querySelector(ext.selector);
    if (el) {
      const value = (el as HTMLElement).textContent?.trim() || "";
      if (value) {
        data[field] = value;
        console.log(`[SuperTroopers] Extracted ${field}: ${value.substring(0, 60)}`);
      }
    } else {
      console.log(`[SuperTroopers] Missing ${field}: tried "${ext.selector.substring(0, 80)}"`);
    }
  }

  // For LinkedIn, use canonical job URL instead of session-specific collections URL
  if (board === "linkedin") {
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get("currentJobId");
    if (jobId) {
      data.url = `https://www.linkedin.com/jobs/view/${jobId}/`;
    } else {
      // Already on /jobs/view/ path — use current URL stripped of tracking params
      const match = window.location.pathname.match(/\/jobs\/view\/(\d+)/);
      data.url = match ? `https://www.linkedin.com/jobs/view/${match[1]}/` : window.location.href;
    }
  } else {
    data.url = window.location.href;
  }
  data.source = board;

  console.log(`[SuperTroopers] Extraction result: ${Object.keys(data).length} fields (need >2)`);
  return Object.keys(data).length > 2 ? data : null;
}
