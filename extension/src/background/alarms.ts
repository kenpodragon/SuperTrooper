import { checkHealth } from "./api";
import { cacheSet } from "./cache";
import { handleNotificationAlarm, getUnreadCount } from "./notifications";

export const ALARMS = {
  HEALTH_CHECK: "health-check",
} as const;

export function setupAlarms() {
  chrome.alarms.create(ALARMS.HEALTH_CHECK, { periodInMinutes: 5 });
  // Badge updates are handled by the 5-min notification poll in notifications.ts.
  // No separate badge alarm needed.
}

export async function handleAlarm(alarm: chrome.alarms.Alarm) {
  switch (alarm.name) {
    case ALARMS.HEALTH_CHECK:
      await runHealthCheck();
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
    // When healthy, show notification count
    const unread = await getUnreadCount();
    const text = unread > 0 ? (unread > 99 ? "99+" : String(unread)) : "";
    chrome.action.setBadgeText({ text });
    chrome.action.setBadgeBackgroundColor({ color: "#00FF41" });
  }
}
