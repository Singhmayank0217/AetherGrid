import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .services.accuracy import evaluate, get_forecast_explorer_data, get_data_quality_report, get_simulator_data
from .services.elexon import get_cached_metadata

app = FastAPI(
    title='AetherGrid API',
    version='1.0.0',
    description='AetherGrid UK Wind Generation Forecast Analytics & Day-Ahead Decision Support Engine for January 2026.'
)

# Configure CORS
allowed_origins_env = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,http://localhost:80,http://localhost')
origins = [o.strip() for o in allowed_origins_env.split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/health')
def health():
    """Health check endpoint providing service uptime and upstream cache status."""
    return {
        'status': 'ok',
        'service': 'aethergrid-api',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'cached_datasets': list(get_cached_metadata().keys())
    }


@app.get('/api/overview')
async def overview(
    start_date: str = Query('2026-01-01', pattern=r'^\d{4}-\d{2}-\d{2}$', description='Evaluation start date (YYYY-MM-DD)'),
    end_date: str = Query('2026-01-31', pattern=r'^\d{4}-\d{2}-\d{2}$', description='Evaluation end date (YYYY-MM-DD)'),
    cutoff_hour: int = Query(23, ge=0, le=23, description='D-1 decision cutoff hour in UTC (0-23, configurable application default)'),
    resolution: str = Query('half_hourly', pattern=r'^(half_hourly|hourly)$', description='Alignment resolution'),
    force_refresh: bool = Query(False, description='Bypass cache and force fresh fetch from Elexon BMRS')
):
    """
    Returns executive summary metrics, recent delivery series, and evaluation coverage.
    """
    try:
        data = await evaluate(
            start_date=start_date,
            end_date=end_date,
            cutoff_hour=cutoff_hour,
            resolution=resolution,
            force_refresh=force_refresh
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to evaluate wind forecast dataset: {exc}")


@app.get('/api/accuracy')
async def accuracy(
    start_date: str = Query('2026-01-01', pattern=r'^\d{4}-\d{2}-\d{2}$'),
    end_date: str = Query('2026-01-31', pattern=r'^\d{4}-\d{2}-\d{2}$'),
    cutoff_hour: int = Query(23, ge=0, le=23),
    resolution: str = Query('half_hourly', pattern=r'^(half_hourly|hourly)$'),
    force_refresh: bool = Query(False)
):
    """
    Returns in-depth statistical accuracy analytics: MAE, RMSE, Bias, Median AE, Max AE,
    error distribution bins, daily summaries, and delivery-period time series.
    """
    try:
        data = await evaluate(
            start_date=start_date,
            end_date=end_date,
            cutoff_hour=cutoff_hour,
            resolution=resolution,
            force_refresh=force_refresh
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Accuracy evaluation failed: {exc}")


@app.get('/api/forecasts')
async def forecasts(
    date: str = Query('2026-01-15', pattern=r'^\d{4}-\d{2}-\d{2}$', description='Target delivery date (YYYY-MM-DD)'),
    cutoff_hour: int = Query(23, ge=0, le=23, description='D-1 decision cutoff hour in UTC (configurable application default)'),
    force_refresh: bool = Query(False)
):
    """
    Returns detailed delivery period breakdown for a specific date, including
    selected day-ahead forecast, actual generation, and all historical published forecast versions.
    """
    try:
        data = await get_forecast_explorer_data(
            date=date,
            cutoff_hour=cutoff_hour,
            force_refresh=force_refresh
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Forecast explorer query failed: {exc}")


@app.get('/api/data-quality')
async def data_quality(
    start_date: str = Query('2026-01-01', pattern=r'^\d{4}-\d{2}-\d{2}$'),
    end_date: str = Query('2026-01-31', pattern=r'^\d{4}-\d{2}-\d{2}$'),
    cutoff_hour: int = Query(23, ge=0, le=23),
    resolution: str = Query('half_hourly', pattern=r'^(half_hourly|hourly)$'),
    force_refresh: bool = Query(False)
):
    """
    Returns data quality diagnostics: completeness, duplicate counts, missing/invalid observations,
    earliest/latest timestamps, and upstream Elexon BMRS connectivity and freshness.
    """
    try:
        data = await get_data_quality_report(
            start_date=start_date,
            end_date=end_date,
            cutoff_hour=cutoff_hour,
            resolution=resolution,
            force_refresh=force_refresh
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data quality audit failed: {exc}")


@app.get('/api/simulator')
async def simulator(
    date: str = Query('2026-01-15', pattern=r'^\d{4}-\d{2}-\d{2}$', description='Delivery date for simulation (YYYY-MM-DD)'),
    cutoff_hour: int = Query(23, ge=0, le=23, description='Decision cutoff hour on D-1 in UTC (e.g. 11, 12, 17, 23)'),
    scenario_pct: float = Query(0.0, ge=-100.0, le=200.0, description='User-adjustable stress scenario percentage shift (-100% to +200%)'),
    scenario_mw: float = Query(0.0, description='User-adjustable stress scenario absolute MW shift'),
    resolution: str = Query('hourly', pattern=r'^(hourly|half_hourly)$', description='Delivery period resolution'),
    context_start: str = Query('2026-01-01', pattern=r'^\d{4}-\d{2}-\d{2}$', description='Context evaluation start date for empirical percentiles'),
    context_end: str = Query('2026-01-31', pattern=r'^\d{4}-\d{2}-\d{2}$', description='Context evaluation end date for empirical percentiles'),
    force_refresh: bool = Query(False, description='Force fresh fetch from Elexon BMRS')
):
    """
    Day-Ahead Procurement Decision Simulator & Forecast Cutoff Replay endpoint.
    Provides:
    - Cutoff-compliant baseline forecast (MW) for target delivery day
    - User scenario generation (MW) and delta deviation from baseline
    - Empirical uncertainty context (P50, P80, P90, P95) derived from historical matched records
    - Cutoff replay with lookahead post-cutoff vintages to inspect intraday forecast evolution
    - Delivery-period attention heatmap flags (severe error, large revision, step-extended, missing data)
    """
    try:
        data = await get_simulator_data(
            date=date,
            cutoff_hour=cutoff_hour,
            scenario_pct=scenario_pct,
            scenario_mw=scenario_mw,
            resolution=resolution,
            context_start=context_start,
            context_end=context_end,
            force_refresh=force_refresh
        )
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Simulator calculation failed: {exc}")

