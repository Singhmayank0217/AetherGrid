import { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckCircle2,
  Download,
  Filter,
  RefreshCw,
  SlidersHorizontal
} from 'lucide-react';
import { getAccuracy, Overview, Point } from '../services/api';

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


function ErrorDistributionView({
  bins
}: {
  bins?: { range: string; count: number; percentage: number }[];
}) {
  if (!bins || !bins.length) return null;
  return (
    <div className="dist-list">
      {bins.map((b, i) => {
        const isNeg = b.range.includes('-');
        return (
          <div key={i} className="dist-row">
            <span style={{ color: 'var(--text)' }}>{b.range}</span>
            <div className="dist-bar-track">
              <div
                className={`dist-bar-fill ${isNeg ? 'neg' : 'pos'}`}
                style={{ width: `${Math.max(b.percentage, 1)}%` }}
              />
            </div>
            <span style={{ textAlign: 'right', color: 'var(--muted)' }}>{b.count} obs</span>
            <b style={{ textAlign: 'right', color: isNeg ? 'var(--amber)' : 'var(--cyan)' }}>
              {b.percentage}%
            </b>
          </div>
        );
      })}
    </div>
  );
}

function AccuracyChart({ data }: { data: Point[] }) {
  const rows = data.filter((p) => p.actual != null && p.forecast != null).slice(-120);
  if (!rows.length) {
    return (
      <div className="empty-chart">
        <Activity size={18} />
        <span>No matched evaluation pairs</span>
      </div>
    );
  }

  const maxVal = Math.max(...rows.flatMap((p) => [p.actual || 0, p.forecast || 0]), 1);
  const w = 900;
  const h = 260;

  const x = (i: number) => 12 + (i / Math.max(rows.length - 1, 1)) * (w - 24);
  const y = (v: number) => h - 20 - (v / maxVal) * (h - 40);

  const actualPath = rows
    .map((p, i) => (p.actual == null ? null : `${i ? 'L' : 'M'} ${x(i)} ${y(p.actual)}`))
    .filter(Boolean)
    .join(' ');

  const forecastPath = rows
    .map((p, i) => (p.forecast == null ? null : `${i ? 'L' : 'M'} ${x(i)} ${y(p.forecast)}`))
    .filter(Boolean)
    .join(' ');

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" preserveAspectRatio="none">
        {[0.25, 0.5, 0.75].map((t) => (
          <line
            key={t}
            x1="12"
            x2={w - 12}
            y1={y(maxVal * t)}
            y2={y(maxVal * t)}
            className="grid-line"
          />
        ))}
        <path d={actualPath} className="line-actual" />
        <path d={forecastPath} className="line-forecast" />
      </svg>
      <div className="chart-axis">
        <span>{formatUtcTime(rows[0].timestamp)}</span>
        <span>{formatUtcTime(rows[Math.floor(rows.length / 2)].timestamp)}</span>
        <span>{formatUtcTime(rows[rows.length - 1].timestamp)}</span>
      </div>
    </div>
  );
}

function SignedErrorChart({ data }: { data: Point[] }) {
  const rows = data.filter((p) => p.error != null).slice(-120);
  if (!rows.length) {
    return (
      <div className="empty-chart">
        <Activity size={18} />
        <span>No error records</span>
      </div>
    );
  }

  const maxErr = Math.max(...rows.map((p) => Math.abs(p.error || 0)), 1);
  const w = 900;
  const h = 240;

  const x = (i: number) => 12 + (i / Math.max(rows.length - 1, 1)) * (w - 24);
  const y = (v: number) => h / 2 - (v / maxErr) * (h / 2 - 20);

  const errorPath = rows
    .map((p, i) => (p.error == null ? null : `${i ? 'L' : 'M'} ${x(i)} ${y(p.error)}`))
    .filter(Boolean)
    .join(' ');

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" preserveAspectRatio="none">
        <line x1="12" x2={w - 12} y1={h / 2} y2={h / 2} className="zero-line" />
        {[0.5].map((t) => (
          <g key={t}>
            <line x1="12" x2={w - 12} y1={h / 2 - t * (h / 2 - 20)} y2={h / 2 - t * (h / 2 - 20)} className="grid-line" />
            <line x1="12" x2={w - 12} y1={h / 2 + t * (h / 2 - 20)} y2={h / 2 + t * (h / 2 - 20)} className="grid-line" />
          </g>
        ))}
        <path d={errorPath} className="line-error" />
      </svg>
      <div className="chart-axis">
        <span>{formatUtcTime(rows[0].timestamp)}</span>
        <span>Zero Error Baseline</span>
        <span>{formatUtcTime(rows[rows.length - 1].timestamp)}</span>
      </div>
    </div>
  );
}

