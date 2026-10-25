# AetherGrid — UK Wind Generation Forecast Analytics

AetherGrid is an analytical web application engineered for UK electricity utilities and trading desks to evaluate national wind generation forecasts for **January 2026** day-ahead electricity procurement decisions.

The application ingests official live stream data from **Elexon BMRS**, reconstructs historical forecast vintages available at the day-ahead procurement decision gate, aligns them against half-hourly settlement outturn, and computes rigorous accuracy and data-quality metrics.

---

## 1. Architecture

```mermaid
flowchart TD
    subgraph Upstream [Official Elexon BMRS Data Streams]
        FUELHH[FUELHH Stream\nActual Fuel Outturn\nfuelType=WIND\n30-min Settlement Cadence]
        WINDFOR[WINDFOR Stream\nNational Wind Forecast\nMulti-Vintage Publications\n60-min Target Cadence]
    end

    subgraph Backend [FastAPI Analytics Service :8000]
        ElexonService[Elexon Ingestion Service\nExtended Query Horizon\nIn-Memory TTL Cache]
        Processor[WindDataProcessor Engine\nTimestamp Normalization (UTC)\nVintage Cutoff Filter (D-1 23:00 UTC)\n30-min Settlement Block Alignment\nPandas Analytics & Pure Python Fallback]
        API[FastAPI Endpoints\n/health\n/api/overview\n/api/forecasts\n/api/accuracy\n/api/data-quality\n/api/simulator]
    end

    subgraph Frontend [React + TypeScript + Vite :3000 / :5173]
        OverviewPage[1. Executive Overview\nKPIs, Dual SVG Charts, Recent Table, CSV Export]
        SimulatorPage[2. Decision Simulator\nStress Slider, Cutoff Replay, Heatmap, Quantiles]
        ForecastPage[3. Forecast Explorer\nSP 1-48 Inspector, Vintage Evolution Timeline]
        AccuracyPage[4. Accuracy Analysis\nMAE, RMSE, Bias, MedAE, MaxAE, Daily Summaries]
        DataPage[5. Data Explorer\nConnectivity vs Freshness, Duplicates, Bounds Audit]
        MethodologyPage[6. Methodology & Data\nOfficial Documentation, LaTeX Formulas, Governance]
    end

    FUELHH --> ElexonService
    WINDFOR --> ElexonService
    ElexonService --> Processor
    Processor --> API
    API --> Frontend
```

---

## 2. Directory Structure

```text
aether-grid/
├── .dockerignore                 # Root container build context exclusions
├── .env.example                  # Documented environment variables (placeholders only)
├── .gitignore                    # Monorepo git exclusion rules
├── docker-compose.yml            # Multi-service container orchestration
├── package.json                  # Root monorepo scripts
├── pytest.ini                    # Root pytest configuration
├── vercel.json                   # Vercel deployment & SPA rewrites configuration
├── README.md                     # Comprehensive documentation & disclosure
│
├── backend/                      # Python FastAPI Backend
│   ├── .dockerignore             # Backend container context exclusions
│   ├── Dockerfile                # Production Python 3.12 container with healthcheck
│   ├── pytest.ini                # Backend pytest configuration
│   ├── requirements.txt          # Python dependencies (FastAPI, Pandas, HTTPX, Pytest)
│   ├── app/
│   │   ├── main.py               # FastAPI application & router with dynamic CORS
│   │   └── services/
│   │       ├── accuracy.py       # Orchestration layer for evaluation endpoints
│   │       ├── elexon.py         # Elexon BMRS client with extended window & caching
│   │       └── processor.py      # Normalization, cutoff logic, alignment & KPIs
│   └── tests/                    # Comprehensive Backend Test Suite (37 tests)
│       ├── test_accuracy.py          # Legacy vintage selection tests
│       ├── test_api_endpoints.py     # FastAPI TestClient endpoint tests with mocks
│       ├── test_cutoff_boundary.py   # D-1 23:00 UTC boundary & cutoff tests
│       ├── test_data_processing.py   # Normalization, duplicates, missing values
│       ├── test_date_boundaries.py   # Jan 1 & Jan 31 boundary vintage tests
│       ├── test_metrics.py           # Mathematical verification of MAE, RMSE, Bias
│       └── test_simulator.py         # Procurement simulator, cutoffs & scenario tests
│
└── frontend/                     # React + TypeScript + Vite Frontend
    ├── .dockerignore             # Frontend container context exclusions
    ├── Dockerfile                # Multi-stage build to Nginx Alpine container
    ├── nginx.conf                # Nginx SPA client-side routing configuration
    ├── package.json              # Frontend dependencies (React 19, Recharts, Lucide)
    ├── vite.config.ts            # Vite & Vitest configuration
    ├── eslint.config.js          # ESLint flat configuration
    ├── index.html                # Semantic HTML5 entrypoint with SEO metadata
    └── src/
        ├── App.tsx               # Main application shell, sidebar & routing
        ├── main.tsx              # React DOM mounting
        ├── styles.css            # Custom dark navy & emerald design system
        ├── pages/
        │   ├── OverviewPage.tsx          # Page 1: Executive KPI & Chart Dashboard
        │   ├── ForecastExplorerPage.tsx  # Page 2: SP 1-48 Vintage Evolution Inspector
        │   ├── AccuracyPage.tsx          # Page 3: Full Statistical Accuracy Analytics
        │   ├── SimulatorPage.tsx         # Page 4: Procurement Decision Simulator & Replay
        │   ├── DataExplorerPage.tsx      # Page 5: Data Quality & System Health Audit
        │   └── MethodologyPage.tsx       # Page 6: Methodology, Sources & Governance
        ├── services/
        │   └── api.ts                    # Strongly typed API client methods & interfaces
        └── __tests__/                    # Frontend Test Suite (7 tests)
            ├── api.test.ts               # API client unit tests
            └── navigation.test.tsx       # Component & route navigation tests
```

