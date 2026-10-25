import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, Database, Download, RefreshCw } from 'lucide-react';
import { getOverview, Overview, Point } from '../services/api';

const fmt = (v: number | null | undefined, d = 0) =>
  v == null ? '—' : new Intl.NumberFormat('en-GB', { maximumFractionDigits: d }).format(v);

const time = (s: string) =>
  new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/London'
  }).format(new Date(s));

function MetricCard({
  label,
  value,
  unit,
  detail,
  accent = 'cyan'
}: {
  label: string;
  value: string;
  unit: string;
  detail: string;
  accent?: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className={`metric-dot ${accent}`} />
      </div>
      <div className="metric-value">
        {value}
        <small>{unit}</small>
      </div>
      <div className="metric-detail">{detail}</div>
    </article>
  );
}

function OverviewChart({ data, isError = false }: { data: Point[]; isError?: boolean }) {
  const rows = data.filter((p) => (isError ? p.error != null : p.actual != null || p.forecast != null)).slice(-96);
  if (!rows.length) {
    return (
      <div className="empty-chart">
        <Activity size={18} />
        <span>No matched observations available</span>
      </div>
    );
  }

  const maxVal = Math.max(
    ...rows.flatMap((p) => (isError ? [Math.abs(p.error || 0)] : [p.actual || 0, p.forecast || 0])),
    1
  );

  const w = 900;
  const h = 260;

  const x = (i: number) => 12 + (i / Math.max(rows.length - 1, 1)) * (w - 24);
  const y = (v: number) =>
    isError ? h / 2 - (v / maxVal) * (h / 2 - 20) : h - 20 - (v / maxVal) * (h - 40);

  const buildLine = (key: 'actual' | 'forecast' | 'error') =>
    rows
      .map((p, i) => (p[key] == null ? null : `${i ? 'L' : 'M'} ${x(i)} ${y(p[key] as number)}`))
      .filter(Boolean)
      .join(' ');

  return (
    <div className="chart-wrap">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={isError ? 'Forecast error chart' : 'Actual vs forecast chart'}
        preserveAspectRatio="none"
      >
        {[0.25, 0.5, 0.75].map((t) => (
          <line
            key={t}
            x1="12"
            x2={w - 12}
            y1={isError ? h / 2 - t * (h / 2 - 20) : y(maxVal * t)}
            y2={isError ? h / 2 - t * (h / 2 - 20) : y(maxVal * t)}
            className="grid-line"
          />
        ))}
        {isError && (
          <>
            {[0.25, 0.5, 0.75].map((t) => (
              <line
                key={`neg-${t}`}
                x1="12"
                x2={w - 12}
                y1={h / 2 + t * (h / 2 - 20)}
                y2={h / 2 + t * (h / 2 - 20)}
                className="grid-line"
              />
            ))}
            <line x1="12" x2={w - 12} y1={h / 2} y2={h / 2} className="zero-line" />
          </>
        )}
        <path d={buildLine(isError ? 'error' : 'actual')} className={isError ? 'line-error' : 'line-actual'} />
        {!isError && <path d={buildLine('forecast')} className="line-forecast" />}
      </svg>
      <div className="chart-axis">
        <span>{time(rows[0].timestamp)}</span>
        <span>{time(rows[Math.floor(rows.length / 2)].timestamp)}</span>
        <span>{time(rows[rows.length - 1].timestamp)}</span>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [resolution, setResolution] = useState<'half_hourly' | 'hourly'>('half_hourly');
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError('');
    getOverview('2026-01-01', '2026-01-31', 23, resolution, refreshIndex > 0)
      .then(setData)
      .catch((e) => setError(e.message || 'Failed to load executive overview'))
      .finally(() => setLoading(false));
  }, [resolution, refreshIndex]);

  const m = data?.metrics;

  const downloadCsv = () => {
    if (!data) return;
    const header = 'delivery_time,settlement_period,forecast_mw,actual_mw,error_mw,publish_time,cutoff_time';
    const rows = data.series.map(
      (r) =>
        `${r.timestamp},${r.settlement_period ?? ''},${r.forecast ?? ''},${r.actual ?? ''},${r.error ?? ''},${r.publish_time ?? ''},${r.cutoff_time ?? ''}`
    );
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aethergrid-overview-jan-2026-${resolution}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="pulse" /> EXECUTIVE INTELLIGENCE / UK NATIONAL
          </div>
          <h1>Wind Intelligence</h1>
          <p>National wind generation forecasts and day-ahead electricity procurement decision support.</p>
        </div>
        <div className="data-status">
          <span className={data ? 'status-live' : 'status-muted'} />
          {data ? 'LIVE DATA CONNECTED' : 'AWAITING DATA'}
        </div>
      </div>

      <div className="control-bar">
        <div className="control-group">
          <span className="control-label">Alignment Resolution:</span>
          <div className="segmented">
            <button
              className={resolution === 'half_hourly' ? 'selected' : ''}
              onClick={() => setResolution('half_hourly')}
              type="button"
            >
              30-Min Settlement (Default)
            </button>
            <button
              className={resolution === 'hourly' ? 'selected' : ''}
              onClick={() => setResolution('hourly')}
              type="button"
            >
              Exact Hourly Top (:00)
            </button>
          </div>
        </div>

        <button
          className="refresh-btn"
          onClick={() => setRefreshIndex((i) => i + 1)}
          disabled={loading}
          type="button"
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          {loading ? 'Refreshing…' : 'Refresh Data'}
        </button>
      </div>

      <div className="context-banner">
        <AlertTriangle size={17} className="banner-icon" />
        <div>
          <strong>Day-Ahead Decision Context</strong>
          <span>
            January 2026 forecasts use the documented previous-day 23:00 UTC cutoff assumption. Publication timestamp is
            rigorously separated from delivery timestamp. Positive bias indicates overforecasting (forecast &gt; actual);
            negative bias indicates underforecasting.
          </span>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={16} />
          <span>{error}. Check the backend service connection and retry.</span>
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

      <section className="metrics-grid">
        <MetricCard
          label="Forecast generation"
          value={loading ? '—' : fmt(m?.forecast_mean)}
          unit="MW avg"
          detail={`${data?.sample_count ?? 0} matched periods`}
        />
        <MetricCard
          label="Actual generation"
          value={loading ? '—' : fmt(m?.actual_mean)}
          unit="MW avg"
          detail="Elexon FUELHH · WIND"
          accent="green"
        />
        <MetricCard
          label="Mean absolute error (MAE)"
          value={loading ? '—' : fmt(m?.mae)}
          unit="MW"
          detail="Lower indicates better accuracy"
          accent="amber"
        />
        <MetricCard
          label="Root mean squared error (RMSE)"
          value={loading ? '—' : fmt(m?.rmse)}
          unit="MW"
          detail="Penalises large tail misses"
          accent="amber"
        />
        <MetricCard
          label="Forecast bias"
          value={loading ? '—' : `${(m?.bias ?? 0) >= 0 ? '+' : ''}${fmt(m?.bias, 1)}`}
          unit="MW"
          detail={(m?.bias ?? 0) >= 0 ? 'Overforecasting tendency' : 'Underforecasting tendency'}
          accent={(m?.bias ?? 0) >= 0 ? 'amber' : 'red'}
        />
      </section>

      <section className="section-card chart-card">
        <div className="card-head">
          <div>
            <h2>Actual vs forecast generation</h2>
            <p>National wind generation · selected day-ahead procurement decision vintages</p>
          </div>
          <div className="legend">
            <span>
              <i className="legend-line actual" /> Actual generation (FUELHH)
            </span>
            <span>
              <i className="legend-line forecast" /> Eligible day-ahead forecast (WINDFOR)
            </span>
          </div>
        </div>
        {loading ? <div className="chart-skeleton" /> : <OverviewChart data={data?.series || []} />}
      </section>

      <div className="two-col">
        <section className="section-card">
          <div className="card-head">
            <div>
              <h2>Forecast error (MW)</h2>
              <p>Forecast minus actual with zero baseline (amber = overforecast)</p>
            </div>
          </div>
          {loading ? (
            <div className="chart-skeleton small" />
          ) : (
            <OverviewChart data={data?.series || []} isError />
          )}
        </section>

        <section className="section-card quality-card">
          <div className="card-head">
            <div>
              <h2>Data coverage &amp; integrity</h2>
              <p>Evaluation sample completeness</p>
            </div>
            <Database size={17} className="muted-icon" />
          </div>

          <div className="coverage">
            <div
              className="coverage-ring"
              style={{ '--coverage': `${data?.quality.coverage_pct ?? 0}%` } as React.CSSProperties}
            >
              <strong>{loading ? '—' : `${data?.quality.coverage_pct ?? 0}%`}</strong>
              <small>matched</small>
            </div>
            <div className="quality-list">
              <div>
                <span>Matched periods</span>
                <b>{fmt(data?.quality.matched)}</b>
              </div>
              <div>
                <span>Unmatched actual periods</span>
                <b>{fmt(data?.quality.unmatched_actual)}</b>
              </div>
              <div>
                <span>Unmatched forecast periods</span>
                <b>{fmt(data?.quality.unmatched_forecast)}</b>
              </div>
              <div>
                <span>Total evaluation series</span>
                <b>{fmt(data?.quality.total_series_periods)}</b>
              </div>
            </div>
          </div>
          <div className="quality-note">
            In 30-min settlement alignment, hourly WINDFOR forecasts cover both half-hours (yielding 100% match). In
            exact-hour mode, top-of-hour periods match and :30 half-hours reflect native cadence differences.
          </div>
        </section>
      </div>

      <section className="section-card table-card">
        <div className="card-head">
          <div>
            <h2>Recent delivery periods</h2>
            <p>Selected forecast vintages aligned with matched actual output</p>
          </div>
          <button className="outline-btn" onClick={downloadCsv} disabled={!data} type="button">
            <Download size={14} />
            Export CSV
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>DELIVERY TIME (UTC)</th>
                <th>PERIOD</th>
                <th>FORECAST (MW)</th>
                <th>ACTUAL (MW)</th>
                <th>ERROR (MW)</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="table-empty">
                    Loading verified Elexon BMRS records…
                  </td>
                </tr>
              ) : !data?.series.length ? (
                <tr>
                  <td colSpan={6} className="table-empty">
                    No records found for the selected evaluation period.
                  </td>
                </tr>
              ) : (
                data?.series
                  .slice(-12)
                  .reverse()
                  .map((r, i) => (
                    <tr key={i}>
                      <td>{time(r.timestamp)}</td>
                      <td>SP {r.settlement_period ?? '—'}</td>
                      <td className="forecast-text">{fmt(r.forecast)}</td>
                      <td className="actual-text">{fmt(r.actual)}</td>
                      <td className={(r.error ?? 0) >= 0 ? 'positive' : 'negative'}>
                        {r.error == null ? '—' : `${(r.error ?? 0) >= 0 ? '+' : ''}${fmt(r.error)}`}
                      </td>
                      <td>
                        <span className="badge green">Matched</span>
                      </td>
                    </tr>
                  ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
