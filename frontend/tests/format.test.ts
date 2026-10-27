import assert from "node:assert/strict";
import { test } from "node:test";

import { DASH, formatCompact, formatCurrency, formatDate, formatNumber, formatPct, formatRatio, formatSigned } from "../src/lib/format";
import { EMPTY_FILTERS, activeCount, toQuery, windowStart } from "../src/lib/filters";

const nbsp = (s: string) => s.replace(/[  ]/g, " ");

test("currency follows locale conventions", () => {
  assert.equal(nbsp(formatCurrency(12345.6, "en")), "€12,346");
  assert.equal(nbsp(formatCurrency(12345.6, "es")), "12.346 €");
  assert.equal(nbsp(formatCurrency(3.456, "es")), "3,46 €");
  assert.equal(formatCurrency(null, "en"), DASH);
});

test("percentages and ratios", () => {
  assert.equal(nbsp(formatRatio(0.256, "en")), "25.6%");
  assert.equal(nbsp(formatRatio(0.256, "es")), "25,6 %");
  assert.equal(nbsp(formatPct(-26.4, "es")), "-26,4 %");
  assert.equal(formatSigned(formatPct(12, "en"), 12), "+12.0%");
  assert.equal(formatPct(undefined, "en"), DASH);
});

test("numbers and compact numbers", () => {
  assert.equal(formatNumber(1234567, "en"), "1,234,567");
  assert.equal(nbsp(formatNumber(1234567, "es")), "1.234.567");
  assert.equal(formatCompact(2_958_261_432, "en"), "3bn");
  assert.equal(formatCompact(999, "es"), "999");
});

test("dates", () => {
  assert.equal(formatDate("2026-09-30", "en"), "30 Sept 2026");
  assert.equal(formatDate("2026-09-30", "es"), "30 sept 2026");
  assert.equal(formatDate(null, "en"), DASH);
});

test("filters encode to the API query string", () => {
  assert.equal(toQuery(EMPTY_FILTERS), "");
  const f = { ...EMPTY_FILTERS, start: "2026-09-01", departments: ["sales", "marketing"], models: ["gpt-demo-large"] };
  assert.equal(toQuery(f, { locale: "es" }), "?start=2026-09-01&departments=sales%2Cmarketing&models=gpt-demo-large&locale=es");
  assert.equal(activeCount(f), 3);
  assert.equal(windowStart("2026-09-30", 30), "2026-09-01");
});
