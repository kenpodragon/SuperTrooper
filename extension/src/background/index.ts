import { handleMessage } from "./messages";
import { setupAlarms, handleAlarm, runHealthCheck, updateBadge } from "./alarms";

chrome.runtime.onInstalled.addListener(() => {
  console.log("[SuperTroopers] Extension installed");
  setupAlarms();
  runHealthCheck();
  updateBadge();
});

chrome.runtime.onStartup.addListener(() => {
  console.log("[SuperTroopers] Browser started");
  setupAlarms();
  runHealthCheck();
  updateBadge();
});

chrome.runtime.onMessage.addListener(handleMessage);
chrome.alarms.onAlarm.addListener(handleAlarm);
