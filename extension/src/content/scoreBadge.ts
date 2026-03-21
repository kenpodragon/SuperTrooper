import { createShadowContainer } from "./shadow";
import type { GapAnalysisResult } from "@shared/types";

export function injectScoreBadge(
  anchor: Element,
  result: GapAnalysisResult,
  mcpAvailable: boolean,
  onDeepAnalysis: () => Promise<GapAnalysisResult | null>
): void {
  // Remove old badge if exists
  document.getElementById("st-score-badge")?.remove();

  const { host, root } = createShadowContainer("st-score-badge");

  const style = document.createElement("style");
  style.textContent = `
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Consolas', 'Fira Code', monospace; }
    .st-score-row {
      display: inline-flex; align-items: center; gap: 6px;
      margin-left: 8px; vertical-align: middle;
    }
    .st-score {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 700;
      border: 1px solid; line-height: 1; cursor: default;
    }
    .st-score.high { color: #00FF41; border-color: #00FF41; background: rgba(0,255,65,0.08); }
    .st-score.mid { color: #FFD700; border-color: #FFD700; background: rgba(255,215,0,0.08); }
    .st-score.low { color: #ff4444; border-color: #ff4444; background: rgba(255,68,68,0.08); }
    .st-score .label { font-size: 10px; font-weight: 400; opacity: 0.8; }
    .st-score .mode { font-size: 9px; opacity: 0.5; margin-left: 2px; }
    .st-deep {
      display: inline-flex; align-items: center; justify-content: center;
      width: 24px; height: 24px; border-radius: 4px; border: 1px solid #00FF41;
      background: rgba(0,255,65,0.05); color: #00FF41; cursor: pointer;
      font-size: 14px; line-height: 1; transition: all 0.2s;
    }
    .st-deep:hover { background: rgba(0,255,65,0.2); }
    .st-deep.running { opacity: 0.6; cursor: wait; animation: pulse 1s infinite; }
    .st-deep.done { border-color: #FFD700; color: #FFD700; cursor: default; }
    @keyframes pulse { 0%,100% { opacity: 0.6; } 50% { opacity: 1; } }
    .st-tooltip {
      position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
      background: #1a1a2e; color: #00FF41; border: 1px solid #00FF41;
      padding: 4px 8px; border-radius: 4px; font-size: 11px; white-space: nowrap;
      pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 10000;
    }
    .st-deep-wrap { position: relative; display: inline-flex; }
    .st-deep-wrap:hover .st-tooltip { opacity: 1; }
  `;
  root.appendChild(style);

  const row = document.createElement("div");
  row.className = "st-score-row";

  // Score badge
  const scoreBadge = document.createElement("div");
  updateScoreBadge(scoreBadge, result);
  row.appendChild(scoreBadge);

  // Deep analysis button (only if MCP available and not already an AI result)
  if (mcpAvailable && result.analysis_mode !== "ai") {
    const deepWrap = document.createElement("div");
    deepWrap.className = "st-deep-wrap";

    const deepBtn = document.createElement("div");
    deepBtn.className = "st-deep";
    deepBtn.textContent = "\uD83D\uDD2C"; // microscope emoji
    deepBtn.setAttribute("role", "button");
    deepBtn.setAttribute("tabindex", "0");

    const tooltip = document.createElement("div");
    tooltip.className = "st-tooltip";
    tooltip.textContent = "Run AI-powered deep analysis";

    deepWrap.appendChild(deepBtn);
    deepWrap.appendChild(tooltip);
    row.appendChild(deepWrap);

    let clicked = false;
    deepBtn.addEventListener("click", async () => {
      if (clicked) return;
      clicked = true;
      deepBtn.classList.add("running");
      deepBtn.textContent = "\u23F3"; // hourglass
      tooltip.textContent = "Analyzing...";

      const aiResult = await onDeepAnalysis();
      if (aiResult) {
        updateScoreBadge(scoreBadge, aiResult);
        deepBtn.classList.remove("running");
        deepBtn.classList.add("done");
        deepBtn.textContent = "\u2713"; // checkmark
        tooltip.textContent = "AI analysis complete";
      } else {
        // AI failed — revert
        deepBtn.classList.remove("running");
        deepBtn.textContent = "\uD83D\uDD2C";
        tooltip.textContent = "AI unavailable — try again later";
        clicked = false;
      }
    });
  }

  root.appendChild(row);

  // Insert after the save button
  anchor.parentElement?.insertBefore(host, anchor.nextSibling);
}

function updateScoreBadge(el: HTMLElement, result: GapAnalysisResult): void {
  const score = Math.round(result.fit_score);
  const tier = score >= 60 ? "high" : score >= 35 ? "mid" : "low";
  const modeLabel = result.analysis_mode === "ai" ? "AI" : "KW";
  el.className = `st-score ${tier}`;
  el.innerHTML = `${score}<span class="label">FIT</span><span class="mode">${modeLabel}</span>`;
}
