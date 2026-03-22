// API client for communicating with the SuperTroopers backend
import { DEFAULT_CONFIG } from "./config";

async function getApiUrl(): Promise<string> {
  try {
    const result = await chrome.storage.local.get("settings");
    return result.settings?.apiUrl || DEFAULT_CONFIG.apiUrl;
  } catch {
    return DEFAULT_CONFIG.apiUrl;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = await getApiUrl();
  const url = `${baseUrl}${path}`;

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`API ${response.status}: ${errorText}`);
  }

  return response.json();
}
