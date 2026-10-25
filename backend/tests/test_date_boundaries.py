from datetime import datetime, timezone
from app.services.processor import WindDataProcessor


def test_january_1_cutoff_boundary_retrieves_december_forecast():
    """
    Verifies that for delivery on January 1, 2026:
    The D-1 23:00 UTC cutoff occurs on 2025-12-31 at 23:00 UTC.
    Forecasts published on 2025-12-31 on or before 23:00 UTC are correctly selected.
    """
    processor = WindDataProcessor(cutoff_hour=23)

    raw_forecasts = [
        # Target Jan 1 at 00:00:00Z, published on Dec 31 at 22:30:00Z
        {
            'startTime': '2026-01-01T00:00:00Z',
            'publishTime': '2025-12-31T22:30:00Z',
            'generation': 18500.0
        },
        # Target Jan 1 at 00:00:00Z, published on Jan 1 at 01:00:00Z (post cutoff)
        {
            'startTime': '2026-01-01T00:00:00Z',
            'publishTime': '2026-01-01T01:00:00Z',
            'generation': 19999.0
        }
    ]

    records, _ = processor.process_windfor(raw_forecasts)
    selected, _ = processor.select_day_ahead_vintages(records, '2026-01-01', '2026-01-01')

    key = '2026-01-01T00:00:00+00:00'
    assert key in selected, "Jan 1 delivery period must match vintage published on Dec 31"
    assert selected[key]['forecast'] == 18500.0
    assert selected[key]['publish_time'] == '2025-12-31T22:30:00+00:00'


def test_january_31_cutoff_boundary():
    """
    Verifies that for delivery on January 31, 2026:
    The D-1 23:00 UTC cutoff occurs on 2026-01-30 at 23:00 UTC.
    Forecasts published on 2026-01-30 are correctly selected.
    """
    processor = WindDataProcessor(cutoff_hour=23)

    raw_forecasts = [
        {
            'startTime': '2026-01-31T23:00:00Z',
            'publishTime': '2026-01-30T21:00:00Z',
            'generation': 21400.0
        }
    ]

    records, _ = processor.process_windfor(raw_forecasts)
    selected, _ = processor.select_day_ahead_vintages(records, '2026-01-31', '2026-01-31')

    key = '2026-01-31T23:00:00+00:00'
    assert key in selected
    assert selected[key]['forecast'] == 21400.0
