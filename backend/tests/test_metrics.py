import math
from datetime import datetime, timezone
from app.services.processor import WindDataProcessor


def test_metric_calculations_exact():
    """
    Verifies mathematical formulas for MAE, RMSE, Bias, MedAE, MaxAE:
    - Actual: [100, 200, 300]
    - Forecast: [120, 190, 330]
    - Error (forecast - actual): [+20, -10, +30]
    - Abs Error: [20, 10, 30]
    - MAE = (20 + 10 + 30)/3 = 20.0
    - RMSE = sqrt((400 + 100 + 900)/3) = sqrt(1400/3) = 21.602... -> round to 21.6
    - Bias = (+20 - 10 + 30)/3 = +13.333... -> round to 13.3 (overforecast)
    - Median AE = 20.0
    - Max AE = 30.0
    """
    processor = WindDataProcessor(resolution='hourly')

    matched = [
        {'timestamp': '2026-01-15T00:00:00+00:00', 'datetime': datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc), 'actual': 100.0, 'forecast': 120.0, 'error': 20.0, 'abs_error': 20.0},
        {'timestamp': '2026-01-15T01:00:00+00:00', 'datetime': datetime(2026, 1, 15, 1, 0, tzinfo=timezone.utc), 'actual': 200.0, 'forecast': 190.0, 'error': -10.0, 'abs_error': 10.0},
        {'timestamp': '2026-01-15T02:00:00+00:00', 'datetime': datetime(2026, 1, 15, 2, 0, tzinfo=timezone.utc), 'actual': 300.0, 'forecast': 330.0, 'error': 30.0, 'abs_error': 30.0},
    ]

    metrics = processor._calculate_metrics(matched)
    assert metrics['mae'] == 20.0
    assert metrics['rmse'] == 21.6
    assert metrics['bias'] == 13.3
    assert metrics['median_abs_error'] == 20.0
    assert metrics['max_abs_error'] == 30.0
    assert metrics['actual_mean'] == 200.0
    assert metrics['forecast_mean'] == 213.3


def test_negative_bias_underforecasting():
    """Verifies that negative bias correctly flags underforecasting (forecast < actual)."""
    processor = WindDataProcessor()
    matched = [
        {'timestamp': '2026-01-15T00:00:00+00:00', 'datetime': datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc), 'actual': 500.0, 'forecast': 400.0, 'error': -100.0, 'abs_error': 100.0},
    ]
    metrics = processor._calculate_metrics(matched)
    assert metrics['bias'] == -100.0
    assert metrics['mae'] == 100.0


def test_zero_actuals_retained():
    """
    Verifies that zero actual generation values are retained in MAE and sample counts.
    """
    processor = WindDataProcessor()
    matched = [
        {'timestamp': '2026-01-15T00:00:00+00:00', 'datetime': datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc), 'actual': 0.0, 'forecast': 50.0, 'error': 50.0, 'abs_error': 50.0},
        {'timestamp': '2026-01-15T01:00:00+00:00', 'datetime': datetime(2026, 1, 15, 1, 0, tzinfo=timezone.utc), 'actual': 100.0, 'forecast': 100.0, 'error': 0.0, 'abs_error': 0.0},
    ]
    metrics = processor._calculate_metrics(matched)
    assert metrics['mae'] == 25.0
    assert metrics['actual_mean'] == 50.0


def test_daily_summary_and_error_distribution():
    """Verifies daily aggregation and error distribution binning."""
    processor = WindDataProcessor()
    matched = [
        # Day 1: error = +500
        {'timestamp': '2026-01-01T10:00:00+00:00', 'datetime': datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), 'actual': 1000.0, 'forecast': 1500.0, 'error': 500.0, 'abs_error': 500.0},
        # Day 2: error = -2500
        {'timestamp': '2026-01-02T10:00:00+00:00', 'datetime': datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc), 'actual': 5000.0, 'forecast': 2500.0, 'error': -2500.0, 'abs_error': 2500.0},
    ]

    daily = processor._calculate_daily_summary(matched)
    assert len(daily) == 2
    assert daily[0]['date'] == '2026-01-01'
    assert daily[0]['mae'] == 500.0
    assert daily[1]['date'] == '2026-01-02'
    assert daily[1]['mae'] == 2500.0

    dist = processor._calculate_error_distribution(matched)
    assert len(dist) == 6
    # < -2000 MW bin should have 1 count
    lt_2000 = next(b for b in dist if b['range'] == '< -2000 MW')
    assert lt_2000['count'] == 1
    # 0 to +1000 MW bin should have 1 count
    zero_to_1000 = next(b for b in dist if b['range'] == '0 to +1000 MW')
    assert zero_to_1000['count'] == 1
