import { useState, useEffect, useCallback } from "react";
import { sendToBackground, MSG } from "@shared/messages";
import type { HealthStatus } from "@shared/types";

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    const result = await sendToBackground<HealthStatus>(MSG.HEALTH_CHECK);
    setHealth(result);
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { health, loading, refresh };
}

export function usePipeline() {
  const [pipeline, setPipeline] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    sendToBackground<Record<string, number>>(MSG.GET_PIPELINE).then((data) => {
      setPipeline(data);
      setLoading(false);
    });
  }, []);

  return { pipeline, loading };
}
