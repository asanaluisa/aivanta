/** Response shapes of the Aivanta API (mirrors backend/aivanta_core/serialize.py). */

export type Basis = "measured" | "evidence_backed" | "estimated";
export type Unit = "currency" | "count" | "decimal" | "ratio" | "percent" | "hours";

export interface Kpi {
  value: number | null;
  basis: Basis;
  definition_key: string;
  unit: Unit;
  net?: number | null;
}

export interface Scenario {
  name: "conservative" | "expected" | "optimistic";
  gross_benefit: number;
  total_cost: number;
  net_benefit: number;
  roi_pct: number | null;
  includes_estimates: boolean;
}

export interface Claim {
  id: string;
  use_case: string;
  category: string;
  amount: number;
  verification_status: string;
  evidence_key: string;
  period_start: string;
  period_end: string;
  confidence: number;
  source: string;
  reason?: string;
}

export type CostKey =
  | "model_usage" | "subscription" | "infrastructure" | "implementation"
  | "maintenance" | "human_review" | "rework" | "other_operating" | "total";

export interface Roi {
  status: "ok" | "insufficient_evidence" | "no_costs";
  reasons: string[];
  period_days: number;
  costs: Record<CostKey, number>;
  one_off_cost: number;
  recurring_cost: number;
  benefits: {
    verified_savings: number;
    supported_contribution: number;
    supported_cost_avoidance: number;
    verified_component: number;
    supported_component: number;
    gross: number;
    estimated_excluded: number;
    counted: Claim[];
    excluded: Claim[];
  };
  gross_benefit: number;
  net_benefit: number | null;
  roi_pct: number | null;
  benefit_cost_ratio: number | null;
  cost_per_successful_task: number | null;
  successful_tasks: number;
  break_even_tasks: number | null;
  payback_months: number | null;
  hours: {
    gross: number | null;
    net: number | null;
    baseline_source: string | null;
    baseline_minutes_per_task: number | null;
    ai_minutes_per_task: number | null;
  };
  estimated_time_value: number | null;
  scenarios: Partial<Record<Scenario["name"], Scenario>>;
}

export interface Overview {
  synthetic: boolean;
  currency: string;
  period: { start: string; end: string; days: number };
  roi_applicable: boolean;
  roi_status: string;
  roi_reasons: string[];
  insufficient_use_cases: string[];
  kpis: Record<string, Kpi>;
  roi: Roi | null;
}

export interface BreakdownRow {
  key: string;
  spend: number;
  share: number;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
  requests: number;
  error_rate: number | null;
  avg_latency_ms: number | null;
  retries: number;
  active_users: number;
  cost_per_request: number | null;
}

export interface Breakdown {
  dimension: "department" | "provider" | "model" | "use_case";
  rows: BreakdownRow[];
}

export interface TrendRow {
  date: string;
  spend: number;
  requests: number;
  tokens: number;
  active_users: number;
  errors: number;
}

export interface Trend {
  rows: TrendRow[];
  anomalies: { date: string; spend: number; zscore: number; typical: number }[];
}

export interface AdoptionRow {
  week_start: string;
  active_users: number;
  eligible_users: number;
  adoption_rate: number | null;
}

export interface BudgetRow {
  budget_id: string;
  department: string;
  month: string;
  budget: number;
  spent: number;
  utilization: number | null;
  forecast: number;
  forecast_utilization: number | null;
  status: "ok" | "warning" | "forecast_exceeds" | "exceeded";
}

export interface Dashboard {
  overview: Overview;
  trend: Trend;
  adoption: { rows: AdoptionRow[] };
  breakdowns: Record<Breakdown["dimension"], Breakdown>;
  budgets: { as_of: string; basis: string; rows: BudgetRow[] };
}

export interface DepartmentRow {
  department: string;
  spend: number;
  total_cost: number;
  tokens: number;
  requests: number;
  active_users: number;
  tasks_completed: number | null;
  hours_saved: number | null;
  net_hours_saved: number | null;
  quality: number | null;
  success_rate: number | null;
  gross_benefit: number;
  estimated_time_value: number | null;
  roi_status: string;
  roi_pct: number | null;
  net_benefit: number | null;
  insufficient_use_cases: string[];
}

