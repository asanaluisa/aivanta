"use client";

/**
 * SVG charts built on d3-scale / d3-shape and rendered by React.
 * Conventions: thin marks, recessive axes, one y-axis, hover tooltips, and a
 * table view for every chart (see ChartFrame). Categorical colours follow the
 * validated order s1…s8; status colours are never used for series.
 */
import { scaleBand, scaleLinear } from "d3-scale";
import { area, curveMonotoneX, line } from "d3-shape";
import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode, type RefObject } from "react";

import { useI18n } from "@/i18n/I18nProvider";

import { Button, cx } from "./ui";

export function useWidth<T extends HTMLElement>(initial = 640): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWidth(Math.max(240, el.clientWidth));
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

/** Wraps a chart with a chart/table toggle so data is never colour-only. */
export function ChartFrame({ chart, table }: { chart: ReactNode; table: ReactNode }) {
  const { t } = useI18n();
  const [showTable, setShowTable] = useState(false);
  return (
    <div>
      <div className="mb-2 flex justify-end">
        <Button variant="ghost" className="px-2 py-0.5 text-xs" onClick={() => setShowTable((s) => !s)} aria-pressed={showTable}>
          {showTable ? t("app.show_chart") : t("app.show_table")}
        </Button>
      </div>
      {showTable ? table : chart}
    </div>
  );
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const left = Math.min(Math.max(x + 12, 0), width - 200);
  return (
    <div className="pointer-events-none absolute z-20 w-48 rounded-md border border-line bg-surface px-3 py-2 text-xs text-ink shadow-md" style={{ left, top: Math.max(0, y - 10) }}>
      {children}
    </div>
  );
}

// ------------------------------------------------------------------ time series

export interface SeriesPoint { date: string; value: number }

