"use client";

import { useState, useEffect, useCallback } from "react";
import {
  checkBackendHealth,
  checkDatabaseHealth,
  type HealthState,
} from "@/lib/api";

const POLL_INTERVAL_MS = 15_000; // re-check every 15 seconds

export function useHealthCheck(): HealthState & { refresh: () => void } {
  const [state, setState] = useState<HealthState>({
    backend: "checking",
    database: "checking",
    backendDetail: "Checking…",
    databaseDetail: "Checking…",
  });

  const run = useCallback(async () => {
    // Reset to checking state on each run
    setState((prev) => ({
      ...prev,
      backend: "checking",
      database: "checking",
      backendDetail: "Checking…",
      databaseDetail: "Checking…",
    }));

    // Backend check
    try {
      const data = await checkBackendHealth();
      setState((prev) => ({
        ...prev,
        backend: data.status === "ok" ? "ok" : "error",
        backendDetail: data.status === "ok" ? "Connected" : `Unexpected status: ${data.status}`,
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unreachable";
      setState((prev) => ({
        ...prev,
        backend: "error",
        backendDetail: msg,
      }));
    }

    // Database check
    try {
      const data = await checkDatabaseHealth();
      setState((prev) => ({
        ...prev,
        database: data.database === "connected" ? "ok" : "error",
        databaseDetail:
          data.database === "connected" ? "Connected" : data.database,
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unreachable";
      setState((prev) => ({
        ...prev,
        database: "error",
        databaseDetail: msg,
      }));
    }
  }, []);

  useEffect(() => {
    run();
    const interval = setInterval(run, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [run]);

  return { ...state, refresh: run };
}
