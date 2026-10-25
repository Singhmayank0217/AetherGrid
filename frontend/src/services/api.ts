export interface Point {
  timestamp: string;
  forecast: number | null;
  actual: number | null;
  error: number | null;
  abs_error?: number | null;
  publish_time?: string | null;
  cutoff_time?: string | null;
  settlement_period?: number | null;
  versions_count?: number;
  is_step_extended?: boolean;
  forecast_type?: string;
}

export interface MetricsSummary {
  forecast_mean: number | null;
  actual_mean: number | null;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  median_abs_error?: number | null;
  max_abs_error?: number | null;
}

export interface QualitySummary {
  total_expected_periods?: number;
  total_series_periods: number;
  matched: number;
  unmatched_actual: number;
  unmatched_forecast: number;
  coverage_pct: number;
  step_extended_periods?: number;
}

export interface DailySummaryItem {
  date: string;
  sample_count: number;
  actual_mean: number;
  forecast_mean: number;
  mae: number;
  rmse: number;
  bias: number;
  max_error: number;
}

export interface ErrorDistributionItem {
  range: string;
  min: number | null;
  max: number | null;
  count: number;
  percentage: number;
}

export interface Overview {
  status: string;
  source: string;
  fetched_at: string;
  evaluation_range: { start_date: string; end_date: string };
  resolution: string;
  cutoff_policy: { hour_utc: number; description: string };
  forecast_representation?: string;
  forecast_representation_note?: string;
  sample_count: number;
  metrics: MetricsSummary;
  daily_summary?: DailySummaryItem[];
  distribution?: ErrorDistributionItem[];
  series: Point[];
  quality: QualitySummary;
}

export interface HistoricalVersion {
  publish_time: string;
  generation: number;
  is_eligible: boolean;
  hours_before_delivery: number;
  hours_before_cutoff: number;
}

export interface PeriodDetail extends Point {
  historical_versions: HistoricalVersion[];
}

export interface ForecastExplorerData {
  status: string;
  date: string;
  cutoff_policy: {
    hour_utc: number;
    cutoff_timestamp: string;
    description: string;
  };
  metrics: MetricsSummary;
  sample_count: number;
  periods: PeriodDetail[];
}

export interface DataQualityReport {
  status: string;
  generated_at: string;
  evaluation_range: { start_date: string; end_date: string };
  resolution: string;
  summary: {
    actual_record_count: number;
    forecast_raw_record_count: number;
    distinct_forecast_targets: number;
    total_expected_periods?: number;
    matched_delivery_periods: number;
    unmatched_actual_periods: number;
    unmatched_forecast_periods: number;
    coverage_pct: number;
    step_extended_periods?: number;
    zero_actual_periods: number;
  };
  integrity: {
    duplicate_actual_timestamps: number;
    duplicate_forecast_publications: number;
    missing_invalid_actuals: number;
    missing_invalid_forecasts: number;
    duplicate_policy: string;
  };
  temporal_bounds: {
    earliest_actual_delivery: string | null;
    latest_actual_delivery: string | null;
    earliest_forecast_target: string | null;
    latest_forecast_target: string | null;
    earliest_forecast_publish: string | null;
    latest_forecast_publish: string | null;
  };
  upstream_connectivity: {
    fuelhh: {
      status: string;
      status_code: number;
      latency_ms: number;
      fetched_at: string;
      record_count: number;
      endpoint: string;
    };
    windfor: {
      status: string;
      status_code: number;
      latency_ms: number;
      fetched_at: string;
      record_count: number;
      endpoint: string;
      query_publish_window?: string;
    };
    connectivity_status: string;
    freshness_status: string;
    note: string;
  };
}

const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function getOverview(
  start = '2026-01-01',
  end = '2026-01-31',
  cutoffHour = 23,
  resolution = 'half_hourly',
  forceRefresh = false
): Promise<Overview> {
  const url = `${base}/api/overview?start_date=${start}&end_date=${end}&cutoff_hour=${cutoffHour}&resolution=${resolution}&force_refresh=${forceRefresh}`;
  const r = await fetch(url);
  if (!r.ok) {
    const errorData = await r.json().catch(() => ({}));
    throw new Error(errorData.detail || `Backend data service unavailable (HTTP ${r.status})`);
  }
  return r.json();
}

