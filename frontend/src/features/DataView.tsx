"use client";

import { useState, type FormEvent } from "react";

import { useMeta } from "@/components/AppShell";
import { Button, Card, DataTable, EmptyState, ErrorState, PageHeader, RoiStatusPill, StatusPill } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { ApiError, apiFetch, downloadFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFilters } from "@/lib/filtersContext";
import type { Batch, IngestionSummary, Snapshot } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useFormat } from "@/lib/useFormat";

export function DataView() {
  const { t, locale } = useI18n();
  const meta = useMeta();
  const { token, can } = useAuth();
  const { query } = useFilters();
  const fmt = useFormat(meta.currency);
  const [format, setFormat] = useState(meta.ingestion_formats[0] ?? "aivanta_csv");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngestionSummary | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const batches = useApi<{ rows: Batch[] }>("/api/ingestion/batches");
  const snapshots = useApi<{ rows: Snapshot[] }>("/api/roi-snapshots");

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    const body = new FormData();
    body.append("file", file);
    try {
      setResult(await apiFetch<IngestionSummary>(`/api/ingestion/${format}`, token, { method: "POST", body }));
      batches.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "unknown"));
    } finally {
      setBusy(false);
    }
  };

  const snapshot = async () => {
    await apiFetch(`/api/roi-snapshots${query()}`, token, { method: "POST", body: JSON.stringify({ scope_type: "organization", scope_key: "organization" }) })
      .catch(() => undefined);
    snapshots.reload();
  };

  return (
    <>
      <PageHeader title={t("data.title")} subtitle={t("data.subtitle")}
        actions={<>
          <Button onClick={() => downloadFile(`/api/reports/roi.csv${query({ locale })}`, token, locale === "es" ? "aivanta_roi_resumen.csv" : "aivanta_roi_summary.csv").catch(() => undefined)}>
            ROI · CSV ({locale.toUpperCase()})
          </Button>
        </>} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title={t("data.upload")} description={t("data.samples")}>
          {!can("ingest") ? <p className="text-sm text-ink-2">{t("data.no_permission")}</p> : (
            <form onSubmit={upload} className="space-y-3">
              <label className="block text-sm">
                <span className="text-xs font-medium text-ink-2">{t("data.format")}</span>
                <select value={format} onChange={(e) => setFormat(e.target.value)} className="mt-1 h-9 w-full rounded-md border border-line bg-surface px-2 text-sm">
                  {meta.ingestion_formats.map((f) => <option key={f} value={f}>{t(`data.format_${f}`)}</option>)}
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-xs font-medium text-ink-2">{t("data.choose_file")}</span>
                <input type="file" accept=".csv,.json,.jsonl,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border file:border-line file:bg-surface file:px-3 file:py-1.5 file:text-sm" />
              </label>
              <Button type="submit" variant="primary" disabled={!file || busy}>{busy ? t("data.processing") : t("data.submit")}</Button>
            </form>
          )}
          {error && <div className="mt-4"><ErrorState error={error} /></div>}
          {result && (
            <div className="mt-4 rounded-md border border-line p-3" aria-live="polite">
              <p className="text-xs font-semibold text-ink">{t("data.result")}</p>
              <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                {(["accepted", "duplicates", "rejected", "unallocated"] as const).map((k) => (
                  <div key={k}><dt className="text-xs text-muted">{t(`data.${k}`)}</dt><dd className="tabular font-semibold">{fmt.num(result[k])}</dd></div>
                ))}
              </dl>
              {result.rejections.length > 0 && (
                <details className="mt-2"><summary className="cursor-pointer text-xs text-accent">{t("data.rejections")}</summary>
                  <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-ink-2">{result.rejections.map((r, i) => <li key={i}>{r.row}: {r.reason}</li>)}</ul>
                </details>
              )}
            </div>
          )}
          <div className="mt-4 border-t border-line pt-3 text-xs">
            <p className="font-medium text-ink">{t("data.live_sync")}</p>
            <ul className="mt-1 space-y-1">
              {Object.keys(meta.live_sync).map((p) => (
                <li key={p} className="flex items-center justify-between gap-2"><span>{t(`provider.${p}`)}</span><StatusPill tone="neutral">{t("data.live_sync_status")}</StatusPill></li>
              ))}
            </ul>
          </div>
        </Card>

        <Card title={t("data.history")}>
          {batches.error ? <ErrorState error={batches.error} onRetry={batches.reload} /> : !batches.data?.rows.length ? <EmptyState title={t("data.no_history")} body=" " /> : (
            <DataTable rowKey={(b) => String(b.id)} rows={batches.data.rows}
              columns={[
                { key: "f", header: t("table.name"), cell: (b) => <><span className="font-medium">{b.filename}</span><div className="text-[11px] text-muted">{t(`data.format_${b.format}`)}</div></> },
                { key: "d", header: t("data.created"), cell: (b) => fmt.date(b.created_at) },
                { key: "a", header: t("data.accepted"), cell: (b) => fmt.num(b.accepted), align: "right" },
                { key: "u", header: t("data.duplicates"), cell: (b) => fmt.num(b.duplicates), align: "right" },
                { key: "r", header: t("data.rejected"), cell: (b) => fmt.num(b.rejected), align: "right" },
                { key: "n", header: t("data.unallocated"), cell: (b) => fmt.num(b.unallocated), align: "right" },
              ]} />
          )}
        </Card>
      </div>

      <Card className="mt-4" title={t("data.snapshots")} description={t("data.snapshots_desc")}
        actions={can("snapshots") ? <Button variant="primary" onClick={snapshot}>{t("data.create_snapshot")}</Button> : undefined}>
        {!snapshots.data?.rows.length ? <EmptyState title={t("data.no_snapshots")} body=" " /> : (
          <DataTable rowKey={(s) => String(s.id)} rows={snapshots.data.rows}
            columns={[
              { key: "c", header: t("data.created"), cell: (s) => fmt.date(s.created_at) },
              { key: "s", header: t("table.scope"), cell: (s) => (s.scope_type === "use_case" ? t(`use_case.${s.scope_key}`) : s.scope_type === "department" ? t(`department.${s.scope_key}`) : t("department.organization")) },
              { key: "p", header: t("table.period"), cell: (s) => `${fmt.shortDate(s.period_start)} – ${fmt.date(s.period_end)}` },
              { key: "st", header: t("table.status"), cell: (s) => <RoiStatusPill status={s.status} /> },
              { key: "t", header: t("table.total_cost"), cell: (s) => fmt.money(s.total_cost), align: "right" },
              { key: "g", header: t("table.gross_benefit"), cell: (s) => fmt.money(s.gross_benefit), align: "right" },
              { key: "r", header: t("table.roi"), cell: (s) => fmt.byUnit(s.roi_pct, "percent"), align: "right" },
            ]} />
        )}
      </Card>
    </>
  );
}
