/**
 * atsDetector.ts — Detect ATS form pages and map fields to standard types.
 * Content script module (plain TS, no React).
 */

export type AtsFieldType =
  | "name"
  | "email"
  | "phone"
  | "resume"
  | "linkedin"
  | "cover_letter"
  | "custom";

export interface AtsField {
  type: AtsFieldType;
  element: string; // CSS selector
  label: string;
}

export interface AtsDetectResult {
  isAts: boolean;
  platform: string;
  fields: AtsField[];
}

// --- Platform detection by URL + DOM signals ---

interface PlatformSignal {
  name: string;
  urlPatterns: RegExp[];
  domSelectors?: string[];
}

const PLATFORMS: PlatformSignal[] = [
  {
    name: "greenhouse",
    urlPatterns: [/greenhouse\.io\//, /boards\.greenhouse\.io\//],
    domSelectors: ["#application_form", "form[action*='greenhouse']"],
  },
  {
    name: "lever",
    urlPatterns: [/jobs\.lever\.co\//],
    domSelectors: ["form.application-form", "[data-lever-source]"],
  },
  {
    name: "workday",
    urlPatterns: [/myworkdayjobs\.com\//, /wd\d+\.myworkday\.com\//],
    domSelectors: ["[data-automation-id='applicationPage']", "[data-uxi-widget-type='panel']"],
  },
  {
    name: "icims",
    urlPatterns: [/icims\.com\//],
    domSelectors: ["#iCIMS_MainColumn", "form[id*='iCIMS']"],
  },
  {
    name: "taleo",
    urlPatterns: [/taleo\.net\//, /tbe\.taleo\.net\//],
    domSelectors: ["#mainContent", "form[name='ftlForm']"],
  },
  {
    name: "smartrecruiters",
    urlPatterns: [/smartrecruiters\.com\//],
    domSelectors: ["[data-qa='apply-form']", ".application-form"],
  },
  {
    name: "jobvite",
    urlPatterns: [/jobs\.jobvite\.com\//],
    domSelectors: ["form.jv-form", "#apply-form"],
  },
  {
    name: "brassring",
    urlPatterns: [/brassring\.com\//],
    domSelectors: ["#reqapp", "form[name='appform']"],
  },
  {
    name: "successfactors",
    urlPatterns: [/successfactors\.(com|eu|cn)\//],
    domSelectors: ["[id*='careersite']", ".sapSFCareer"],
  },
];

// --- Field label -> type mapping ---

const LABEL_MAP: Array<{ patterns: RegExp[]; type: AtsFieldType }> = [
  {
    patterns: [/first.?name|last.?name|full.?name|your name/i],
    type: "name",
  },
  {
    patterns: [/e.?mail/i],
    type: "email",
  },
  {
    patterns: [/phone|mobile|cell|telephone/i],
    type: "phone",
  },
  {
    patterns: [/resume|cv|curriculum vitae/i],
    type: "resume",
  },
  {
    patterns: [/linkedin/i],
    type: "linkedin",
  },
  {
    patterns: [/cover.?letter|covering.?letter/i],
    type: "cover_letter",
  },
];

function classifyLabel(label: string): AtsFieldType {
  for (const entry of LABEL_MAP) {
    if (entry.patterns.some((p) => p.test(label))) return entry.type;
  }
  return "custom";
}

// --- Field discovery ---

function discoverFields(): AtsField[] {
  const fields: AtsField[] = [];
  const seen = new Set<string>();

  // Collect all input/textarea/select elements
  const inputs = Array.from(
    document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
      "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio']), textarea, select"
    )
  );

  for (const el of inputs) {
    // Build a stable CSS selector
    let selector = "";
    if (el.id) {
      selector = `#${CSS.escape(el.id)}`;
    } else if (el.name) {
      selector = `[name="${el.name}"]`;
    } else {
      continue; // Can't reliably target this element
    }

    if (seen.has(selector)) continue;
    seen.add(selector);

    // Find the associated label text
    let labelText = "";
    if (el.id) {
      const labelEl = document.querySelector(`label[for="${el.id}"]`);
      if (labelEl) labelText = labelEl.textContent?.trim() || "";
    }
    if (!labelText) {
      // Walk up for wrapping label or aria-label
      labelText =
        el.getAttribute("aria-label") ||
        el.getAttribute("placeholder") ||
        el.closest("label")?.textContent?.trim() ||
        "";
    }

    const fieldType = classifyLabel(labelText || selector);

    fields.push({ type: fieldType, element: selector, label: labelText || selector });
  }

  return fields;
}

// --- Main export ---

/**
 * Detect whether the current page is an ATS application form.
 * Returns the platform name, field map, and a boolean flag.
 */
export function detectAtsForm(): AtsDetectResult {
  const url = window.location.href;

  let detectedPlatform = "";

  for (const platform of PLATFORMS) {
    const urlMatch = platform.urlPatterns.some((p) => p.test(url));
    const domMatch =
      platform.domSelectors?.some((sel) => document.querySelector(sel) !== null) ?? false;

    if (urlMatch || domMatch) {
      detectedPlatform = platform.name;
      break;
    }
  }

  // Generic fallback: detect any form with application-related action
  if (!detectedPlatform) {
    const forms = Array.from(document.querySelectorAll("form"));
    const hasAppForm = forms.some((f) => {
      const action = (f.getAttribute("action") || "").toLowerCase();
      return (
        action.includes("apply") ||
        action.includes("application") ||
        action.includes("career")
      );
    });
    if (hasAppForm) detectedPlatform = "generic";
  }

  if (!detectedPlatform) {
    return { isAts: false, platform: "", fields: [] };
  }

  const fields = discoverFields();

  return {
    isAts: true,
    platform: detectedPlatform,
    fields,
  };
}
