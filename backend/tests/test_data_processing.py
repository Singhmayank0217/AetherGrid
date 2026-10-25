from datetime import datetime, timezone
from app.services.processor import WindDataProcessor, parse_utc_timestamp, parse_numeric


def test_timestamp_parsing_normalization():
    """Verifies UTC normalization and format parsing."""
    assert parse_utc_timestamp('2026-01-15T12:00:00Z') == datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    assert parse_utc_timestamp('2026-01-15T12:00:00+00:00') == datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    assert parse_utc_timestamp('invalid') is None
    assert parse_utc_timestamp(None) is None


def test_numeric_parsing():
    """Verifies float parsing and NaN/None conversion."""
    assert parse_numeric(14000) == 14000.0
    assert parse_numeric('14200.5') == 14200.5
    assert parse_numeric('invalid') is None
    assert parse_numeric(None) is None


def test_duplicate_actual_timestamps_retains_latest_publication():
    """
    Verifies that when duplicate FUELHH records with the same startTime exist,
    the documented policy retains the latest publishTime and increments duplicate count.
    """
    processor = WindDataProcessor()
    rows = [
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-15T12:35:00Z', 'generation': 10000.0, 'settlementPeriod': 25},
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-15T12:40:00Z', 'generation': 10500.0, 'settlementPeriod': 25},
    ]

    records, meta = processor.process_fuelhh(rows)
    assert meta['duplicate_actual_timestamps'] == 1
    assert len(records) == 1
    # Documented policy kept the one with latest publishTime (generation 10500.0)
    assert records[0]['generation'] == 10500.0


def test_duplicate_forecast_publications_deduplication():
    """
    Verifies that duplicate forecast publications (identical startTime and publishTime) are deduplicated.
    """
    processor = WindDataProcessor()
    rows = [
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T20:00:00Z', 'generation': 8000.0},
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T20:00:00Z', 'generation': 8000.0},
    ]

    records, meta = processor.process_windfor(rows)
    assert meta['duplicate_forecast_publications'] == 1
    assert len(records) == 1


def test_missing_values_and_fuel_type_filtering():
    """
    Verifies FUELHH non-wind filtering and missing value counting.
    """
    processor = WindDataProcessor()
    rows = [
        {'fuelType': 'CCGT', 'startTime': '2026-01-15T12:00:00Z', 'generation': 5000.0},  # filtered out
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:00:00Z', 'generation': None},    # missing value
        {'fuelType': 'WIND', 'startTime': '2026-01-15T12:30:00Z', 'generation': 12000.0}, # valid
    ]

    records, meta = processor.process_fuelhh(rows)
    assert len(records) == 1
    assert meta['missing_invalid_actuals'] == 1
    assert records[0]['generation'] == 12000.0


def test_empty_dataset_handling():
    """Verifies that empty datasets are handled gracefully without exceptions."""
    processor = WindDataProcessor()
    rec_act, meta_act = processor.process_fuelhh([])
    rec_fc, meta_fc = processor.process_windfor([])
    selected, vintages = processor.select_day_ahead_vintages(rec_fc, '2026-01-01', '2026-01-31')
    result = processor.align_and_evaluate(rec_act, selected, vintages, '2026-01-01', '2026-01-31')

    assert result['sample_count'] == 0
    assert result['metrics']['mae'] is None
    assert result['quality']['matched'] == 0
