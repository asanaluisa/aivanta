"use client";

import Link from "next/link";

import { useMeta } from "@/components/AppShell";
import { KpiCard } from "@/components/KpiCard";
import { BridgeChart, ChartFrame } from "@/components/charts";
import {
  BasisBadge, Card, DECISION_TONE, DataTable, DefinitionList, EmptyState, ErrorState, Loading, PageHeader,
  RoiStatusPill, SectionTitle, StatusPill, cx,
} from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { useFilters } from "@/lib/filtersContext";
import type { Claim, Roi, UseCaseDetail, UseCaseRow } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

import { Scenarios, bridgeSteps } from "./DashboardView";

export function reasonText(t: (k: string, p?: Record<string, string | number>) => string, reason: string): string {
  if (reason.startsWith("favourable_segments:")) {
    const list = reason.split(":")[1].split(",").map((s) => t(`task_type.${s}`)).join(", ");
    return t("reason.favourable_segments", { list });
  }
  return t(`reason.${reason}`);
}

export function OutcomesView() {
  const { t } = useI18n();
  const meta = useMeta();
  const { query } = useFilters();
  const fmt = useFormat(meta.currency);
  const { data, error, reload } = useApi<{ rows: UseCaseRow[] }>(`/api/use-cases${query()}`);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Loading />;

  return (
    <>
      <PageHeader title={t("outcomes.title")} subtitle={t("outcomes.subtitle")} />
      {data.rows.length === 0 ? <EmptyState /> : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {data.rows.map((u) => (
            <Link key={u.use_case} href={`/use-cases/${u.use_case}`} className="group rounded-lg border border-line bg-surface p-4 hover:border-brand/40">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-semibold text-ink group-hover:text-brand">{t(`use_case.${u.use_case}`)}</h2>
                  <p className="mt-0.5 text-xs text-muted">
                    {t(`department.${u.department ?? "unallocated"}`)} · {t(`study_design.${u.study_design}`)} · {t(`complexity.${u.task_complexity}`)}
                  </p>
                </div>
                <StatusPill tone={DECISION_TONE[u.decision]}>{t(`decision.${u.decision}`)}</StatusPill>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div><dt className="text-xs text-muted">{t("table.roi")}</dt>
                  <dd className="mt-0.5">{u.roi_pct != null
                    ? <span className={cx("tabular font-semibold", u.roi_pct < 0 ? "text-critical-ink" : "text-ink")}>{fmt.byUnit(u.roi_pct, "percent")}</span>
                    : <RoiStatusPill status={u.roi_status} />}</dd></div>
                <div><dt className="text-xs text-muted">{t("table.total_cost")}</dt><dd className="tabular mt-0.5 text-ink">{fmt.money(u.total_cost, true)}</dd></div>
                <div><dt className="text-xs text-muted">{t("table.gross_benefit")}</dt><dd className="tabular mt-0.5 text-ink">{fmt.money(u.gross_benefit, true)}</dd></div>
                <div><dt className="text-xs text-muted">{t("table.hours_saved")}</dt><dd className="tabular mt-0.5 text-ink">{u.hours_saved == null ? "—" : `${fmt.num(u.hours_saved)} h`}</dd></div>
              </dl>
              <p className="mt-3 text-xs text-muted">{t(u.causal ? "outcomes.causal_yes" : "outcomes.causal_no")}</p>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}

function ClaimsTable({ claims, excluded, currency }: { claims: Claim[]; excluded?: boolean; currency: string }) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  return (
    <DataTable rowKey={(c) => c.id + (c.reason ?? "")} rows={claims}
      columns={[
        { key: "c", header: t("outcomes.category"), cell: (c) => t(`benefit_category.${c.category}`) },
        { key: "s", header: t("outcomes.status"), cell: (c) => t(`verification.${c.verification_status}`) },
        { key: "p", header: t("table.period"), cell: (c) => `${fmt.shortDate(c.period_start)} – ${fmt.shortDate(c.period_end)}` },
        { key: "a", header: t("outcomes.amount"), cell: (c) => fmt.money(c.amount), align: "right" },
        { key: "f", header: t("outcomes.confidence"), cell: (c) => fmt.ratio(c.confidence, 0), align: "right" },
        excluded
          ? { key: "r", header: t("outcomes.reason"), cell: (c) => <span className="text-ink-2">{t(`exclusion.${c.reason}`)}</span> }
          : { key: "src", header: t("outcomes.source"), cell: (c) => <span className="text-ink-2">{c.source}</span> },
      ]} />
  );
}

export function RoiDetail({ roi, currency }: { roi: Roi; currency: string }) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  const ok = roi.status === "ok";
  return (
    <>
      {!ok && (
        <div className="mb-4 rounded-lg border border-[#f1dca6] bg-warning-soft px-4 py-3 text-sm">
          <p className="font-medium text-warning-ink">{t("roi_status.insufficient_evidence")}</p>
          <ul className="mt-1 list-disc pl-5 text-ink-2">{roi.reasons.map((r) => <li key={r}>{reasonText(t, r)}</li>)}</ul>
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard currency={currency} emphasis kpi={{ value: roi.roi_pct, basis: "evidence_backed", definition_key: "metric.roi", unit: "percent" }}
          empty={<span className="text-base">{t(`roi_status.${roi.status}`)}</span>} />
        <KpiCard currency={currency} kpi={{ value: roi.net_benefit, basis: "evidence_backed", definition_key: "metric.net_benefit", unit: "currency" }} />
        <KpiCard currency={currency} kpi={{ value: roi.gross_benefit, basis: "evidence_backed", definition_key: "metric.gross_benefit", unit: "currency" }} />
        <KpiCard currency={currency} kpi={{ value: roi.costs.total, basis: "measured", definition_key: "metric.total_ai_cost", unit: "currency" }} />
        <KpiCard currency={currency} kpi={{ value: roi.benefit_cost_ratio, basis: "evidence_backed", definition_key: "metric.benefit_cost_ratio", unit: "decimal" }} />
        <KpiCard currency={currency} kpi={{ value: roi.payback_months, basis: "evidence_backed", definition_key: "metric.payback", unit: "decimal" }}
          sub={roi.payback_months != null ? t("units.months", { value: fmt.num(roi.payback_months, 1) }) : undefined} />
        <KpiCard currency={currency} kpi={{ value: roi.cost_per_successful_task, basis: "measured", definition_key: "metric.cost_per_successful_task", unit: "currency" }}
          sub={t("units.tasks", { value: fmt.num(roi.successful_tasks) })} />
        <KpiCard currency={currency} kpi={{ value: roi.hours.gross, basis: "measured", definition_key: "metric.hours_saved", unit: "hours" }}
          sub={roi.hours.net != null ? t("metric.net_hours", { value: `${fmt.num(roi.hours.net)} h` }) : undefined} />
      </div>
      {ok && roi.break_even_tasks != null && (
        <p className="mt-2 text-xs text-muted">{t("metric.break_even.label")}: {t("units.tasks", { value: fmt.num(roi.break_even_tasks) })}</p>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title={t("dashboard.roi_bridge")} description={t("dashboard.roi_bridge_desc")}>
          <ChartFrame
            chart={<BridgeChart steps={bridgeSteps(roi, t)} format={(v) => fmt.money(v, true)} label={t("dashboard.roi_bridge")} />}
            table={<DataTable rowKey={(r) => r.key} rows={(Object.entries(roi.costs) as [string, number][]).map(([k, v]) => ({ key: k, v }))}
              columns={[{ key: "k", header: t("outcomes.category"), cell: (r) => t(`cost_category.${r.key}`) },
                { key: "v", header: t("outcomes.amount"), cell: (r) => fmt.money(r.v), align: "right" }]} />}
          />
        </Card>
        <Card title={t("dashboard.scenarios")} description={t("dashboard.scenarios_desc")}>
          {ok ? <Scenarios roi={roi} currency={currency} /> : <EmptyState title={t("roi_status.insufficient_evidence")} body={t("dashboard.verdict_insufficient")} />}
        </Card>
      </div>

      <SectionTitle>{t("outcomes.benefits_counted")}</SectionTitle>
      <Card>
        {roi.benefits.counted.length ? <ClaimsTable claims={roi.benefits.counted} currency={currency} />
          : <EmptyState title={t("outcomes.no_benefits_counted")} body={t("reason.no_supported_benefits")} />}
      </Card>
      {roi.benefits.excluded.length > 0 && (
        <>
          <SectionTitle>{t("outcomes.benefits_excluded")}</SectionTitle>
          <Card actions={<BasisBadge basis="estimated" />}>
            <ClaimsTable claims={roi.benefits.excluded} excluded currency={currency} />
          </Card>
        </>
      )}
    </>
  );
}

export function UseCaseView({ id }: { id: string }) {
  const { t } = useI18n();
  const meta = useMeta();
  const { query } = useFilters();
  const fmt = useFormat(meta.currency);
  const { data, error, reload } = useApi<UseCaseDetail>(`/api/use-cases/${encodeURIComponent(id)}${query()}`);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const c = data.comparison;
  const baseline = data.roi.hours.baseline_source === "control_group"
    ? t("outcomes.baseline_control")
    : data.documented_baseline_minutes != null
      ? t("outcomes.baseline_documented", { value: t("units.minutes", { value: fmt.num(data.documented_baseline_minutes) }) })
      : t("outcomes.baseline_none");

  return (
    <>
      <Link href="/outcomes" className="mb-3 inline-block text-xs font-medium text-accent hover:underline">← {t("outcomes.back")}</Link>
      <PageHeader title={t(`use_case.${data.use_case}`)}
        subtitle={`${t(`department.${data.department ?? "unallocated"}`)} · ${t(`complexity.${data.task_complexity}`)}`}
        actions={<StatusPill tone={DECISION_TONE[c.decision]}>{t(`decision.${c.decision}`)}</StatusPill>} />

      <Card title={t("outcomes.measurement")} className="mb-4">
        <DefinitionList items={[
          { term: t("outcomes.design"), value: <>{t(`study_design.${data.study_design}`)}<p className="mt-0.5 text-xs text-muted">{t(c.causal ? "outcomes.causal_yes" : "outcomes.causal_no")}</p></> },
          { term: t("outcomes.data_source"), value: data.data_source || "—" },
          { term: t("outcomes.baseline"), value: baseline },
          { term: t("table.period"), value: `${fmt.date(data.measurement_period.start)} – ${fmt.date(data.measurement_period.end)}` },
          { term: t("outcomes.labour_rate"), value: data.labour_rate != null ? t("units.per_hour", { value: fmt.money2(data.labour_rate) }) : "—" },
          { term: t("outcomes.tasks"), value: `${fmt.num(data.tasks_ai)} · ${t("outcomes.success_rate")} ${fmt.ratio(data.success_rate_ai)} · ${t("outcomes.quality")} ${fmt.ratio(data.quality_ai)}` },
          { term: t("table.decision"), value: <>{t(`decision_help.${c.decision}`)}<ul className="mt-1 list-disc pl-5 text-xs text-ink-2">{c.reasons.map((r) => <li key={r}>{reasonText(t, r)}</li>)}</ul></> },
        ]} />
      </Card>

      <RoiDetail roi={data.roi} currency={meta.currency} />
      <p className="mt-6"><Link href="/comparison" className="text-sm font-medium text-accent hover:underline">{t("nav.comparison")} →</Link></p>
    </>
  );
}
