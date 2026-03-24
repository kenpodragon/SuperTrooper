/**
 * LinkedIn Messaging Panel — shows pending outreach drafts when visiting a contact's profile.
 *
 * Flow:
 * 1. User composes a LinkedIn message in SuperTroopers frontend
 * 2. Frontend opens the contact's LinkedIn profile
 * 3. This content script detects the /in/ page, queries backend for pending drafts
 * 4. If found, injects a floating panel with edit, save, delete, AI wordsmith, copy
 * 5. User edits/polishes, copies, pastes into LinkedIn's native compose, sends
 */

import { createShadowContainer } from "./shadow";

const API_BASE = "http://localhost:8055";

interface LinkedInDraft {
  id: number;
  contact_id?: number;
  contact_name?: string;
  contact_company?: string;
  subject?: string;
  body?: string;
  created_at?: string;
}

let panelHost: HTMLElement | null = null;

function getLinkedInProfileUrl(): string | null {
  const url = window.location.href;
  const match = url.match(/linkedin\.com\/in\/[^/?#]+/);
  return match ? `https://www.${match[0]}` : null;
}

async function fetchPendingDrafts(linkedinUrl: string): Promise<LinkedInDraft[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/crm/pending-linkedin?linkedin_url=${encodeURIComponent(linkedinUrl)}`
    );
    if (!res.ok) return [];
    const data = await res.json();
    return data.drafts || [];
  } catch {
    return [];
  }
}

async function saveDraft(draftId: number, body: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/crm/drafts/${draftId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body, subject: "", action: "update" }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function deleteDraft(draftId: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/crm/drafts/${draftId}`, { method: "DELETE" });
    return res.ok;
  } catch {
    return false;
  }
}

