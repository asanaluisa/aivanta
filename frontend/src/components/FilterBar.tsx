"use client";

import { useI18n } from "@/i18n/I18nProvider";
import { EMPTY_FILTERS, activeCount, windowStart } from "@/lib/filters";
import { useFilters } from "@/lib/filtersContext";
import type { Meta } from "@/lib/types";

import { cx } from "./ui";

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  const { t } = useI18n();
  return (
    <label className="flex min-w-0 flex-col gap-0.5">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cx("h-8 w-40 min-w-0 rounded-md border bg-surface px-2 text-xs text-ink", value ? "border-brand/40" : "border-line")}
      >
        <option value="">{t("filters.all")}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function FilterBar({ meta }: { meta: Meta }) {
  const { t } = useI18n();
  const { filters, update, setFilters } = useFilters();
  const end = meta.period.end;
  const preset = !filters.start && !filters.end ? "full" : filters.end === end && filters.start === windowStart(end, 30) ? "30" : filters.end === end && filters.start === windowStart(end, 60) ? "60" : "custom";
  const one = (v: string) => (v ? [v] : []);
  const models = Array.from(new Map(meta.models.map((m) => [`${m.provider}/${m.model}`, m])).values())
    .filter((m) => !filters.providers.length || filters.providers.includes(m.provider));
  const count = activeCount(filters);

  return (
    <div className="border-t border-line px-4 py-2 lg:px-8">
      <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-medium uppercase tracking-wide text-muted">{t("filters.date_range")}</span>
          <div className="flex flex-wrap items-center gap-1">
            {[["full", "filters.full_period"], ["60", "filters.last_60"], ["30", "filters.last_30"]].map(([k, label]) => (
              <button
                key={k}
                type="button"
                aria-pressed={preset === k}
                onClick={() => update(k === "full" ? { start: null, end: null } : { start: windowStart(end, Number(k)), end })}
                className={cx("h-8 whitespace-nowrap rounded-md border px-2 text-xs", preset === k ? "border-brand bg-brand text-white" : "border-line bg-surface text-ink-2 hover:bg-subtle")}
              >
                {t(label)}
              </button>
            ))}
            <input type="date" aria-label={t("filters.from")} min={meta.period.start} max={end} value={filters.start ?? meta.period.start}
              onChange={(e) => update({ start: e.target.value || null })} className="h-8 rounded-md border border-line bg-surface px-1.5 text-xs" />
            <span className="text-xs text-muted">–</span>
            <input type="date" aria-label={t("filters.to")} min={meta.period.start} max={end} value={filters.end ?? end}
              onChange={(e) => update({ end: e.target.value || null })} className="h-8 rounded-md border border-line bg-surface px-1.5 text-xs" />
          </div>
        </div>
        <Select label={t("filters.department")} value={filters.departments[0] ?? ""} onChange={(v) => update({ departments: one(v) })}
          options={[...meta.departments.map((d) => ({ value: d.id, label: t(`department.${d.id}`) })), { value: "unallocated", label: t("department.unallocated") }]} />
        <Select label={t("filters.use_case")} value={filters.useCases[0] ?? ""} onChange={(v) => update({ useCases: one(v) })}
          options={meta.use_cases.map((u) => ({ value: u.id, label: t(`use_case.${u.id}`) }))} />
        <Select label={t("filters.provider")} value={filters.providers[0] ?? ""} onChange={(v) => update({ providers: one(v), models: [] })}
          options={meta.providers.map((p) => ({ value: p, label: t(`provider.${p}`) }))} />
        <Select label={t("filters.model")} value={filters.models[0] ?? ""} onChange={(v) => update({ models: one(v) })}
          options={models.map((m) => ({ value: m.model, label: m.model }))} />
        {count > 0 && (
          <button type="button" onClick={() => setFilters(EMPTY_FILTERS)} className="h-8 text-xs font-medium text-accent hover:underline">
            {t("filters.clear")} ({t("filters.active", { count })})
          </button>
        )}
      </div>
    </div>
  );
}
