const THEME = {
  bg: "#1a1a2e",
  surface: "#16213e",
  border: "#1f3460",
  text: "#e0e0e0",
  muted: "#8899aa",
  green: "#00FF41",
  greenDim: "#00cc33",
  red: "#ff4444",
};

export function createShadowContainer(id: string): { host: HTMLElement; root: ShadowRoot } {
  const existing = document.getElementById(id);
  if (existing) existing.remove();

  const host = document.createElement("div");
  host.id = id;
  host.style.cssText = "all: initial; position: relative; z-index: 999999;";

  const root = host.attachShadow({ mode: "open" });

  const style = document.createElement("style");
  style.textContent = `
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Consolas', 'Fira Code', monospace; }
    .st-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 14px; border-radius: 4px; border: 1px solid ${THEME.green};
      background: ${THEME.bg}; color: ${THEME.green};
      font-size: 12px; font-weight: bold; cursor: pointer;
      transition: all 0.2s;
    }
    .st-btn:hover { background: ${THEME.green}; color: ${THEME.bg}; }
    .st-btn.saved { border-color: ${THEME.muted}; color: ${THEME.muted}; cursor: default; }
    .st-badge {
      display: inline-flex; align-items: center; justify-content: center;
      width: 36px; height: 36px; border-radius: 50%;
      background: ${THEME.bg}; border: 2px solid ${THEME.green};
      color: ${THEME.green}; font-size: 11px; font-weight: bold;
    }
  `;
  root.appendChild(style);

  return { host, root };
}
