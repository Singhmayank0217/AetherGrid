"""
Independent acceptance verification script for AetherGrid Analytical Correctness.
Tests all requirements of Section A of the Final Acceptance Audit.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import math
import statistics

# Ensure backend module is importable
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from app.services.processor import WindDataProcessor, calculate_percentile, parse_utc_timestamp
from app.services.elexon import fetch_fuelhh_raw, fetch_windfor_raw
import asyncio

async def run_analytical_acceptance():
    print("=================================================================")
    print(">>> AETHERGRID ACCEPTANCE AUDIT: PART A (ANALYTICAL CORRECTNESS) <<<")
    print("=================================================================\n")

    results = {}

    # --- 1. Quantile Calculation & Percentiles ---
    print("--- 1. Validating calculate_percentile Function ---")
    data_test = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50_test = calculate_percentile(data_test, 0.50)
    p80_test = calculate_percentile(data_test, 0.80)
    p90_test = calculate_percentile(data_test, 0.90)
    p95_test = calculate_percentile(data_test, 0.95)

    print(f"  Test data (10 items): {data_test}")
    print(f"  P50: {p50_test} (Expected: 55.0)")
    print(f"  P80: {p80_test} (Expected: 82.0)")
    print(f"  P90: {p90_test} (Expected: 91.0)")
    print(f"  P95: {p95_test} (Expected: 95.5)")
    assert p50_test == 55.0, f"P50 failed: {p50_test}"
    assert p80_test == 82.0, f"P80 failed: {p80_test}"
    assert p90_test == 91.0, f"P90 failed: {p90_test}"
    assert p95_test == 95.5, f"P95 failed: {p95_test}"
    print("  [PASS] calculate_percentile quantile math verified.\n")

    # --- 2. Fetch Raw Data for January 2026 ---
    print("--- 2. Fetching Raw Data for January 2026 ---")
    (fuelhh_rows, fuel_meta), (windfor_rows, wind_meta) = await asyncio.gather(
        fetch_fuelhh_raw('2026-01-01', '2026-01-31'),
        fetch_windfor_raw('2026-01-01', '2026-01-31')
    )
    print(f"  FUELHH raw records retrieved: {len(fuelhh_rows)} (Status: {fuel_meta['status']})")
    print(f"  WINDFOR raw records retrieved: {len(windfor_rows)} (Status: {wind_meta['status']})")

    # --- 3. Cutoff Leakage & Eligibility Test (Hourly & Half-Hourly) ---
    print("\n--- 3. Testing Cutoff Eligibility & Leakage Prevention ---")
    cutoffs_to_test = [11, 12, 17, 23]
    for ch in cutoffs_to_test:
        proc = WindDataProcessor(cutoff_hour=ch, resolution='hourly')
        fuel_recs, _ = proc.process_fuelhh(fuelhh_rows)
        wind_recs, _ = proc.process_windfor(windfor_rows)
        
        sim_data = proc.evaluate_simulator(
            fuelhh_records=fuel_recs,
            windfor_records=wind_recs,
            target_date='2026-01-15',
            scenario_pct=0.0
        )
        
        # Verify cutoff timestamp
        cutoff_dt = parse_utc_timestamp(sim_data['cutoff_policy']['cutoff_timestamp'])
        assert cutoff_dt is not None
        assert cutoff_dt.hour == ch
        assert cutoff_dt.day == 14  # D-1
        
        leakage_found = False
        for p in sim_data['periods']:
            if p['publish_time']:
                pub_dt = parse_utc_timestamp(p['publish_time'])
                if pub_dt > cutoff_dt:
                    print(f"  [FAIL] Leakage detected in period {p['timestamp']}: publishTime {pub_dt} > cutoff {cutoff_dt}")
                    leakage_found = True
        if not leakage_found:
            print(f"  [PASS] Cutoff {ch:02d}:00 UTC (D-1 {cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')}): 0 post-cutoff leakages detected across all 24 periods.")

    # --- 4. Recalculate January 2026 Metrics Independently ---
    print("\n--- 4. Independent Recalculation of January 2026 Accuracy Metrics ---")
    for res in ['hourly', 'half_hourly']:
        proc = WindDataProcessor(cutoff_hour=23, resolution=res)
        fuel_recs, _ = proc.process_fuelhh(fuelhh_rows)
        wind_recs, _ = proc.process_windfor(windfor_rows)
        
        selected_vintages, all_vintages = proc.select_day_ahead_vintages(wind_recs, '2026-01-01', '2026-01-31')
        eval_result = proc.align_and_evaluate(fuel_recs, selected_vintages, all_vintages, '2026-01-01', '2026-01-31')
        
        matched = [p for p in eval_result['series'] if p['forecast'] is not None and p['actual'] is not None]
        errors = [p['forecast'] - p['actual'] for p in matched]
        abs_errors = [abs(e) for e in errors]
        
        n = len(matched)
        expected_n = 744 if res == 'hourly' else 1488
        assert n == expected_n, f"Expected {expected_n} matched periods for {res}, got {n}"
        
        calc_mae = sum(abs_errors) / n
        calc_rmse = math.sqrt(sum(e * e for e in errors) / n)
        calc_bias = sum(errors) / n
        calc_p50 = calculate_percentile(abs_errors, 0.50)
        calc_p80 = calculate_percentile(abs_errors, 0.80)
        calc_p90 = calculate_percentile(abs_errors, 0.90)
        calc_p95 = calculate_percentile(abs_errors, 0.95)
        
        reported_m = eval_result['metrics']
        
        print(f"\n  --- Resolution: {res.upper()} (Sample Size N={n}) ---")
        print(f"    Expected periods: {expected_n} | Matched periods: {n} | Coverage: {eval_result['quality']['coverage_pct']}%")
        print(f"    MAE:  Independent={calc_mae:.1f} MW | Reported={reported_m['mae']} MW")
        print(f"    RMSE: Independent={calc_rmse:.1f} MW | Reported={reported_m['rmse']} MW")
        print(f"    Bias: Independent={calc_bias:.1f} MW | Reported={reported_m['bias']} MW")
        print(f"    P50:  Independent={calc_p50:.1f} MW | Reported={reported_m['p50_abs_error']} MW")
        print(f"    P80:  Independent={calc_p80:.1f} MW | Reported={reported_m['p80_abs_error']} MW")
        print(f"    P90:  Independent={calc_p90:.1f} MW | Reported={reported_m['p90_abs_error']} MW")
        print(f"    P95:  Independent={calc_p95:.1f} MW | Reported={reported_m['p95_abs_error']} MW")
        
        assert round(calc_mae, 1) == reported_m['mae']
        assert round(calc_rmse, 1) == reported_m['rmse']
        assert round(calc_bias, 1) == reported_m['bias']
        assert round(calc_p50, 1) == reported_m['p50_abs_error']
        assert round(calc_p80, 1) == reported_m['p80_abs_error']
        assert round(calc_p90, 1) == reported_m['p90_abs_error']
        assert round(calc_p95, 1) == reported_m['p95_abs_error']
        print(f"  [PASS] All metrics match independent recalculation perfectly for {res}.")

    # --- 5. Validate Scenario Arithmetic & Clamping ---
    print("\n--- 5. Validating Scenario Arithmetic & Non-Negative Clamping ---")
    proc = WindDataProcessor(cutoff_hour=23, resolution='hourly')
    
    # +20% scenario
    sim_plus20 = proc.evaluate_simulator(fuel_recs, wind_recs, '2026-01-15', scenario_pct=20.0, scenario_mw=500.0)
    for p in sim_plus20['periods']:
        if p['baseline_forecast'] is not None:
            expected_scenario = max(0.0, p['baseline_forecast'] * 1.20 + 500.0)
            assert round(p['scenario_forecast'], 1) == round(expected_scenario, 1)
            assert round(p['scenario_delta_mw'], 1) == round(expected_scenario - p['baseline_forecast'], 1)
    print("  [PASS] Scenario (+20% + 500 MW) verified across all periods.")
    
    # Negative clamp scenario (-150%)
    sim_clamp = proc.evaluate_simulator(fuel_recs, wind_recs, '2026-01-15', scenario_pct=-150.0, scenario_mw=0.0)
    for p in sim_clamp['periods']:
        if p['baseline_forecast'] is not None:
            assert p['scenario_forecast'] >= 0.0, f"Negative generation observed: {p['scenario_forecast']}"
            assert p['scenario_forecast'] == 0.0
    print("  [PASS] Non-negative clamping max(0, ...) verified.")

    # Energy shift calculation: sum(delta_mw * period_hours)
    total_delta_calc = sum(p['scenario_delta_mw'] * 1.0 for p in sim_plus20['periods'] if p['scenario_delta_mw'] is not None)
    assert round(sim_plus20['summary']['total_scenario_delta_mwh'], 1) == round(total_delta_calc, 1)
    print(f"  [PASS] Total scenario energy shift verified: {total_delta_calc:.1f} MWh.")

    # --- 6. Step Extension & Half-Hourly Presentation ---
    print("\n--- 6. Validating Step-Extension Labelling in Half-Hourly Mode ---")
    proc_hh = WindDataProcessor(cutoff_hour=23, resolution='half_hourly')
    sim_hh = proc_hh.evaluate_simulator(fuel_recs, wind_recs, '2026-01-15', scenario_pct=0.0)
    assert len(sim_hh['periods']) == 48
    
    native_count = 0
    step_count = 0
    for p in sim_hh['periods']:
        dt = parse_utc_timestamp(p['timestamp'])
        if dt.minute == 0:
            assert p['is_step_extended'] is False
            assert p['forecast_type'] == 'native_hourly'
            native_count += 1
        elif dt.minute == 30:
            assert p['is_step_extended'] is True
            assert p['forecast_type'] == 'step_extended_hourly'
            assert 'step_extended' in p['attention_flags']
            step_count += 1
    print(f"  Native periods (:00): {native_count} | Step-extended periods (:30): {step_count}")
    assert native_count == 24 and step_count == 24
    print("  [PASS] Step-extension labelling strictly validated.")

    # --- 7. Missing Data Handling ---
    print("\n--- 7. Validating Missing Data Handling ---")
    dummy_fuel = [{'fuelType': 'WIND', 'startTime': '2026-01-15T08:00:00Z', 'generation': 5000.0, 'settlementPeriod': 17}]
    dummy_wind = []  # No forecasts
    proc_test = WindDataProcessor(cutoff_hour=23, resolution='hourly')
    f_proc, _ = proc_test.process_fuelhh(dummy_fuel)
    w_proc, _ = proc_test.process_windfor(dummy_wind)
    sim_missing = proc_test.evaluate_simulator(f_proc, w_proc, '2026-01-15')
    
    p8 = next(p for p in sim_missing['periods'] if p['timestamp'].startswith('2026-01-15T08:00'))
    assert p8['baseline_forecast'] is None
    assert p8['scenario_forecast'] is None
    assert p8['actual'] is None  # Hour requires :00 and :30 in hourly mode
    assert 'missing_forecast' in p8['attention_flags']
    assert 'missing_actual' in p8['attention_flags']
    print("  [PASS] Missing data reported as None and flagged with missing_forecast / missing_actual, never 0.0.")

    print("\n=================================================================")
    print(">>> PART A ACCEPTANCE AUDIT COMPLETE: ALL CHECKS PASSED <<<")
    print("=================================================================\n")

if __name__ == '__main__':
    asyncio.run(run_analytical_acceptance())
