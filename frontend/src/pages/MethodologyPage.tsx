import {
  AlertTriangle,
  BookOpen,
  CheckCircle,
  ExternalLink,
  FileText,
  Info,
  Scale,
  ShieldAlert
} from 'lucide-react';

export default function MethodologyPage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="pulse" /> GOVERNANCE / DATA SPECIFICATION
          </div>
          <h1>Methodology &amp; Data Documentation</h1>
          <p>
            Official dataset contracts, alignment conventions, forecast vintage selection rules, and mathematical formulas.
          </p>
        </div>
      </div>

      <div className="methodology-grid">
        <section className="methodology-section">
          <h2>
            <BookOpen size={18} style={{ color: 'var(--cyan)' }} />
            1. Official Upstream Data Sources
          </h2>
          <p>
            All data utilized by AetherGrid is sourced exclusively from the official Elexon BMRS (Balancing Mechanism
            Reporting Service) API v1 stream endpoints:
          </p>
          <ul>
            <li>
              <strong>Actual Generation (FUELHH):</strong> Half-hourly generation outturn by fuel type across Great Britain.
              Filtered strictly to <code>fuelType = 'WIND'</code>. Records reflect actual settlement period generation
              delivered to the transmission system.
            </li>
            <li>
              <strong>Forecast Generation (WINDFOR):</strong> National wind generation forecasts produced by the Electricity
              System Operator (NESO). Each record provides expected generation for a specific target start time across
              multiple published vintages.
            </li>
          </ul>

          <div className="source-link-box">
            <div>
              <strong>Elexon BMRS FUELHH Stream Documentation</strong>
              <div style={{ color: 'var(--muted)', fontSize: 10 }}>Dataset: Half-hourly fuel breakdown (MW)</div>
            </div>
            <a
              href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream"
              target="_blank"
              rel="noopener noreferrer"
            >
              API Docs <ExternalLink size={13} />
            </a>
          </div>

          <div className="source-link-box">
            <div>
              <strong>Elexon BMRS WINDFOR Stream Documentation</strong>
              <div style={{ color: 'var(--muted)', fontSize: 10 }}>Dataset: Wind forecast stream (MW)</div>
            </div>
            <a
              href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream"
              target="_blank"
              rel="noopener noreferrer"
            >
              API Docs <ExternalLink size={13} />
            </a>
          </div>
        </section>

        <section className="methodology-section">
          <h2>
            <Scale size={18} style={{ color: 'var(--amber)' }} />
            2. Day-Ahead Decision Cutoff &amp; Vintage Selection
          </h2>
          <p>
            The fundamental business problem in electricity procurement is that procurement commitments must be made
            before the delivery period begins. Evaluating forecasts using the latest forecast available today creates
            severe look-ahead bias and invalidates procurement models.
          </p>
          <ul>
            <li>
              <strong>Cutoff Policy:</strong> For any delivery period beginning on date <em>D</em>, the procurement
              decision cutoff is set to <strong>previous day (D-1) at 23:00 UTC</strong>.
            </li>
            <li>
              <strong>Assumption Disclosure:</strong> 23:00 UTC on D-1 represents an operational day-ahead procurement
              benchmark (coinciding with the close of day-ahead schedule nominations under the Balancing and Settlement
              Code). It is an analytical assumption and does not represent an official exchange auction gate closure
              (such as EPEX SPOT day-ahead auction at 11:00 GMT / 12:00 CET).
            </li>
            <li>
              <strong>Selection Algorithm:</strong> For each delivery period <em>T</em>, all available WINDFOR records with{' '}
              <code>publishTime &le; Cutoff(T)</code> are considered. The forecast with the latest publication timestamp
              prior to cutoff is selected as the decision vintage.
            </li>
            <li>
              <strong>Extended Query Horizon:</strong> To avoid silently omitting eligible forecasts for January 1st
              (which are published on December 30–31, 2025), the upstream retrieval query window extends back 3 days prior
              to the evaluation month.
            </li>
          </ul>
        </section>

        <section className="methodology-section">
          <h2>
            <FileText size={18} style={{ color: 'var(--green)' }} />
            3. Alignment Resolution &amp; Settlement Period Cadence
          </h2>
          <p>
            In Great Britain, wholesale power trading and settlement run on 30-minute settlement periods (48 periods per
            day). However, the upstream System Operator publishes WINDFOR forecasts on an hourly cadence (start times at{' '}
            <code>:00</code> minutes).
          </p>
          <ul>
            <li>
              <strong>30-Minute Settlement Alignment (Default):</strong> Preserves all 1,488 actual settlement periods.
              Power is measured in average rate of energy delivery (MW). Under standard power trading convention, an hourly
              block forecast of <em>M</em> MW covers the two 30-minute settlement periods in that hour (e.g. 10:00–10:30 and
              10:30–11:00). Half-hour (:30) forecasts are explicitly tagged as <code>step_extended_hourly</code> so they
              are never implied to be separate forecast observations.
            </li>
            <li>
              <strong>Exact Hourly Alignment (Aggregated Mean):</strong> Evaluates strictly on a 60-minute delivery basis.
              The two corresponding 30-minute FUELHH actual values (:00 and :30) are aggregated into one hourly actual
              using their arithmetic mean: <code>(SP_odd + SP_even) / 2</code>. This matches the native hourly WINDFOR
              forecast and achieves 100% coverage across all 744 expected hourly delivery periods in January 2026.
            </li>
          </ul>
        </section>

        <section className="methodology-section">
          <h2>
            <Info size={18} style={{ color: 'var(--cyan)' }} />
            4. Metric Definitions &amp; Formulas
          </h2>
          <p>
            All metrics are calculated strictly on matched pairs where both actual generation and forecast generation are
            valid non-null values:
          </p>

          <div className="formula-card">
            <div>Forecast Error: Error_t = Forecast_t - Actual_t (MW)</div>
            <div style={{ marginTop: 8 }}>Mean Absolute Error: MAE = (1 / N) * Σ |Forecast_t - Actual_t|</div>
            <div style={{ marginTop: 8 }}>Root Mean Squared Error: RMSE = sqrt( (1 / N) * Σ (Forecast_t - Actual_t)^2 )</div>
            <div style={{ marginTop: 8 }}>Forecast Bias: Bias = (1 / N) * Σ (Forecast_t - Actual_t)</div>
            <div style={{ marginTop: 8 }}>Median Absolute Error: MedAE = median( |Forecast_t - Actual_t| )</div>
            <div style={{ marginTop: 8 }}>Maximum Absolute Error: MaxAE = max( |Forecast_t - Actual_t| )</div>
          </div>

          <ul>
            <li>
              <strong>Bias Sign Convention:</strong> <code>Forecast - Actual</code>. A positive bias (+ MW) indicates
              systematic overforecasting (the model expected more wind than materialized, leading to short positions or
              deficit risk). A negative bias (- MW) indicates underforecasting (long positions or surplus wind).
            </li>
            <li>
              <strong>Zero Actuals Treatment:</strong> Periods with 0 MW actual generation are valid physical occurrences
              and are retained in all absolute metric calculations (MAE, RMSE, Bias). They are excluded from percentage-based
              ratios (such as MAPE) to prevent division-by-zero singularities.
            </li>
          </ul>
        </section>

        <section className="methodology-section">
          <h2>
            <ShieldAlert size={18} style={{ color: 'var(--amber)' }} />
            5. Decision Support vs. Procurement Optimization Limitations
          </h2>
          <p>
            AetherGrid is an analytics and decision support platform, not an automated procurement trading robot or
            hedging engine:
          </p>
          <ul>
            <li>
              <strong>Imbalance Price Dynamics:</strong> True procurement optimization requires factoring in dual cashout
              prices (System Sell Price / System Buy Price), which are asymmetric and volatile. AetherGrid evaluates physical
              forecast error, which is the primary driver of imbalance exposure.
            </li>
            <li>
              <strong>Transmission &amp; Physical Constraints:</strong> National forecasts represent total GB generation and
              do not incorporate locational transmission boundaries (such as B6 Scottish boundary export limits) or
              curtailment actions taken by the System Operator via the Balancing Mechanism.
            </li>
            <li>
              <strong>No Fabricated Data Fallbacks:</strong> The application operates strictly on verifiable Elexon records.
              In the event of upstream outages, error states and warnings are surfaced rather than synthetic interpolations.
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