async function markDraftSent(draftId: number, body: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/crm/drafts/${draftId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body, subject: "", action: "send" }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function wordsmith(body: string, contactId?: number): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/api/crm/wordsmith`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body, contact_id: contactId, channel: "linkedin" }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.body || null;
  } catch {
    return null;
  }
}

const BTN = `
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 10px; border-radius: 4px;
  font-size: 10px; font-weight: bold; cursor: pointer;
  font-family: inherit; transition: all 0.2s; white-space: nowrap;
`;

function buildPanel(root: ShadowRoot, drafts: LinkedInDraft[]) {
  const draft = drafts[0];
  let currentBody = draft.body || "";
  let aiEnabled = false;

  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div id="st-panel" style="
      position: fixed; bottom: 20px; right: 20px; z-index: 999999;
      width: 400px;
      background: #1a1a2e; border: 1px solid #00FF41; border-radius: 8px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      font-family: 'Consolas', 'Fira Code', monospace;
      display: flex; flex-direction: column;
    ">
      <!-- Header -->
      <div style="
        padding: 10px 14px; border-bottom: 1px solid #1f3460;
        display: flex; align-items: center; justify-content: space-between;
      ">
        <div>
          <div style="color: #00FF41; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">
            SUPERTROOPERS
          </div>
          <div style="color: #8899aa; font-size: 10px; margin-top: 2px;">
            Message for ${escapeHtml(draft.contact_name || "this contact")}${draft.contact_company ? ` at ${escapeHtml(draft.contact_company)}` : ""}
          </div>
        </div>
        <button id="st-close" style="
          background: none; border: none; color: #8899aa; font-size: 18px;
          cursor: pointer; padding: 0 4px; line-height: 1;
        ">&times;</button>
      </div>

      <!-- AI Wordsmith toggle -->
      <div style="padding: 8px 14px; border-bottom: 1px solid #1f3460; display: flex; align-items: center; gap: 8px;">
        <div id="st-ai-toggle" style="
          position: relative; width: 32px; height: 16px; border-radius: 8px;
          background: #1f3460; cursor: pointer; transition: background 0.2s;
        ">
          <div id="st-ai-knob" style="
            position: absolute; top: 2px; left: 2px;
            width: 12px; height: 12px; border-radius: 50%;
            background: #8899aa; transition: all 0.2s;
          "></div>
        </div>
        <span id="st-ai-label" style="color: #8899aa; font-size: 10px; font-weight: bold;">AI Wordsmith</span>
        <button id="st-ai-run" style="
          ${BTN}
          border: 1px solid #1f3460; background: #16213e; color: #8899aa;
          display: none;
        ">Wordsmith It</button>
        <span id="st-ai-badge" style="
          font-size: 9px; padding: 2px 6px; border-radius: 3px;
          display: none;
        "></span>
      </div>

      <!-- Message body (editable) -->
      <div style="padding: 10px 14px; flex: 1; overflow-y: auto;">
        <textarea id="st-msg-body" style="
          width: 100%; min-height: 160px; max-height: 280px;
          background: #16213e; border: 1px solid #1f3460; border-radius: 4px;
          color: #e0e0e0; font-size: 12px; font-family: inherit;
          padding: 10px; resize: vertical; outline: none;
        ">${escapeHtml(currentBody)}</textarea>
      </div>

      <!-- Status bar -->
      <div id="st-status" style="padding: 0 14px 4px; color: #8899aa; font-size: 10px; min-height: 16px;"></div>

      <!-- Action buttons -->
      <div style="
        padding: 8px 14px 10px; border-top: 1px solid #1f3460;
        display: flex; align-items: center; justify-content: space-between;
      ">
        <div style="display: flex; gap: 6px;">
          <button id="st-save" style="
            ${BTN} border: 1px solid #1f3460; background: #16213e; color: #e0e0e0;
          ">Save</button>
          <button id="st-delete" style="
            ${BTN} border: 1px solid #ff4444; background: #1a1a2e; color: #ff4444;
          ">Delete</button>
        </div>
        <div style="display: flex; gap: 6px;">
          <button id="st-copy" style="
            ${BTN} border: 1px solid #00FF41; background: #1a1a2e; color: #00FF41;
          ">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
            </svg>
            Copy
          </button>
          <button id="st-done" style="
            ${BTN} border: 1px solid #00FF41; background: #00FF41; color: #1a1a2e;
          ">Done &amp; Sent</button>
        </div>
      </div>
    </div>
  `;

  root.appendChild(wrapper);

  // --- DOM refs ---
  const textarea = root.getElementById("st-msg-body") as HTMLTextAreaElement;
  const statusEl = root.getElementById("st-status") as HTMLElement;
  const copyBtn = root.getElementById("st-copy") as HTMLButtonElement;
  const doneBtn = root.getElementById("st-done") as HTMLButtonElement;
  const closeBtn = root.getElementById("st-close") as HTMLButtonElement;
  const saveBtn = root.getElementById("st-save") as HTMLButtonElement;
  const deleteBtn = root.getElementById("st-delete") as HTMLButtonElement;
  const aiToggle = root.getElementById("st-ai-toggle") as HTMLElement;
  const aiKnob = root.getElementById("st-ai-knob") as HTMLElement;
  const aiLabel = root.getElementById("st-ai-label") as HTMLElement;
  const aiRunBtn = root.getElementById("st-ai-run") as HTMLButtonElement;
  const aiBadge = root.getElementById("st-ai-badge") as HTMLElement;

  function setStatus(text: string, color = "#8899aa") {
    statusEl.textContent = text;
    statusEl.style.color = color;
  }

  function disableAll(disable: boolean) {
    [saveBtn, deleteBtn, copyBtn, doneBtn, aiRunBtn].forEach(b => {
      if (b) b.style.opacity = disable ? "0.4" : "1";
      if (b) b.style.pointerEvents = disable ? "none" : "auto";
    });
  }

  // --- Textarea ---
  textarea?.addEventListener("input", () => { currentBody = textarea.value; });

  // --- AI Toggle ---
  aiToggle?.addEventListener("click", () => {
    aiEnabled = !aiEnabled;
    aiKnob.style.left = aiEnabled ? "18px" : "2px";
    aiKnob.style.background = aiEnabled ? "#a855f7" : "#8899aa";
    aiToggle.style.background = aiEnabled ? "#581c87" : "#1f3460";
    aiLabel.style.color = aiEnabled ? "#a855f7" : "#8899aa";
    aiRunBtn.style.display = aiEnabled ? "inline-flex" : "none";
    if (aiEnabled) {
      aiRunBtn.style.border = "1px solid #a855f7";
      aiRunBtn.style.color = "#a855f7";
    }
  });

  // --- AI Wordsmith ---
  aiRunBtn?.addEventListener("click", async () => {
    if (!currentBody.trim()) return;
    setStatus("AI is wordsmithing...", "#a855f7");
    disableAll(true);
    aiRunBtn.textContent = "Working...";

    const result = await wordsmith(currentBody, draft.contact_id);
    disableAll(false);
    aiRunBtn.textContent = "Wordsmith It";

    if (result) {
      currentBody = result;
      textarea.value = result;
      aiBadge.textContent = "AI polished";
      aiBadge.style.display = "inline";
      aiBadge.style.background = "#581c87";
      aiBadge.style.color = "#a855f7";
      setStatus("AI wordsmith applied — review and edit as needed", "#a855f7");
    } else {
      setStatus("AI unavailable — message unchanged", "#ff4444");
    }
  });

  // --- Save ---
  saveBtn?.addEventListener("click", async () => {
    setStatus("Saving...");
    disableAll(true);
    const ok = await saveDraft(draft.id, currentBody);
    disableAll(false);
    setStatus(ok ? "Draft saved!" : "Save failed", ok ? "#00FF41" : "#ff4444");
  });

  // --- Delete ---
  deleteBtn?.addEventListener("click", async () => {
    setStatus("Deleting...");
    disableAll(true);
    const ok = await deleteDraft(draft.id);
    disableAll(false);
    if (ok) {
      setStatus("Deleted!", "#00FF41");
      setTimeout(removePanel, 600);
    } else {
      setStatus("Delete failed", "#ff4444");
    }
  });

  // --- Copy ---
  copyBtn?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(currentBody);
      setStatus("Copied! Now paste into LinkedIn's message box", "#00FF41");
      const origHTML = copyBtn.innerHTML;
      copyBtn.innerHTML = `
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        Copied!
      `;
      setTimeout(() => { copyBtn.innerHTML = origHTML; }, 2000);
    } catch {
      setStatus("Copy failed — select text manually", "#ff4444");
    }
  });

  // --- Done (mark sent + close) ---
  doneBtn?.addEventListener("click", async () => {
    setStatus("Marking as sent...");
    disableAll(true);
    await markDraftSent(draft.id, currentBody);
    setStatus("Marked as sent!", "#00FF41");
    setTimeout(removePanel, 600);
  });

  // --- Close ---
  closeBtn?.addEventListener("click", removePanel);
}

function removePanel() {
  if (panelHost) {
    panelHost.remove();
    panelHost = null;
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export async function checkLinkedInProfile(): Promise<void> {
  if (!window.location.hostname.includes("linkedin.com")) return;
  if (!window.location.pathname.startsWith("/in/")) return;
  if (document.getElementById("st-linkedin-msg")) return;

  const profileUrl = getLinkedInProfileUrl();
  if (!profileUrl) return;

  const drafts = await fetchPendingDrafts(profileUrl);
  if (drafts.length === 0) return;

  console.log(`[SuperTroopers] Found ${drafts.length} pending LinkedIn draft(s)`);

  const { host, root } = createShadowContainer("st-linkedin-msg");
  panelHost = host;
  buildPanel(root, drafts);
  document.body.appendChild(host);
}