export function TimeSeriesChart({ points, highlights = [], format, formatDate, label, height = 220, highlightLabel }: {
  points: SeriesPoint[]; highlights?: string[]; format: (v: number) => string; formatDate: (d: string) => string;
  label: string; height?: number; highlightLabel?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const m = { top: 12, right: 12, bottom: 26, left: 56 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;
  const max = Math.max(1, ...points.map((p) => p.value));
  const x = scaleLinear().domain([0, Math.max(1, points.length - 1)]).range([0, iw]);
  const y = scaleLinear().domain([0, max]).nice(4).range([ih, 0]);
  const path = line<SeriesPoint>().x((_, i) => x(i)).y((p) => y(p.value)).curve(curveMonotoneX)(points) ?? "";
  const fill = area<SeriesPoint>().x((_, i) => x(i)).y0(ih).y1((p) => y(p.value)).curve(curveMonotoneX)(points) ?? "";
  const hl = new Set(highlights);
  const ticks = y.ticks(4);
  const xTicks = points.length > 1 ? [0, Math.floor((points.length - 1) / 2), points.length - 1] : [0];

  const onMove = (e: MouseEvent<SVGRectElement>) => {
    const rect = (e.target as SVGRectElement).getBoundingClientRect();
    const i = Math.round(x.invert(e.clientX - rect.left));
    setHover(Math.max(0, Math.min(points.length - 1, i)));
  };

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={height} role="img" aria-label={label}>
        <g transform={`translate(${m.left},${m.top})`}>
          {ticks.map((tk) => (
            <g key={tk}>
              <line x1={0} x2={iw} y1={y(tk)} y2={y(tk)} stroke="var(--color-line)" />
              <text x={-8} y={y(tk)} dy="0.32em" textAnchor="end" className="tabular fill-muted text-[10px]">{format(tk)}</text>
            </g>
          ))}
          <path d={fill} fill="var(--color-s1)" opacity={0.08} />
          <path d={path} fill="none" stroke="var(--color-s1)" strokeWidth={2} />
          {points.map((p, i) => hl.has(p.date) && (
            <g key={p.date}>
              <circle cx={x(i)} cy={y(p.value)} r={5} fill="var(--color-critical)" stroke="var(--color-surface)" strokeWidth={2} />
              <text x={x(i)} y={y(p.value) - 10} textAnchor="middle" className="fill-critical-ink text-[10px] font-semibold">{highlightLabel}</text>
            </g>
          ))}
          {xTicks.map((i) => points[i] && (
            <text key={i} x={x(i)} y={ih + 18} textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"} className="fill-muted text-[10px]">
              {formatDate(points[i].date)}
            </text>
          ))}
          <line x1={0} x2={iw} y1={ih} y2={ih} stroke="var(--color-axis)" />
          {hover !== null && points[hover] && (
            <g pointerEvents="none">
              <line x1={x(hover)} x2={x(hover)} y1={0} y2={ih} stroke="var(--color-axis)" />
              <circle cx={x(hover)} cy={y(points[hover].value)} r={4} fill="var(--color-s1)" stroke="var(--color-surface)" strokeWidth={2} />
            </g>
          )}
          <rect width={iw} height={ih} fill="transparent" onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
        </g>
      </svg>
      {hover !== null && points[hover] && (
        <Tooltip x={m.left + x(hover)} y={m.top + y(points[hover].value)} width={width}>
          <div className="text-muted">{formatDate(points[hover].date)}</div>
          <div className="tabular font-semibold">{format(points[hover].value)}</div>
        </Tooltip>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ horizontal bars

export interface BarDatum { key: string; label: string; value: number; detail?: string }

export function HBarChart({ rows, format, onSelect, label, color = "var(--color-s1)", maxRows = 8 }: {
  rows: BarDatum[]; format: (v: number) => string; onSelect?: (key: string) => void; label: string; color?: string; maxRows?: number;
}) {
  const shown = rows.slice(0, maxRows);
  const max = Math.max(1e-9, ...shown.map((r) => Math.abs(r.value)));
  return (
    <ul aria-label={label} className="space-y-2.5">
      {shown.map((r) => {
        const pct = Math.max(0.5, (Math.abs(r.value) / max) * 100);
        const content = (
          <>
            <div className="flex items-baseline justify-between gap-3 text-xs">
              <span className="truncate text-ink">{r.label}</span>
              <span className="tabular shrink-0 font-medium text-ink">{format(r.value)}</span>
            </div>
            <div className="mt-1 h-2 w-full rounded-full bg-subtle">
              <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: color }} />
            </div>
            {r.detail && <div className="mt-0.5 text-[11px] text-muted">{r.detail}</div>}
          </>
        );
        return (
          <li key={r.key}>
            {onSelect ? (
              <button type="button" onClick={() => onSelect(r.key)} className="block w-full rounded text-left hover:bg-subtle/60 focus-visible:bg-subtle" title={r.label}>
                {content}
              </button>
            ) : content}
          </li>
        );
      })}
    </ul>
  );
}

// ------------------------------------------------------------------ columns

export function ColumnChart({ rows, format, label, height = 180 }: {
  rows: { key: string; label: string; value: number | null }[]; format: (v: number) => string; label: string; height?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const m = { top: 10, right: 8, bottom: 24, left: 44 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;
  const x = scaleBand<number>().domain(rows.map((_, i) => i)).range([0, iw]).paddingInner(0.3).paddingOuter(0.1);
  const y = scaleLinear().domain([0, Math.max(0.01, ...rows.map((r) => r.value ?? 0))]).nice(4).range([ih, 0]);
  const bw = Math.min(28, x.bandwidth());
  return (
    <div ref={ref} className="relative">
      <svg width={width} height={height} role="img" aria-label={label}>
        <g transform={`translate(${m.left},${m.top})`}>
          {y.ticks(4).map((tk) => (
            <g key={tk}>
              <line x1={0} x2={iw} y1={y(tk)} y2={y(tk)} stroke="var(--color-line)" />
              <text x={-8} y={y(tk)} dy="0.32em" textAnchor="end" className="tabular fill-muted text-[10px]">{format(tk)}</text>
            </g>
          ))}
          {rows.map((r, i) => {
            const v = r.value ?? 0;
            const cx0 = (x(i) ?? 0) + (x.bandwidth() - bw) / 2;
            return (
              <g key={r.key} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect x={x(i)} y={0} width={x.bandwidth()} height={ih} fill="transparent" />
                <path d={roundedTop(cx0, y(v), bw, ih - y(v), 4)} fill="var(--color-s1)" opacity={hover === null || hover === i ? 1 : 0.55} />
              </g>
            );
          })}
          {rows.length > 0 && [0, rows.length - 1].map((i) => (
            <text key={i} x={(x(i) ?? 0) + x.bandwidth() / 2} y={ih + 16} textAnchor="middle" className="fill-muted text-[10px]">{rows[i].label}</text>
          ))}
          <line x1={0} x2={iw} y1={ih} y2={ih} stroke="var(--color-axis)" />
        </g>
      </svg>
      {hover !== null && rows[hover] && (
        <Tooltip x={m.left + (x(hover) ?? 0)} y={m.top + y(rows[hover].value ?? 0)} width={width}>
          <div className="text-muted">{rows[hover].label}</div>
          <div className="tabular font-semibold">{rows[hover].value === null ? "—" : format(rows[hover].value as number)}</div>
        </Tooltip>
      )}
    </div>
  );
}

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0) return "";
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

// ------------------------------------------------------------------ bridge (waterfall)

export interface BridgeStep { key: string; label: string; value: number; kind: "benefit" | "cost" | "total" }

export function BridgeChart({ steps, format, label, height = 260 }: { steps: BridgeStep[]; format: (v: number) => string; label: string; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const m = { top: 16, right: 8, bottom: 64, left: 60 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;

  const bars = useMemo(() => {
    let run = 0;
    return steps.map((s) => {
      if (s.kind === "total") return { ...s, from: 0, to: s.value };
      const from = run;
      run += s.kind === "benefit" ? s.value : -s.value;
      return { ...s, from, to: run };
    });
  }, [steps]);
  const lo = Math.min(0, ...bars.map((b) => Math.min(b.from, b.to)));
  const hi = Math.max(0, ...bars.map((b) => Math.max(b.from, b.to)));
  const x = scaleBand<number>().domain(bars.map((_, i) => i)).range([0, iw]).paddingInner(0.25).paddingOuter(0.1);
  const y = scaleLinear().domain([lo, hi]).nice(5).range([ih, 0]);
  const color = { benefit: "var(--color-s1)", cost: "var(--color-s2)", total: "var(--color-brand)" };

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={height} role="img" aria-label={label}>
        <g transform={`translate(${m.left},${m.top})`}>
          {y.ticks(5).map((tk) => (
            <g key={tk}>
              <line x1={0} x2={iw} y1={y(tk)} y2={y(tk)} stroke={tk === 0 ? "var(--color-axis)" : "var(--color-line)"} />
              <text x={-8} y={y(tk)} dy="0.32em" textAnchor="end" className="tabular fill-muted text-[10px]">{format(tk)}</text>
            </g>
          ))}
          {bars.map((b, i) => {
            const top = y(Math.max(b.from, b.to));
            const h = Math.max(1, Math.abs(y(b.from) - y(b.to)));
            const bx = x(i) ?? 0;
            return (
              <g key={b.key} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect x={bx} y={top} width={x.bandwidth()} height={h} rx={3} fill={color[b.kind]} opacity={hover === null || hover === i ? 1 : 0.6} />
                {i < bars.length - 1 && b.kind !== "total" && (
                  <line x1={bx + x.bandwidth()} x2={(x(i + 1) ?? 0)} y1={y(b.to)} y2={y(b.to)} stroke="var(--color-axis)" strokeDasharray="2 2" />
                )}
                <text transform={`translate(${bx + x.bandwidth() / 2},${ih + 10}) rotate(35)`} className="fill-ink-2 text-[10px]">
                  {b.label.length > 18 ? `${b.label.slice(0, 17)}…` : b.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      {hover !== null && bars[hover] && (
        <Tooltip x={m.left + (x(hover) ?? 0)} y={m.top + y(Math.max(bars[hover].from, bars[hover].to))} width={width}>
          <div className="text-muted">{bars[hover].label}</div>
          <div className="tabular font-semibold">{bars[hover].kind === "cost" ? "−" : ""}{format(bars[hover].value)}</div>
        </Tooltip>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ forest plot

export interface ForestRow { key: string; label: string; estimate: number | null; low: number | null; high: number | null; significant: boolean; note?: string }

export function ForestPlot({ rows, format, label, zeroLabel }: { rows: ForestRow[]; format: (v: number) => string; label: string; zeroLabel?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const rowH = 34;
  const m = { top: 8, right: 16, bottom: 28, left: Math.min(220, width * 0.38) };
  const iw = width - m.left - m.right;
  const height = m.top + m.bottom + rows.length * rowH;
  const vals = rows.flatMap((r) => [r.low, r.high, r.estimate].filter((v): v is number => v !== null));
  const ext = Math.max(1, ...vals.map(Math.abs));
  const x = scaleLinear().domain([-ext, ext]).nice(4).range([0, iw]);
  return (
    <div ref={ref}>
      <svg width={width} height={height} role="img" aria-label={label} overflow="hidden">
        <g transform={`translate(${m.left},${m.top})`}>
          {x.ticks(5).map((tk) => (
            <g key={tk}>
              <line x1={x(tk)} x2={x(tk)} y1={0} y2={rows.length * rowH} stroke={tk === 0 ? "var(--color-ink-2)" : "var(--color-line)"} strokeDasharray={tk === 0 ? undefined : "2 3"} />
              <text x={x(tk)} y={rows.length * rowH + 16} textAnchor="middle" className="tabular fill-muted text-[10px]">{format(tk)}</text>
            </g>
          ))}
          {zeroLabel && <text x={x(0) + 4} y={10} className="fill-muted text-[10px]">{zeroLabel}</text>}
          {rows.map((r, i) => {
            const cy = i * rowH + rowH / 2;
            return (
              <g key={r.key}>
                <text x={-12} y={cy} dy="0.32em" textAnchor="end" className="fill-ink text-[11px]">{r.label.length > 34 ? `${r.label.slice(0, 33)}…` : r.label}</text>
                {r.estimate !== null && r.low !== null && r.high !== null ? (
                  <>
                    <line x1={x(r.low)} x2={x(r.high)} y1={cy} y2={cy} stroke={r.significant ? "var(--color-s1)" : "var(--color-axis)"} strokeWidth={2} />
                    <circle cx={x(r.estimate)} cy={cy} r={5} fill={r.significant ? "var(--color-s1)" : "var(--color-surface)"} stroke={r.significant ? "var(--color-surface)" : "var(--color-ink-2)"} strokeWidth={2}>
                      <title>{`${r.label}: ${format(r.estimate)} (${format(r.low)} … ${format(r.high)})`}</title>
                    </circle>
                  </>
                ) : (
                  <text x={x(0) + 8} y={cy} dy="0.32em" className="fill-muted text-[10px]">{r.note ?? "—"}</text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

// ------------------------------------------------------------------ progress (budgets / scenarios)

export function Meter({ value, marker, tone = "neutral", label }: { value: number; marker?: number | null; tone?: "neutral" | "warning" | "critical" | "good"; label: string }) {
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  const fill = { neutral: "var(--color-s1)", good: "var(--color-s1)", warning: "var(--color-warning)", critical: "var(--color-critical)" }[tone];
  return (
    <div className="relative h-2.5 w-full rounded-full bg-subtle" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)} aria-label={label}>
      <div className="h-2.5 rounded-full" style={{ width: `${clamp(value) * 100}%`, background: fill }} />
      {marker !== undefined && marker !== null && (
        <div className={cx("absolute -top-1 h-4.5 w-0.5 rounded bg-ink")} style={{ left: `calc(${clamp(marker) * 100}% - 1px)`, height: 18 }} />
      )}
    </div>
  );
}
