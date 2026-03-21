interface CacheEntry<T> {
  data: T;
  expiry: number;
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  const result = await chrome.storage.local.get(key);
  const entry = result[key] as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (Date.now() > entry.expiry) {
    await chrome.storage.local.remove(key);
    return null;
  }
  return entry.data;
}

export async function cacheSet<T>(key: string, data: T, ttlMinutes: number): Promise<void> {
  const entry: CacheEntry<T> = {
    data,
    expiry: Date.now() + ttlMinutes * 60 * 1000,
  };
  await chrome.storage.local.set({ [key]: entry });
}

export async function cacheClear(prefix?: string): Promise<void> {
  if (!prefix) {
    await chrome.storage.local.clear();
    return;
  }
  const all = await chrome.storage.local.get(null);
  const keys = Object.keys(all).filter((k) => k.startsWith(prefix));
  if (keys.length) await chrome.storage.local.remove(keys);
}
