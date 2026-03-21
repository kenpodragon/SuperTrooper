import { handleMessage } from "./messages";
import { setupAlarms, handleAlarm, runHealthCheck, updateBadge } from "./alarms";
import { checkAiAvailability, isMcpAvailable } from "./mcpState";

chrome.runtime.onInstalled.addListener(() => {
  console.log("[SuperTroopers] Extension installed");
  setupAlarms();
  runHealthCheck();
  updateBadge();
  checkAiAvailability();
});

chrome.runtime.onStartup.addListener(() => {
  console.log("[SuperTroopers] Browser started");
  setupAlarms();
  runHealthCheck();
  updateBadge();
  checkAiAvailability();
});

chrome.runtime.onMessage.addListener(handleMessage);
chrome.alarms.onAlarm.addListener(handleAlarm);

export { isMcpAvailable };
