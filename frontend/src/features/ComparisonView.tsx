"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useMeta } from "@/components/AppShell";
import { ChartFrame, ForestPlot } from "@/components/charts";
import { BasisBadge, Card, DECISION_TONE, DataTable, EmptyState, ErrorState, Loading, PageHeader, StatusPill, cx } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { useFilters } from "@/lib/filtersContext";
import type { ComparisonRow, Difference } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

import { reasonText } from "./OutcomesView";

function DiffCell({ d, format }: { d: Difference; format: (v: number) => string }) {
  const { t } = useI18n();
  if (d.estimate === null) return <span className="text-muted">—</span>;
  const sign = d.estimate > 0 ? "+" : "";
  return (
    <span>
      <span className={cx("tabular font-medium", d.significant ? "text-ink" : "text-ink-2")}>{sign}{format(d.estimate)}</span>
      {d.low !== null && d.high !== null && (
        <span className="tabular ml-1 text-[11px] text-muted">[{format(d.low)}; {format(d.high)}]</span>
      )}
      <span className="sr-only">{d.significant ? t("comparison.significant") : t("comparison.not_significant")}</span>
      {!d.significant && <span aria-hidden className="ml-1 text-[10px] text-muted">n.s.</span>}
    </span>
  );
}

function ComparisonCard({ c, currency }: { c: ComparisonRow; currency: string }) {
  const { t } = useI18n();
  const fmt = useFormat(currency);
  const pp = (v: number) => t("units.pp", { value: fmt.num(v * 100, 1) });
  const minutes = (v: number) => fmt.num(v, 1);
  type Row = { key: string; label: string; ai: string; base: string; diff?: ReactNode };
  const rows: Row[] = [
    { key: "cpt", label: t("comparison.cost_per_task"), ai: fmt.money2(c.ai.cost_per_completed_task), base: fmt.money2(c.non_ai.cost_per_completed_task),
      diff: c.cost_per_task_delta != null ? <span className="tabular font-medium">{c.cost_per_task_delta > 0 ? "+" : ""}{fmt.money2(c.cost_per_task_delta)}</span> : "—" },
    { key: "min", label: t("comparison.total_minutes"), ai: fmt.num(c.ai.mean_total_minutes, 1), base: fmt.num(c.non_ai.mean_total_minutes, 1),
      diff: <DiffCell d={c.differences.total_minutes} format={minutes} /> },
    { key: "tp", label: t("comparison.throughput"), ai: t("units.per_hour", { value: fmt.num(c.ai.tasks_per_hour, 2) }), base: t("units.per_hour", { value: fmt.num(c.non_ai.tasks_per_hour, 2) }) },
    { key: "q", label: t("comparison.quality"), ai: fmt.ratio(c.ai.quality), base: fmt.ratio(c.non_ai.quality), diff: <DiffCell d={c.differences.quality} format={pp} /> },
    { key: "s", label: t("comparison.success_rate"), ai: fmt.ratio(c.ai.success_rate), base: fmt.ratio(c.non_ai.success_rate), diff: <DiffCell d={c.differences.success_rate} format={pp} /> },
    { key: "e", label: t("comparison.error_rate"), ai: fmt.ratio(c.ai.error_rate), base: fmt.ratio(c.non_ai.error_rate), diff: <DiffCell d={c.differences.error_rate} format={pp} /> },
    { key: "r", label: t("comparison.rework_rate"), ai: fmt.ratio(c.ai.rework_rate), base: fmt.ratio(c.non_ai.rework_rate) },
    ...(c.ai.csat != null || c.non_ai.csat != null
      ? [{ key: "c", label: t("comparison.csat"), ai: fmt.num(c.ai.csat, 2), base: fmt.num(c.non_ai.csat, 2) }] : []),
    { key: "tco", label: t("comparison.tco"), ai: fmt.money(c.ai.total_cost, true), base: fmt.money(c.non_ai.total_cost, true) },
  ];
  return (
    <Card
      title={<Link href={`/use-cases/${c.use_case}`} className="hover:underline">{t(`use_case.${c.use_case}`)}</Link>}
      description={`${t(`study_design.${c.study_design}`)} · ${t(c.causal ? "outcomes.causal_yes" : "outcomes.causal_no")}`}
      actions={<StatusPill tone={DECISION_TONE[c.decision]}>{t(`decision.${c.decision}`)}</StatusPill>}
    >
      <p className="text-sm text-ink-2">{t(`decision_help.${c.decision}`)}</p>
      <ul className="mt-1 list-disc pl-5 text-xs text-ink-2">{c.reasons.map((r) => <li key={r}>{reasonText(t, r)}</li>)}</ul>
      {c.non_ai.n === 0 ? <div className="mt-4"><EmptyState title={t("comparison.no_data")} body={t("decision_help.experiment")} /></div> : (
        <div className="mt-4">
          <DataTable rowKey={(r) => r.key} rows={rows}
            columns={[
              { key: "m", header: t("comparison.metric"), cell: (r) => r.label },
              { key: "a", header: <>{t("comparison.arm_ai")} <span className="text-[10px]">(n={fmt.num(c.ai.n)})</span></>, cell: (r) => r.ai, align: "right" },
              { key: "b", header: <>{t("comparison.arm_non_ai")} <span className="text-[10px]">(n={fmt.num(c.non_ai.n)})</span></>, cell: (r) => r.base, align: "right" },
              { key: "d", header: t("comparison.difference"), cell: (r) => r.diff ?? "", align: "right" },
            ]} />
          <p className="mt-2 text-[11px] text-muted">
            {t("comparison.arm_ai")}: {t("comparison.observed", { start: fmt.shortDate(c.ai.first_day), end: fmt.shortDate(c.ai.last_day) })} ·{" "}
            {t("comparison.arm_non_ai")}: {t("comparison.observed", { start: fmt.shortDate(c.non_ai.first_day), end: fmt.shortDate(c.non_ai.last_day) })}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-ink-2">{t("comparison.net_benefit_estimate")}:</span>
            <span className={cx("tabular font-semibold", (c.estimated_net_benefit ?? 0) < 0 ? "text-critical-ink" : "text-ink")}>{fmt.money(c.estimated_net_benefit)}</span>
            <BasisBadge basis="estimated" />
          </div>
          <p className="text-[11px] text-muted">{t("comparison.net_benefit_estimate_help")}</p>
          {c.segments.length > 1 && (
            <div className="mt-4">
              <h3 className="mb-1 text-xs font-semibold text-ink">{t("comparison.segments")}</h3>
              <DataTable rowKey={(s) => s.task_type} rows={c.segments}
                columns={[
                  { key: "t", header: t("table.name"), cell: (s) => t(`task_type.${s.task_type}`) },
                  { key: "n", header: t("comparison.sample"), cell: (s) => `${fmt.num(s.n_ai)} / ${fmt.num(s.n_non_ai)}`, align: "right" },
                  { key: "m", header: t("comparison.total_minutes"), cell: (s) => <DiffCell d={s.total_minutes} format={minutes} />, align: "right" },
                  { key: "q", header: t("comparison.quality"), cell: (s) => <DiffCell d={s.quality} format={pp} />, align: "right" },
                  { key: "f", header: t("table.status"), cell: (s) => <StatusPill tone={s.favourable ? "good" : "critical"}>{t(s.favourable ? "comparison.favourable" : "comparison.not_favourable")}</StatusPill> },
                ]} />
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export function ComparisonView() {
  const { t } = useI18n();
  const meta = useMeta();
  const { query } = useFilters();
  const fmt = useFormat(meta.currency);
  const { data, error, reload } = useApi<{ rows: ComparisonRow[] }>(`/api/comparison${query()}`);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const forest = data.rows.map((c) => ({
    key: c.use_case, label: t(`use_case.${c.use_case}`), estimate: c.differences.total_minutes.estimate,
    low: c.differences.total_minutes.low, high: c.differences.total_minutes.high, significant: c.differences.total_minutes.significant,
    note: t("app.not_available"),
  }));
  return (
    <>
      <PageHeader title={t("comparison.title")} subtitle={t("comparison.subtitle")} />
      {data.rows.length === 0 ? <EmptyState /> : (
        <>
          <Card title={t("comparison.forest")} description={t("comparison.forest_desc")}>
            <ChartFrame
              chart={<ForestPlot rows={forest} format={(v) => t("units.minutes", { value: fmt.num(v, 0) })} label={t("comparison.forest")} />}
              table={<DataTable rowKey={(r) => r.key} rows={forest}
                columns={[{ key: "l", header: t("table.use_case"), cell: (r) => r.label },
                  { key: "d", header: t("comparison.difference"), align: "right",
                    cell: (r) => r.estimate == null ? "—" : `${fmt.num(r.estimate, 1)} [${fmt.num(r.low, 1)}; ${fmt.num(r.high, 1)}]` }]} />}
            />
          </Card>
          <div className="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-2">
            {data.rows.map((c) => <ComparisonCard key={c.use_case} c={c} currency={meta.currency} />)}
          </div>
        </>
      )}
    </>
  );
}
