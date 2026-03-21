import { apiPost } from "./api";

let mcpAvailable = false;

/** Check AI provider availability on startup. */
export async function checkAiAvailability(): Promise<void> {
  try {
    const resp = await apiPost<{ ai_available?: boolean; provider?: string }>(
      "/api/settings/test-ai",
      {}
    );
    mcpAvailable = !!resp?.ai_available;
    console.log(`[SuperTroopers] MCP/AI available: ${mcpAvailable}`);
  } catch {
    mcpAvailable = false;
    console.log("[SuperTroopers] MCP/AI check failed, disabled for session");
  }
}

/** Query current MCP state. */
export function isMcpAvailable(): boolean {
  return mcpAvailable;
}

/** Disable MCP for the rest of this session (called on AI failure). */
export function disableMcp(): void {
  mcpAvailable = false;
  console.log("[SuperTroopers] MCP/AI disabled for this session (failure)");
}
