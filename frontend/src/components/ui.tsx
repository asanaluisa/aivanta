"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";

import { useI18n } from "@/i18n/I18nProvider";
import type { ApiError } from "@/lib/api";
import type { Basis } from "@/lib/types";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// ------------------------------------------------------------------ layout

export function PageHeader({ title, subtitle, actions, meta }: { title: string; subtitle?: string; actions?: ReactNode; meta?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-ink-2">{subtitle}</p>}
        {meta && <div className="mt-2 text-xs text-muted">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ title, description, actions, children, className, bodyClassName }: {
  title?: ReactNode; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClassName?: string;
}) {
  return (
    <section className={cx("min-w-0 rounded-lg border border-line bg-surface", className)}>
      {(title || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cx("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 mt-8 text-xs font-semibold uppercase tracking-wider text-muted first:mt-0">{children}</h2>;
}

// ------------------------------------------------------------------ buttons

export function Button({ children, variant = "secondary", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  const styles = {
    primary: "bg-brand text-white hover:bg-brand-2 disabled:opacity-50",
    secondary: "border border-line bg-surface text-ink hover:bg-subtle disabled:opacity-50",
    ghost: "text-ink-2 hover:bg-subtle hover:text-ink",
  }[variant];
  return (
    <button {...props} className={cx("inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed", styles, className)}>
      {children}
    </button>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cx(
            "rounded px-2.5 py-1 text-xs font-medium",
            o.value === value ? "bg-brand text-white" : "text-ink-2 hover:bg-subtle",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ badges

const BASIS_STYLE: Record<Basis | "synthetic", string> = {
  measured: "bg-subtle text-ink-2 ring-line",
  evidence_backed: "bg-brand-soft text-brand ring-[#c9d4e6]",
  estimated: "bg-warning-soft text-warning-ink ring-[#f1dca6]",
  synthetic: "bg-info-soft text-[#1c5cab] ring-[#c7dbf5]",
};

export function BasisBadge({ basis }: { basis: Basis | "synthetic" }) {
  const { t } = useI18n();
  return (
    <span title={basis === "synthetic" ? undefined : t(`basis.${basis}_help`)} className={cx("inline-flex shrink-0 items-center whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset", BASIS_STYLE[basis])}>
      {basis === "estimated" && <span aria-hidden className="mr-1">≈</span>}
      {t(`basis.${basis}`)}
    </span>
  );
}

export type Tone = "good" | "warning" | "serious" | "critical" | "neutral" | "info";

const TONE_STYLE: Record<Tone, { box: string; dot: string }> = {
  good: { box: "bg-good-soft text-good-ink", dot: "bg-good" },
  warning: { box: "bg-warning-soft text-warning-ink", dot: "bg-warning" },
  serious: { box: "bg-serious-soft text-serious-ink", dot: "bg-serious" },
  critical: { box: "bg-critical-soft text-critical-ink", dot: "bg-critical" },
  neutral: { box: "bg-subtle text-ink-2", dot: "bg-axis" },
  info: { box: "bg-info-soft text-[#1c5cab]", dot: "bg-accent" },
};

/** Status pill: colour is always paired with a symbol and a text label. */
export function StatusPill({ tone, children, symbol }: { tone: Tone; children: ReactNode; symbol?: string }) {
  const s = TONE_STYLE[tone];
  const icon = symbol ?? { good: "✓", warning: "!", serious: "!", critical: "✕", neutral: "•", info: "i" }[tone];
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium", s.box)}>
      <span aria-hidden className={cx("inline-flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] font-bold text-white", s.dot, tone === "warning" && "text-ink")}>{icon}</span>
      {children}
    </span>
  );
}

export const DECISION_TONE: Record<string, Tone> = {
  continue: "good",
  optimize: "warning",
  selective: "serious",
  experiment: "info",
  stop: "critical",
};

export const BUDGET_TONE: Record<string, Tone> = { ok: "good", warning: "warning", forecast_exceeds: "serious", exceeded: "critical" };
export const SEVERITY_TONE: Record<string, Tone> = { critical: "critical", warning: "warning", opportunity: "good", info: "info" };

export function RoiStatusPill({ status }: { status: string }) {
  const { t } = useI18n();
  const tone: Tone = status === "ok" ? "good" : status === "insufficient_evidence" ? "warning" : "neutral";
  return <StatusPill tone={tone}>{t(`roi_status.${status}`)}</StatusPill>;
}

// ------------------------------------------------------------------ info tip

export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-axis text-[10px] font-semibold text-muted hover:border-ink-2 hover:text-ink"
      >
        ?
      </button>
      {open && (
        <span role="tooltip" id={id} className="absolute left-1/2 top-6 z-30 w-72 -translate-x-1/2 rounded-md border border-line bg-surface p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-ink-2 shadow-lg">
          {children}
        </span>
      )}
    </span>
  );
}

// ------------------------------------------------------------------ states

export function Loading({ rows = 3 }: { rows?: number }) {
  const { t } = useI18n();
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{t("app.loading")}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-lg bg-subtle" />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError | null; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div role="alert" className="rounded-lg border border-[#efc6c6] bg-critical-soft p-4 text-sm">
      <p className="font-semibold text-critical-ink">{t("error.title")}</p>
      <p className="mt-1 text-ink-2">{t(`error.${error?.code ?? "unknown"}`)}</p>
      {onRetry && (
        <Button className="mt-3" onClick={onRetry}>
          {t("app.retry")}
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, body }: { title?: string; body?: string }) {
  const { t } = useI18n();
  return (
    <div className="rounded-lg border border-dashed border-axis p-8 text-center">
      <p className="text-sm font-medium text-ink">{title ?? t("empty.title")}</p>
      <p className="mt-1 text-xs text-muted">{body ?? t("empty.body")}</p>
    </div>
  );
}

// ------------------------------------------------------------------ table

export interface Column<R> {
  key: string;
  header: ReactNode;
  cell: (row: R) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

export function DataTable<R>({ columns, rows, rowKey, caption, onRowClick }: {
  columns: Column<R>[]; rows: R[]; rowKey: (r: R) => string; caption?: string; onRowClick?: (r: R) => void;
}) {
  return (
    <div className="relative -mx-4 overflow-x-auto px-4">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cx("whitespace-nowrap px-2 py-2 text-xs font-medium text-muted", c.align === "right" ? "text-right" : "text-left")}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={rowKey(r)}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={cx("border-b border-line/70 last:border-0", onRowClick && "cursor-pointer hover:bg-subtle")}
            >
              {columns.map((c) => (
                <td key={c.key} className={cx("px-2 py-2 align-top", c.align === "right" ? "tabular text-right" : "text-left", c.className)}>
                  {c.cell(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="text-sm font-medium text-accent hover:underline">
      {children}
    </Link>
  );
}

export function DefinitionList({ items }: { items: { term: ReactNode; value: ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
      {items.map((it, i) => (
        <div key={i} className="min-w-0">
          <dt className="text-xs text-muted">{it.term}</dt>
          <dd className="mt-0.5 text-ink">{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