---

## 3. Official Upstream Data Sources

All calculations rely solely on the official Elexon BMRS API v1 stream endpoints:

- **Actual Wind Generation (FUELHH Stream):**  
  Endpoint: `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`  
  Filtered to: `fuelType=WIND`. Measures actual half-hourly wind generation in Megawatts (MW) delivered to the GB transmission grid.
- **Forecast Wind Generation (WINDFOR Stream):**  
  Endpoint: `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`  
  Published by the Electricity System Operator (NESO). Provides national wind generation forecasts in Megawatts (MW) published at multiple intervals ahead of real time.

---

## 4. Key Methodology & Business Logic

### Day-Ahead Procurement Decision Cutoff
In day-ahead electricity procurement, utilities commit capital and submit physical schedules before the delivery day begins. A valid evaluation must reflect the forecast **actually available at the procurement decision cutoff**, avoiding look-ahead bias from intraday updates.

- **Baseline Policy:** Previous day (D-1) at **23:00 UTC**.
- **Cutoff Semantics:** For a delivery settlement period on date $D$, any forecast version published on or before $(D-1)\text{ 23:00:00 UTC}$ is eligible ($T_{\text{publish}} \le \text{Cutoff}(T)$). The latest published forecast among all eligible vintages is selected.
- **Regulatory Disclosure:** 23:00 UTC on D-1 corresponds to the standard operational scheduling deadline under the Balancing and Settlement Code (BSC). It is an analytical assumption and does not represent an exchange auction gate closure (e.g. EPEX SPOT at 11:00 GMT / Nord Pool at 12:00 CET).
- **Date Boundary Handling:** Forecasts for delivery on January 1, 2026 are published on December 30–31, 2025. The backend query window explicitly queries from $D-3$ to capture all eligible day-ahead publications.

### Delivery Period Alignment
- **Cadence Difference:** Actual wind generation (`FUELHH`) is recorded at **30-minute settlement period resolution** (1,488 periods in Jan 2026). Forecast wind generation (`WINDFOR`) is published by the System Operator at **60-minute resolution** (744 hours in Jan 2026).
- **30-Minute Settlement Alignment (Default):** Generation is an average rate of delivery (MW). Under standard power market conventions, an hourly forecast of $M$ MW covers both 30-minute settlement periods within that hour (e.g. SP 1 00:00–00:30 and SP 2 00:30–01:00). This provides **100% matched coverage (1,488 / 1,488 periods)**.
- **Exact Hourly Alignment (Optional):** Only top-of-hour settlement periods (:00) are joined, yielding 744 matched periods. The remaining 744 half-hours (:30) are transparently categorized as cadence-unmatched in the Data Explorer.

### Metric Formulas
All accuracy metrics are evaluated on matched non-null observation pairs:

$$\text{Error}_t = \text{Forecast}_t - \text{Actual}_t \quad (\text{MW})$$

$$\text{MAE} = \frac{1}{N} \sum_{t=1}^{N} |\text{Forecast}_t - \text{Actual}_t| \quad (\text{MW})$$

$$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^{N} (\text{Forecast}_t - \text{Actual}_t)^2} \quad (\text{MW})$$

$$\text{Bias} = \frac{1}{N} \sum_{t=1}^{N} (\text{Forecast}_t - \text{Actual}_t) \quad (\text{MW})$$

- **Sign Convention:** Positive bias indicates systematic **overforecasting** (forecast &gt; actual, leading to short imbalance risk). Negative bias indicates **underforecasting** (forecast &lt; actual, leading to long position risk).
- **Zero Actuals Treatment:** Periods with 0 MW actual generation are valid physical states and are retained in absolute metrics (MAE, RMSE, Bias).

---

## 5. Local Setup & Execution

