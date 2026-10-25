import math
from datetime import datetime, timezone, timedelta
import pytest
from app.services.processor import (
    WindDataProcessor,
    parse_utc_timestamp,
    parse_numeric
)


def test_aggregation_of_two_half_hourly_actuals_arithmetic_mean():
    """
    Verifies that in hourly resolution, two half-hourly FUELHH actual values
    (:00 and :30) are aggregated into a single hourly actual using their arithmetic mean.
    """
    processor = WindDataProcessor(resolution='hourly')

    # SP 25 (12:00:00Z) = 10,000 MW, SP 26 (12:30:00Z) = 14,000 MW
    # Arithmetic mean = (10,000 + 14,000) / 2 = 12,000.0 MW
    sample_fuelhh = [
        {
            'fuelType': 'WIND',
            'startTime': '2026-01-15T12:00:00Z',
            'publishTime': '2026-01-15T12:35:00Z',
            'settlementDate': '2026-01-15',
            'settlementPeriod': 25,
            'generation': 10000.0
        },
        {
            'fuelType': 'WIND',
            'startTime': '2026-01-15T12:30:00Z',
            'publishTime': '2026-01-15T13:05:00Z',
            'settlementDate': '2026-01-15',
            'settlementPeriod': 26,
            'generation': 14000.0
        }
    ]

    sample_windfor = [
        {
            'startTime': '2026-01-15T12:00:00Z',
            'publishTime': '2026-01-14T22:30:00Z',
            'generation': 13000.0
        }
    ]

    fuel_records, _ = processor.process_fuelhh(sample_fuelhh)
    wind_records, _ = processor.process_windfor(sample_windfor)
    selected, vintages = processor.select_day_ahead_vintages(wind_records, '2026-01-15', '2026-01-15')

    eval_result = processor.align_and_evaluate(
        fuel_records, selected, vintages, '2026-01-15', '2026-01-15'
    )

    # Find the 12:00:00 period in series
    p12 = next(p for p in eval_result['series'] if p['timestamp'] == '2026-01-15T12:00:00+00:00')
    assert p12['actual'] == 12000.0, "Aggregated actual must be the arithmetic mean of SP25 and SP26"
    assert p12['forecast'] == 13000.0
    assert p12['error'] == 1000.0
    assert p12['abs_error'] == 1000.0
    assert p12['is_step_extended'] is False
    assert p12['forecast_type'] == 'native_hourly'


def test_hourly_coverage_denominator_and_100_percent_full_month():
    """
    Verifies that for a complete month (January 1–31, 2026):
    - Expected hourly delivery periods is exactly 744 (31 days * 24 hours).
    - Matched count is 744.
    - Coverage percentage is 100.0% with 744 as denominator.
    """
    processor = WindDataProcessor(resolution='hourly')

    # Generate synthetic complete January 2026 data
    fuelhh_rows = []
    windfor_rows = []

    cur_dt = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 1, 31, 23, 30, tzinfo=timezone.utc)

    sp = 1
    while cur_dt <= end_dt:
        date_str = cur_dt.strftime('%Y-%m-%d')
        # Add half-hourly actual
        fuelhh_rows.append({
            'fuelType': 'WIND',
            'startTime': cur_dt.isoformat(),
            'publishTime': (cur_dt + timedelta(minutes=35)).isoformat(),
            'settlementDate': date_str,
            'settlementPeriod': sp,
            'generation': 10000.0 + (sp * 10)
        })

        # Add hourly forecast if on top of hour
        if cur_dt.minute == 0:
            target_date = cur_dt.date()
            prev_day = target_date - timedelta(days=1)
            # Publication on D-1 at 22:30 UTC (prior to D-1 23:00 cutoff)
            pub_time = datetime(prev_day.year, prev_day.month, prev_day.day, 22, 30, tzinfo=timezone.utc)
            windfor_rows.append({
                'startTime': cur_dt.isoformat(),
                'publishTime': pub_time.isoformat(),
                'generation': 11000.0 + (sp * 10)
            })

        sp = (sp % 48) + 1
        cur_dt += timedelta(minutes=30)

    assert len(fuelhh_rows) == 1488, "Should have 1,488 half-hourly actual records"
    assert len(windfor_rows) == 744, "Should have 744 hourly forecast records"

    fuel_records, _ = processor.process_fuelhh(fuelhh_rows)
    wind_records, _ = processor.process_windfor(windfor_rows)
    selected, vintages = processor.select_day_ahead_vintages(wind_records, '2026-01-01', '2026-01-31')

    eval_result = processor.align_and_evaluate(
        fuel_records, selected, vintages, '2026-01-01', '2026-01-31'
    )

    quality = eval_result['quality']
    assert quality['total_expected_periods'] == 744, "Expected hourly periods denominator must be 744"
    assert quality['total_series_periods'] == 744
    assert quality['matched'] == 744
    assert quality['unmatched_actual'] == 0
    assert quality['unmatched_forecast'] == 0
    assert quality['coverage_pct'] == 100.0
    assert eval_result['sample_count'] == 744
    assert len(eval_result['series']) == 744


