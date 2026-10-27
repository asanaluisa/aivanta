"use client";

import { useRouter } from "next/navigation";

import { useMeta } from "@/components/AppShell";
import { HBarChart } from "@/components/charts";
import { Card, DataTable, EmptyState, ErrorState, InfoTip, Loading, PageHeader, RoiStatusPill } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { useFilters } from "@/lib/filtersContext";
import type { DepartmentRow } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

export function DepartmentsView() {
  const { t } = useI18n();
  const meta = useMeta();
  const router = useRouter();
  const { query, update } = useFilters();
  const fmt = useFormat(meta.currency);
  const { data, error, reload } = useApi<{ rows: DepartmentRow[] }>(`/api/departments${query()}`);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Loading />;
  const rows = data.rows;

  return (
    <>
      <PageHeader title={t("departments.title")} subtitle={t("departments.subtitle")} />
      {rows.length === 0 ? <EmptyState /> : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title={t("table.total_cost")}>
              <HBarChart label={t("table.total_cost")} format={(v) => fmt.money(v, true)} color="var(--color-s2)"
                rows={rows.map((r) => ({ key: r.department, label: t(`department.${r.department}`), value: r.total_cost }))} />
            </Card>
            <Card title={t("table.gross_benefit")} description={t("basis.evidence_backed_help")}>
              <HBarChart label={t("table.gross_benefit")} format={(v) => fmt.money(v, true)}
                rows={rows.filter((r) => r.department !== "unallocated").map((r) => ({ key: r.department, label: t(`department.${r.department}`), value: r.gross_benefit }))} />
            </Card>
          </div>
          <Card className="mt-4" title={t("departments.title")} description={t("departments.unallocated_note")}>
            <DataTable caption={t("departments.title")} rowKey={(r) => r.department} rows={rows}
              onRowClick={(r) => { if (r.department !== "unallocated") { update({ departments: [r.department] }); router.push("/outcomes"); } }}
              columns={[
                { key: "d", header: t("table.department"), cell: (r) => <span className="font-medium">{t(`department.${r.department}`)}</span> },
                { key: "sp", header: t("table.spend"), cell: (r) => fmt.money(r.spend), align: "right" },
                { key: "tc", header: t("table.total_cost"), cell: (r) => fmt.money(r.total_cost), align: "right" },
                { key: "tk", header: t("table.tokens"), cell: (r) => fmt.compact(r.tokens), align: "right" },
                { key: "u", header: t("table.users"), cell: (r) => fmt.num(r.active_users), align: "right" },
                { key: "t", header: t("table.tasks_completed"), cell: (r) => fmt.num(r.tasks_completed), align: "right" },
                { key: "h", header: t("table.hours_saved"), cell: (r) => (r.hours_saved == null ? "—" : `${fmt.num(r.hours_saved)} h`), align: "right" },
                { key: "q", header: t("table.quality"), cell: (r) => fmt.ratio(r.quality), align: "right" },
                { key: "s", header: t("table.success_rate"), cell: (r) => fmt.ratio(r.success_rate), align: "right" },
                { key: "g", header: t("table.gross_benefit"), cell: (r) => fmt.money(r.gross_benefit), align: "right" },
                { key: "v", header: t("table.time_value"), cell: (r) => <span className="text-warning-ink">{fmt.money(r.estimated_time_value)}</span>, align: "right" },
                {
                  key: "r", header: t("table.roi"), align: "right",
                  cell: (r) => r.roi_pct != null ? (
                    <span className={r.roi_pct < 0 ? "font-semibold text-critical-ink" : "font-semibold text-ink"}>{fmt.byUnit(r.roi_pct, "percent")}</span>
                  ) : (
                    <span className="inline-flex items-center gap-1">
                      <RoiStatusPill status={r.roi_status} />
                      {r.insufficient_use_cases.length > 0 && (
                        <InfoTip label={t("reason.partial_evidence")}>{r.insufficient_use_cases.map((u) => t(`use_case.${u}`)).join(", ")}</InfoTip>
                      )}
                    </span>
                  ),
                },
              ]} />
          </Card>
        </>
      )}
    </>
  );
}
