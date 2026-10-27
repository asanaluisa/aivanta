/** Global analysis filters and their query-string encoding (pure, unit-tested). */

export interface FilterState {
  start: string | null;
  end: string | null;
  departments: string[];
  providers: string[];
  models: string[];
  useCases: string[];
}

export const EMPTY_FILTERS: FilterState = {
  start: null,
  end: null,
  departments: [],
  providers: [],
  models: [],
  useCases: [],
};

export function toQuery(f: FilterState, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams();
  if (f.start) p.set("start", f.start);
  if (f.end) p.set("end", f.end);
  if (f.departments.length) p.set("departments", f.departments.join(","));
  if (f.providers.length) p.set("providers", f.providers.join(","));
  if (f.models.length) p.set("models", f.models.join(","));
  if (f.useCases.length) p.set("use_cases", f.useCases.join(","));
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

export function activeCount(f: FilterState): number {
  return (
    (f.start || f.end ? 1 : 0) +
    (f.departments.length ? 1 : 0) +
    (f.providers.length ? 1 : 0) +
    (f.models.length ? 1 : 0) +
    (f.useCases.length ? 1 : 0)
  );
}

/** ISO date ``days`` before ``end`` (inclusive window of ``days`` days). */
export function windowStart(end: string, days: number): string {
  const [y, m, d] = end.split("-").map(Number);
  const t = Date.UTC(y, m - 1, d) - (days - 1) * 86_400_000;
  return new Date(t).toISOString().slice(0, 10);
}