def test_incomplete_hourly_actual_missing_half_hour():
    """
    Verifies that if one half-hour within an hourly block is missing (e.g. SP1 is present but SP2 is missing),
    the hour cannot form a valid aggregated arithmetic mean actual, so actual_mw evaluates to None.
    """
    processor = WindDataProcessor(resolution='hourly')

    # Only provide SP1 (00:00:00Z); SP2 (00:30:00Z) is omitted
    sample_fuelhh = [
        {
            'fuelType': 'WIND',
            'startTime': '2026-01-15T00:00:00Z',
            'publishTime': '2026-01-15T00:35:00Z',
            'settlementDate': '2026-01-15',
            'settlementPeriod': 1,
            'generation': 12000.0
        }
    ]

    sample_windfor = [
        {
            'startTime': '2026-01-15T00:00:00Z',
            'publishTime': '2026-01-14T22:30:00Z',
            'generation': 13000.0
        }
    ]

    fuel_records, _ = processor.process_fuelhh(sample_fuelhh)
    wind_records, _ = processor.process_windfor(sample_windfor)
    selected, vintages = processor.select_day_ahead_vintages(wind_records, '2026-01-15', '2026-01-15')

    eval_result = processor.align_and_evaluate(
        fuel_records, selected, vintages, '2026-01-15', '2026-01-15'
    )

    p0 = next(p for p in eval_result['series'] if p['timestamp'] == '2026-01-15T00:00:00+00:00')
    assert p0['actual'] is None, "Incomplete hour must not form an actual value"
    assert p0['forecast'] == 13000.0
    assert p0['error'] is None
    # Counted as unmatched forecast (forecast present, valid actual missing)
    assert eval_result['quality']['unmatched_forecast'] == 1
    assert eval_result['quality']['matched'] == 0


def test_missing_actual_and_missing_forecast_periods():
    """
    Verifies quality accounting when some periods have actuals but no forecast,
    and other periods have forecast but no actuals.
    """
    processor = WindDataProcessor(resolution='hourly')

    # Hour 0 (00:00): Both actuals (SP1 & SP2) and forecast present -> MATCHED
    # Hour 1 (01:00): Forecast present, actuals missing -> UNMATCHED FORECAST
    # Hour 2 (02:00): Both actuals (SP5 & SP6) present, forecast missing -> UNMATCHED ACTUAL
    sample_fuelhh = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T00:00:00Z', 'generation': 10000.0, 'settlementPeriod': 1},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T00:30:00Z', 'generation': 10000.0, 'settlementPeriod': 2},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T02:00:00Z', 'generation': 15000.0, 'settlementPeriod': 5},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T02:30:00Z', 'generation': 15000.0, 'settlementPeriod': 6},
    ]

    sample_windfor = [
        {'startTime': '2026-01-15T00:00:00Z', 'publishTime': '2026-01-14T22:30:00Z', 'generation': 11000.0},
        {'startTime': '2026-01-15T01:00:00Z', 'publishTime': '2026-01-14T22:30:00Z', 'generation': 12000.0},
    ]

    fuel_records, _ = processor.process_fuelhh(sample_fuelhh)
    wind_records, _ = processor.process_windfor(sample_windfor)
    selected, vintages = processor.select_day_ahead_vintages(wind_records, '2026-01-15', '2026-01-15')

    eval_result = processor.align_and_evaluate(
        fuel_records, selected, vintages, '2026-01-15', '2026-01-15'
    )

    quality = eval_result['quality']
    assert quality['total_expected_periods'] == 24
    assert quality['matched'] == 1
    assert quality['unmatched_actual'] == 1  # Hour 2
    assert quality['unmatched_forecast'] == 1  # Hour 1
    assert quality['coverage_pct'] == round(1 / 24 * 100, 1)


