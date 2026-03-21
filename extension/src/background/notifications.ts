/**
 * notifications.ts — Chrome notification polling and badge count management.
 * Background service worker module (plain TS).
 */

const API_URL = "http://localhost:8055/api";
const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
const STORAGE_KEY = "notifications_last_seen";

interface Notification {
  id: number;
  message: string;
  type: string;
  read: boolean;
  created_at: string;
}

// --- API helpers ---

async function fetchUnreadNotifications(): Promise<Notification[]> {
  try {
    const res = await fetch(`${API_URL}/notifications?read=false`, {
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.notifications || data || [];
  } catch {
    return [];
  }
}

// --- Badge ---

async function refreshBadge(): Promise<void> {
  const count = await getUnreadCount();
  const text = count > 0 ? (count > 99 ? "99+" : String(count)) : "";
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color: count > 0 ? "#00FF41" : "#1a1a2e" });
}

// --- Show Chrome notification ---

function showChromeNotification(n: Notification): void {
  chrome.notifications.create(`st-notif-${n.id}`, {
    type: "basic",
    iconUrl: "icons/icon48.png",
    title: "SuperTroopers",
    message: n.message,
    priority: 1,
  });
}

// --- Polling ---

async function poll(): Promise<void> {
  const notifications = await fetchUnreadNotifications();

  if (notifications.length === 0) {
    await refreshBadge();
    return;
  }

  // Read last-seen ID from storage
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  const lastSeenId: number = stored[STORAGE_KEY] || 0;

  // Show Chrome notifications for any newer than last seen
  const newNotifs = notifications.filter((n) => n.id > lastSeenId);

  for (const n of newNotifs) {
    showChromeNotification(n);
  }

  // Update last-seen to highest ID shown
  if (newNotifs.length > 0) {
    const maxId = Math.max(...newNotifs.map((n) => n.id));
    await chrome.storage.local.set({ [STORAGE_KEY]: maxId });
  }

  await refreshBadge();
}

// --- Public API ---

/**
 * Start polling /api/notifications every 5 minutes.
 * Shows Chrome notifications for new unread items and updates the badge count.
 */
export function setupNotificationPolling(): void {
  // Run immediately on setup
  poll().catch(console.error);

  // Use chrome.alarms for reliable MV3 polling
  chrome.alarms.create("st-notification-poll", {
    periodInMinutes: POLL_INTERVAL_MS / 60000,
  });
}

/**
 * Handle the notification poll alarm — call from the background alarm listener.
 */
export async function handleNotificationAlarm(alarmName: string): Promise<void> {
  if (alarmName === "st-notification-poll") {
    await poll();
  }
}

/**
 * Get current unread notification count from the API.
 */
export async function getUnreadCount(): Promise<number> {
  const notifications = await fetchUnreadNotifications();
  return notifications.length;
}

/**
 * Mark a notification as read via the API.
 */
export async function markNotificationRead(id: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/notifications/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ read: true }),
    });
    if (res.ok) await refreshBadge();
    return res.ok;
  } catch {
    return false;
  }
}
