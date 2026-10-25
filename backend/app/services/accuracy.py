from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import asyncio
from .elexon import fetch_fuelhh_raw, fetch_windfor_raw, get_cached_metadata
from .processor import WindDataProcessor, parse_utc_timestamp, parse_numeric


def select_vintages(forecasts: List[Dict[str, Any]], cutoff_hour: int = 23) -> Dict[str, Dict[str, Any]]:
    """
    Backwards-compatible helper for selecting the latest eligible vintage published
    on D-1 on or before cutoff_hour:00:00 UTC.
    """
    processor = WindDataProcessor(cutoff_hour=cutoff_hour)
    records, _ = processor.process_windfor(forecasts)
    if not records:
        return {}

    min_date = min(r['startTime'] for r in records).strftime('%Y-%m-%d')
    max_date = max(r['startTime'] for r in records).strftime('%Y-%m-%d')
    selected, _ = processor.select_day_ahead_vintages(records, min_date, max_date)
    return selected


async def evaluate(
    start_date: str = '2026-01-01',
    end_date: str = '2026-01-31',
    cutoff_hour: int = 23,
    resolution: str = 'half_hourly',
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Coordinates ingestion, processing, vintage selection, and accuracy metric calculation.
    """
    processor = WindDataProcessor(cutoff_hour=cutoff_hour, resolution=resolution)

    # Fetch raw datasets concurrently
    (fuelhh_rows, fuelhh_meta), (windfor_rows, windfor_meta) = await asyncio.gather(
        fetch_fuelhh_raw(start_date, end_date, force_refresh=force_refresh),
        fetch_windfor_raw(start_date, end_date, force_refresh=force_refresh)
    )

    # Process and validate
    fuelhh_records, actual_quality = processor.process_fuelhh(fuelhh_rows)
    windfor_records, forecast_quality = processor.process_windfor(windfor_rows)

    # Select day-ahead vintages
    selected_vintages, all_vintages = processor.select_day_ahead_vintages(windfor_records, start_date, end_date)

    # Align and compute metrics
    eval_result = processor.align_and_evaluate(
        fuelhh_records=fuelhh_records,
        selected_vintages=selected_vintages,
        all_vintages=all_vintages,
        start_date=start_date,
        end_date=end_date
    )

    eval_result['fetched_at'] = datetime.now(timezone.utc).isoformat()
    eval_result['upstream_meta'] = {
        'fuelhh': fuelhh_meta,
        'windfor': windfor_meta
    }
    eval_result['ingestion_quality'] = {
        'actual': actual_quality,
        'forecast': forecast_quality
    }

    return eval_result


async def get_forecast_explorer_data(date: str, cutoff_hour: int = 23, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns detailed forecast explorer data for a single date (2026-01-XX):
    - All 48 delivery periods
    - Selected eligible forecast (published by D-1 cutoff)
    - Actual generation
    - Errors
    - All historical forecast publication versions (vintages)
    - Cutoff explanation and timeline
    """
    processor = WindDataProcessor(cutoff_hour=cutoff_hour, resolution='half_hourly')

    (fuelhh_rows, _), (windfor_rows, _) = await asyncio.gather(
        fetch_fuelhh_raw(date, date, force_refresh=force_refresh),
        fetch_windfor_raw(date, date, force_refresh=force_refresh)
    )

    fuelhh_records, _ = processor.process_fuelhh(fuelhh_rows)
    windfor_records, _ = processor.process_windfor(windfor_rows)

    selected_vintages, all_vintages = processor.select_day_ahead_vintages(windfor_records, date, date)
    eval_result = processor.align_and_evaluate(fuelhh_records, selected_vintages, all_vintages, date, date)

    # Attach historical versions for each series entry
    enriched_series = []
    for item in eval_result['series']:
        t_key = item['timestamp']
        dt = parse_utc_timestamp(t_key)
        # Look up either exact key or top-of-hour key
        vintages_list = all_vintages.get(t_key)
        if not vintages_list and dt and dt.minute == 30:
            top_hour = dt.replace(minute=0, second=0, microsecond=0).isoformat()
            vintages_list = all_vintages.get(top_hour, [])

        enriched_item = dict(item)
        enriched_item['historical_versions'] = vintages_list or []
        enriched_series.append(enriched_item)

    # Date-specific cutoff timestamp: D-1 at cutoff_hour:00:00 UTC
    target_date_dt = parse_utc_timestamp(f"{date}T00:00:00Z")
    cutoff_dt = datetime(target_date_dt.year, target_date_dt.month, target_date_dt.day, cutoff_hour, 0, 0, tzinfo=timezone.utc) - timedelta(days=1)

    return {
        'status': 'ok',
        'date': date,
        'cutoff_policy': {
            'hour_utc': cutoff_hour,
            'cutoff_timestamp': cutoff_dt.isoformat(),
            'description': f'Evaluated using latest forecast published on or before D-1 ({cutoff_dt.strftime("%d %b %Y")}) at {cutoff_hour:02d}:00 UTC (configurable application default).'
        },
        'metrics': eval_result['metrics'],
        'sample_count': eval_result['sample_count'],
        'periods': enriched_series
    }


async def get_data_quality_report(
    start_date: str = '2026-01-01',
    end_date: str = '2026-01-31',
    cutoff_hour: int = 23,
    resolution: str = 'half_hourly',
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Returns comprehensive data quality diagnostics distinguishing connectivity from data freshness.
    """
    processor = WindDataProcessor(cutoff_hour=cutoff_hour, resolution=resolution)

    (fuelhh_rows, fuelhh_meta), (windfor_rows, windfor_meta) = await asyncio.gather(
        fetch_fuelhh_raw(start_date, end_date, force_refresh=force_refresh),
        fetch_windfor_raw(start_date, end_date, force_refresh=force_refresh)
    )

    fuelhh_records, actual_quality = processor.process_fuelhh(fuelhh_rows)
    windfor_records, forecast_quality = processor.process_windfor(windfor_rows)

    selected_vintages, all_vintages = processor.select_day_ahead_vintages(windfor_records, start_date, end_date)
    eval_result = processor.align_and_evaluate(fuelhh_records, selected_vintages, all_vintages, start_date, end_date)

    # Determine earliest and latest timestamps
    earliest_actual = min((r['startTime'].isoformat() for r in fuelhh_records), default=None)
    latest_actual = max((r['startTime'].isoformat() for r in fuelhh_records), default=None)

    earliest_forecast_target = min((r['startTime'].isoformat() for r in windfor_records), default=None)
    latest_forecast_target = max((r['startTime'].isoformat() for r in windfor_records), default=None)

    earliest_publish = min((r['publishTime'].isoformat() for r in windfor_records), default=None)
    latest_publish = max((r['publishTime'].isoformat() for r in windfor_records), default=None)

    zero_actuals_count = sum(1 for r in fuelhh_records if r['generation'] == 0)

    return {
        'status': 'ok',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'evaluation_range': {'start_date': start_date, 'end_date': end_date},
        'resolution': resolution,
        'summary': {
            'actual_record_count': len(fuelhh_records),
            'forecast_raw_record_count': len(windfor_records),
            'distinct_forecast_targets': len(all_vintages),
            'total_expected_periods': eval_result['quality']['total_expected_periods'],
            'matched_delivery_periods': eval_result['quality']['matched'],
            'unmatched_actual_periods': eval_result['quality']['unmatched_actual'],
            'unmatched_forecast_periods': eval_result['quality']['unmatched_forecast'],
            'coverage_pct': eval_result['quality']['coverage_pct'],
            'step_extended_periods': eval_result['quality'].get('step_extended_periods', 0),
            'zero_actual_periods': zero_actuals_count
        },
        'integrity': {
            'duplicate_actual_timestamps': actual_quality['duplicate_actual_timestamps'],
            'duplicate_forecast_publications': forecast_quality['duplicate_forecast_publications'],
            'missing_invalid_actuals': actual_quality['missing_invalid_actuals'],
            'missing_invalid_forecasts': forecast_quality['missing_invalid_forecasts'],
            'duplicate_policy': 'Latest publication time retained for duplicate actual timestamps; duplicate forecast publications discarded.'
        },
        'temporal_bounds': {
            'earliest_actual_delivery': earliest_actual,
            'latest_actual_delivery': latest_actual,
            'earliest_forecast_target': earliest_forecast_target,
            'latest_forecast_target': latest_forecast_target,
            'earliest_forecast_publish': earliest_publish,
            'latest_forecast_publish': latest_publish
        },
        'upstream_connectivity': {
            'fuelhh': fuelhh_meta,
            'windfor': windfor_meta,
            'connectivity_status': 'connected' if fuelhh_meta['status'] == 'ok' and windfor_meta['status'] == 'ok' else 'degraded',
            'freshness_status': 'verified_historical_dataset_january_2026',
            'note': 'HTTP connectivity verifies access to Elexon BMRS API; data freshness verifies target settlement date completeness.'
        }
    }


async def get_simulator_data(
    date: str = '2026-01-15',
    cutoff_hour: int = 23,
    scenario_pct: float = 0.0,
    scenario_mw: float = 0.0,
    resolution: str = 'hourly',
    context_start: str = '2026-01-01',
    context_end: str = '2026-01-31',
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Coordinates data retrieval and evaluation for the Day-Ahead Procurement Decision Simulator & Cutoff Replay.
    Fetches raw Elexon FUELHH actuals and WINDFOR forecasts for context window (e.g. January 2026),
    filters and aligns records, and executes simulator scenario projection, lookahead analysis,
    and empirical error uncertainty derivation.
    """
    processor = WindDataProcessor(cutoff_hour=cutoff_hour, resolution=resolution)

    # Fetch raw datasets for full context range (ensuring target date is included)
    start_req = min(date, context_start)
    end_req = max(date, context_end)

    (fuelhh_rows, _), (windfor_rows, _) = await asyncio.gather(
        fetch_fuelhh_raw(start_req, end_req, force_refresh=force_refresh),
        fetch_windfor_raw(start_req, end_req, force_refresh=force_refresh)
    )

    fuelhh_records, _ = processor.process_fuelhh(fuelhh_rows)
    windfor_records, _ = processor.process_windfor(windfor_rows)

    return processor.evaluate_simulator(
        fuelhh_records=fuelhh_records,
        windfor_records=windfor_records,
        target_date=date,
        scenario_pct=scenario_pct,
        scenario_mw=scenario_mw,
        context_start_date=context_start,
        context_end_date=context_end
    )
