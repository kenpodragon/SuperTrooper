/**
 * linkedinContactExtractor.ts — Extracts name + profile URL from LinkedIn
 * conversations across three contexts:
 *   1. Messaging page (/messaging/thread/...)
 *   2. Profile page (/in/...)
 *   3. Floating chat widget(s) (any LinkedIn page)
 *
 * Detected contacts are sent to the background script and stored so the popup
 * or backend can link/create the contact in SuperTroopers.
 */

const EXTRACTOR_API = "http://localhost:8055";

export interface LinkedInContact {
  name: string;
  profileUrl: string;
  title?: string;
  company?: string;
  location?: string;
  source: "messaging" | "profile" | "chat_widget";
}

// ---------------------------------------------------------------------------
// Selector-based extraction per context
// ---------------------------------------------------------------------------

/** Messaging page: /messaging/thread/... */
function extractFromMessagingPage(): LinkedInContact | null {
  const link = document.querySelector<HTMLAnchorElement>(
    "a.msg-thread__link-to-profile"
  );
  if (!link) return null;

  const nameEl = link.querySelector<HTMLElement>(
    "h2.msg-entity-lockup__entity-title"
  );
  const name = nameEl?.textContent?.trim();
  const href = link.getAttribute("href");
  if (!name || !href) return null;

  // The messaging page header may show title under the name
  const titleEl = document.querySelector<HTMLElement>(
    ".msg-entity-lockup__entity-subtitle, .msg-entity-lockup__entity-info"
  );
  const titleText = titleEl?.textContent?.trim();

  return {
    name,
    profileUrl: normalizeProfileUrl(href),
    title: titleText && !titleText.includes("Active") ? titleText : undefined,
    source: "messaging",
  };
}

/** Profile page: /in/username/ */
function extractFromProfilePage(): LinkedInContact | null {
  // Name is in the h1 inside the profile intro section
  const h1 = document.querySelector<HTMLElement>(
    "h1.inline, h1.text-heading-xlarge"
  );
  // Fallback: any h1 inside a link with aria-label
  const fallbackLink = document.querySelector<HTMLAnchorElement>(
    'a[href*="/in/"][aria-label]'
  );

  const name =
    h1?.textContent?.trim() || fallbackLink?.getAttribute("aria-label")?.trim();
  if (!name) return null;

  // Profile URL from the address bar
  const match = window.location.pathname.match(/\/in\/([^/]+)/);
  if (!match) return null;

  // Grab visible profile details
  const titleEl = document.querySelector<HTMLElement>(
    ".text-body-medium.break-words, .pv-text-details__left-panel .text-body-medium"
  );
  const locationEl = document.querySelector<HTMLElement>(
    ".text-body-small.inline.t-black--light.break-words, .pv-text-details__left-panel .text-body-small"
  );
  // Company from experience or the headline
  const companyEl = document.querySelector<HTMLElement>(
    'button[aria-label*="Current company"] span, .pv-text-details__right-panel .inline-show-more-text'
  );

  const rawTitle = titleEl?.textContent?.trim();

  return {
    name,
    profileUrl: `https://www.linkedin.com/in/${match[1]}/`,
    title: rawTitle,
    company: companyEl?.textContent?.trim(),
    location: locationEl?.textContent?.trim(),
    source: "profile",
  };
}

