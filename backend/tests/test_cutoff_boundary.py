from datetime import datetime, timezone, timedelta
from app.services.processor import WindDataProcessor


def test_cutoff_boundary_inclusion_and_exclusion():
    """
    Tests exact boundary cases for D-1 23:00 UTC cutoff:
    - 2026-01-15 12:00:00Z delivery target.
    - Cutoff is 2026-01-14 23:00:00Z.
    - Publication at 22:59:59Z: eligible.
    - Publication at 23:00:00Z: eligible (on cutoff boundary).
    - Publication at 23:00:01Z: ineligible (post cutoff).
    - Publication on delivery day 01:00:00Z: ineligible.
    """
    processor = WindDataProcessor(cutoff_hour=23)

    raw_forecasts = [
        # Eligible earlier vintage
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T20:00:00Z', 'generation': 1000.0},
        # Eligible exactly on boundary
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T23:00:00Z', 'generation': 1200.0},
        # Ineligible 1 second after boundary
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T23:00:01Z', 'generation': 9999.0},
        # Ineligible day-of publication
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-15T02:00:00Z', 'generation': 8888.0},
    ]

    records, _ = processor.process_windfor(raw_forecasts)
    selected, all_vintages = processor.select_day_ahead_vintages(records, '2026-01-15', '2026-01-15')

    key = '2026-01-15T12:00:00+00:00'
    assert key in selected, "Target period should have a selected vintage"
    # Latest eligible on or before 23:00 is 1200.0 MW
    assert selected[key]['forecast'] == 1200.0
    assert selected[key]['publish_time'] == '2026-01-14T23:00:00+00:00'

    # All vintages should still be tracked for the explorer
    vintages = all_vintages[key]
    assert len(vintages) == 4
    eligible_count = sum(1 for v in vintages if v['is_eligible'])
    assert eligible_count == 2


def test_custom_cutoff_hour():
    """
    Tests configurable cutoff hour (e.g. 17:00 UTC instead of 23:00 UTC).
    """
    processor_17 = WindDataProcessor(cutoff_hour=17)

    raw_forecasts = [
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T16:30:00Z', 'generation': 1500.0},
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-14T18:00:00Z', 'generation': 2500.0},
    ]

    records, _ = processor_17.process_windfor(raw_forecasts)
    selected, _ = processor_17.select_day_ahead_vintages(records, '2026-01-15', '2026-01-15')

    key = '2026-01-15T12:00:00+00:00'
    assert selected[key]['forecast'] == 1500.0
    assert selected[key]['publish_time'] == '2026-01-14T16:30:00+00:00'


def test_no_eligible_forecasts_returns_empty():
    """
    If all publications are after cutoff, no vintage should be selected.
    """
    processor = WindDataProcessor(cutoff_hour=23)
    raw_forecasts = [
        {'startTime': '2026-01-15T12:00:00Z', 'publishTime': '2026-01-15T01:00:00Z', 'generation': 1000.0}
    ]
    records, _ = processor.process_windfor(raw_forecasts)
    selected, _ = processor.select_day_ahead_vintages(records, '2026-01-15', '2026-01-15')
    assert selected == {}
