"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Button, Card, ErrorState, Loading, PageHeader } from "@/components/ui";
import { useI18n } from "@/i18n/I18nProvider";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Assumptions } from "@/lib/types";
import { useApi } from "@/lib/useApi";

/** Fields shown as percentages in the form but stored as fractions. */
const PERCENT_FIELDS = new Set([
  "conservative_benefit_haircut", "conservative_cost_contingency", "optimistic_estimated_benefit_share",
  "quality_tolerance", "budget_warning_ratio", "review_erosion_ratio", "spend_growth_alert_ratio",
]);
const ORDER = [
  "min_sample_size", "min_measurement_days", "conservative_benefit_haircut", "conservative_cost_contingency",
  "optimistic_estimated_benefit_share", "quality_tolerance", "budget_warning_ratio", "review_erosion_ratio",
  "spend_growth_alert_ratio", "anomaly_sigma",
];

export function toForm(a: Assumptions): Record<string, string> {
  return Object.fromEntries(ORDER.map((k) => [k, String(PERCENT_FIELDS.has(k) ? Math.round(a[k] * 1000) / 10 : a[k])]));
}

export function fromForm(f: Record<string, string>): Assumptions {
  return Object.fromEntries(ORDER.map((k) => {
    const n = Number(f[k].replace(",", "."));
    return [k, PERCENT_FIELDS.has(k) ? n / 100 : n];
  }));
}

export function SettingsView() {
  const { t } = useI18n();
  const { token, can } = useAuth();
  const { data, error, reload } = useApi<Assumptions>("/api/assumptions");
  const [form, setForm] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);
  const editable = can("assumptions");

  useEffect(() => {
    if (data) setForm(toForm(data));
  }, [data]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      await apiFetch("/api/assumptions", token, { method: "PUT", body: JSON.stringify({ values: fromForm(form) }) });
      setSaved(true);
      reload();
    } catch (err) {
      setSaveError(err instanceof ApiError ? err : new ApiError(0, "unknown"));
    } finally {
      setSaving(false);
    }
  };

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!form) return <Loading />;

  return (
    <>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />
      {!editable && <p className="mb-4 rounded-md border border-line bg-subtle px-3 py-2 text-sm text-ink-2">{t("settings.read_only")}</p>}
      <Card>
        <form onSubmit={submit}>
          <fieldset disabled={!editable || saving} className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
            {ORDER.map((k) => (
              <label key={k} className="block">
                <span className="text-sm text-ink">{t(`settings.${k}`)}</span>
                <span className="mt-1 flex items-center gap-2">
                  <input inputMode="decimal" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                    className="tabular h-9 w-32 rounded-md border border-line bg-surface px-2 text-sm disabled:bg-subtle" />
                  {PERCENT_FIELDS.has(k) && <span className="text-sm text-muted">%</span>}
                </span>
              </label>
            ))}
          </fieldset>
          {editable && (
            <div className="mt-6 flex items-center gap-3">
              <Button type="submit" variant="primary" disabled={saving}>{saving ? t("app.saving") : t("app.save")}</Button>
              <Button type="button" onClick={() => data && setForm(toForm(data))}>{t("app.reset")}</Button>
              {saved && <span role="status" className="text-sm text-good-ink">✓ {t("settings.saved")}</span>}
            </div>
          )}
          {saveError && <div className="mt-4"><ErrorState error={saveError} /></div>}
        </form>
      </Card>
    </>
  );
}