def test_cutoff_eligibility_and_exclusion_of_post_cutoff_vintages():
    """
    Verifies that:
    - Publications at or prior to cutoff are eligible.
    - Publications after cutoff are strictly excluded from the day-ahead decision vintage.
    - The latest publication before cutoff is selected.
    """
    processor = WindDataProcessor(cutoff_hour=23)

    target_time = '2026-01-15T12:00:00Z'
    # Cutoff is 2026-01-14 23:00:00 UTC
    raw_vintages = [
        # Vintage A: published D-1 20:00 UTC (eligible, gen 8000)
        {'startTime': target_time, 'publishTime': '2026-01-14T20:00:00Z', 'generation': 8000.0},
        # Vintage B: published D-1 22:30 UTC (eligible, latest before cutoff, gen 9500)
        {'startTime': target_time, 'publishTime': '2026-01-14T22:30:00Z', 'generation': 9500.0},
        # Vintage C: published D-1 23:00:01 UTC (ineligible, post-cutoff, gen 12000)
        {'startTime': target_time, 'publishTime': '2026-01-14T23:00:01Z', 'generation': 12000.0},
        # Vintage D: published D 08:00 UTC (ineligible, intraday, gen 9999)
        {'startTime': target_time, 'publishTime': '2026-01-15T08:00:00Z', 'generation': 9999.0},
    ]

    records, _ = processor.process_windfor(raw_vintages)
    selected, all_vintages = processor.select_day_ahead_vintages(records, '2026-01-15', '2026-01-15')

    key = '2026-01-15T12:00:00+00:00'
    assert key in selected
    assert selected[key]['forecast'] == 9500.0, "Selected forecast must be the latest vintage published on or before cutoff"
    assert selected[key]['publish_time'] == '2026-01-14T22:30:00+00:00'

    # Check vintage list preserves all historical versions with proper eligibility flags
    v_list = all_vintages[key]
    assert len(v_list) == 4
    v_c = next(v for v in v_list if v['publish_time'] == '2026-01-14T23:00:01+00:00')
    assert v_c['is_eligible'] is False
    v_d = next(v for v in v_list if v['publish_time'] == '2026-01-15T08:00:00+00:00')
    assert v_d['is_eligible'] is False


def test_timezone_aware_timestamps_handling():
    """
    Verifies that all input timestamps (Z suffix, explicit offset, datetime objects)
    are parsed into timezone-aware UTC datetime objects.
    """
    dt_z = parse_utc_timestamp('2026-01-15T12:00:00Z')
    dt_offset = parse_utc_timestamp('2026-01-15T12:00:00+00:00')
    dt_raw = datetime(2026, 1, 15, 12, 0)

    assert dt_z.tzinfo is not None and dt_z.tzinfo == timezone.utc
    assert dt_offset.tzinfo is not None and dt_offset.tzinfo == timezone.utc
    parsed_raw = parse_utc_timestamp(dt_raw)
    assert parsed_raw.tzinfo is not None and parsed_raw.tzinfo == timezone.utc
    assert dt_z == dt_offset == parsed_raw


def test_half_hourly_step_extension_labelling():
    """
    Verifies that in half-hourly resolution:
    - The :00 forecast is labelled as native_hourly (is_step_extended=False).
    - The :30 forecast is explicitly labelled as step_extended_hourly (is_step_extended=True).
    - Step-extended count is tracked in quality metadata.
    """
    processor = WindDataProcessor(resolution='half_hourly')

    sample_fuelhh = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:00:00Z', 'generation': 10000.0, 'settlementPeriod': 25},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:30:00Z', 'generation': 12000.0, 'settlementPeriod': 26},
    ]

    sample_windfor = [
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T22:30:00Z', 'generation': 11000.0}
    ]

    fuel_records, _ = processor.process_fuelhh(sample_fuelhh)
    wind_records, _ = processor.process_windfor(sample_windfor)
    selected, vintages = processor.select_day_ahead_vintages(wind_records, '2026-01-15', '2026-01-15')

    eval_result = processor.align_and_evaluate(
        fuel_records, selected, vintages, '2026-01-15', '2026-01-15'
    )

    series = eval_result['series']
    p00 = next(p for p in series if p['timestamp'] == '2026-01-15T12:00:00+00:00')
    p30 = next(p for p in series if p['timestamp'] == '2026-01-15T12:30:00+00:00')

    assert p00['is_step_extended'] is False
    assert p00['forecast_type'] == 'native_hourly'
    assert p00['forecast'] == 11000.0
    assert p00['actual'] == 10000.0

    assert p30['is_step_extended'] is True
    assert p30['forecast_type'] == 'step_extended_hourly'
    assert p30['forecast'] == 11000.0
    assert p30['actual'] == 12000.0

    assert eval_result['quality']['step_extended_periods'] == 1
    assert eval_result['forecast_representation'] == 'step_extended_hourly'
    assert 'Hourly WINDFOR forecast step-extended' in eval_result['forecast_representation_note']
