import { handleMessage } from "./messages";
import { setupAlarms, handleAlarm, runHealthCheck } from "./alarms";
import { checkAiAvailability, isMcpAvailable } from "./mcpState";
import { setupNotificationPolling, refreshBadge } from "./notifications";

chrome.runtime.onInstalled.addListener(() => {
  console.log("[SuperTroopers] Extension installed");
  setupAlarms();
  setupNotificationPolling();
  runHealthCheck();
  refreshBadge();
  checkAiAvailability();
});

chrome.runtime.onStartup.addListener(() => {
  console.log("[SuperTroopers] Browser started");
  setupAlarms();
  setupNotificationPolling();
  runHealthCheck();
  refreshBadge();
  checkAiAvailability();
});

chrome.runtime.onMessage.addListener(handleMessage);
chrome.alarms.onAlarm.addListener(handleAlarm);

export { isMcpAvailable };
