"use client";

import { useState } from "react";

import { useMeta } from "@/components/AppShell";
import { ChartFrame, HBarChart, TimeSeriesChart } from "@/components/charts";
import { Button, Card, DataTable, EmptyState, ErrorState, Loading, PageHeader, Segmented } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFilters } from "@/lib/filtersContext";
import type { Breakdown, Trend } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

import { labelFor } from "./DashboardView";

type Dim = Breakdown["dimension"];

export function CostsView() {
  const { t, locale } = useI18n();
  const meta = useMeta();
  const { token } = useAuth();
  const { query } = useFilters();
  const fmt = useFormat(meta.currency);
  const [dim, setDim] = useState<Dim>("provider");
  const breakdown = useApi<Breakdown>(`/api/usage/breakdown/${dim}${query()}`);
  const trend = useApi<Trend>(`/api/usage/trend${query()}`);

  const exportCsv = () =>
    downloadFile(`/api/reports/usage.csv${query({ dimension: dim, locale })}`, token,
      `aivanta_${locale === "es" ? "uso" : "usage"}_${dim}.csv`).catch(() => undefined);

  const rows = breakdown.data?.rows ?? [];
  const totals = rows.reduce((a, r) => ({ i: a.i + r.input_tokens, o: a.o + r.output_tokens, c: a.c + r.cached_input_tokens }), { i: 0, o: 0, c: 0 });

  return (
    <>
      <PageHeader title={t("costs.title")} subtitle={t("costs.subtitle")}
        actions={<>
          <Segmented label={t("costs.dimension")} value={dim} onChange={setDim}
            options={(["provider", "model", "department", "use_case"] as Dim[]).map((d) => ({ value: d, label: t(`filters.${d}`) }))} />
          <Button onClick={exportCsv}>{t("costs.export")}</Button>
        </>} />

      {breakdown.error ? <ErrorState error={breakdown.error} onRetry={breakdown.reload} /> : !breakdown.data ? <Loading /> : rows.length === 0 ? <EmptyState /> : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card title={t(`dashboard.by_${dim}`)}>
            <HBarChart label={t(`dashboard.by_${dim}`)} format={(v) => fmt.money(v, true)}
              rows={rows.map((r) => ({ key: r.key, label: labelFor(t, dim, r.key), value: r.spend, detail: fmt.ratio(r.share) }))} />
          </Card>
          <Card className="xl:col-span-2" title={t("costs.tokens_mix")}
            description={`${t("metric.input_tokens.label")} ${fmt.compact(totals.i)} · ${t("metric.cached_input_tokens.label")} ${fmt.compact(totals.c)} (${fmt.ratio(totals.i ? totals.c / totals.i : null)}) · ${t("metric.output_tokens.label")} ${fmt.compact(totals.o)}`}>
            <DataTable caption={t("costs.title")} rowKey={(r) => r.key} rows={rows}
              columns={[
                { key: "n", header: t("table.name"), cell: (r) => <span className="font-medium">{labelFor(t, dim, r.key)}</span> },
                { key: "s", header: t("table.spend"), cell: (r) => fmt.money2(r.spend), align: "right" },
                { key: "sh", header: t("table.share"), cell: (r) => fmt.ratio(r.share), align: "right" },
                { key: "ti", header: t("metric.input_tokens.label"), cell: (r) => fmt.compact(r.input_tokens), align: "right" },
                { key: "tc", header: t("metric.cached_input_tokens.label"), cell: (r) => fmt.compact(r.cached_input_tokens), align: "right" },
                { key: "to", header: t("metric.output_tokens.label"), cell: (r) => fmt.compact(r.output_tokens), align: "right" },
                { key: "rq", header: t("table.requests"), cell: (r) => fmt.num(r.requests), align: "right" },
                { key: "cpr", header: t("table.cost_per_request"), cell: (r) => fmt.unitCost(r.cost_per_request), align: "right" },
                { key: "er", header: t("metric.error_rate.label"), cell: (r) => fmt.ratio(r.error_rate), align: "right" },
                { key: "lt", header: t("table.latency"), cell: (r) => (r.avg_latency_ms == null ? "—" : `${fmt.num(r.avg_latency_ms)} ms`), align: "right" },
                { key: "re", header: t("table.retries"), cell: (r) => fmt.num(r.retries), align: "right" },
                { key: "u", header: t("table.users"), cell: (r) => fmt.num(r.active_users), align: "right" },
              ]} />
          </Card>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title={t("metric.requests.label")} description={t("metric.requests.definition")}>
          {trend.error ? <ErrorState error={trend.error} onRetry={trend.reload} /> : !trend.data ? <Loading rows={1} /> : (
            <ChartFrame
              chart={<TimeSeriesChart points={trend.data.rows.map((r) => ({ date: r.date, value: r.requests }))} format={(v) => fmt.compact(v)}
                formatDate={fmt.shortDate} label={t("metric.requests.label")} />}
              table={<DataTable caption={t("metric.requests.label")} rowKey={(r) => r.date} rows={trend.data.rows}
                columns={[{ key: "d", header: t("table.date"), cell: (r) => fmt.date(r.date) },
                  { key: "r", header: t("table.requests"), cell: (r) => fmt.num(r.requests), align: "right" },
                  { key: "e", header: t("metric.error_rate.label"), cell: (r) => fmt.num(r.errors), align: "right" },
                  { key: "k", header: t("table.tokens"), cell: (r) => fmt.compact(r.tokens), align: "right" }]} />}
            />
          )}
        </Card>
        <Card title={t("costs.pricing")} description={t("costs.pricing_desc")}>
          <DataTable caption={t("costs.pricing")} rowKey={(r) => `${r.provider}/${r.model}/${r.effective_from}`} rows={meta.models}
            columns={[
              { key: "m", header: t("filters.model"), cell: (r) => <><span className="font-medium">{r.model}</span><div className="text-[11px] text-muted">{t(`provider.${r.provider}`)} · {t(`costs.tier_${r.tier}`)}</div></> },
              { key: "e", header: t("costs.effective_from"), cell: (r) => fmt.date(r.effective_from) },
              { key: "i", header: t("costs.input_price"), cell: (r) => fmt.money2(r.input_per_mtok), align: "right" },
              { key: "c", header: t("costs.cached_price"), cell: (r) => fmt.money2(r.cached_input_per_mtok), align: "right" },
              { key: "o", header: t("costs.output_price"), cell: (r) => fmt.money2(r.output_per_mtok), align: "right" },
            ]} />
        </Card>
      </div>
    </>
  );
}