export async function getAccuracy(
  start = '2026-01-01',
  end = '2026-01-31',
  cutoffHour = 23,
  resolution = 'half_hourly',
  forceRefresh = false
): Promise<Overview> {
  const url = `${base}/api/accuracy?start_date=${start}&end_date=${end}&cutoff_hour=${cutoffHour}&resolution=${resolution}&force_refresh=${forceRefresh}`;
  const r = await fetch(url);
  if (!r.ok) {
    const errorData = await r.json().catch(() => ({}));
    throw new Error(errorData.detail || `Accuracy analytics service unavailable (HTTP ${r.status})`);
  }
  return r.json();
}

export async function getForecasts(
  date = '2026-01-15',
  cutoffHour = 23,
  forceRefresh = false
): Promise<ForecastExplorerData> {
  const url = `${base}/api/forecasts?date=${date}&cutoff_hour=${cutoffHour}&force_refresh=${forceRefresh}`;
  const r = await fetch(url);
  if (!r.ok) {
    const errorData = await r.json().catch(() => ({}));
    throw new Error(errorData.detail || `Forecast explorer service unavailable (HTTP ${r.status})`);
  }
  return r.json();
}

export async function getDataQuality(
  start = '2026-01-01',
  end = '2026-01-31',
  cutoffHour = 23,
  resolution = 'half_hourly',
  forceRefresh = false
): Promise<DataQualityReport> {
  const url = `${base}/api/data-quality?start_date=${start}&end_date=${end}&cutoff_hour=${cutoffHour}&resolution=${resolution}&force_refresh=${forceRefresh}`;
  const r = await fetch(url);
  if (!r.ok) {
    const errorData = await r.json().catch(() => ({}));
    throw new Error(errorData.detail || `Data quality service unavailable (HTTP ${r.status})`);
  }
  return r.json();
}

export interface CutoffPreset {
  hour_utc: number;
  label: string;
  description: string;
  is_selected: boolean;
}

export interface PostCutoffVintage {
  publish_time: string;
  generation: number;
  hours_before_delivery: number;
}

export interface SimulatorPeriod {
  timestamp: string;
  settlement_period: number | null;
  baseline_forecast: number | null;
  scenario_forecast: number | null;
  scenario_delta_mw: number | null;
  actual: number | null;
  error_mw: number | null;
  scenario_error_mw: number | null;
  abs_error_mw: number | null;
  publish_time: string | null;
  cutoff_time: string;
  is_step_extended: boolean;
  forecast_type: string;
  historical_versions_count: number;
  historical_versions: HistoricalVersion[];
  latest_post_cutoff: PostCutoffVintage | null;
  lookahead_delta_mw: number | null;
  max_revision_mw: number;
  attention_flags: string[];
  attention_reason: string;
}

export interface UncertaintyContext {
  sample_size: number;
  evaluation_range: { start_date: string; end_date: string };
  resolution: string;
  p50_mw: number | null;
  p80_mw: number | null;
  p90_mw: number | null;
  p95_mw: number | null;
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  methodology: string;
  disclaimer: string;
}

export interface SimulatorData {
  status: string;
  date: string;
  resolution: string;
  cutoff_policy: {
    hour_utc: number;
    cutoff_timestamp: string;
    description: string;
    presets: CutoffPreset[];
  };
  scenario_config: {
    scenario_pct: number;
    scenario_mw: number;
    total_delta_mwh: number;
    description: string;
    note: string;
  };
  summary: {
    periods_count: number;
    matched_count: number;
    coverage_pct: number;
    baseline_mean_mw: number | null;
    scenario_mean_mw: number | null;
    actual_mean_mw: number | null;
    baseline_mae: number | null;
    scenario_mae: number | null;
    total_scenario_delta_mwh: number;
  };
  uncertainty_context: UncertaintyContext;
  periods: SimulatorPeriod[];
  disclaimers: string[];
}

export async function getSimulator(
  date = '2026-01-15',
  cutoffHour = 23,
  scenarioPct = 0.0,
  scenarioMw = 0.0,
  resolution = 'hourly',
  forceRefresh = false
): Promise<SimulatorData> {
  const url = `${base}/api/simulator?date=${date}&cutoff_hour=${cutoffHour}&scenario_pct=${scenarioPct}&scenario_mw=${scenarioMw}&resolution=${resolution}&force_refresh=${forceRefresh}`;
  const r = await fetch(url);
  if (!r.ok) {
    const errorData = await r.json().catch(() => ({}));
    throw new Error(errorData.detail || `Simulator service unavailable (HTTP ${r.status})`);
  }
  return r.json();
}

export async function getHealth(): Promise<{ status: string; service: string; timestamp: string }> {
  const r = await fetch(`${base}/health`);
  if (!r.ok) throw new Error(`Health check failed (HTTP ${r.status})`);
  return r.json();
}

