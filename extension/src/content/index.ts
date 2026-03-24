import { detectPage } from "./detector";
import { MSG, sendToBackground } from "@shared/messages";
import type { PageContext } from "@shared/types";
import { processJobPage, resetProcessedUrl, getCurrentJobData } from "./jobCapture";
import { checkLinkedInProfile } from "./linkedinMessaging";
import {
  startContactExtractor,
  extractLinkedInContacts,
  lookupContact,
  createContactFromLinkedIn,
} from "./linkedinContactExtractor";
import type { LinkedInContact, ContactLookupResult } from "./linkedinContactExtractor";

let currentContext: PageContext | null = null;

function init() {
  currentContext = detectPage();

  // Check for LinkedIn profile with pending messages (runs on /in/* pages)
  checkLinkedInProfile();

  // Start LinkedIn contact extractor on any LinkedIn page
  if (window.location.hostname.includes("linkedin.com")) {
    startContactExtractor();
  }

  if (currentContext.type === "unknown") return;

  console.log(`[SuperTroopers] Detected: ${currentContext.type} on ${currentContext.board}`);

  sendToBackground(MSG.PAGE_CONTEXT, currentContext);

  // Process job page (inject save button + inline score badge)
  if (currentContext.type === "job_listing") {
    processJobPage();
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  console.log(`[SuperTroopers] Content received: ${message.type}`);

  if (message.type === "GET_JOB_DATA") {
    const jobData = getCurrentJobData();
    sendResponse({ job: jobData });
    return true;
  }

  // LinkedIn contact extraction requests from popup
  if (message.type === "GET_LINKEDIN_CONTACTS") {
    const contacts = extractLinkedInContacts();
    sendResponse({ contacts });
    return true;
  }

  if (message.type === "LOOKUP_LINKEDIN_CONTACT") {
    const contact = message.contact as LinkedInContact;
    lookupContact(contact).then((result: ContactLookupResult) => {
      sendResponse(result);
    });
    return true; // async
  }

  if (message.type === "CREATE_LINKEDIN_CONTACT") {
    const contact = message.contact as LinkedInContact;
    createContactFromLinkedIn(contact).then((id: number | null) => {
      sendResponse({ id });
    });
    return true; // async
  }

  sendResponse({ ok: true });
  return true;
});

// Detect SPA navigation via MutationObserver + URL polling fallback
// LinkedIn uses history.replaceState which doesn't always trigger DOM mutations
let lastUrl = window.location.href;

function onUrlChange() {
  lastUrl = window.location.href;
  console.log(`[SuperTroopers] SPA navigation detected: ${lastUrl}`);
  resetProcessedUrl();
  init();
}

// MutationObserver catches most SPA navigations
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    onUrlChange();
  }
});
observer.observe(document.body, { childList: true, subtree: true });

init();
