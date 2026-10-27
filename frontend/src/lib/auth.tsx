"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { apiFetch } from "./api";
import type { Me } from "./types";

const TOKEN_KEY = "aivanta.token";

interface Auth {
  ready: boolean;
  token: string | null;
  me: Me | null;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
  can: (permission: string) => boolean;
  setMe: (me: Me) => void;
}

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(() => {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setToken(null);
    setMe(null);
  }, []);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    if (!stored) {
      setReady(true);
      return;
    }
    apiFetch<Me>("/api/auth/me", stored)
      .then((m) => {
        setToken(stored);
        setMe(m);
      })
      .catch(() => logout())
      .finally(() => setReady(true));
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<{ access_token: string; user: Me }>("/api/auth/login", null, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    try {
      window.localStorage.setItem(TOKEN_KEY, res.access_token);
    } catch {
      /* ignore */
    }
    setToken(res.access_token);
    setMe(res.user);
    return res.user;
  }, []);

  const value = useMemo<Auth>(
    () => ({
      ready,
      token,
      me,
      login,
      logout,
      setMe,
      can: (p) => !!me?.permissions.includes(p),
    }),
    [ready, token, me, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