/** Floating chat widget(s) — returns all open conversations */
function extractFromChatWidgets(): LinkedInContact[] {
  const contacts: LinkedInContact[] = [];
  const headers = document.querySelectorAll<HTMLElement>(
    "h2.msg-overlay-bubble-header__title"
  );

  for (const header of headers) {
    const link = header.querySelector<HTMLAnchorElement>('a[href*="/in/"]');
    const nameSpan = header.querySelector<HTMLElement>("span");

    const name = nameSpan?.textContent?.trim() || link?.textContent?.trim();
    const href = link?.getAttribute("href");
    if (!name || !href) continue;

    contacts.push({
      name,
      profileUrl: normalizeProfileUrl(href),
      source: "chat_widget",
    });
  }

  return contacts;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Normalize LinkedIn profile URLs (handle encoded URNs and clean paths) */
function normalizeProfileUrl(href: string): string {
  // Already a full URL
  if (href.startsWith("http")) {
    // Strip overlay paths, query params, trailing junk
    const url = new URL(href);
    const match = url.pathname.match(/\/in\/([^/]+)/);
    return match
      ? `https://www.linkedin.com/in/${match[1]}/`
      : href;
  }
  // Relative path
  const match = href.match(/\/in\/([^/]+)/);
  return match
    ? `https://www.linkedin.com/in/${match[1]}/`
    : `https://www.linkedin.com${href}`;
}

// ---------------------------------------------------------------------------
// Main extraction — runs across all contexts
// ---------------------------------------------------------------------------

export function extractLinkedInContacts(): LinkedInContact[] {
  const contacts: LinkedInContact[] = [];

  // 1. Messaging page
  if (window.location.pathname.startsWith("/messaging/")) {
    const c = extractFromMessagingPage();
    if (c) contacts.push(c);
  }

  // 2. Profile page
  if (window.location.pathname.startsWith("/in/")) {
    const c = extractFromProfilePage();
    if (c) contacts.push(c);
  }

  // 3. Chat widgets (present on any page)
  const widgets = extractFromChatWidgets();
  contacts.push(...widgets);

  // Deduplicate by profileUrl
  const seen = new Set<string>();
  return contacts.filter((c) => {
    const key = c.profileUrl.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ---------------------------------------------------------------------------
// Background communication — send detected contacts to service worker
// ---------------------------------------------------------------------------

let lastSentKey = "";

export function sendDetectedContacts(contacts: LinkedInContact[]): void {
  if (contacts.length === 0) return;

  // Avoid spamming: only send if the set changed
  const key = contacts.map((c) => c.profileUrl).sort().join("|");
  if (key === lastSentKey) return;
  lastSentKey = key;

  chrome.runtime.sendMessage({
    type: "LINKEDIN_CONTACTS_DETECTED",
    contacts,
  });
}

// ---------------------------------------------------------------------------
// Backend contact lookup — check if this person is in SuperTroopers
// ---------------------------------------------------------------------------

export interface ContactLookupResult {
  found: boolean;
  contact_id?: number;
  contact_name?: string;
  linkedInContact: LinkedInContact;
}

export async function lookupContact(
  contact: LinkedInContact
): Promise<ContactLookupResult> {
  try {
    const searchRes = await fetch(
      `${EXTRACTOR_API}/api/contacts?q=${encodeURIComponent(contact.profileUrl)}&limit=1`
    );
    if (searchRes.ok) {
      const data = await searchRes.json();
      if (data.contacts?.length > 0) {
        return {
          found: true,
          contact_id: data.contacts[0].id,
          contact_name: data.contacts[0].name,
          linkedInContact: contact,
        };
      }
    }
  } catch {
    // Backend unavailable
  }
  return { found: false, linkedInContact: contact };
}

/**
 * Create a new contact in SuperTroopers from extracted LinkedIn data.
 * Returns the new contact ID or null on failure.
 */
export async function createContactFromLinkedIn(
  contact: LinkedInContact
): Promise<number | null> {
  try {
    const res = await fetch(`${EXTRACTOR_API}/api/contacts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: contact.name,
        linkedin_url: contact.profileUrl,
        title: contact.title || null,
        company: contact.company || null,
        source: "linkedin",
        relationship_strength: "cold",
        notes: contact.location
          ? `Location: ${contact.location}`
          : null,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return data.id || null;
    }
  } catch {
    // Backend unavailable
  }
  return null;
}

// ---------------------------------------------------------------------------
// Observer — watch for DOM changes (SPA navigation, chat opening/closing)
// ---------------------------------------------------------------------------

let pollTimer: ReturnType<typeof setInterval> | null = null;

export function startContactExtractor(): void {
  if (!window.location.hostname.includes("linkedin.com")) return;

  // Run immediately
  const initial = extractLinkedInContacts();
  sendDetectedContacts(initial);

  // Poll for changes (LinkedIn is a SPA, MutationObserver is unreliable
  // for their virtual DOM updates)
  pollTimer = setInterval(() => {
    const contacts = extractLinkedInContacts();
    sendDetectedContacts(contacts);
  }, 3000);

  // Also re-check on URL changes (SPA navigation)
  let lastUrl = window.location.href;
  const urlObserver = setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      // Small delay for DOM to settle after navigation
      setTimeout(() => {
        const contacts = extractLinkedInContacts();
        sendDetectedContacts(contacts);
      }, 1500);
    }
  }, 1000);
}

export function stopContactExtractor(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}
