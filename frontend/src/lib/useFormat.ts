"use client";

import { useMemo } from "react";

import { useI18n } from "@/i18n/I18nProvider";

import * as F from "./format";
import type { Unit } from "./types";

/** Formatters bound to the active locale and the organisation currency. */
export function useFormat(currency = "EUR") {
  const { locale } = useI18n();
  return useMemo(
    () => ({
      locale,
      money: (v: number | null | undefined, compact = false) => F.formatCurrency(v, locale, currency, { compact }),
      money2: (v: number | null | undefined) => F.formatCurrency(v, locale, currency, { decimals: 2 }),
      unitCost: (v: number | null | undefined) => F.formatUnitCost(v, locale, currency),
      num: (v: number | null | undefined, d = 0) => F.formatNumber(v, locale, d),
      compact: (v: number | null | undefined) => F.formatCompact(v, locale),
      ratio: (v: number | null | undefined, d = 1) => F.formatRatio(v, locale, d),
      pct: (v: number | null | undefined, d = 1) => F.formatPct(v, locale, d),
      date: (v: string | null | undefined) => F.formatDate(v, locale),
      shortDate: (v: string | null | undefined) => F.formatShortDate(v, locale),
      byUnit: (v: number | null | undefined, unit: Unit) => {
        switch (unit) {
          case "currency": return F.formatCurrency(v, locale, currency, { compact: true });
          case "ratio": return F.formatRatio(v, locale);
          case "decimal": return F.formatNumber(v, locale, v !== null && v !== undefined && Math.abs(v) >= 100 ? 0 : 2);
          case "percent": return F.formatSigned(F.formatPct(v, locale), v);
          case "hours": return v === null || v === undefined ? F.DASH : `${F.formatNumber(v, locale)} h`;
          default: return F.formatCompact(v, locale);
        }
      },
    }),
    [locale, currency],
  );
}