export interface Difference {
  estimate: number | null;
  low: number | null;
  high: number | null;
  significant: boolean;
}

export interface Arm {
  n: number;
  first_day: string | null;
  last_day: string | null;
  mean_minutes: number | null;
  mean_total_minutes: number | null;
  success_rate: number | null;
  error_rate: number | null;
  rework_rate: number | null;
  quality: number | null;
  csat: number | null;
  tasks_per_hour: number | null;
  labour_cost: number;
  ai_cost: number;
  total_cost: number;
  cost_per_completed_task: number | null;
}

export type Decision = "continue" | "optimize" | "selective" | "experiment" | "stop";

export interface Comparison {
  use_case: string;
  study_design: string;
  causal: boolean;
  ai: Arm;
  non_ai: Arm;
  differences: Record<"total_minutes" | "quality" | "success_rate" | "error_rate", Difference>;
  cost_per_task_delta: number | null;
  estimated_net_benefit: number | null;
  segments: { task_type: string; n_ai: number; n_non_ai: number; total_minutes: Difference; quality: Difference; favourable: boolean }[];
  decision: Decision;
  reasons: string[];
}

export interface ComparisonRow extends Comparison {
  name_key: string;
  department: string | null;
  roi_status: string;
  roi_pct: number | null;
  net_benefit: number | null;
}

export interface UseCaseDetail {
  use_case: string;
  name_key: string;
  department: string | null;
  task_complexity: string;
  study_design: string;
  data_source: string;
  measurement_period: { start: string | null; end: string | null };
  documented_baseline_minutes: number | null;
  labour_rate: number | null;
  tasks_ai: number;
  quality_ai: number | null;
  success_rate_ai: number | null;
  roi: Roi;
  comparison: Comparison;
}

export interface UseCaseRow {
  use_case: string;
  name_key: string;
  department: string | null;
  study_design: string;
  task_complexity: string;
  tasks_ai: number;
  quality_ai: number | null;
  success_rate_ai: number | null;
  decision: Decision;
  roi_status: string;
  roi_pct: number | null;
  total_cost: number;
  gross_benefit: number;
  net_benefit: number | null;
  hours_saved: number | null;
  cost_per_task_delta: number | null;
  causal: boolean;
}

export interface Recommendation {
  rule_id: string;
  message_key: string;
  severity: "critical" | "warning" | "opportunity" | "info";
  scope_type: "organization" | "department" | "use_case" | "budget";
  scope_id: string;
  metrics: Record<string, unknown>;
  projected_monthly_saving: number | null;
  is_estimate: boolean;
  acknowledged?: boolean;
}

export interface PriceRow {
  provider: string;
  model: string;
  tier: string;
  effective_from: string;
  input_per_mtok: number;
  output_per_mtok: number;
  cached_input_per_mtok: number | null;
}

export type Assumptions = Record<string, number>;

export interface Meta {
  organization: string;
  currency: string;
  synthetic: boolean;
  period: { start: string; end: string };
  departments: { id: string; name_key: string; loaded_hourly_rate: number }[];
  use_cases: { id: string; name_key: string; department: string | null }[];
  providers: string[];
  models: PriceRow[];
  assumptions: Assumptions;
  ingestion_formats: string[];
  live_sync: Record<string, string>;
}

export interface Me {
  email: string | null;
  display_name: string | null;
  role: string;
  permissions: string[];
  preferred_locale: string;
  organization: string;
  organization_name: string;
}

export interface IngestionSummary {
  provider: string;
  format: string;
  accepted: number;
  duplicates: number;
  rejected: number;
  unallocated: number;
  rejections: { row: string; reason: string }[];
  batch_id?: number;
}

export interface Batch {
  id: number;
  format: string;
  filename: string;
  accepted: number;
  duplicates: number;
  rejected: number;
  unallocated: number;
  created_at: string;
}

export interface Snapshot {
  id: number;
  scope_type: string;
  scope_key: string;
  period_start: string;
  period_end: string;
  status: string;
  total_cost: number;
  gross_benefit: number;
  net_benefit: number | null;
  roi_pct: number | null;
  data_version: number;
  created_at: string;
}
