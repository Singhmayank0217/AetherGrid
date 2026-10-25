import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Calendar,
  Clock,
  ExternalLink,
  History,
  Info,
  RefreshCw,
  Wind
} from 'lucide-react';
import { ForecastExplorerData, getForecasts, PeriodDetail } from '../services/api';

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

export default function ForecastExplorerPage() {
  const [date, setDate] = useState('2026-01-15');
  const [data, setData] = useState<ForecastExplorerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPeriodIdx, setSelectedPeriodIdx] = useState(0);
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError('');
    getForecasts(date, 23, refreshIndex > 0)
      .then((res) => {
        setData(res);
        if (res.periods && res.periods.length > 0) {
          setSelectedPeriodIdx(0);
        }
      })
      .catch((e) => setError(e.message || 'Failed to fetch forecast explorer records'))
      .finally(() => setLoading(false));
  }, [date, refreshIndex]);

  const currentPeriod: PeriodDetail | undefined = data?.periods?.[selectedPeriodIdx];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="pulse" /> VINTAGE EXPLORATION / TEMPORAL ANALYSIS
          </div>
          <h1>Forecast Explorer</h1>
          <p>
            Audit individual delivery periods, observe forecast vintage evolution, and inspect day-ahead cutoff compliance.
          </p>
        </div>
        <div className="data-status">
          <span className={data ? 'status-live' : 'status-muted'} />
          {data ? 'DATA READY' : 'FETCHING'}
        </div>
      </div>

      <div className="control-bar">
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
            Settlement Period:
          </span>
          <select
            className="select-input"
            value={selectedPeriodIdx}
            onChange={(e) => setSelectedPeriodIdx(Number(e.target.value))}
            disabled={loading || !data?.periods?.length}
          >
            {data?.periods?.map((p, idx) => (
              <option key={p.timestamp} value={idx}>
                SP {p.settlement_period} ({formatUtcTime(p.timestamp)})
              </option>
            ))}
          </select>
        </div>

        <button
          className="refresh-btn"
          onClick={() => setRefreshIndex((i) => i + 1)}
          disabled={loading}
          type="button"
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          {loading ? 'Refreshing…' : 'Refresh'}
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

      {loading ? (
        <div className="chart-skeleton" style={{ height: 350 }} />
      ) : !currentPeriod ? (
        <div className="section-card placeholder-page">
          <Wind size={28} />
          <h2>No Delivery Period Data</h2>
          <p>Please select a valid date in January 2026.</p>
        </div>
      ) : (
        <>
          <section className="metrics-grid">
            <article className="metric-card">
              <div className="metric-top">
                <span>Selected Eligible Forecast</span>
                <span className="metric-dot cyan" />
              </div>
              <div className="metric-value">
                {fmt(currentPeriod.forecast)}
                <small>MW</small>
              </div>
              <div className="metric-detail">Published by D-1 23:00 UTC cutoff</div>
            </article>

            <article className="metric-card">
              <div className="metric-top">
                <span>Actual Generation</span>
                <span className="metric-dot green" />
              </div>
              <div className="metric-value">
                {fmt(currentPeriod.actual)}
                <small>MW</small>
              </div>
              <div className="metric-detail">Elexon FUELHH · WIND</div>
            </article>

            <article className="metric-card">
              <div className="metric-top">
                <span>Forecast Error</span>
                <span className={`metric-dot ${(currentPeriod.error ?? 0) >= 0 ? 'amber' : 'red'}`} />
              </div>
              <div className="metric-value">
                {currentPeriod.error == null
                  ? '—'
                  : `${(currentPeriod.error ?? 0) >= 0 ? '+' : ''}${fmt(currentPeriod.error)}`}
                <small>MW</small>
              </div>
              <div className="metric-detail">
                {(currentPeriod.error ?? 0) >= 0 ? 'Overforecast (Surplus)' : 'Underforecast (Deficit)'}
              </div>
            </article>

            <article className="metric-card">
              <div className="metric-top">
                <span>Absolute Error</span>
                <span className="metric-dot amber" />
              </div>
              <div className="metric-value">
                {fmt(currentPeriod.abs_error)}
                <small>MW</small>
              </div>
              <div className="metric-detail">Magnitude of procurement miss</div>
            </article>

            <article className="metric-card">
              <div className="metric-top">
                <span>Historical Vintages</span>
                <span className="metric-dot cyan" />
              </div>
              <div className="metric-value">
                {currentPeriod.historical_versions?.length ?? 0}
                <small>vintages</small>
              </div>
              <div className="metric-detail">Published across time horizon</div>
            </article>
          </section>

          <div className="two-col">
            <section className="section-card">
              <div className="card-head">
                <div>
                  <h2>Cutoff &amp; Eligibility Audit</h2>
                  <p>Distinguishing publication time from delivery time</p>
                </div>
                <Clock size={16} className="muted-icon" />
              </div>

              <div className="quality-list">
                <div>
                  <span>Delivery Period</span>
                  <b>
                    SP {currentPeriod.settlement_period} ({formatUtcTime(currentPeriod.timestamp)})
                  </b>
                </div>
                <div>
                  <span>Forecast Publication Time</span>
                  <b className="forecast-text">{formatUtcTime(currentPeriod.publish_time)}</b>
                </div>
                <div>
                  <span>Decision Cutoff Policy</span>
                  <b>{formatUtcTime(currentPeriod.cutoff_time)} (D-1 23:00 UTC)</b>
                </div>
                <div>
                  <span>Lead Time Before Delivery</span>
                  <b>
                    {currentPeriod.publish_time
                      ? `${Math.round(
                          ((new Date(currentPeriod.timestamp).getTime() -
                            new Date(currentPeriod.publish_time).getTime()) /
                            3600000) *
                            10
                        ) / 10} hours`
                      : '—'}
                  </b>
                </div>
                <div>
                  <span>Why This Forecast Was Chosen</span>
                  <b style={{ color: 'var(--green)' }}>Latest vintage published prior to decision cutoff</b>
                </div>
              </div>

              <div className="quality-note" style={{ marginTop: 16 }}>
                <strong>Trading Policy Note:</strong> In power trading, procurement decisions cannot rely on post-cutoff
                forecast updates. This vintage reflects the exact intelligence available to the procurement desk at the
                day-ahead decision gate.
              </div>
            </section>

            <section className="section-card">
              <div className="card-head">
                <div>
                  <h2>Historical Forecast Evolution</h2>
                  <p>All forecast publications covering this settlement period</p>
                </div>
                <History size={16} className="muted-icon" />
              </div>

              {!currentPeriod.historical_versions?.length ? (
                <div className="table-empty">No historical publication versions found for this period.</div>
              ) : (
                <div className="timeline-list">
                  {currentPeriod.historical_versions.map((v, i) => {
                    const isSelected = v.publish_time === currentPeriod.publish_time;
                    return (
                      <div
                        key={i}
                        className={`timeline-item ${isSelected ? 'selected' : ''} ${
                          !v.is_eligible ? 'ineligible' : ''
                        }`}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <strong className="forecast-text">{fmt(v.generation)} MW</strong>
                            {isSelected && <span className="badge green">Selected (Decision Vintage)</span>}
                            {!v.is_eligible && <span className="badge red">Post-Cutoff</span>}
                            {v.is_eligible && !isSelected && <span className="badge gray">Eligible Earlier</span>}
                          </div>
                          <small style={{ color: 'var(--muted)', fontSize: 10 }}>
                            Published: {formatUtcTime(v.publish_time)} ({v.hours_before_delivery}h before delivery)
                          </small>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}