export default function AccuracyPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-01-31');
  const [resolution, setResolution] = useState<'half_hourly' | 'hourly'>('half_hourly');
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError('');
    getAccuracy(startDate, endDate, 23, resolution, refreshIndex > 0)
      .then(setData)
      .catch((e) => setError(e.message || 'Failed to fetch accuracy evaluation'))
      .finally(() => setLoading(false));
  }, [startDate, endDate, resolution, refreshIndex]);

  const m = data?.metrics;

  const downloadCsv = () => {
    if (!data) return;
    const header = 'delivery_time,settlement_period,forecast_mw,actual_mw,error_mw,abs_error_mw,publish_time';
    const rows = data.series.map(
      (r) =>
        `${r.timestamp},${r.settlement_period ?? ''},${r.forecast ?? ''},${r.actual ?? ''},${r.error ?? ''},${r.abs_error ?? ''},${r.publish_time ?? ''}`
    );
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aethergrid-accuracy-${startDate}-to-${endDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const paginatedRows = data?.series
    ? data.series.slice((page - 1) * pageSize, page * pageSize)
    : [];

  const totalPages = data?.series ? Math.ceil(data.series.length / pageSize) : 1;

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="pulse" /> STATISTICAL EVALUATION / MODEL ACCURACY
          </div>
          <h1>Accuracy Analysis</h1>
          <p>
            Rigorous evaluation of day-ahead wind generation forecasts against Elexon BMRS actual settlement output.
          </p>
        </div>
        <div className="data-status">
          <span className={data ? 'status-live' : 'status-muted'} />
          {data ? 'DATA READY' : 'AWAITING'}
        </div>
      </div>

      <div className="control-bar">
        <div className="control-group">
          <span className="control-label">Range:</span>
          <input
            type="date"
            className="date-input"
            value={startDate}
            min="2026-01-01"
            max="2026-01-31"
            onChange={(e) => setStartDate(e.target.value)}
          />
          <span style={{ color: 'var(--muted)' }}>to</span>
          <input
            type="date"
            className="date-input"
            value={endDate}
            min="2026-01-01"
            max="2026-01-31"
            onChange={(e) => setEndDate(e.target.value)}
          />

          <span className="control-label" style={{ marginLeft: 14 }}>
            Resolution:
          </span>
          <div className="segmented">
            <button
              className={resolution === 'half_hourly' ? 'selected' : ''}
              onClick={() => setResolution('half_hourly')}
              type="button"
            >
              30-Min SP
            </button>
            <button
              className={resolution === 'hourly' ? 'selected' : ''}
              onClick={() => setResolution('hourly')}
              type="button"
            >
              Hourly (:00)
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
          {loading ? 'Evaluating…' : 'Re-Evaluate'}
        </button>
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

      <section className="metrics-grid">
        <article className="metric-card">
          <div className="metric-top">
            <span>Mean Absolute Error (MAE)</span>
            <span className="metric-dot amber" />
          </div>
          <div className="metric-value">
            {loading ? '—' : fmt(m?.mae)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Average magnitude of misses</div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Root Mean Squared Error (RMSE)</span>
            <span className="metric-dot amber" />
          </div>
          <div className="metric-value">
            {loading ? '—' : fmt(m?.rmse)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Quadratic penalty on large errors</div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Forecast Bias</span>
            <span className={`metric-dot ${(m?.bias ?? 0) >= 0 ? 'amber' : 'red'}`} />
          </div>
          <div className="metric-value">
            {loading ? '—' : `${(m?.bias ?? 0) >= 0 ? '+' : ''}${fmt(m?.bias, 1)}`}
            <small>MW</small>
          </div>
          <div className="metric-detail">
            {(m?.bias ?? 0) >= 0 ? 'Overforecasting (+ MW)' : 'Underforecasting (- MW)'}
          </div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Median Absolute Error</span>
            <span className="metric-dot cyan" />
          </div>
          <div className="metric-value">
            {loading ? '—' : fmt(m?.median_abs_error)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Robust typical error (50th percentile)</div>
        </article>

        <article className="metric-card">
          <div className="metric-top">
            <span>Maximum Absolute Error</span>
            <span className="metric-dot red" />
          </div>
          <div className="metric-value">
            {loading ? '—' : fmt(m?.max_abs_error)}
            <small>MW</small>
          </div>
          <div className="metric-detail">Worst-case tail miss in sample</div>
        </article>
      </section>

      <section className="section-card chart-card">
        <div className="card-head">
          <div>
            <h2>Actual generation vs day-ahead forecast</h2>
            <p>Aligned by delivery period across selected evaluation horizon</p>
          </div>
          <div className="legend">
            <span>
              <i className="legend-line actual" /> Actual (FUELHH)
            </span>
            <span>
              <i className="legend-line forecast" /> Forecast (WINDFOR)
            </span>
          </div>
        </div>
        {loading ? <div className="chart-skeleton" /> : <AccuracyChart data={data?.series || []} />}
      </section>

      <div className="two-col">
        <section className="section-card">
          <div className="card-head">
            <div>
              <h2>Signed forecast error (MW)</h2>
              <p>Forecast minus actual with zero baseline (amber = overforecast, deficit risk)</p>
            </div>
          </div>
          {loading ? <div className="chart-skeleton small" /> : <SignedErrorChart data={data?.series || []} />}
        </section>

        <section className="section-card">
          <div className="card-head">
            <div>
              <h2>Error distribution breakdown</h2>
              <p>Histogram of forecast misses (MW bands)</p>
            </div>
            <BarChart3 size={17} className="muted-icon" />
          </div>
          {loading ? (
            <div className="chart-skeleton small" />
          ) : (
            <ErrorDistributionView bins={data?.distribution} />
          )}
        </section>
      </div>

      {data?.daily_summary && data.daily_summary.length > 0 && (
        <section className="section-card table-card" style={{ marginBottom: 18 }}>
          <div className="card-head">
            <div>
              <h2>Daily accuracy summary</h2>
              <p>Aggregated daily procurement performance across January 2026</p>
            </div>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>DATE</th>
                  <th>SAMPLE (PERIODS)</th>
                  <th>ACTUAL MEAN (MW)</th>
                  <th>FORECAST MEAN (MW)</th>
                  <th>MAE (MW)</th>
                  <th>RMSE (MW)</th>
                  <th>BIAS (MW)</th>
                  <th>MAX MISS (MW)</th>
                </tr>
              </thead>
              <tbody>
                {data.daily_summary.map((d, i) => (
                  <tr key={i}>
                    <td>
                      <strong>{d.date}</strong>
                    </td>
                    <td>{d.sample_count}</td>
                    <td className="actual-text">{fmt(d.actual_mean)}</td>
                    <td className="forecast-text">{fmt(d.forecast_mean)}</td>
                    <td>{fmt(d.mae)}</td>
                    <td>{fmt(d.rmse)}</td>
                    <td className={d.bias >= 0 ? 'positive' : 'negative'}>
                      {d.bias >= 0 ? `+${fmt(d.bias, 1)}` : fmt(d.bias, 1)}
                    </td>
                    <td style={{ color: 'var(--amber)' }}>{fmt(d.max_error)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="section-card table-card">
        <div className="card-head">
          <div>
            <h2>Delivery period inspection table</h2>
            <p>
              Showing {data?.series.length ? (page - 1) * pageSize + 1 : 0} to{' '}
              {Math.min(page * pageSize, data?.series.length ?? 0)} of {data?.series.length ?? 0} periods
            </p>
          </div>
          <button className="outline-btn" onClick={downloadCsv} disabled={!data} type="button">
            <Download size={14} />
            Export Complete Dataset (CSV)
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
                <th>ABS ERROR (MW)</th>
                <th>PUBLISHED (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="table-empty">
                    Loading evaluation pairs…
                  </td>
                </tr>
              ) : !paginatedRows.length ? (
                <tr>
                  <td colSpan={7} className="table-empty">
                    No records found for current filters.
                  </td>
                </tr>
              ) : (
                paginatedRows.map((r, i) => (
                  <tr key={i}>
                    <td>{formatUtcTime(r.timestamp)}</td>
                    <td>SP {r.settlement_period ?? '—'}</td>
                    <td className="forecast-text">{fmt(r.forecast)}</td>
                    <td className="actual-text">{fmt(r.actual)}</td>
                    <td className={(r.error ?? 0) >= 0 ? 'positive' : 'negative'}>
                      {r.error == null ? '—' : `${(r.error ?? 0) >= 0 ? '+' : ''}${fmt(r.error)}`}
                    </td>
                    <td>{fmt(r.abs_error)}</td>
                    <td style={{ color: 'var(--muted)', fontSize: 10 }}>
                      {formatUtcTime(r.publish_time)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="pagination">
            <span>
              Page {page} of {totalPages}
            </span>
            <div className="pagination-controls">
              <button
                className="page-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                type="button"
              >
                Previous
              </button>
              <button
                className="page-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
