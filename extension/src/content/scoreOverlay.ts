import { createShadowContainer } from "./shadow";
import type { GapAnalysisResult } from "@shared/types";

export interface ScoreOverlayHandle {
  update: (result: GapAnalysisResult) => void;
  remove: () => void;
  onRefresh: (callback: () => void) => void;
}

export function injectScoreOverlay(result: GapAnalysisResult): ScoreOverlayHandle {
  const { host, root } = createShadowContainer("st-score-overlay");

  // Position fixed bottom-right
  host.style.cssText = "all: initial; position: fixed; bottom: 80px; right: 20px; z-index: 2147483646;";

  // Overlay-specific styles
  const style = document.createElement("style");
  style.textContent = `
    .badge { cursor: pointer; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.5)); transition: transform 0.2s; }
    .badge:hover { transform: scale(1.1); }
    .panel {
      position: absolute; bottom: 72px; right: 0; width: 320px;
      background: #1a1a2e; border: 1px solid #00FF41; border-radius: 8px;
      padding: 12px; font-family: 'Consolas', 'Fira Code', monospace; color: #e0e0e0;
      max-height: 420px; overflow-y: auto;
      box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    }
    .hidden { display: none; }
    .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .panel-title { font-size: 14px; font-weight: 700; color: #00FF41; }
    .panel-close { background: none; border: none; color: #e0e0e0; cursor: pointer; font-size: 16px; padding: 2px 6px; }
    .panel-close:hover { color: #00FF41; }
    .section { margin-bottom: 8px; }
    .section-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .section-label.strong { color: #00FF41; }
    .section-label.partial { color: #FFD700; }
    .section-label.gaps { color: #ff4444; }
    .section-label.recs { color: #88aaff; }
    .item { font-size: 12px; padding: 2px 0; line-height: 1.4; }
    .mode-badge {
      display: inline-block; font-size: 9px; padding: 2px 6px; border-radius: 3px;
      background: rgba(136, 170, 255, 0.15); color: #88aaff; text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .btn-refresh {
      width: 100%; margin-top: 8px; padding: 6px; font-size: 12px;
      background: rgba(0,255,65,0.08); border: 1px solid #00FF41;
      color: #00FF41; border-radius: 4px; cursor: pointer;
      font-family: 'Consolas', 'Fira Code', monospace;
    }
    .btn-refresh:hover { background: rgba(0,255,65,0.2); }
  `;
  root.appendChild(style);

  const badge = document.createElement("div");
  badge.className = "badge";
  const panel = document.createElement("div");
  panel.className = "panel hidden";

  root.appendChild(badge);
  root.appendChild(panel);
  document.body.appendChild(host);

  // Toggle panel on badge click
  badge.addEventListener("click", () => panel.classList.toggle("hidden"));

  let refreshCallback: (() => void) | null = null;

  function update(r: GapAnalysisResult): void {
    const score = Math.round(r.fit_score);
    const color = score >= 75 ? "#00FF41" : score >= 50 ? "#FFD700" : "#ff4444";

    badge.innerHTML = `
      <svg viewBox="0 0 80 80" width="64" height="64">
        <circle cx="40" cy="40" r="36" fill="#1a1a2e" stroke="${color}" stroke-width="3"/>
        <text x="40" y="36" text-anchor="middle" fill="${color}" font-size="22" font-weight="bold" font-family="Consolas, monospace">${score}</text>
        <text x="40" y="52" text-anchor="middle" fill="#e0e0e0" font-size="9" font-family="Consolas, monospace">FIT</text>
      </svg>
    `;

    const modeLabel = r.analysis_mode === "ai" ? "AI Analysis" : "Rule-Based";

    panel.innerHTML = `
      <div class="panel-header">
        <span class="panel-title">Match Analysis</span>
        <span class="mode-badge">${modeLabel}</span>
        <button class="panel-close">\u2715</button>
      </div>
      ${renderSection("Strong Matches", "strong", r.strong_matches, "\u2713")}
      ${renderSection("Partial Matches", "partial", r.partial_matches, "\u25D0")}
      ${renderSection("Gaps", "gaps", r.gaps, "\u2717")}
      ${r.recommendations.length ? renderSection("Recommendations", "recs", r.recommendations, "\u2192") : ""}
      <button class="btn-refresh">\u21BB Refresh Analysis</button>
    `;

    // Wire close button
    panel.querySelector(".panel-close")?.addEventListener("click", (e) => {
      e.stopPropagation();
      panel.classList.add("hidden");
    });

    // Wire refresh button
    panel.querySelector(".btn-refresh")?.addEventListener("click", () => {
      if (refreshCallback) refreshCallback();
    });
  }

  function renderSection(title: string, cls: string, items: string[], icon: string): string {
    if (!items.length) return "";
    return `
      <div class="section">
        <div class="section-label ${cls}">${title} (${items.length})</div>
        ${items.map((s) => `<div class="item">${icon} ${s}</div>`).join("")}
      </div>
    `;
  }

  update(result);

  return {
    update,
    remove: () => host.remove(),
    onRefresh: (cb: () => void) => {
      refreshCallback = cb;
    },
  };
}
