import { checkHealth, getPipelineSummary } from "./api";
import { cacheSet } from "./cache";
import { handleNotificationAlarm, getUnreadCount } from "./notifications";

export const ALARMS = {
  HEALTH_CHECK: "health-check",
  BADGE_UPDATE: "badge-update",
} as const;

export function setupAlarms() {
  chrome.alarms.create(ALARMS.HEALTH_CHECK, { periodInMinutes: 5 });
  chrome.alarms.create(ALARMS.BADGE_UPDATE, { periodInMinutes: 30 });
}

export async function handleAlarm(alarm: chrome.alarms.Alarm) {
  switch (alarm.name) {
    case ALARMS.HEALTH_CHECK:
      await runHealthCheck();
      break;
    case ALARMS.BADGE_UPDATE:
      await updateBadge();
      break;
    default:
      // Delegate notification alarm
      await handleNotificationAlarm(alarm.name);
      break;
  }
}

export async function runHealthCheck() {
  const health = await checkHealth();
  await cacheSet("health", { ...health, timestamp: Date.now() }, 10);
  if (!health.connected) {
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#ff4444" });
  } else {
    // When healthy, show notification count instead of clearing badge
    const unread = await getUnreadCount();
    const text = unread > 0 ? (unread > 99 ? "99+" : String(unread)) : "";
    chrome.action.setBadgeText({ text });
    chrome.action.setBadgeBackgroundColor({ color: "#00FF41" });
  }
}

export async function updateBadge() {
  const summary = await getPipelineSummary();
  if (!summary) return;
  const counts = summary as Record<string, number>;
  const active = (counts.applied || 0) + (counts.interviewing || 0) + (counts.phone_screen || 0);
  // Prefer notification count if there are unread notifications
  const unread = await getUnreadCount();
  const displayCount = unread > 0 ? unread : active;
  chrome.action.setBadgeText({ text: displayCount > 0 ? String(displayCount) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#00FF41" });
  await cacheSet("pipeline", summary, 30);
}
