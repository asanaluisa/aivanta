"use client";

import { useRouter } from "next/navigation";

import { useMeta } from "@/components/AppShell";
import { KpiCard } from "@/components/KpiCard";
import { BridgeChart, ChartFrame, ColumnChart, HBarChart, Meter, TimeSeriesChart, type BridgeStep } from "@/components/charts";
import { BUDGET_TONE, Card, DataTable, EmptyState, ErrorState, Loading, PageHeader, SectionTitle, StatusPill, cx } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { useFilters } from "@/lib/filtersContext";
import type { Breakdown, Dashboard, Overview, Roi } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

export function labelFor(t: (k: string) => string, dimension: Breakdown["dimension"], key: string): string {
  if (dimension === "department") return t(`department.${key}`);
  if (dimension === "use_case") return t(`use_case.${key}`);
  if (dimension === "provider") return t(`provider.${key}`);
  return key;
}

function Verdict({ o }: { o: Overview }) {
  const { t } = useI18n();
  const fmt = useFormat(o.currency);
  if (!o.roi_applicable) {
    return <p className="rounded-lg border border-line bg-subtle px-4 py-3 text-sm text-ink-2">{t("filters.roi_not_applicable")}</p>;
  }
  const roi = o.roi;
  if (!roi || roi.roi_pct === null) {
    return <p className="rounded-lg border border-[#f1dca6] bg-warning-soft px-4 py-3 text-sm text-warning-ink">{t("dashboard.verdict_insufficient")}</p>;
  }
  const positive = roi.roi_pct >= 0;
  const pct = fmt.pct(roi.roi_pct);
  return (
    <div className={cx("rounded-lg border px-4 py-3 text-sm", positive ? "border-[#bfe0bf] bg-good-soft" : "border-[#f0cbbb] bg-serious-soft")}>
      <p className={cx("font-medium", positive ? "text-good-ink" : "text-serious-ink")}>
        {t(positive ? "dashboard.verdict_positive" : "dashboard.verdict_negative", { roi: pct })}
      </p>
      {o.insufficient_use_cases.length > 0 && (
        <p className="mt-1 text-ink-2">
          {t("dashboard.verdict_partial", { list: o.insufficient_use_cases.map((u) => t(`use_case.${u}`)).join(", ") })}
        </p>
      )}
    </div>
  );
}

export function bridgeSteps(roi: Roi, t: (k: string) => string): BridgeStep[] {
  const steps: BridgeStep[] = [];
  if (roi.benefits.verified_component > 0) steps.push({ key: "verified", label: t("bridge.verified"), value: roi.benefits.verified_component, kind: "benefit" });
  if (roi.benefits.supported_component > 0) steps.push({ key: "supported", label: t("bridge.supported"), value: roi.benefits.supported_component, kind: "benefit" });
  const order = ["model_usage", "subscription", "infrastructure", "implementation", "maintenance", "human_review", "rework", "other_operating"] as const;
  for (const k of order) {
    if (roi.costs[k] > 0) steps.push({ key: k, label: t(`cost_category.${k}`), value: roi.costs[k], kind: "cost" });
  }
  steps.push({ key: "net", label: t("bridge.net"), value: roi.gross_benefit - roi.costs.total, kind: "total" });
  return steps;
}

export function Scenarios({ roi, currency }: { roi: Roi; currency: string }) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  const list = (["conservative", "expected", "optimistic"] as const).map((k) => roi.scenarios[k]).filter(Boolean);
  if (!list.length) return <EmptyState />;
  const max = Math.max(...list.map((s) => Math.abs(s!.roi_pct ?? 0)), 1);
  return (
    <ul className="space-y-4">
      {list.map((s) => (
        <li key={s!.name}>
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium text-ink">{t(`scenario.${s!.name}`)}</span>
            <span className={cx("tabular font-semibold", (s!.roi_pct ?? 0) < 0 ? "text-critical-ink" : "text-ink")}>{fmt.byUnit(s!.roi_pct, "percent")}</span>
          </div>
          <div className="relative mt-1 h-2 rounded-full bg-subtle">
            <div className="absolute top-0 h-2 w-px bg-axis" style={{ left: "50%" }} />
            <div
              className="absolute top-0 h-2 rounded-full"
              style={{
                background: (s!.roi_pct ?? 0) < 0 ? "var(--color-s2)" : "var(--color-s1)",
                left: (s!.roi_pct ?? 0) < 0 ? `${50 - (Math.abs(s!.roi_pct ?? 0) / max) * 50}%` : "50%",
                width: `${(Math.abs(s!.roi_pct ?? 0) / max) * 50}%`,
              }}
            />
          </div>
          <p className="mt-1 text-[11px] text-muted">
            {fmt.money(s!.gross_benefit, true)} − {fmt.money(s!.total_cost, true)} = {fmt.money(s!.net_benefit, true)}
            {s!.includes_estimates && <span className="ml-1 font-medium text-warning-ink">· {t("scenario.includes_estimates")}</span>}
          </p>
        </li>
      ))}
    </ul>
  );
}

