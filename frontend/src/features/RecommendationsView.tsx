"use client";

import Link from "next/link";
import { useState } from "react";

import { useMeta } from "@/components/AppShell";
import { BasisBadge, Button, EmptyState, ErrorState, Loading, PageHeader, SEVERITY_TONE, StatusPill } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFilters } from "@/lib/filtersContext";
import type { Recommendation } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

const MONEY = /(spend|budget|saving|cost|benefit|spent|forecast$)/;
const RATIO = /(rate|ratio|share|growth|utilization|quality)/;

export function useMetricFormatter(currency: string) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  return (name: string, value: unknown): string => {
    if (value === null || value === undefined) return "—";
    if (Array.isArray(value)) return value.map((v) => (typeof v === "string" ? t(`reason.${v.split(":")[0]}`) : String(v))).join(" · ");
    if (typeof value === "string") {
      if (name === "decision") return t(`decision.${value}`);
      if (name === "task_complexity") return t(`complexity.${value}`);
      if (name === "assumption") return t(`rec_metric.${value}`);
      if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return fmt.date(value);
      return value;
    }
    if (typeof value !== "number") return String(value);
    if (name === "roi_pct") return fmt.byUnit(value, "percent");
    if (name === "zscore") return fmt.num(value, 1);
    if (name === "cost_per_task_delta") return fmt.money2(value);
    if (name === "quality_delta") return t("units.pp", { value: fmt.num(value * 100, 1) });
    if (name.includes("minutes")) return t("units.minutes", { value: fmt.num(value, 1) });
    if (name.includes("tokens")) return fmt.compact(value);
    if (name === "ai_tasks") return fmt.num(value);
    if (RATIO.test(name)) return fmt.ratio(value);
    if (MONEY.test(name)) return fmt.money(value);
    return fmt.num(value, 2);
  };
}

export function scopeLabel(t: (k: string) => string, r: Recommendation, formatDate: (d: string) => string): string {
  if (r.scope_type === "use_case") return t(`use_case.${r.scope_id}`);
  if (r.scope_type === "department" || r.scope_type === "budget") return t(`department.${r.scope_id}`);
  if (/^\d{4}-\d{2}-\d{2}$/.test(r.scope_id)) return formatDate(r.scope_id);
  return t("department.organization");
}

function RecCard({ r, currency, onAck, canAck }: { r: Recommendation; currency: string; onAck: (r: Recommendation) => void; canAck: boolean }) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  const metric = useMetricFormatter(currency);
  const scope = scopeLabel(t, r, fmt.date);
  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <StatusPill tone={SEVERITY_TONE[r.severity]}>{t(`severity.${r.severity}`)}</StatusPill>
          <h2 className="mt-2 text-sm font-semibold text-ink">{t(`${r.message_key}.title`, { scope })}</h2>
          <p className="mt-1 max-w-3xl text-sm text-ink-2">{t(`${r.message_key}.body`)}</p>
        </div>
        {r.acknowledged ? (
          <span className="text-xs font-medium text-good-ink">✓ {t("recommendations.acknowledged")}</span>
        ) : canAck ? (
          <Button onClick={() => onAck(r)}>{t("recommendations.acknowledge")}</Button>
        ) : null}
      </div>
      {r.projected_monthly_saving != null && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
          {t("recommendations.projected", { value: fmt.money(r.projected_monthly_saving) })}
          <BasisBadge basis="estimated" />
        </p>
      )}
      <details className="mt-3 group">
        <summary className="cursor-pointer text-xs font-medium text-accent">{t("recommendations.supporting")}</summary>
        <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(r.metrics).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 border-b border-line/60 py-1">
              <dt className="text-muted">{t(`rec_metric.${k}`)}</dt>
              <dd className="tabular text-right text-ink">{metric(k, v)}</dd>
            </div>
          ))}
        </dl>
      </details>
      {r.scope_type === "use_case" && (
        <Link href={`/use-cases/${r.scope_id}`} className="mt-3 inline-block text-xs font-medium text-accent hover:underline">{t("app.drill_down")} →</Link>
      )}
    </article>
  );
}

export function RecommendationsView() {
  const { t } = useI18n();
  const meta = useMeta();
  const { token, me } = useAuth();
  const { query } = useFilters();
  const { data, error, reload } = useApi<{ rows: Recommendation[] }>(`/api/recommendations${query()}`);
  const [showAcked, setShowAcked] = useState(false);
  const canAck = !!me && me.role !== "viewer";

  const ack = async (r: Recommendation) => {
    await apiFetch("/api/alerts/acknowledge", token, {
      method: "POST",
      body: JSON.stringify({ rule_id: r.rule_id, scope_type: r.scope_type, scope_key: r.scope_id, severity: r.severity }),
    }).catch(() => undefined);
    reload();
  };

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const rows = data.rows.filter((r) => showAcked || !r.acknowledged);

  return (
    <>
      <PageHeader title={t("recommendations.title")} subtitle={t("recommendations.subtitle")}
        actions={<label className="flex items-center gap-2 text-xs text-ink-2">
          <input type="checkbox" checked={showAcked} onChange={(e) => setShowAcked(e.target.checked)} />
          {t("recommendations.show_acknowledged")}
        </label>} />
      {rows.length === 0 ? <EmptyState title={t("recommendations.none")} body=" " /> : (
        <div className="space-y-3">
          {rows.map((r) => <RecCard key={`${r.rule_id}:${r.scope_type}:${r.scope_id}`} r={r} currency={meta.currency} onAck={ack} canAck={canAck} />)}
        </div>
      )}
    </>
  );
}
