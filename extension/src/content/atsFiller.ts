/**
 * atsFiller.ts — Fill detected ATS forms with candidate profile data.
 * Content script module (plain TS, no React).
 */

import type { AtsField } from "./atsDetector";

export interface CandidateProfile {
  full_name?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  cover_letter?: string;
}

export interface FillReport {
  filled: number;
  skipped: number;
  errors: string[];
}

/**
 * Dispatch synthetic input + change events so React/Vue/Angular forms register the value.
 */
function setNativeValue(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  )?.set;
  const nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    "value"
  )?.set;

  if (el instanceof HTMLTextAreaElement && nativeTextareaValueSetter) {
    nativeTextareaValueSetter.call(el, value);
  } else if (nativeInputValueSetter) {
    nativeInputValueSetter.call(el, value);
  } else {
    el.value = value;
  }

  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

function setSelectValue(el: HTMLSelectElement, value: string): boolean {
  // Try to find the closest option (case-insensitive, partial match)
  const options = Array.from(el.options);
  const match = options.find(
    (o) =>
      o.value.toLowerCase().includes(value.toLowerCase()) ||
      o.text.toLowerCase().includes(value.toLowerCase())
  );
  if (!match) return false;
  el.value = match.value;
  el.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function resolveValue(field: AtsField, profile: CandidateProfile): string | null {
  switch (field.type) {
    case "name":
      return (
        profile.full_name ||
        [profile.first_name, profile.last_name].filter(Boolean).join(" ") ||
        null
      );
    case "email":
      return profile.email || null;
    case "phone":
      return profile.phone || null;
    case "linkedin":
      return profile.linkedin_url || null;
    case "cover_letter":
      return profile.cover_letter || null;
    case "resume":
      return null; // File uploads are skipped
    case "custom":
      return null;
    default:
      return null;
  }
}

/**
 * Fill detected ATS form fields with profile data.
 * File upload fields are marked as skipped.
 * Returns a report of filled/skipped/error counts.
 */
export function fillAtsForm(profile: CandidateProfile, fields: AtsField[]): FillReport {
  let filled = 0;
  let skipped = 0;
  const errors: string[] = [];

  for (const field of fields) {
    // Skip file uploads
    if (field.type === "resume") {
      skipped++;
      continue;
    }

    const value = resolveValue(field, profile);
    if (value === null) {
      skipped++;
      continue;
    }

    const el = document.querySelector(field.element);
    if (!el) {
      errors.push(`Element not found: ${field.element}`);
      continue;
    }

    try {
      if (el instanceof HTMLSelectElement) {
        const ok = setSelectValue(el, value);
        if (ok) filled++;
        else {
          skipped++;
        }
      } else if (
        el instanceof HTMLInputElement ||
        el instanceof HTMLTextAreaElement
      ) {
        setNativeValue(el, value);
        filled++;
      } else {
        skipped++;
      }
    } catch (e) {
      errors.push(
        `Error filling ${field.element}: ${(e as Error).message}`
      );
    }
  }

  return { filled, skipped, errors };
}
