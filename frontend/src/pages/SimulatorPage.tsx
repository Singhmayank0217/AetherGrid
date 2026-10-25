import { useEffect, useState, useId } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  Download,
  Info,
  Layers,
  RefreshCw,
  SlidersHorizontal,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wind
} from 'lucide-react';
import {
  SimulatorData,
  SimulatorPeriod,
  getSimulator
} from '../services/api';

const fmt = (v: number | null | undefined, d = 0) =>
  v == null ? '—' : new Intl.NumberFormat('en-GB', { maximumFractionDigits: d }).format(v);

const formatUtcTime = (s: string | null | undefined) => {
  if (!s) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC'
  }).format(new Date(s)) + ' UTC';
};

const formatHourUtc = (s: string | null | undefined) => {
  if (!s) return '—';
  const d = new Date(s);
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${hh}:${mm} UTC`;
};

const formatCutoffLabel = (h: number) => `${String(h).padStart(2, '0')}:00 UTC`;


// Interactive SVG Chart for Simulator
function SimulatorChart({
  periods,
  scenarioPct,
  onSelectPeriod,
  selectedIdx
}: {
  periods: SimulatorPeriod[];
  scenarioPct: number;
  onSelectPeriod: (idx: number) => void;
  selectedIdx: number | null;
}) {
  const chartId = useId();
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (!periods || periods.length === 0) {
    return <div className="empty-chart">No period records available</div>;
  }

  const w = 920;
  const h = 260;
  const pX = 40;
  const pY = 25;

  const validVals: number[] = [];
  periods.forEach((p) => {
    if (p.baseline_forecast != null) validVals.push(p.baseline_forecast);
    if (p.scenario_forecast != null) validVals.push(p.scenario_forecast);
    if (p.actual != null) validVals.push(p.actual);
  });

  const maxVal = validVals.length ? Math.max(...validVals, 1000) * 1.1 : 20000;
  const minVal = 0;

  const getX = (idx: number) => {
    if (periods.length <= 1) return pX;
    return pX + (idx / (periods.length - 1)) * (w - 2 * pX);
  };

  const getY = (val: number | null) => {
    if (val == null) return h - pY;
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    return h - pY - ((clamped - minVal) / (maxVal - minVal)) * (h - 2 * pY);
  };

  const buildPath = (key: 'baseline_forecast' | 'scenario_forecast' | 'actual') => {
    let d = '';
    periods.forEach((p, idx) => {
      const v = p[key];
      if (v != null) {
        const x = getX(idx);
        const y = getY(v);
        d += (d === '' ? 'M ' : ' L ') + `${x.toFixed(1)} ${y.toFixed(1)}`;
      }
    });
    return d;
  };

  const activeIdx = hoverIdx ?? selectedIdx ?? (periods.length > 0 ? 0 : null);
  const activePeriod = activeIdx != null ? periods[activeIdx] : null;

  return (
    <div className="chart-wrap" style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        onMouseLeave={() => setHoverIdx(null)}
      >
        {/* Horizontal grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((r) => {
          const y = h - pY - r * (h - 2 * pY);
          const mw = Math.round(minVal + r * (maxVal - minVal));
          return (
            <g key={r}>
              <line x1={pX} x2={w - pX} y1={y} y2={y} className="grid-line" />
              <text x={pX - 6} y={y + 3} fill="#5a7182" fontSize="9" textAnchor="end">
                {fmt(mw)}
              </text>
            </g>
          );
        })}

        {/* Curves */}
        <path d={buildPath('actual')} className="line-actual" />
        <path d={buildPath('baseline_forecast')} className="line-forecast" />
        <path d={buildPath('scenario_forecast')} className="line-scenario" />

        {/* Hover / selection tracker */}
        {activeIdx != null && (
          <line
            x1={getX(activeIdx)}
            x2={getX(activeIdx)}
            y1={pY}
            y2={h - pY}
            stroke="#6cc7d9"
            strokeWidth="1"
            strokeDasharray="2 3"
          />
        )}

        {/* Interaction trigger zones */}
        {periods.map((p, idx) => (
          <rect
            key={p.timestamp}
            x={getX(idx) - (w / periods.length) / 2}
            y={0}
            width={w / periods.length}
            height={h}
            fill="transparent"
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHoverIdx(idx)}
            onClick={() => onSelectPeriod(idx)}
          />
        ))}

        {/* Point markers for active period */}
        {activeIdx != null && activePeriod && (
          <g>
            {activePeriod.actual != null && (
              <circle
                cx={getX(activeIdx)}
                cy={getY(activePeriod.actual)}
                r="4"
                fill="#39c79a"
                stroke="#071019"
                strokeWidth="2"
              />
            )}
            {activePeriod.baseline_forecast != null && (
              <circle
                cx={getX(activeIdx)}
                cy={getY(activePeriod.baseline_forecast)}
                r="4"
                fill="#6cc7d9"
                stroke="#071019"
                strokeWidth="2"
              />
            )}
            {activePeriod.scenario_forecast != null && (
              <circle
                cx={getX(activeIdx)}
                cy={getY(activePeriod.scenario_forecast)}
                r="4"
                fill="#e2ad62"
                stroke="#071019"
                strokeWidth="2"
              />
            )}
          </g>
        )}
      </svg>

      {/* Axis labels */}
      <div className="chart-axis" style={{ paddingLeft: pX, paddingRight: pX }}>
        <span>{formatHourUtc(periods[0].timestamp)}</span>
        <span>{formatHourUtc(periods[Math.floor(periods.length / 2)].timestamp)}</span>
        <span>{formatHourUtc(periods[periods.length - 1].timestamp)}</span>
      </div>

      {/* Active tooltip floating overlay */}
      {activePeriod && (
        <div
          style={{
            marginTop: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#091824',
            border: '1px solid #1c3242',
            padding: '8px 14px',
            borderRadius: 4,
            fontSize: 11
          }}
        >
          <div>
            <strong style={{ color: '#dce8ee' }}>
              {formatHourUtc(activePeriod.timestamp)} (SP {activePeriod.settlement_period ?? '—'})
            </strong>{' '}
            <span style={{ color: '#718797', marginLeft: 8 }}>
              Baseline: <b style={{ color: 'var(--cyan)' }}>{fmt(activePeriod.baseline_forecast)} MW</b>
            </span>{' '}
            <span style={{ color: '#718797', marginLeft: 10 }}>
              Scenario ({scenarioPct >= 0 ? '+' : ''}{scenarioPct}%):{' '}
              <b style={{ color: 'var(--amber)' }}>{fmt(activePeriod.scenario_forecast)} MW</b> (
              {activePeriod.scenario_delta_mw != null && activePeriod.scenario_delta_mw >= 0 ? '+' : ''}
              {fmt(activePeriod.scenario_delta_mw)} MW)
            </span>{' '}
            <span style={{ color: '#718797', marginLeft: 10 }}>
              Actual: <b style={{ color: 'var(--green)' }}>{fmt(activePeriod.actual)} MW</b>
            </span>
          </div>
          <div>
            <span style={{ color: '#718797' }}>
              Baseline Error:{' '}
              <b style={{ color: (activePeriod.error_mw ?? 0) >= 0 ? 'var(--amber)' : 'var(--red)' }}>
                {activePeriod.error_mw != null && activePeriod.error_mw >= 0 ? '+' : ''}
                {fmt(activePeriod.error_mw)} MW
              </b>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SimulatorPage() {
  const [date, setDate] = useState('2026-01-15');
  const [cutoffHour, setCutoffHour] = useState(23);
  const [scenarioPct, setScenarioPct] = useState(15.0);
  const [scenarioMw, setScenarioMw] = useState(0.0);
  const [resolution, setResolution] = useState<'hourly' | 'half_hourly'>('hourly');
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const [data, setData] = useState<SimulatorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    getSimulator(date, cutoffHour, scenarioPct, scenarioMw, resolution, refreshIndex > 0)
      .then((res) => {
        setData(res);
        if (res.periods && res.periods.length > 0) {
          setSelectedIdx(0);
        }
      })
      .catch((err) => setError(err.message || 'Failed to load simulator data'))
      .finally(() => setLoading(false));
  }, [date, cutoffHour, scenarioPct, scenarioMw, resolution, refreshIndex]);

  const selectedPeriod =
    data?.periods && selectedIdx != null ? data.periods[selectedIdx] : null;

  const downloadCsv = () => {
    if (!data) return;
    const header = [
      'delivery_time_utc',
      'settlement_period',
      'baseline_forecast_mw',
      'publish_time_utc',
      'cutoff_time_utc',
      'scenario_forecast_mw',
      'scenario_delta_mw',
      'actual_outturn_mw',
      'baseline_error_mw',
      'scenario_error_mw',
      'is_step_extended',
      'latest_post_cutoff_mw',
      'attention_flags',
      'attention_reason'
    ].join(',');

    const rows = data.periods.map((p) =>
      [
        p.timestamp,
        p.settlement_period ?? '',
        p.baseline_forecast ?? '',
        p.publish_time ?? '',
        p.cutoff_time ?? '',
        p.scenario_forecast ?? '',
        p.scenario_delta_mw ?? '',
        p.actual ?? '',
        p.error_mw ?? '',
        p.scenario_error_mw ?? '',
        p.is_step_extended ? 'true' : 'false',
        p.latest_post_cutoff?.generation ?? '',
        `"${p.attention_flags.join(';')}"`,
        `"${p.attention_reason.replace(/"/g, '""')}"`
      ].join(',')
    );

    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aethergrid-simulator-${date}-cutoff${cutoffHour}h-${resolution}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="pulse" /> DAY-AHEAD TRADING & PROCUREMENT SIMULATOR
          </div>
          <h1>Procurement Decision Simulator & Cutoff Replay</h1>
          <p>
            Reconstruct available Elexon wind forecasts at day-ahead decision cutoffs, stress test upside/downside scenarios,
            and audit delivery-period forecast deviations against empirical error quantiles.
          </p>
        </div>
        <div className="data-status">
          <span className={data ? 'status-live' : 'status-muted'} />
          {data ? 'DECISION SIMULATION READY' : 'SIMULATING'}
        </div>
      </div>

      {/* Top Controls: Date, Cutoff Presets, Resolution */}
      <div className="control-bar" style={{ display: 'grid', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div className="control-group">
            <span className="control-label">Delivery Date:</span>
            <select
              className="select-input"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              disabled={loading}
            >
              {Array.from({ length: 31 }, (_, i) => {
                const day = String(i + 1).padStart(2, '0');
                const dStr = `2026-01-${day}`;
                return (
                  <option key={dStr} value={dStr}>
                    {day} Jan 2026
                  </option>
                );
              })}
            </select>

            <span className="control-label" style={{ marginLeft: 12 }}>
              Delivery Resolution:
            </span>
            <div className="segmented">
              <button
                type="button"
                className={resolution === 'hourly' ? 'selected' : ''}
                onClick={() => setResolution('hourly')}
                disabled={loading}
              >
                Hourly (24 Periods)
              </button>
              <button
                type="button"
                className={resolution === 'half_hourly' ? 'selected' : ''}
                onClick={() => setResolution('half_hourly')}
                disabled={loading}
              >
                Half-Hourly (48 SP)
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="outline-btn"
              onClick={downloadCsv}
              disabled={!data}
              type="button"
              title="Export simulation to CSV"
            >
              <Download size={13} />
              Export Simulation CSV
            </button>
            <button
              className="refresh-btn"
              onClick={() => setRefreshIndex((i) => i + 1)}
              disabled={loading}
              type="button"
            >
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
              Recalculate
            </button>
          </div>
        </div>

        {/* Cutoff Presets Bar */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span className="control-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Clock size={12} /> Day-Ahead Publication Cutoff (D-1):
            </span>
            <span style={{ fontSize: 10, color: '#688092' }}>
              Publications after cutoff are strictly excluded from the baseline forecast.
            </span>
          </div>
          <div className="cutoff-presets-bar">
            {data?.cutoff_policy?.presets?.map((p) => (
              <button
                key={p.hour_utc}
                type="button"
                className={`preset-btn ${cutoffHour === p.hour_utc ? 'active' : ''}`}
                onClick={() => setCutoffHour(p.hour_utc)}
                disabled={loading}
                title={p.description}
              >
                <Clock size={12} />
                <span>{p.label}</span>
              </button>
            )) || (
              <>
                <button
                  type="button"
                  className={`preset-btn ${cutoffHour === 11 ? 'active' : ''}`}
                  onClick={() => setCutoffHour(11)}
                >
                  11:00 UTC — EPEX SPOT Auction
                </button>
                <button
                  type="button"
                  className={`preset-btn ${cutoffHour === 12 ? 'active' : ''}`}
                  onClick={() => setCutoffHour(12)}
                >
                  12:00 UTC — Nord Pool Auction
                </button>
                <button
                  type="button"
                  className={`preset-btn ${cutoffHour === 17 ? 'active' : ''}`}
                  onClick={() => setCutoffHour(17)}
                >
                  17:00 UTC — BMRS Gate Closure
                </button>
                <button
                  type="button"
                  className={`preset-btn ${cutoffHour === 23 ? 'active' : ''}`}
                  onClick={() => setCutoffHour(23)}
                >
                  23:00 UTC — Application Default
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button
            className="outline-btn"
            style={{ marginLeft: 'auto' }}
            onClick={() => setRefreshIndex((i) => i + 1)}
            type="button"
          >
            Retry
          </button>
        </div>
      )}

      {/* Scenario Control Panel */}
      <div className="section-card scenario-panel" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ fontSize: 14, margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <SlidersHorizontal size={15} style={{ color: 'var(--amber)' }} />
              Hypothetical Wind Generation Stress Scenario
            </h2>
            <p style={{ margin: 0, fontSize: 11, color: '#7b92a3' }}>
              Adjust generation up or down to stress-test procurement buffers. Formula:{' '}
              <code style={{ color: 'var(--amber)', background: '#0a1723', padding: '2px 6px', borderRadius: 3 }}>
                G_scenario = max(0, Baseline × (1 + %/100) + MW)
              </code>
            </p>
          </div>
          <div className="badge amber">
            Analytical Stress Scenario · NOT an Official Elexon Forecast
          </div>
        </div>

        <div className="scenario-slider-row">
          <span style={{ minWidth: 80, fontSize: 11, color: 'var(--muted)' }}>
            Adjustment:
          </span>
          <input
            type="range"
            min="-50"
            max="50"
            step="1"
            value={scenarioPct}
            onChange={(e) => setScenarioPct(Number(e.target.value))}
            className="scenario-slider"
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="number"
              min="-100"
              max="200"
              step="0.5"
              value={scenarioPct}
              onChange={(e) => setScenarioPct(Number(e.target.value))}
              style={{
                width: 72,
                background: '#0a1723',
                border: '1px solid #233b4e',
                color: 'var(--amber)',
                fontSize: 13,
                fontWeight: 600,
                textAlign: 'center',
                padding: '4px 6px',
                borderRadius: 3
              }}
            />
            <span style={{ fontSize: 12, color: 'var(--amber)', fontWeight: 600 }}>%</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 16 }}>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>MW Offset:</span>
            <input
              type="number"
              step="100"
              value={scenarioMw}
              onChange={(e) => setScenarioMw(Number(e.target.value))}
              placeholder="0 MW"
              style={{
                width: 84,
                background: '#0a1723',
                border: '1px solid #233b4e',
                color: '#dce8ee',
                fontSize: 12,
                textAlign: 'center',
                padding: '4px 6px',
                borderRadius: 3
              }}
            />
            <span style={{ fontSize: 11, color: '#6a8293' }}>MW</span>
          </div>

          <button
            type="button"
            className="chip-btn"
            style={{ marginLeft: 8 }}
            onClick={() => {
              setScenarioPct(0.0);
              setScenarioMw(0.0);
            }}
          >
            Reset (0%)
          </button>
        </div>

        <div className="scenario-chips">
          <span style={{ fontSize: 10, color: '#688092', alignSelf: 'center', marginRight: 4 }}>
            Quick Presets:
          </span>
          {[-20, -10, -5, 0, 5, 10, 20].map((pct) => (
            <button
              key={pct}
              type="button"
              className={`chip-btn ${scenarioPct === pct && scenarioMw === 0 ? 'active' : ''}`}
              onClick={() => {
                setScenarioPct(pct);
                setScenarioMw(0.0);
              }}
            >
              {pct > 0 ? `+${pct}%` : `${pct}%`}
            </button>
          ))}
          <span style={{ fontSize: 10, color: '#576f81', marginLeft: 'auto', alignSelf: 'center' }}>
            Net Energy Deviation:{' '}
            <b style={{ color: (data?.summary?.total_scenario_delta_mwh ?? 0) >= 0 ? 'var(--amber)' : 'var(--cyan)' }}>
              {(data?.summary?.total_scenario_delta_mwh ?? 0) >= 0 ? '+' : ''}
              {fmt(data?.summary?.total_scenario_delta_mwh)} MWh
            </b>
          </span>
        </div>
      </div>

      {/* KPI Cards Strip */}
      <section className="metrics-grid">
        <article className="metric-card">
          <div className="metric-top">
            <span>Cutoff Baseline Mean</span>
            <span className="metric-dot cyan" />
          </div>
          <div className="metric-value">
            {fmt(data?.summary?.baseline_mean_mw)}
            <small>MW</small>
          </div>
          <div className="metric-detail">D-1 {formatCutoffLabel(cutoffHour)} Cutoff</div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Scenario Mean</span>
            <span className="metric-dot amber" />
          </div>
          <div className="metric-value">
            {fmt(data?.summary?.scenario_mean_mw)}
            <small>MW</small>
          </div>
          <div className="metric-detail">
            {scenarioPct >= 0 ? '+' : ''}{scenarioPct}% stress scenario
          </div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Actual Generation Mean</span>
            <span className="metric-dot green" />
          </div>
          <div className="metric-value">
            {fmt(data?.summary?.actual_mean_mw)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Eventual Elexon Outturn</div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Baseline MAE</span>
            <span className="metric-dot amber" />
          </div>
          <div className="metric-value">
            {fmt(data?.summary?.baseline_mae)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Day-ahead forecast error</div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Scenario MAE</span>
            <span className="metric-dot amber" />
          </div>
          <div className="metric-value">
            {fmt(data?.summary?.scenario_mae)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Scenario error vs actual</div>
        </article>
      </section>

      {/* Empirical Uncertainty Context Strip */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Compass size={15} style={{ color: 'var(--green)' }} />
            <strong style={{ fontSize: 13, color: '#e6edf3' }}>
              Historical January 2026 Empirical Error Percentiles
            </strong>
            <span className="badge green" style={{ fontSize: 9 }}>
              N = {data?.uncertainty_context?.sample_size ?? 744} {resolution === 'hourly' ? 'Hours' : 'Half-Hours'} (100% Coverage)
            </span>
          </div>
          <span style={{ fontSize: 10, color: '#688092' }}>
            Cutoff Policy: D-1 {formatCutoffLabel(cutoffHour)}
          </span>
        </div>

        <div className="uncertainty-strip">
          <div className="uncertainty-box">
            <div className="p-label">P50 (MEDIAN ABSOLUTE ERROR)</div>
            <div className="p-val" style={{ color: 'var(--green)' }}>
              {fmt(data?.uncertainty_context?.p50_mw)} <small style={{ fontSize: 11, color: 'var(--muted)' }}>MW</small>
            </div>
            <div className="p-sub">
              50% of historical hours experienced a forecast error less than this threshold.
            </div>
          </div>

          <div className="uncertainty-box">
            <div className="p-label">P80 ABSOLUTE ERROR</div>
            <div className="p-val" style={{ color: 'var(--cyan)' }}>
              {fmt(data?.uncertainty_context?.p80_mw)} <small style={{ fontSize: 11, color: 'var(--muted)' }}>MW</small>
            </div>
            <div className="p-sub">
              80% of historical hours fell within this absolute procurement deviation.
            </div>
          </div>

          <div className="uncertainty-box">
            <div className="p-label">P90 ABSOLUTE ERROR</div>
            <div className="p-val" style={{ color: 'var(--amber)' }}>
              {fmt(data?.uncertainty_context?.p90_mw)} <small style={{ fontSize: 11, color: 'var(--muted)' }}>MW</small>
            </div>
            <div className="p-sub">
              Tail risk boundary: Only 10% of periods experienced errors exceeding this magnitude.
            </div>
          </div>

          <div className="uncertainty-box">
            <div className="p-label">P95 ABSOLUTE ERROR</div>
            <div className="p-val" style={{ color: 'var(--red)' }}>
              {fmt(data?.uncertainty_context?.p95_mw)} <small style={{ fontSize: 11, color: 'var(--muted)' }}>MW</small>
            </div>
            <div className="p-sub">
              Extreme stress threshold: Severe ramp or storm volatility conditions.
            </div>
          </div>
        </div>

        <div style={{ fontSize: 10, color: '#6d8596', fontStyle: 'italic', paddingLeft: 4 }}>
          {data?.uncertainty_context?.disclaimer ||
            'Historical January 2026 empirical error percentiles for analytical context. These reflect observed winter volatility and are NOT forward-looking calibrated prediction intervals or guarantees.'}
        </div>
      </div>

      {/* Baseline vs Scenario vs Actual Multi-Line Chart */}
      <section className="section-card chart-card">
        <div className="card-head">
          <div>
            <h2>Forecast vs Scenario vs Eventual Actual Outturn</h2>
            <p>
              Delivery day trajectory: Baseline Elexon WINDFOR forecast (cutoff-compliant) vs hypothetical scenario vs eventual FUELHH actuals.
            </p>
          </div>
          <div className="legend">
            <span>
              <i className="legend-line forecast" /> Baseline Forecast (D-1 {formatCutoffLabel(cutoffHour)})
            </span>
            <span>
              <i className="legend-line scenario" /> Scenario ({scenarioPct >= 0 ? '+' : ''}{scenarioPct}%)
            </span>
            <span>
              <i className="legend-line actual" /> Eventual Actual (FUELHH)
            </span>
          </div>
        </div>

        {loading ? (
          <div className="chart-skeleton" />
        ) : (
          <SimulatorChart
            periods={data?.periods || []}
            scenarioPct={scenarioPct}
            onSelectPeriod={(idx) => setSelectedIdx(idx)}
            selectedIdx={selectedIdx}
          />
        )}
      </section>

      {/* Delivery-Period Attention Heatmap Matrix */}
      <section className="section-card heatmap-card">
        <div className="card-head">
          <div>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers size={16} style={{ color: 'var(--cyan)' }} />
              Delivery-Period Attention Heatmap Matrix ({data?.periods?.length || 24} Periods)
            </h2>
            <p>
              Identifies periods requiring procurement scrutiny due to severe historical error (&gt; P90 / P80), large publication revisions (&gt; 1,000 MW), intraday post-cutoff shifts, or step-extensions.
            </p>
          </div>
          <div className="legend" style={{ fontSize: 9 }}>
            <span>
              <span className="metric-dot red" style={{ display: 'inline-block', marginRight: 4 }} /> Severe Error (&gt; P90)
            </span>
            <span>
              <span className="metric-dot amber" style={{ display: 'inline-block', marginRight: 4 }} /> High Error (&gt; P80)
            </span>
            <span>
              <span className="metric-dot cyan" style={{ display: 'inline-block', marginRight: 4 }} /> Large Revision (&gt; 1GW)
            </span>
            <span>
              <span className="metric-dot green" style={{ display: 'inline-block', marginRight: 4 }} /> In-Spec
            </span>
          </div>
        </div>

        <div className="heatmap-grid">
          {data?.periods?.map((p, idx) => {
            const isSevere = p.attention_flags.includes('severe_error');
            const isHigh = p.attention_flags.includes('high_error');
            const isRevision = p.attention_flags.includes('large_revision');
            const isLookahead = p.attention_flags.includes('lookahead_shift');
            const isStep = p.is_step_extended;
            const isSelected = selectedIdx === idx;

            let cellClass = 'heatmap-cell';
            if (isSevere) cellClass += ' severe';
            else if (isHigh) cellClass += ' high';
            else if (isRevision) cellClass += ' revision';
            if (isStep) cellClass += ' step';
            if (isSelected) cellClass += ' selected';

            return (
              <div
                key={p.timestamp}
                className={cellClass}
                onClick={() => setSelectedIdx(idx)}
              >
                <div className="heatmap-time">
                  <span>{formatHourUtc(p.timestamp)}</span>
                  <span style={{ fontSize: 9, color: '#6f8696' }}>SP {p.settlement_period ?? '—'}</span>
                </div>
                <div className="heatmap-mw">
                  {fmt(p.baseline_forecast)} <small style={{ fontSize: 9, color: '#637b8c' }}>MW</small>
                </div>
                <div className="heatmap-error">
                  Err:{' '}
                  <span style={{ color: (p.error_mw ?? 0) >= 0 ? 'var(--amber)' : 'var(--red)' }}>
                    {p.error_mw != null && p.error_mw >= 0 ? '+' : ''}
                    {fmt(p.error_mw)} MW
                  </span>
                </div>
                <div className="heatmap-tags">
                  {isSevere && <span className="badge red" style={{ fontSize: 8, padding: '1px 4px' }}>&gt;P90</span>}
                  {!isSevere && isHigh && <span className="badge amber" style={{ fontSize: 8, padding: '1px 4px' }}>&gt;P80</span>}
                  {isRevision && <span className="badge cyan" style={{ fontSize: 8, padding: '1px 4px' }}>Rev Jump</span>}
                  {isLookahead && <span className="badge amber" style={{ fontSize: 8, padding: '1px 4px' }}>Intraday Shift</span>}
                  {isStep && <span className="badge gray" style={{ fontSize: 8, padding: '1px 4px' }}>Step-Ext</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Period Deep-Dive Detail */}
        {selectedPeriod && (
          <div
            style={{
              marginTop: 18,
              background: '#07131e',
              border: '1px solid #193144',
              padding: 16,
              borderRadius: 4
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
              <div>
                <strong style={{ fontSize: 13, color: '#dce8ee' }}>
                  Period Detail: {formatHourUtc(selectedPeriod.timestamp)} (Settlement Period {selectedPeriod.settlement_period ?? '—'})
                </strong>
                <span style={{ marginLeft: 12, fontSize: 11, color: '#688293' }}>
                  Delivery Window: {formatUtcTime(selectedPeriod.timestamp)}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {selectedPeriod.is_step_extended && (
                  <span className="badge gray">Step-Extended from Top-of-Hour Forecast</span>
                )}
                {selectedPeriod.attention_flags.map((flag) => (
                  <span
                    key={flag}
                    className={`badge ${flag === 'severe_error' ? 'red' : flag === 'high_error' ? 'amber' : 'cyan'}`}
                  >
                    {flag.replace(/_/g, ' ').toUpperCase()}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, fontSize: 11 }}>
              <div style={{ background: '#0b1926', padding: '10px 12px', borderRadius: 3 }}>
                <span style={{ color: '#667d8f', fontSize: 10 }}>Cutoff Baseline Forecast:</span>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--cyan)', marginTop: 4 }}>
                  {fmt(selectedPeriod.baseline_forecast)} MW
                </div>
                <div style={{ fontSize: 9, color: '#597082', marginTop: 2 }}>
                  Published: {formatUtcTime(selectedPeriod.publish_time)}
                </div>
              </div>

              <div style={{ background: '#0b1926', padding: '10px 12px', borderRadius: 3 }}>
                <span style={{ color: '#667d8f', fontSize: 10 }}>Hypothetical Scenario:</span>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--amber)', marginTop: 4 }}>
                  {fmt(selectedPeriod.scenario_forecast)} MW
                </div>
                <div style={{ fontSize: 9, color: '#597082', marginTop: 2 }}>
                  Deviation: {selectedPeriod.scenario_delta_mw != null && selectedPeriod.scenario_delta_mw >= 0 ? '+' : ''}
                  {fmt(selectedPeriod.scenario_delta_mw)} MW
                </div>
              </div>

              <div style={{ background: '#0b1926', padding: '10px 12px', borderRadius: 3 }}>
                <span style={{ color: '#667d8f', fontSize: 10 }}>Eventual Actual Outturn:</span>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--green)', marginTop: 4 }}>
                  {fmt(selectedPeriod.actual)} MW
                </div>
                <div style={{ fontSize: 9, color: '#597082', marginTop: 2 }}>
                  Outturn Miss: {selectedPeriod.error_mw != null && selectedPeriod.error_mw >= 0 ? '+' : ''}
                  {fmt(selectedPeriod.error_mw)} MW
                </div>
              </div>

              <div style={{ background: '#0b1926', padding: '10px 12px', borderRadius: 3 }}>
                <span style={{ color: '#667d8f', fontSize: 10 }}>Post-Cutoff Lookahead Vintage:</span>
                <div style={{ fontSize: 16, fontWeight: 600, color: selectedPeriod.latest_post_cutoff ? '#8ac7d8' : '#627786', marginTop: 4 }}>
                  {selectedPeriod.latest_post_cutoff ? `${fmt(selectedPeriod.latest_post_cutoff.generation)} MW` : 'No Later Vintage'}
                </div>
                <div style={{ fontSize: 9, color: '#597082', marginTop: 2 }}>
                  {selectedPeriod.latest_post_cutoff
                    ? `Published: ${formatUtcTime(selectedPeriod.latest_post_cutoff.publish_time)} (Shift: ${selectedPeriod.lookahead_delta_mw != null && selectedPeriod.lookahead_delta_mw >= 0 ? '+' : ''}${fmt(selectedPeriod.lookahead_delta_mw)} MW)`
                    : 'Cutoff baseline was latest available'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: 10, fontSize: 11, color: '#889ea8', background: '#0b1a27', padding: '8px 12px', borderRadius: 3 }}>
              <strong style={{ color: '#cad8df' }}>Explainable Attention Assessment:</strong> {selectedPeriod.attention_reason}
            </div>
          </div>
        )}
      </section>

      {/* Delivery-Period Cutoff Replay & Simulation Table */}
      <section className="section-card table-card" style={{ marginBottom: 20 }}>
        <div className="card-head" style={{ padding: '0 4px 12px' }}>
          <div>
            <h2>Delivery Period Cutoff Replay & Baseline Comparison</h2>
            <p>
              Replay table showing cutoff compliance, hypothetical scenario generation, eventual actual outturn, and lookahead post-cutoff vintages.
            </p>
          </div>
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Delivery Time (UTC)</th>
                <th>SP</th>
                <th>Baseline Forecast</th>
                <th>Published (UTC)</th>
                <th>Scenario ({scenarioPct >= 0 ? '+' : ''}{scenarioPct}%)</th>
                <th>Δ MW</th>
                <th>Actual Outturn</th>
                <th>Baseline Error</th>
                <th>Post-Cutoff Lookahead</th>
                <th>Attention Reason</th>
              </tr>
            </thead>
            <tbody>
              {data?.periods?.map((p, idx) => (
                <tr
                  key={p.timestamp}
                  style={{ cursor: 'pointer', background: selectedIdx === idx ? 'rgba(108, 199, 217, 0.08)' : undefined }}
                  onClick={() => setSelectedIdx(idx)}
                >
                  <td>
                    <strong>{formatUtcTime(p.timestamp)}</strong>
                  </td>
                  <td>{p.settlement_period ?? '—'}</td>
                  <td className="forecast-text">
                    {fmt(p.baseline_forecast)} MW
                  </td>
                  <td style={{ fontSize: 9, color: '#688294' }}>
                    {formatHourUtc(p.publish_time)}
                  </td>
                  <td style={{ color: 'var(--amber)', fontWeight: 500 }}>
                    {fmt(p.scenario_forecast)} MW
                  </td>
                  <td style={{ color: (p.scenario_delta_mw ?? 0) >= 0 ? 'var(--amber)' : 'var(--cyan)' }}>
                    {p.scenario_delta_mw != null && p.scenario_delta_mw >= 0 ? '+' : ''}
                    {fmt(p.scenario_delta_mw)}
                  </td>
                  <td className="actual-text">
                    {fmt(p.actual)} MW
                  </td>
                  <td className={(p.error_mw ?? 0) >= 0 ? 'positive' : 'negative'}>
                    {p.error_mw != null && p.error_mw >= 0 ? '+' : ''}
                    {fmt(p.error_mw)} MW
                  </td>
                  <td style={{ fontSize: 10, color: p.latest_post_cutoff ? '#7fb8c7' : '#576c7b' }}>
                    {p.latest_post_cutoff ? (
                      <>
                        {fmt(p.latest_post_cutoff.generation)} MW{' '}
                        <small style={{ color: '#577080' }}>({p.lookahead_delta_mw != null && p.lookahead_delta_mw >= 0 ? '+' : ''}{fmt(p.lookahead_delta_mw)})</small>
                      </>
                    ) : (
                      'None'
                    )}
                  </td>
                  <td style={{ fontSize: 9, maxWidth: 220, color: '#8aa1af' }}>
                    {p.attention_reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Prominent Data Integrity & Scope Disclaimers */}
      <div className="disclaimer-card">
        <h3>
          <CheckCircle2 size={15} /> Data Scope, Analytical Boundaries & Procurement Disclaimers
        </h3>
        <ul>
          {data?.disclaimers?.map((d, i) => (
            <li key={i}>{d}</li>
          )) || (
            <>
              <li>
                National wind generation values represent Great Britain transmission-connected and embedded wind outturn/forecasts from Elexon BMRS (FUELHH and WINDFOR).
              </li>
              <li>
                This simulator does NOT calculate a utility’s net procurement volume. Customer load demand, bilateral hedges, retail contracts, and other generation assets are excluded.
              </li>
              <li>
                Scenario adjustments are purely hypothetical analytical stress tests and must not be described as new or alternative Elexon forecasts.
              </li>
            </>
          )}
          <li>
            Day-ahead publication cutoff presets (11:00, 12:00, 17:00, 23:00 UTC) represent standard British power market convention benchmarks. They do not constitute official legal trading deadlines without verified evidence.
          </li>
        </ul>
      </div>
    </>
  );
}
