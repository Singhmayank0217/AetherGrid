from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.processor import WindDataProcessor, calculate_percentile


client = TestClient(app)


def test_calculate_percentile():
    """Verify linear interpolation quantile calculation matches expected values."""
    assert calculate_percentile([], 0.5) is None
    assert calculate_percentile([100.0], 0.5) == 100.0

    # 10 sorted elements: 0 to 90
    data = [float(i * 10) for i in range(10)]
    assert calculate_percentile(data, 0.5) == 45.0
    assert calculate_percentile(data, 0.8) == 72.0
    assert calculate_percentile(data, 0.9) == 81.0


def test_simulator_scenario_arithmetic():
    """Verify scenario math: percentage shift, absolute MW shift, non-negative clamping, and delta MW."""
    processor = WindDataProcessor(cutoff_hour=23, resolution='hourly')

    fuelhh = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T10:00:00Z', 'generation': 12000.0, 'settlementPeriod': 21},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T10:30:00Z', 'generation': 12000.0, 'settlementPeriod': 22},
    ]
    windfor = [
        {'startTime': '2026-01-15T10:00:00Z', 'publishTime': '2026-01-14T22:30:00Z', 'generation': 10000.0},
    ]

    fuel_recs, _ = processor.process_fuelhh(fuelhh)
    wind_recs, _ = processor.process_windfor(windfor)

    # Test +20% scenario
    res_plus = processor.evaluate_simulator(
        fuelhh_records=fuel_recs,
        windfor_records=wind_recs,
        target_date='2026-01-15',
        scenario_pct=20.0,
        scenario_mw=0.0
    )
    period = next(p for p in res_plus['periods'] if p['timestamp'].startswith('2026-01-15T10:00'))
    assert period['baseline_forecast'] == 10000.0
    assert period['scenario_forecast'] == 12000.0
    assert period['scenario_delta_mw'] == 2000.0
    assert period['actual'] == 12000.0
    assert period['error_mw'] == -2000.0  # baseline error = 10000 - 12000
    assert period['scenario_error_mw'] == 0.0  # scenario error = 12000 - 12000

    # Test -20% scenario
    res_minus = processor.evaluate_simulator(
        fuelhh_records=fuel_recs,
        windfor_records=wind_recs,
        target_date='2026-01-15',
        scenario_pct=-20.0,
        scenario_mw=0.0
    )
    period_m = next(p for p in res_minus['periods'] if p['timestamp'].startswith('2026-01-15T10:00'))
    assert period_m['baseline_forecast'] == 10000.0
    assert period_m['scenario_forecast'] == 8000.0
    assert period_m['scenario_delta_mw'] == -2000.0

    # Test extreme negative clamp (generation cannot be negative)
    res_clamp = processor.evaluate_simulator(
        fuelhh_records=fuel_recs,
        windfor_records=wind_recs,
        target_date='2026-01-15',
        scenario_pct=-150.0,
        scenario_mw=0.0
    )
    period_c = next(p for p in res_clamp['periods'] if p['timestamp'].startswith('2026-01-15T10:00'))
    assert period_c['scenario_forecast'] == 0.0


def test_simulator_cutoff_eligibility_and_lookahead():
    """Verify that only publications on or before D-1 cutoff are selected as baseline, and later ones appear in lookahead."""
    processor = WindDataProcessor(cutoff_hour=23, resolution='hourly')

    fuelhh = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:00:00Z', 'generation': 10500.0, 'settlementPeriod': 25},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:30:00Z', 'generation': 10500.0, 'settlementPeriod': 26},
    ]
    # Publication 1: eligible (2026-01-14 22:00 UTC)
    # Publication 2: post-cutoff (2026-01-15 08:00 UTC)
    windfor = [
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T22:00:00Z', 'generation': 9000.0},
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-15T08:00:00Z', 'generation': 11000.0},
    ]

    fuel_recs, _ = processor.process_fuelhh(fuelhh)
    wind_recs, _ = processor.process_windfor(windfor)

    res = processor.evaluate_simulator(
        fuelhh_records=fuel_recs,
        windfor_records=wind_recs,
        target_date='2026-01-15'
    )

    period = next(p for p in res['periods'] if p['timestamp'].startswith('2026-01-15T12:00'))
    # Selected baseline MUST be the eligible 9000.0, NOT 11000.0
    assert period['baseline_forecast'] == 9000.0
    assert period['publish_time'] == '2026-01-14T22:00:00+00:00'

    # Lookahead post-cutoff vintage must capture the 11000.0 publication
    assert period['latest_post_cutoff'] is not None
    assert period['latest_post_cutoff']['generation'] == 11000.0
    assert period['lookahead_delta_mw'] == 2000.0  # 11000 - 9000
    assert 'lookahead_shift' in period['attention_flags']


