/**
 * Locale-aware formatting. English uses en-GB conventions (the demo
 * organisation reports in EUR from Spain); Spanish uses es-ES.
 * ``null``/``undefined`` render as an em dash, never as zero.
 */
import type { Locale } from "../i18n/core";

export const DASH = "—";

export function localeTag(locale: Locale): string {
  return locale === "es" ? "es-ES" : "en-GB";
}

type Num = number | null | undefined;

const cache = new Map<string, Intl.NumberFormat>();
function nf(locale: Locale, opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = locale + JSON.stringify(opts);
  let f = cache.get(key);
  if (!f) {
    f = new Intl.NumberFormat(localeTag(locale), opts);
    cache.set(key, f);
  }
  return f;
}

export function formatCurrency(v: Num, locale: Locale, currency = "EUR", opts: { compact?: boolean; decimals?: number } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  if (opts.compact && Math.abs(v) >= 10_000) {
    return nf(locale, { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }).format(v);
  }
  const d = opts.decimals ?? (Math.abs(v) < 10 && v !== 0 ? 2 : 0);
  return nf(locale, { style: "currency", currency, minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
}

export function formatUnitCost(v: Num, locale: Locale, currency = "EUR"): string {
  if (v === null || v === undefined) return DASH;
  return nf(locale, { style: "currency", currency, minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(v);
}

export function formatNumber(v: Num, locale: Locale, decimals = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  return nf(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(v);
}

export function formatCompact(v: Num, locale: Locale): string {
  if (v === null || v === undefined) return DASH;
  if (Math.abs(v) < 10_000) return formatNumber(v, locale);
  return nf(locale, { notation: "compact", maximumFractionDigits: 1 }).format(v);
}

/** ``ratio`` is a fraction (0.25 → 25 %). */
export function formatRatio(ratio: Num, locale: Locale, decimals = 1): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return DASH;
  return nf(locale, { style: "percent", minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(ratio);
}

/** ``pct`` is already a percentage (25 → 25 %). */
export function formatPct(pct: Num, locale: Locale, decimals = 1): string {
  if (pct === null || pct === undefined) return DASH;
  return formatRatio(pct / 100, locale, decimals);
}

export function formatSigned(text: string, v: Num): string {
  if (v === null || v === undefined || v <= 0 || text === DASH) return text;
  return `+${text}`;
}

export function formatDate(iso: string | null | undefined, locale: Locale, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }): string {
  if (!iso) return DASH;
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Intl.DateTimeFormat(localeTag(locale), { ...opts, timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, d)));
}

export function formatShortDate(iso: string | null | undefined, locale: Locale): string {
  return formatDate(iso, locale, { day: "numeric", month: "short" });
}