export function DashboardView() {
  const { t } = useI18n();
  const meta = useMeta();
  const router = useRouter();
  const { query, update } = useFilters();
  const { data, error, loading, reload } = useApi<Dashboard>(`/api/dashboard${query()}`);
  const fmt = useFormat(meta.currency);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return loading ? <Loading rows={4} /> : <EmptyState />;

  const o = data.overview;
  const k = o.kpis;
  const hasUsage = (k.requests.value ?? 0) > 0;
  const drill = (dimension: Breakdown["dimension"], key: string) => {
    if (dimension === "department") { update({ departments: [key] }); router.push("/departments"); }
    else if (dimension === "use_case") { if (key !== "unallocated") router.push(`/use-cases/${key}`); }
    else if (dimension === "provider") { update({ providers: [key] }); router.push("/costs"); }
    else { update({ models: [key.split("/")[1] ?? key] }); router.push("/costs"); }
  };

  return (
    <>
      <PageHeader
        title={t("dashboard.title")}
        subtitle={t("dashboard.subtitle")}
        meta={`${t("app.period", { start: fmt.date(o.period.start), end: fmt.date(o.period.end) })} · ${t("app.days", { count: o.period.days })}`}
      />
      <Verdict o={o} />

      <SectionTitle>{t("dashboard.section_value")}</SectionTitle>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard kpi={k.roi_pct} emphasis href="/outcomes" currency={o.currency}
          empty={<span className="text-base">{t(`roi_status.${o.roi_status}`)}</span>}
          sub={o.roi?.benefit_cost_ratio != null ? `${t("metric.benefit_cost_ratio.label")}: ${fmt.num(o.roi.benefit_cost_ratio, 2)}` : undefined} />
        <KpiCard kpi={k.net_benefit} href="/outcomes" currency={o.currency}
          sub={o.roi?.payback_months != null ? `${t("metric.payback.label")}: ${t("units.months", { value: fmt.num(o.roi.payback_months, 1) })}` : undefined} />
        <KpiCard kpi={k.gross_benefit} href="/outcomes" currency={o.currency} />
        <KpiCard kpi={k.verified_savings} href="/outcomes" currency={o.currency} />
        <KpiCard kpi={k.total_ai_cost} href="/costs" currency={o.currency} />
        <KpiCard kpi={k.cost_per_successful_task} href="/comparison" currency={o.currency}
          sub={o.roi ? t("units.tasks", { value: fmt.num(o.roi.successful_tasks) }) : undefined} />
        <KpiCard kpi={k.hours_saved} href="/comparison" currency={o.currency}
          sub={k.hours_saved.net != null ? t("metric.net_hours", { value: `${fmt.num(k.hours_saved.net)} h` }) : undefined} />
        <KpiCard kpi={k.estimated_total_value} currency={o.currency} />
      </div>

      <SectionTitle>{t("dashboard.section_spend")}</SectionTitle>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard kpi={k.ai_spend} href="/costs" currency={o.currency} />
        <KpiCard kpi={{ ...k.input_tokens, value: (k.input_tokens.value ?? 0) + (k.output_tokens.value ?? 0), definition_key: "metric.total_tokens" }} href="/costs"
          sub={`${t("metric.input_tokens.label")} ${fmt.compact(k.input_tokens.value)} · ${t("metric.output_tokens.label")} ${fmt.compact(k.output_tokens.value)} · ${t("metric.cached_input_tokens.label")} ${fmt.compact(k.cached_input_tokens.value)}`} />
        <KpiCard kpi={k.requests} href="/costs" sub={`${t("metric.error_rate.label")}: ${fmt.ratio(k.error_rate.value)}`} />
        <KpiCard kpi={k.active_users} href="/departments" sub={`${t("metric.active_departments.label")}: ${fmt.num(k.active_departments.value)}`} />
      </div>

      {!hasUsage ? <div className="mt-6"><EmptyState /></div> : (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2" title={t("dashboard.spend_trend")} description={t("dashboard.spend_trend_desc")}>
              <ChartFrame
                chart={<TimeSeriesChart points={data.trend.rows.map((r) => ({ date: r.date, value: r.spend }))} highlights={data.trend.anomalies.map((a) => a.date)}
                  highlightLabel={t("dashboard.anomaly")} format={(v) => fmt.money(v, true)} formatDate={fmt.shortDate} label={t("dashboard.spend_trend")} />}
                table={<DataTable caption={t("dashboard.spend_trend")} rowKey={(r) => r.date} rows={data.trend.rows}
                  columns={[{ key: "d", header: t("table.date"), cell: (r) => fmt.date(r.date) },
                    { key: "s", header: t("table.spend"), cell: (r) => fmt.money2(r.spend), align: "right" },
                    { key: "q", header: t("table.requests"), cell: (r) => fmt.num(r.requests), align: "right" },
                    { key: "u", header: t("table.users"), cell: (r) => fmt.num(r.active_users), align: "right" }]} />}
              />
            </Card>
            <Card title={t("dashboard.budgets")} description={t("dashboard.budgets_desc", { date: fmt.date(data.budgets.as_of) })}>
              {data.budgets.rows.length === 0 ? <EmptyState /> : (
                <ul className="space-y-4">
                  {data.budgets.rows.map((b) => (
                    <li key={b.budget_id}>
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="font-medium text-ink">{t(`department.${b.department}`)}</span>
                        <StatusPill tone={BUDGET_TONE[b.status]}>{t(`budget_status.${b.status}`)}</StatusPill>
                      </div>
                      <div className="mt-1.5">
                        <Meter value={b.utilization ?? 0} marker={b.forecast_utilization} label={t("metric.budget_utilization.label")}
                          tone={b.status === "exceeded" ? "critical" : b.status === "ok" ? "neutral" : "warning"} />
                      </div>
                      <p className="tabular mt-1 text-[11px] text-muted">
                        {t("dashboard.spent")} {fmt.money(b.spent)} {t("app.of")} {fmt.money(b.budget)} · {fmt.ratio(b.utilization, 0)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          {o.roi && o.roi.status === "ok" && (
            <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
              <Card className="xl:col-span-2" title={t("dashboard.roi_bridge")} description={t("dashboard.roi_bridge_desc")}>
                <ChartFrame
                  chart={<BridgeChart steps={bridgeSteps(o.roi, t)} format={(v) => fmt.money(v, true)} label={t("dashboard.roi_bridge")} />}
                  table={<DataTable caption={t("dashboard.roi_bridge")} rowKey={(r) => r.key} rows={bridgeSteps(o.roi, t)}
                    columns={[{ key: "l", header: t("table.name"), cell: (r) => r.label },
                      { key: "v", header: t("table.value"), cell: (r) => `${r.kind === "cost" ? "−" : ""}${fmt.money(r.value)}`, align: "right" }]} />}
                />
              </Card>
              <Card title={t("dashboard.scenarios")} description={t("dashboard.scenarios_desc")}>
                <Scenarios roi={o.roi} currency={o.currency} />
              </Card>
            </div>
          )}

          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {(["department", "use_case", "provider", "model"] as const).map((dim) => (
              <Card key={dim} title={t(`dashboard.by_${dim}`)}>
                <HBarChart label={t(`dashboard.by_${dim}`)} format={(v) => fmt.money(v, true)} onSelect={(key) => drill(dim, key)}
                  rows={data.breakdowns[dim].rows.map((r) => ({ key: r.key, label: labelFor(t, dim, r.key), value: r.spend, detail: fmt.ratio(r.share) }))} />
              </Card>
            ))}
          </div>

          <div className="mt-4">
            <Card title={t("dashboard.adoption_trend")} description={t("dashboard.adoption_trend_desc")}>
              <ChartFrame
                chart={<ColumnChart label={t("dashboard.adoption_trend")} format={(v) => fmt.ratio(v, 0)}
                  rows={data.adoption.rows.map((r) => ({ key: r.week_start, label: fmt.shortDate(r.week_start), value: r.adoption_rate }))} />}
                table={<DataTable caption={t("dashboard.adoption_trend")} rowKey={(r) => r.week_start} rows={data.adoption.rows}
                  columns={[{ key: "w", header: t("table.week"), cell: (r) => fmt.date(r.week_start) },
                    { key: "a", header: t("table.users"), cell: (r) => `${fmt.num(r.active_users)} / ${fmt.num(r.eligible_users)}`, align: "right" },
                    { key: "r", header: t("metric.adoption.label"), cell: (r) => fmt.ratio(r.adoption_rate), align: "right" }]} />}
              />
            </Card>
          </div>
        </>
      )}
    </>
  );
}
