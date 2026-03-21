import type { SavedJob, GapAnalysisResult, JobExtraction } from "./types";

export const MSG = {
  HEALTH_CHECK: "HEALTH_CHECK",
  HEALTH_STATUS: "HEALTH_STATUS",
  GET_PIPELINE: "GET_PIPELINE",
  PIPELINE_DATA: "PIPELINE_DATA",
  SAVE_JOB: "SAVE_JOB",
  JOB_SAVED: "JOB_SAVED",
  CHECK_JOB_URL: "CHECK_JOB_URL",
  JOB_URL_STATUS: "JOB_URL_STATUS",
  RUN_GAP_ANALYSIS: "RUN_GAP_ANALYSIS",
  GAP_RESULT: "GAP_RESULT",
  PAGE_CONTEXT: "PAGE_CONTEXT",
  GET_SETTINGS: "GET_SETTINGS",
  SAVE_SETTINGS: "SAVE_SETTINGS",
  SETTINGS_DATA: "SETTINGS_DATA",
  GET_SAVED_JOBS: "GET_SAVED_JOBS",
  GET_MCP_STATUS: "GET_MCP_STATUS",
  APPLICATION_SUBMITTED: "APPLICATION_SUBMITTED",
  GET_APPLICATIONS: "GET_APPLICATIONS",
  UPDATE_APP_STATUS: "UPDATE_APP_STATUS",
  GET_NOTIFICATIONS: "GET_NOTIFICATIONS",
  MARK_NOTIFICATION_READ: "MARK_NOTIFICATION_READ",
  DISMISS_NOTIFICATION: "DISMISS_NOTIFICATION",
  GET_UNREAD_COUNT: "GET_UNREAD_COUNT",
  BATCH_START: "BATCH_START",
  BATCH_PAUSE: "BATCH_PAUSE",
  BATCH_RESUME: "BATCH_RESUME",
  BATCH_SKIP: "BATCH_SKIP",
  BATCH_JOB_STATUS: "BATCH_JOB_STATUS",
  BATCH_COMPLETE: "BATCH_COMPLETE",
  BATCH_GET_STATE: "BATCH_GET_STATE",
  ATS_DETECTED: "ATS_DETECTED",
  ATS_FILL: "ATS_FILL",
} as const;

export type MessageType = (typeof MSG)[keyof typeof MSG];

export interface Message<T = unknown> {
  type: MessageType;
  data?: T;
}

export function sendToBackground<T = unknown>(
  type: MessageType,
  data?: unknown
): Promise<T> {
  return chrome.runtime.sendMessage({ type, data });
}

export function sendToTab<T = unknown>(
  tabId: number,
  type: MessageType,
  data?: unknown
): Promise<T> {
  return chrome.tabs.sendMessage(tabId, { type, data });
}

export interface SaveJobPayload {
  job: JobExtraction;
}

export interface SaveJobResponse {
  saved_job: SavedJob;
  already_existed: boolean;
}

export interface CheckJobUrlPayload {
  url: string;
}

export interface CheckJobUrlResponse {
  exists: boolean;
  saved_job?: SavedJob;
}

export interface GapAnalysisPayload {
  jd_text: string;
  job_url: string;
  force_refresh?: boolean;
  saved_job_id?: number;
  mode?: "python" | "ai" | "auto";
}

export interface McpStatusResponse {
  available: boolean;
}

export interface GapAnalysisResponse {
  result: GapAnalysisResult;
  from_cache: boolean;
}

export interface GetSavedJobsResponse {
  jobs: SavedJob[];
}
