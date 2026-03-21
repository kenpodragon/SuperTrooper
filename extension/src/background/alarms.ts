import { checkHealth, getPipelineSummary } from "./api";
import { cacheSet } from "./cache";

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
  }
}

export async function runHealthCheck() {
  const health = await checkHealth();
  await cacheSet("health", { ...health, timestamp: Date.now() }, 10);
  const color = health.connected ? "#00FF41" : "#ff4444";
  chrome.action.setBadgeBackgroundColor({ color });
  if (!health.connected) {
    chrome.action.setBadgeText({ text: "!" });
  } else {
    chrome.action.setBadgeText({ text: "" });
  }
}

export async function updateBadge() {
  const summary = await getPipelineSummary();
  if (!summary) return;
  const counts = summary as Record<string, number>;
  const active = (counts.applied || 0) + (counts.interviewing || 0) + (counts.phone_screen || 0);
  chrome.action.setBadgeText({ text: active > 0 ? String(active) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#00FF41" });
  await cacheSet("pipeline", summary, 30);
}
