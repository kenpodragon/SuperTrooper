/**
 * applicationTracker.ts — Auto-detect application submissions and notify background.
 * Content script module (plain TS, no React).
 */

export interface ApplicationContext {
  company: string;
  role: string;
  source: string;
  url: string;
}

// --- Success signal detection ---

const SUCCESS_URL_PATTERNS = [
  /\/thank.?you/i,
  /\/confirmation/i,
  /\/success/i,
  /\/application.?received/i,
  /\/submitted/i,
  /apply\/complete/i,
  /applicationsubmitted/i,
];

const SUCCESS_TEXT_PATTERNS = [
  /application (received|submitted|complete)/i,
  /thank you for (applying|your application)/i,
  /we.?ve received your application/i,
  /successfully submitted/i,
  /your application has been/i,
];

function isSuccessUrl(url: string): boolean {
  return SUCCESS_URL_PATTERNS.some((p) => p.test(url));
}

function isSuccessPage(): boolean {
  if (isSuccessUrl(window.location.href)) return true;

  // Scan visible page text (limit to first 5000 chars for performance)
  const bodyText = document.body?.innerText?.slice(0, 5000) || "";
  return SUCCESS_TEXT_PATTERNS.some((p) => p.test(bodyText));
}

// --- Context extraction ---

/**
 * Extract application context from the current page.
 * Best-effort: uses meta tags, og tags, or document title.
 */
export function getApplicationContext(): ApplicationContext {
  const url = window.location.href;

  // Try og:site_name or meta company hints
  const ogSite =
    document.querySelector<HTMLMetaElement>('meta[property="og:site_name"]')?.content || "";
  const ogTitle =
    document.querySelector<HTMLMetaElement>('meta[property="og:title"]')?.content || "";

  // Attempt to extract company from hostname
  const hostname = window.location.hostname;
  const hostParts = hostname.replace(/^www\./, "").split(".");
  const companyFromHost = hostParts[0] || "";

  const company =
    ogSite ||
    companyFromHost ||
    document.title.split("|").pop()?.trim() ||
    "Unknown";

  // Extract role from title or og:title
  const role =
    ogTitle ||
    document.querySelector("h1")?.textContent?.trim() ||
    document.title.split("|")[0]?.trim() ||
    "Unknown";

  // Identify source board
  let source = "direct";
  if (/greenhouse\.io/.test(hostname)) source = "greenhouse";
  else if (/lever\.co/.test(hostname)) source = "lever";
  else if (/myworkday/.test(hostname)) source = "workday";
  else if (/icims\.com/.test(hostname)) source = "icims";
  else if (/taleo\.net/.test(hostname)) source = "taleo";
  else if (/smartrecruiters\.com/.test(hostname)) source = "smartrecruiters";
  else if (/jobvite\.com/.test(hostname)) source = "jobvite";

  return { company, role, source, url };
}

// --- Submission notification ---

let _submissionReported = false;

function reportSubmission(): void {
  if (_submissionReported) return;
  _submissionReported = true;

  const context = getApplicationContext();

  chrome.runtime.sendMessage({
    type: "APPLICATION_SUBMITTED",
    data: {
      company: context.company,
      role: context.role,
      source: context.source,
      url: context.url,
      submitted_at: new Date().toISOString(),
    },
  }).catch((e) => {
    console.warn("[SuperTroopers] Failed to report submission:", e);
  });

  console.log("[SuperTroopers] Application submission detected:", context);
}

// --- Watch for submission ---

let _watching = false;

/**
 * Start watching the page for application submission success signals.
 * Monitors URL changes, DOM mutations for success text, and form submits.
 */
export function watchForSubmission(): void {
  if (_watching) return;
  _watching = true;

  // Check immediately in case we're already on a success page
  if (isSuccessPage()) {
    reportSubmission();
    return;
  }

  // Watch for URL changes (SPA navigation to thank-you page)
  let lastUrl = window.location.href;
  const urlObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (isSuccessUrl(lastUrl)) {
        reportSubmission();
        urlObserver.disconnect();
      }
    }
  });
  urlObserver.observe(document.body, { childList: true, subtree: true });

  // URL polling fallback
  const pollInterval = setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      if (isSuccessUrl(lastUrl)) {
        reportSubmission();
        clearInterval(pollInterval);
        urlObserver.disconnect();
      }
    }
    // Also check DOM text periodically
    if (isSuccessPage()) {
      reportSubmission();
      clearInterval(pollInterval);
      urlObserver.disconnect();
    }
  }, 1500);

  // Watch form submissions
  document.addEventListener(
    "submit",
    (e) => {
      const form = e.target as HTMLFormElement;
      const action = (form?.getAttribute("action") || "").toLowerCase();
      if (
        action.includes("apply") ||
        action.includes("application") ||
        action.includes("submit")
      ) {
        // Give the page 2s to navigate to success before declaring submitted
        setTimeout(() => {
          if (isSuccessPage()) reportSubmission();
        }, 2000);
      }
    },
    true
  );
}
