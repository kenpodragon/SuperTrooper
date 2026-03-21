import type { GapAnalysisResult } from "@shared/types";

const CACHE_PREFIX = 'gap_';
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

function normalizeUrl(url: string): string {
  // Strip tracking params (utm_*, fbclid, etc.)
  const u = new URL(url);
  const strip = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid'];
  strip.forEach(p => u.searchParams.delete(p));
  return u.toString();
}

export async function getCachedGap(url: string): Promise<GapAnalysisResult | null> {
  const key = CACHE_PREFIX + normalizeUrl(url);
  const result = await chrome.storage.local.get(key);
  if (!result[key]) return null;
  const cached = result[key] as GapAnalysisResult;
  if (Date.now() - (cached.cached_at || 0) > TTL_MS) {
    await chrome.storage.local.remove(key);
    return null;
  }
  return cached;
}

export async function setCachedGap(url: string, result: GapAnalysisResult): Promise<void> {
  const key = CACHE_PREFIX + normalizeUrl(url);
  result.cached_at = Date.now();
  result.job_url = url;
  await chrome.storage.local.set({ [key]: result });
}

export async function clearCachedGap(url: string): Promise<void> {
  const key = CACHE_PREFIX + normalizeUrl(url);
  await chrome.storage.local.remove(key);
}

export async function clearAllGapCache(): Promise<void> {
  const all = await chrome.storage.local.get(null);
  const gapKeys = Object.keys(all).filter(k => k.startsWith(CACHE_PREFIX));
  await chrome.storage.local.remove(gapKeys);
}