def test_simulator_step_extension_labelling_in_half_hourly():
    """Verify that in half-hourly mode, :30 periods are explicitly labelled as step_extended."""
    processor = WindDataProcessor(cutoff_hour=23, resolution='half_hourly')

    fuelhh = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T14:00:00Z', 'generation': 8000.0, 'settlementPeriod': 29},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T14:30:00Z', 'generation': 8200.0, 'settlementPeriod': 30},
    ]
    # Native hourly forecast at 14:00
    windfor = [
        {'startTime': '2026-01-15T14:00:00Z', 'publishTime': '2026-01-14T22:00:00Z', 'generation': 8100.0},
    ]

    fuel_recs, _ = processor.process_fuelhh(fuelhh)
    wind_recs, _ = processor.process_windfor(windfor)

    res = processor.evaluate_simulator(
        fuelhh_records=fuel_recs,
        windfor_records=wind_recs,
        target_date='2026-01-15'
    )

    p_00 = next(p for p in res['periods'] if p['timestamp'].startswith('2026-01-15T14:00'))
    p_30 = next(p for p in res['periods'] if p['timestamp'].startswith('2026-01-15T14:30'))

    assert p_00['is_step_extended'] is False
    assert p_00['forecast_type'] == 'native_hourly'

    assert p_30['is_step_extended'] is True
    assert p_30['forecast_type'] == 'step_extended_hourly'
    assert 'step_extended' in p_30['attention_flags']


def test_simulator_missing_and_incomplete_periods():
    """Verify explanation and attention flags when forecast or actual data is missing."""
    processor = WindDataProcessor(cutoff_hour=23, resolution='hourly')

    # No forecast for 04:00, actual present
    fuelhh = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T04:00:00Z', 'generation': 5000.0, 'settlementPeriod': 9},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T04:30:00Z', 'generation': 5200.0, 'settlementPeriod': 10},
    ]
    windfor = []

    fuel_recs, _ = processor.process_fuelhh(fuelhh)
    wind_recs, _ = processor.process_windfor(windfor)

    res = processor.evaluate_simulator(
        fuelhh_records=fuel_recs,
        windfor_records=wind_recs,
        target_date='2026-01-15'
    )

    p_04 = next(p for p in res['periods'] if p['timestamp'].startswith('2026-01-15T04:00'))
    assert p_04['baseline_forecast'] is None
    assert p_04['scenario_forecast'] is None
    assert p_04['actual'] == 5100.0
    assert 'missing_forecast' in p_04['attention_flags']


def test_simulator_presets_and_disclaimers():
    """Verify required cutoff presets and explicit national wind & scenario disclaimers."""
    processor = WindDataProcessor(cutoff_hour=11, resolution='hourly')

    res = processor.evaluate_simulator(
        fuelhh_records=[],
        windfor_records=[],
        target_date='2026-01-15'
    )

    presets = res['cutoff_policy']['presets']
    hours = [p['hour_utc'] for p in presets]
    assert 11 in hours
    assert 12 in hours
    assert 17 in hours
    assert 23 in hours

    # Disclaimers
    disclaimers = res['disclaimers']
    assert any("net procurement volume" in d for d in disclaimers)
    assert any("NOT an official Elexon forecast" in d or "new or alternative Elexon forecasts" in d for d in disclaimers)
