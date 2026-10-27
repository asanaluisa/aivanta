"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, apiFetch } from "./api";
import { useAuth } from "./auth";

export interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** GET ``path`` with the session token; re-fetches when ``path`` changes. */
export function useApi<T>(path: string | null): ApiState<T> {
  const { token, logout } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [nonce, setNonce] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    if (!path || !token) return;
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    apiFetch<T>(path, token)
      .then((d) => {
        if (id === seq.current) setData(d);
      })
      .catch((e: unknown) => {
        if (id !== seq.current) return;
        const err = e instanceof ApiError ? e : new ApiError(0, "unknown");
        if (err.status === 401) logout();
        setError(err);
      })
      .finally(() => {
        if (id === seq.current) setLoading(false);
      });
  }, [path, token, nonce, logout]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}
