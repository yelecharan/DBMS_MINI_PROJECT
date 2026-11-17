"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

/** Load data from the API, re-fetching whenever the path or query changes. */
export function useApi<T>(path: string | null, query?: Record<string, string | number | undefined>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(query ?? {});

  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api.get<T>(path, JSON.parse(key)));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [path, key]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload, setError };
}
