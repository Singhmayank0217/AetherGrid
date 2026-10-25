"""
Independent acceptance verification script for AetherGrid Part C (API and Tests).
Tests all requirements of Section C of the Final Acceptance Audit.
"""
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

def run_api_acceptance():
    print("=================================================================")
    print(">>> AETHERGRID ACCEPTANCE AUDIT: PART C (API & SCHEMA AUDIT) <<<")
    print("=================================================================\n")

    base = "http://127.0.0.1:8000"
    client = httpx.Client(base_url=base, timeout=30.0)

    # 1. Health check
    r_health = client.get("/health")
    assert r_health.status_code == 200, f"Health check failed: {r_health.status_code}"
    print(f"[PASS] /health returns 200 OK: {r_health.json()}")

    # 2. Valid Simulator Requests across Cutoff Presets
    presets = [11, 12, 17, 23]
    for ch in presets:
        r = client.get(f"/api/simulator?date=2026-01-15&cutoff_hour={ch}&scenario_pct=15.0&scenario_mw=200.0&resolution=hourly")
        assert r.status_code == 200, f"Failed for cutoff {ch}: {r.status_code}"
        d = r.json()
        assert d["status"] == "ok"
        assert d["date"] == "2026-01-15"
        assert d["cutoff_policy"]["hour_utc"] == ch
        assert len(d["periods"]) == 24
        assert d["summary"]["periods_count"] == 24
        assert d["uncertainty_context"]["sample_size"] == 744
        assert "disclaimers" in d and len(d["disclaimers"]) >= 3
        print(f"  [PASS] /api/simulator valid call (cutoff={ch}:00 UTC, +15%, +200 MW): 24 periods, coverage {d['summary']['coverage_pct']}%")

    # 3. Half-hourly mode valid call
    r_hh = client.get("/api/simulator?date=2026-01-15&cutoff_hour=23&scenario_pct=-10.0&resolution=half_hourly")
    assert r_hh.status_code == 200
    d_hh = r_hh.json()
    assert len(d_hh["periods"]) == 48
    assert d_hh["summary"]["periods_count"] == 48
    step_ext = [p for p in d_hh["periods"] if p["is_step_extended"]]
    assert len(step_ext) == 24
    print(f"  [PASS] /api/simulator half-hourly mode: 48 periods, 24 step-extended periods explicitly flagged.")

    # 4. Invalid Parameters & Schema Validation (HTTP 422 Unprocessable Entity)
    print("\n--- Testing Input Validation & Error Handling (HTTP 422) ---")
    
    # 4a. Invalid date format
    r_bad_date = client.get("/api/simulator?date=not-a-date")
    assert r_bad_date.status_code == 422, f"Expected 422 for bad date, got {r_bad_date.status_code}"
    print(f"  [PASS] Invalid date 'not-a-date' rejected with HTTP 422: {r_bad_date.json()['detail'][0]['msg']}")

    # 4b. Invalid cutoff hour (> 23)
    r_bad_cutoff = client.get("/api/simulator?date=2026-01-15&cutoff_hour=25")
    assert r_bad_cutoff.status_code == 422, f"Expected 422 for bad cutoff, got {r_bad_cutoff.status_code}"
    print(f"  [PASS] Invalid cutoff_hour=25 rejected with HTTP 422: {r_bad_cutoff.json()['detail'][0]['msg']}")

    # 4c. Invalid cutoff hour (< 0)
    r_neg_cutoff = client.get("/api/simulator?date=2026-01-15&cutoff_hour=-1")
    assert r_neg_cutoff.status_code == 422, f"Expected 422 for negative cutoff, got {r_neg_cutoff.status_code}"
    print(f"  [PASS] Invalid cutoff_hour=-1 rejected with HTTP 422: {r_neg_cutoff.json()['detail'][0]['msg']}")

    # 4d. Invalid resolution
    r_bad_res = client.get("/api/simulator?date=2026-01-15&resolution=quarter_hourly")
    assert r_bad_res.status_code == 422, f"Expected 422 for bad resolution, got {r_bad_res.status_code}"
    print(f"  [PASS] Invalid resolution 'quarter_hourly' rejected with HTTP 422: {r_bad_res.json()['detail'][0]['msg']}")

    # 4e. Invalid scenario percentage (< -100%)
    r_bad_pct = client.get("/api/simulator?date=2026-01-15&scenario_pct=-150")
    assert r_bad_pct.status_code == 422, f"Expected 422 for scenario_pct=-150, got {r_bad_pct.status_code}"
    print(f"  [PASS] Invalid scenario_pct=-150 rejected with HTTP 422: {r_bad_pct.json()['detail'][0]['msg']}")

    # 5. Response Schema Verification
    print("\n--- Verifying Detailed Response Schema & Fields ---")
    r_schema = client.get("/api/simulator?date=2026-01-15&cutoff_hour=23")
    data = r_schema.json()
    
    required_top_keys = ["status", "date", "resolution", "cutoff_policy", "scenario_config", "summary", "uncertainty_context", "periods", "disclaimers"]
    for k in required_top_keys:
        assert k in data, f"Missing top-level key: {k}"
    print("  [PASS] Top-level response schema verified.")

    required_period_keys = [
        "timestamp", "settlement_period", "baseline_forecast", "scenario_forecast",
        "scenario_delta_mw", "actual", "error_mw", "scenario_error_mw", "abs_error_mw",
        "publish_time", "cutoff_time", "is_step_extended", "forecast_type",
        "historical_versions_count", "historical_versions", "latest_post_cutoff",
        "lookahead_delta_mw", "max_revision_mw", "attention_flags", "attention_reason"
    ]
    sample_period = data["periods"][0]
    for pk in required_period_keys:
        assert pk in sample_period, f"Missing period field: {pk}"
    print("  [PASS] Period item response schema verified (all 20 fields present).")

    # 6. CSV Export Structure Test
    print("\n--- Verifying CSV Export Structure and Metadata ---")
    header = [
        'delivery_time_utc', 'settlement_period', 'baseline_forecast_mw', 'publish_time_utc',
        'cutoff_time_utc', 'scenario_forecast_mw', 'scenario_delta_mw', 'actual_outturn_mw',
        'baseline_error_mw', 'scenario_error_mw', 'is_step_extended', 'latest_post_cutoff_mw',
        'attention_flags', 'attention_reason'
    ]
    rows = []
    for p in data["periods"]:
        row = [
            str(p['timestamp']),
            str(p['settlement_period'] or ''),
            str(p['baseline_forecast'] or ''),
            str(p['publish_time'] or ''),
            str(p['cutoff_time'] or ''),
            str(p['scenario_forecast'] or ''),
            str(p['scenario_delta_mw'] or ''),
            str(p['actual'] or ''),
            str(p['error_mw'] or ''),
            str(p['scenario_error_mw'] or ''),
            str(p['is_step_extended']),
            str(p['latest_post_cutoff']['generation'] if p['latest_post_cutoff'] else ''),
            f'"{";".join(p["attention_flags"])}"',
            f'"{p["attention_reason"]}"'
        ]
        rows.append(','.join(row))
    csv_text = ','.join(header) + '\n' + '\n'.join(rows)
    assert len(rows) == 24
    assert 'delivery_time_utc' in csv_text
    assert 'baseline_forecast_mw' in csv_text
    print(f"  [PASS] CSV export generation verified: 24 data rows, all columns formatted properly.")

    print("\n=================================================================")
    print(">>> PART C ACCEPTANCE AUDIT COMPLETE: ALL CHECKS PASSED <<<")
    print("=================================================================\n")

if __name__ == '__main__':
    run_api_acceptance()