### Prerequisites
- Node.js &ge; 20 (Node v24 recommended)
- Python &ge; 3.12 (Python 3.13 supported)
- Docker & Docker Compose (optional, for containerized run)

### 1. Environment Configuration
Copy the example environment configuration:
```bash
cp .env.example .env
```

### 2. Backend Setup (FastAPI)
```bash
# Navigate to backend and create virtual environment
cd backend
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI backend on port 8000
uvicorn app.main:app --reload --port 8000
```
Backend will be live at `http://localhost:8000`. API docs available at `http://localhost:8000/docs`.

### 3. Frontend Setup (React + Vite)
```bash
# In a new terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
Frontend will be available at `http://localhost:5173`.

---

## 6. Docker Compose Setup

Run both services in containerized mode with a single command:

```bash
docker compose up --build
```

- **Frontend:** `http://localhost:3000` (Nginx Alpine serving optimized production bundle with SPA client routing)
- **Backend:** `http://localhost:8000` (FastAPI service with health checks)
- **Healthcheck:** Evaluates `http://localhost:8000/health` before routing traffic.

To stop the containers:
```bash
docker compose down
```

---

## 7. Automated Testing Suite

### Backend Tests (37 Passing Tests)
The backend test suite mocks upstream HTTP requests to ensure lightning-fast, offline execution. Tests cover boundary cutoffs, post-cutoff exclusion, timestamp normalization, duplicate deduplication, mathematical metric precision, error states, and the decision simulator with error percentiles.

```bash
# From workspace root:
pytest backend/tests -v
```

### Frontend Tests (7 Passing Tests)
Frontend tests use Vitest and React Testing Library to verify API client behavior, error handling, component rendering, and route navigation across all pages including the Decision Simulator.

```bash
# In frontend directory:
cd frontend
npm test
```

### Production Build & Linting Verification
```bash
# Verify frontend TypeScript build
cd frontend
npm run build

# Verify ESLint passes with 0 errors
npm run lint
```

---

## 8. API Specification

| Method | Endpoint | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/health` | — | Service uptime and cached dataset inventory |
| `GET` | `/api/overview` | `start_date`, `end_date`, `cutoff_hour`, `resolution`, `force_refresh` | Executive KPIs, actual vs forecast series, coverage |
| `GET` | `/api/forecasts` | `date` (YYYY-MM-DD), `cutoff_hour`, `force_refresh` | SP 1–48 details, selected vintage, and historical vintages |
| `GET` | `/api/accuracy` | `start_date`, `end_date`, `cutoff_hour`, `resolution`, `force_refresh` | In-depth accuracy: MAE, RMSE, Bias, MedAE, MaxAE, daily summary, distribution |
| `GET` | `/api/simulator` | `date` (YYYY-MM-DD), `cutoff_hour`, `scenario_type`, `scenario_value`, `force_refresh` | Day-Ahead Procurement Decision Simulator: cutoff baseline selection, scenario stress testing, and error percentiles (P50/P80/P90/P95) |
| `GET` | `/api/data-quality` | `start_date`, `end_date`, `cutoff_hour`, `resolution`, `force_refresh` | Completeness, duplicate audit, bounds, upstream latency vs freshness |

---

## 9. January 2026 Evaluation Findings

Evaluating the full 31 days of January 2026 (1,488 settlement periods):
- **Actual Wind Generation (Mean):** 11,580.7 MW avg
- **Day-Ahead Forecast (Mean):** 13,294.5 MW avg
- **Mean Absolute Error (MAE):** 1,940.8 MW
- **Root Mean Squared Error (RMSE):** 2,410.6 MW
- **Forecast Bias:** +1,713.7 MW (Systematic overforecasting)
- **Median Absolute Error:** 1,609.5 MW
- **Maximum Miss:** 7,305.0 MW (observed on high-wind storm volatility day)
- **Data Coverage:** 100.0% (1,488 matched settlement periods)
- **Zero Actuals / Missing Values:** 0 nulls, 0 missing settlement periods.

---

## 10. Limitations

1. **Physical Wind Output vs. Market Financials:** Evaluates MW physical accuracy. It does not calculate financial imbalance settlement costs, which require dual cashout prices (SSP/SBP).
2. **National Aggregation:** Elexon WINDFOR forecasts national GB transmission-connected wind. It does not model zonal transmission congestion (e.g. Scottish B6 export constraint) or BM curtailment bid-offer acceptances.
3. **No Synthetic Fallback:** The application operates strictly on verifiable Elexon data. Upstream errors are surfaced explicitly rather than masking issues with fabricated data.

---

## 11. AI Assistance Disclosure

In accordance with assignment requirements, AI-assisted development tools were utilized during the development, testing, and documentation of this submission. All generated source code, analytical algorithms, metric calculations, and documentation were independently reviewed, validated, and tested against live Elexon BMRS stream data.
