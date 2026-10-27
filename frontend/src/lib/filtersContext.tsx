"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { EMPTY_FILTERS, toQuery, type FilterState } from "./filters";

const KEY = "aivanta.filters";

interface Filters {
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  update: (patch: Partial<FilterState>) => void;
  query: (extra?: Record<string, string>) => string;
}

const FiltersContext = createContext<Filters | null>(null);

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<FilterState>(EMPTY_FILTERS);

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(KEY);
      if (raw) setState({ ...EMPTY_FILTERS, ...JSON.parse(raw) });
    } catch {
      /* ignore */
    }
  }, []);

  const setFilters = useCallback((f: FilterState) => {
    setState(f);
    try {
      window.sessionStorage.setItem(KEY, JSON.stringify(f));
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<Filters>(
    () => ({
      filters,
      setFilters,
      update: (patch) => setFilters({ ...filters, ...patch }),
      query: (extra) => toQuery(filters, extra),
    }),
    [filters, setFilters],
  );
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): Filters {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters must be used inside <FiltersProvider>");
  return ctx;
}
