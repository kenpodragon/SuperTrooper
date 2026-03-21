import { createShadowContainer } from "./shadow";
import { MSG, sendToBackground } from "@shared/messages";
import type { JobExtraction } from "@shared/types";
import type { SaveJobResponse, CheckJobUrlResponse } from "@shared/messages";

type ButtonState = "save" | "saving" | "saved" | "already_saved" | "error";

export function injectSaveButton(anchor: Element, job: JobExtraction): void {
  // Create shadow container
  const { host, root } = createShadowContainer("st-save-btn");

  // Add button-specific styles
  const style = document.createElement("style");
  style.textContent = `
    .st-save-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 8px 16px; margin: 8px 0; font-size: 13px; font-weight: 600;
      cursor: pointer; border: 1px solid #00FF41; border-radius: 6px;
      background: rgba(0, 255, 65, 0.08); color: #00FF41;
      font-family: 'Consolas', 'Fira Code', monospace;
      transition: all 0.2s; line-height: 1;
    }
    .st-save-btn:hover:not(.disabled) { background: rgba(0, 255, 65, 0.2); }
    .st-save-btn.disabled { opacity: 0.7; cursor: default; }
    .st-save-btn.success { border-color: #00FF41; background: rgba(0, 255, 65, 0.15); }
    .st-save-btn.error { border-color: #ff4444; color: #ff4444; background: rgba(255, 68, 68, 0.08); }
  `;
  root.appendChild(style);

  // Create button
  const btn = document.createElement("button");
  btn.className = "st-save-btn";
  root.appendChild(btn);

  // State machine
  function setState(state: ButtonState): void {
    const labels: Record<ButtonState, string> = {
      save: "\u2b21 Save to SuperTroopers",
      saving: "\u2b21 Saving...",
      saved: "\u2713 Saved",
      already_saved: "\u2713 Already Saved",
      error: "\u2717 Error \u2014 Retry?",
    };
    btn.textContent = labels[state];
    btn.className = "st-save-btn";
    if (state === "saving" || state === "saved" || state === "already_saved") {
      btn.classList.add("disabled");
      if (state !== "saving") btn.classList.add("success");
    }
    if (state === "error") btn.classList.add("error");
    btn.dataset.state = state;
  }

  setState("save");

  // Check if already saved (async, non-blocking)
  sendToBackground<CheckJobUrlResponse>(MSG.CHECK_JOB_URL, { url: job.url })
    .then((resp) => {
      if (resp?.exists) setState("already_saved");
    })
    .catch(() => {}); // offline = show save button anyway

  // Click handler
  btn.addEventListener("click", async () => {
    const current = btn.dataset.state;
    if (current === "saved" || current === "already_saved" || current === "saving") return;

    setState("saving");
    try {
      const resp = await sendToBackground<SaveJobResponse>(MSG.SAVE_JOB, { job });
      setState(resp.already_existed ? "already_saved" : "saved");
    } catch {
      setState("error");
      setTimeout(() => {
        if (btn.dataset.state === "error") setState("save");
      }, 3000);
    }
  });

  // Insert after anchor element
  anchor.parentElement?.insertBefore(host, anchor.nextSibling);
}
