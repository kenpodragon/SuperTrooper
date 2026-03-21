import { useState, useEffect, useCallback } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import type { HealthStatus } from "@shared/types";

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await sendToBackground<HealthStatus>(MSG.HEALTH_CHECK);
      setHealth(result);
    } catch (err) {
      console.warn("[SuperTroopers] Health check failed:", err);
      setHealth({ connected: false, version: "", services: {} } as HealthStatus);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { health, loading, refresh };
}

export function usePipeline() {
  const [pipeline, setPipeline] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    sendToBackground<Record<string, number>>(MSG.GET_PIPELINE)
      .then((data) => {
        setPipeline(data);
      })
      .catch((err) => {
        console.warn("[SuperTroopers] Pipeline fetch failed:", err);
        setPipeline({});
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return { pipeline, loading };
}
