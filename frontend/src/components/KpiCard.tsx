"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useI18n } from "@/i18n/I18nProvider";
import type { Kpi } from "@/lib/types";
import { useFormat } from "@/lib/useFormat";

import { BasisBadge, InfoTip, cx } from "./ui";

/**
 * One headline metric: value, provenance badge, "how is this calculated"
 * tooltip and an optional drill-down link.
 */
export function KpiCard({ kpi, labelKey, href, sub, currency, emphasis, empty }: {
  kpi: Kpi; labelKey?: string; href?: string; sub?: ReactNode; currency?: string; emphasis?: boolean; empty?: ReactNode;
}) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  const key = labelKey ?? kpi.definition_key;
  const value = kpi.value;
  const negative = typeof value === "number" && value < 0 && (kpi.unit === "currency" || kpi.unit === "percent");
  return (
    <div className={cx("flex min-w-0 flex-col rounded-lg border bg-surface p-4", emphasis ? "border-brand/30 ring-1 ring-brand/10" : "border-line")}>
      <div className="flex items-start justify-between gap-2">
        <span className="flex min-w-0 items-start gap-1.5 text-xs font-medium leading-snug text-ink-2">
          <span className="line-clamp-2">{t(`${key}.label`)}</span>
          <InfoTip label={`${t("app.definition")}: ${t(`${key}.label`)}`}>
            <span className="mb-1 block font-semibold text-ink">{t("app.definition")}</span>
            {t(`${key}.definition`)}
          </InfoTip>
        </span>
        <BasisBadge basis={kpi.basis} />
      </div>
      <div className={cx("tabular mt-3 text-2xl font-semibold tracking-tight", negative ? "text-critical-ink" : "text-ink", value === null && "text-muted")}>
        {value === null ? (empty ?? "—") : fmt.byUnit(value, kpi.unit)}
      </div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
      {href && (
        <Link href={href} className="mt-auto pt-3 text-xs font-medium text-accent hover:underline">
          {t("app.drill_down")} →
        </Link>
      )}
    </div>
  );
}
