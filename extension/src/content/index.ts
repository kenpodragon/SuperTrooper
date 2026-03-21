import { detectPage } from "./detector";
import { MSG, sendToBackground } from "@shared/messages";
import type { PageContext } from "@shared/types";
import { processJobPage, resetProcessedUrl } from "./jobCapture";

let currentContext: PageContext | null = null;

function init() {
  currentContext = detectPage();

  if (currentContext.type === "unknown") return;

  console.log(`[SuperTroopers] Detected: ${currentContext.type} on ${currentContext.board}`);

  sendToBackground(MSG.PAGE_CONTEXT, currentContext);

  // Process job page (inject save button + gap analysis overlay)
  if (currentContext.type === "job_listing") {
    processJobPage();
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  console.log(`[SuperTroopers] Content received: ${message.type}`);
  sendResponse({ ok: true });
  return true;
});

let lastUrl = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    console.log(`[SuperTroopers] SPA navigation detected: ${lastUrl}`);
    resetProcessedUrl();
    init();
  }
});
observer.observe(document.body, { childList: true, subtree: true });

init();
