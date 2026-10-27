/**
 * Cross-layer check: every enum value, reason, rule id and metric name the
 * backend emits for the demo dataset has a translation in both languages.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { hasKey } from "../src/i18n/core";

const P = JSON.parse(readFileSync(join(__dirname, "fixtures", "demo-payloads.json"), "utf8"));

function need(keys: Set<string>) {
  const missing: string[] = [];
  for (const k of keys) for (const l of ["en", "es"] as const) if (!hasKey(l, k)) missing.push(`${l}:${k}`);
  assert.deepEqual(missing, []);
}

test("departments, use cases, providers", () => {
  const keys = new Set<string>(["department.unallocated", "department.organization"]);
  for (const d of P.meta.departments) keys.add(`department.${d.id}`);
  for (const u of P.meta.use_cases) keys.add(`use_case.${u.id}`);
  for (const p of P.meta.providers) keys.add(`provider.${p}`);
  for (const m of P.meta.models) keys.add(`costs.tier_${m.tier}`);
  for (const f of P.meta.ingestion_formats) keys.add(`data.format_${f}`);
  need(keys);
});

test("decisions, statuses, reasons, designs, segments", () => {
  const keys = new Set<string>();
  for (const d of Object.values<any>(P.use_case_details)) {
    const c = d.comparison;
    keys.add(`decision.${c.decision}`).add(`decision_help.${c.decision}`).add(`study_design.${c.study_design}`);
    keys.add(`roi_status.${d.roi.status}`).add(`complexity.${d.task_complexity}`);
    for (const r of [...c.reasons, ...d.roi.reasons]) keys.add(`reason.${String(r).split(":")[0]}`);
    for (const s of c.segments) keys.add(`task_type.${s.task_type}`);
    for (const cl of [...d.roi.benefits.counted, ...d.roi.benefits.excluded]) {
      keys.add(`benefit_category.${cl.category}`).add(`verification.${cl.verification_status}`);
      if (cl.reason) keys.add(`exclusion.${cl.reason}`);
    }
    for (const k of Object.keys(d.roi.costs)) keys.add(`cost_category.${k}`);
    for (const k of Object.keys(d.roi.scenarios)) keys.add(`scenario.${k}`);
  }
  for (const r of P.dashboard.overview.roi_reasons) keys.add(`reason.${r}`);
  keys.add(`roi_status.${P.dashboard_openai_only.overview.roi_status}`);
  for (const b of P.dashboard.budgets.rows) keys.add(`budget_status.${b.status}`).add(`department.${b.department}`);
  for (const k of Object.values<any>(P.dashboard.overview.kpis)) keys.add(`${k.definition_key}.label`).add(`${k.definition_key}.definition`);
  need(keys);
});

test("recommendations: rules, severities, metric names", () => {
  const keys = new Set<string>();
  for (const r of P.recommendations.rows) {
    keys.add(`${r.message_key}.title`).add(`${r.message_key}.body`).add(`severity.${r.severity}`);
    for (const m of Object.keys(r.metrics)) keys.add(`rec_metric.${m}`);
  }
  need(keys);
});

test("assumptions have labels", () => {
  need(new Set(Object.keys(P.assumptions).map((k) => `settings.${k}`)));
});
