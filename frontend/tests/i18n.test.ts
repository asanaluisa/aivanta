import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { MESSAGES, flattenKeys, hasKey, placeholders, translate, lookup } from "../src/i18n/core";

const en = flattenKeys(MESSAGES.en);
const es = flattenKeys(MESSAGES.es);

test("English and Spanish define exactly the same keys", () => {
  assert.deepEqual([...es].sort(), [...en].sort());
});

test("translations keep the same placeholders and are never empty", () => {
  for (const key of en) {
    const a = lookup(MESSAGES.en, key)!;
    const b = lookup(MESSAGES.es, key)!;
    assert.ok(a.trim() && b.trim(), `empty translation for ${key}`);
    assert.deepEqual(placeholders(b), placeholders(a), `placeholder mismatch for ${key}`);
  }
});

test("required business terminology uses the agreed Spanish terms", () => {
  const expect: [string, string][] = [
    ["metric.ai_spend.label", "Gasto en IA"],
    ["metric.total_tokens.label", "Tokens totales"],
    ["metric.roi.label", "Retorno de la inversión (ROI)"],
    ["metric.net_benefit.label", "Beneficio neto"],
    ["metric.hours_saved.label", "Tiempo ahorrado"],
    ["metric.cost_per_successful_task.label", "Coste por tarea completada con éxito"],
    ["metric.adoption.label", "Adopción de IA"],
    ["nav.comparison", "IA frente a procesos sin IA"],
    ["roi_status.insufficient_evidence", "Evidencia insuficiente"],
  ];
  for (const [key, value] of expect) assert.ok(translate("es", key).startsWith(value), `${key}: ${translate("es", key)}`);
});

test("interpolation and fallbacks", () => {
  assert.equal(translate("en", "app.days", { count: 90 }), "90 days");
  assert.equal(translate("es", "app.days", { count: 90 }), "90 días");
  assert.equal(translate("es", "does.not.exist"), "does.not.exist");
});

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : /\.tsx?$/.test(f) ? [p] : [];
  });
}

test("every literal t(\"…\") key used in the code exists", () => {
  const src = join(__dirname, "..", "src");
  const missing: string[] = [];
  for (const file of walk(src)) {
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(/\bt\(\s*"([a-z_]+(?:\.[a-z0-9_]+)+)"/g)) {
      const key = m[1];
      const leaf = hasKey("en", key) || hasKey("en", `${key}.label`);
      if (!leaf) missing.push(`${file.replace(src, "src")}: ${key}`);
    }
  }
  assert.deepEqual(missing, []);
});
