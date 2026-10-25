from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import math
import statistics

# Attempt to import pandas and numpy for environments with full native C-extension support (e.g. Linux/Docker container).
# On Windows environments with strict Application Control (WDAC/AppLocker), fallback gracefully to pure Python.
try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except (ImportError, AttributeError, Exception):
    pd = None
    np = None
    HAS_PANDAS = False


def parse_utc_timestamp(val: Any) -> Optional[datetime]:
    """Parses ISO timestamp string or datetime into UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc) if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        s = str(val).strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def parse_numeric(val: Any) -> Optional[float]:
    """Parses value to float, returning None on invalid/missing."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if not math.isnan(f) else None
    except (ValueError, TypeError):
        return None


def calculate_percentile(data: List[float], p: float) -> Optional[float]:
    """
    Computes percentile p (0.0 to 1.0) using standard linear interpolation on sorted data.
    Equivalent to numpy.percentile(data, p * 100, method='linear').
    """
    if not data:
        return None
    s = sorted(data)
    n = len(s)
    if n == 1:
        return float(s[0])
    k = (n - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return float(d0 + d1)


class WindDataProcessor:
    def __init__(self, cutoff_hour: int = 23, resolution: str = 'half_hourly'):
        """
        :param cutoff_hour: Cutoff hour on D-1 in UTC (default 23:00 UTC, configurable application default).
        :param resolution: 'half_hourly' (30-min settlement period) or 'hourly' (aggregated 60-min delivery period).
        """
        self.cutoff_hour = cutoff_hour
        self.resolution = resolution

    def process_fuelhh(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Processes FUELHH raw records, filtering to fuelType=WIND and validating structure.
        Documented policy on duplicate actual timestamps:
        If duplicate actual generation records exist for the exact same startTime,
        the latest published record (by publishTime) is retained, and duplicates are recorded in quality diagnostics.
        """
        duplicate_count = 0
        missing_val_count = 0
        records_by_time: Dict[str, Dict[str, Any]] = {}

        for r in rows:
            fuel = str(r.get('fuelType', '')).upper()
            if fuel != 'WIND':
                continue

            st = parse_utc_timestamp(r.get('startTime'))
            pt = parse_utc_timestamp(r.get('publishTime'))
            gen = parse_numeric(r.get('generation'))
            sp = r.get('settlementPeriod')
            sd = r.get('settlementDate')

            if st is None or gen is None:
                missing_val_count += 1
                continue

            iso_key = st.isoformat()
            if iso_key in records_by_time:
                duplicate_count += 1
                # Retain the one with latest publishTime if available
                existing_pt = records_by_time[iso_key]['publishTime']
                if pt and (existing_pt is None or pt > existing_pt):
                    records_by_time[iso_key] = {
                        'startTime': st,
                        'publishTime': pt,
                        'generation': gen,
                        'settlementPeriod': sp,
                        'settlementDate': sd
                    }
            else:
                records_by_time[iso_key] = {
                    'startTime': st,
                    'publishTime': pt,
                    'generation': gen,
                    'settlementPeriod': sp,
                    'settlementDate': sd
                }

        valid_records = sorted(records_by_time.values(), key=lambda x: x['startTime'])

        quality_meta = {
            'total_raw_rows': len(rows),
            'valid_actual_rows': len(valid_records),
            'duplicate_actual_timestamps': duplicate_count,
            'missing_invalid_actuals': missing_val_count
        }
        return valid_records, quality_meta

    def process_windfor(self, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Processes WINDFOR raw records. Retains all historical forecast versions.
        """
        valid_records = []
        duplicate_pub_count = 0
        missing_val_count = 0
        seen_pairs = set()

        for r in rows:
            st = parse_utc_timestamp(r.get('startTime'))
            pt = parse_utc_timestamp(r.get('publishTime'))
            gen = parse_numeric(r.get('generation'))

            if st is None or pt is None or gen is None:
                missing_val_count += 1
                continue

            pair_key = (st.isoformat(), pt.isoformat())
            if pair_key in seen_pairs:
                duplicate_pub_count += 1
                continue
            seen_pairs.add(pair_key)

            valid_records.append({
                'startTime': st,
                'publishTime': pt,
                'generation': gen
            })

        valid_records.sort(key=lambda x: (x['startTime'], x['publishTime']))

        quality_meta = {
            'total_raw_rows': len(rows),
            'valid_forecast_rows': len(valid_records),
            'duplicate_forecast_publications': duplicate_pub_count,
            'missing_invalid_forecasts': missing_val_count
        }
        return valid_records, quality_meta

    def select_day_ahead_vintages(
        self,
        windfor_records: List[Dict[str, Any]],
        start_date: str,
        end_date: str
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        For every target delivery timestamp T in the evaluation range:
        1. Calculate Cutoff(T): previous calendar day (D-1) at self.cutoff_hour:00:00 UTC.
        2. Identify all eligible forecast publications: publishTime <= Cutoff(T).
        3. Select the latest eligible forecast (max publishTime <= Cutoff(T)).
        4. Retain all historical versions for each target for the Forecast Explorer.
        """
        if not windfor_records:
            return {}, {}

        start_dt = parse_utc_timestamp(f"{start_date}T00:00:00Z")
        end_dt = parse_utc_timestamp(f"{end_date}T23:59:59Z")

        # Group records by target delivery startTime
        grouped_by_target: Dict[str, List[Dict[str, Any]]] = {}
        for row in windfor_records:
            st = row['startTime']
            if start_dt <= st <= end_dt:
                k = st.isoformat()
                if k not in grouped_by_target:
                    grouped_by_target[k] = []
                grouped_by_target[k].append(row)

        selected_vintages: Dict[str, Dict[str, Any]] = {}
        all_vintages_by_target: Dict[str, List[Dict[str, Any]]] = {}

        for target_key, records in grouped_by_target.items():
            target_dt = parse_utc_timestamp(target_key)
            if not target_dt:
                continue

            # Cutoff is D-1 at cutoff_hour:00:00 UTC
            cutoff_dt = datetime(
                target_dt.year, target_dt.month, target_dt.day,
                self.cutoff_hour, 0, 0, tzinfo=timezone.utc
            ) - timedelta(days=1)

            # Sort records by publishTime
            sorted_records = sorted(records, key=lambda x: x['publishTime'])
            version_list = []
            eligible_records = []

            for r in sorted_records:
                p_dt: datetime = r['publishTime']
                is_eligible = p_dt <= cutoff_dt
                if is_eligible:
                    eligible_records.append(r)

                version_list.append({
                    'publish_time': p_dt.isoformat(),
                    'generation': round(float(r['generation']), 1),
                    'is_eligible': is_eligible,
                    'hours_before_delivery': round((target_dt - p_dt).total_seconds() / 3600, 1),
                    'hours_before_cutoff': round((cutoff_dt - p_dt).total_seconds() / 3600, 1)
                })

            all_vintages_by_target[target_key] = version_list

            # Select the latest eligible forecast
            if eligible_records:
                latest_eligible = max(eligible_records, key=lambda x: x['publishTime'])
                p_dt = latest_eligible['publishTime']
                selected_vintages[target_key] = {
                    'timestamp': target_key,
                    'forecast': round(float(latest_eligible['generation']), 1),
                    'publish_time': p_dt.isoformat(),
                    'cutoff_time': cutoff_dt.isoformat(),
                    'hours_before_delivery': round((target_dt - p_dt).total_seconds() / 3600, 1),
                    'total_versions_count': len(version_list),
                    'eligible_versions_count': len(eligible_records)
                }

        return selected_vintages, all_vintages_by_target

    def align_and_evaluate(
        self,
        fuelhh_records: List[Dict[str, Any]],
        selected_vintages: Dict[str, Dict[str, Any]],
        all_vintages: Dict[str, List[Dict[str, Any]]],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Aligns actual generation and selected forecasts by delivery period.

        Resolution Handling:
        1. Hourly resolution:
           - Expected delivery periods: 24 hourly delivery periods per day (744 periods for Jan 2026).
           - Actual generation: Aggregated arithmetic mean of the two corresponding 30-minute FUELHH
             settlement periods (:00 and :30) within the hour: (SP_odd + SP_even) / 2.
           - Forecast generation: Native WINDFOR hourly forecast for delivery hour HH:00.
           - Coverage: Calculated against total expected hourly delivery periods (e.g. 744 for Jan 2026).

        2. Half-hourly resolution:
           - Expected delivery periods: 48 settlement periods per day (1,488 periods for Jan 2026).
           - Actual generation: Native 30-minute FUELHH settlement period observations.
           - Forecast generation: Hourly WINDFOR forecast for HH:00 step-extended to cover HH:30.
             Explicitly labelled with is_step_extended=True and forecast_type='step_extended_hourly'
             so it is never implied to be a separate forecast observation.
        """
        # Parse evaluation bounds
        start_dt = parse_utc_timestamp(f"{start_date}T00:00:00Z")
        end_dt = parse_utc_timestamp(f"{end_date}T23:59:59Z")
        if not start_dt or not end_dt:
            raise ValueError(f"Invalid evaluation date bounds: {start_date} to {end_date}")

        # Index raw half-hourly actual records by ISO timestamp
        half_hour_actuals: Dict[str, Dict[str, Any]] = {}
        for r in fuelhh_records:
            st: datetime = r['startTime']
            half_hour_actuals[st.isoformat()] = {
                'actual': round(float(r['generation']), 1),
                'settlementPeriod': int(r['settlementPeriod']) if r.get('settlementPeriod') is not None else None,
                'settlementDate': str(r['settlementDate']) if r.get('settlementDate') is not None else None,
                'startTime': st
            }

        # Generate canonical expected delivery periods across requested date range
        expected_periods: List[datetime] = []
        cur_day = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0, tzinfo=timezone.utc)
        final_day = datetime(end_dt.year, end_dt.month, end_dt.day, 0, 0, 0, tzinfo=timezone.utc)

        while cur_day <= final_day:
            if self.resolution == 'hourly':
                for h in range(24):
                    expected_periods.append(cur_day.replace(hour=h, minute=0, second=0))
            else:
                for h in range(24):
                    expected_periods.append(cur_day.replace(hour=h, minute=0, second=0))
                    expected_periods.append(cur_day.replace(hour=h, minute=30, second=0))
            cur_day += timedelta(days=1)

        # Include canonical expected timestamps and any out-of-grid timestamps present in datasets within bounds
        eval_timestamps_set = set(expected_periods)
        for t_iso in selected_vintages:
            t_dt = parse_utc_timestamp(t_iso)
            if t_dt and start_dt <= t_dt <= end_dt:
                eval_timestamps_set.add(t_dt)
        if self.resolution == 'half_hourly':
            for t_iso in half_hour_actuals:
                t_dt = parse_utc_timestamp(t_iso)
                if t_dt and start_dt <= t_dt <= end_dt:
                    eval_timestamps_set.add(t_dt)
        else:
            # Hourly: if an actual record is present on the hour, ensure its hourly block is evaluated
            for t_iso in half_hour_actuals:
                t_dt = parse_utc_timestamp(t_iso)
                if t_dt and start_dt <= t_dt <= end_dt:
                    eval_timestamps_set.add(t_dt.replace(minute=0, second=0, microsecond=0))

        filtered_timestamps = sorted(eval_timestamps_set)

        series = []
        matched_records = []
        unmatched_actual_count = 0
        unmatched_forecast_count = 0
        step_extended_count = 0

        for dt in filtered_timestamps:
            t_str = dt.isoformat()

            actual_mw: Optional[float] = None
            sp_display: Optional[int] = None
            forecast_mw: Optional[float] = None
            pub_time: Optional[str] = None
            cutoff_time: Optional[str] = None
            versions_count: int = 0
            is_step_extended: bool = False
            forecast_type: str = 'native_hourly'

            if self.resolution == 'hourly':
                # Hourly Resolution:
                # 1. Actual generation: Arithmetic mean of the two 30-min settlement periods (:00 and :30)
                sp1 = half_hour_actuals.get(t_str)
                sp2 = half_hour_actuals.get((dt + timedelta(minutes=30)).isoformat())

                if sp1 is not None and sp2 is not None:
                    actual_mw = round((sp1['actual'] + sp2['actual']) / 2.0, 1)
                    sp_display = sp1['settlementPeriod']
                elif sp1 is not None and sp2 is None:
                    # Incomplete hour: missing second 30-minute settlement period
                    actual_mw = None
                    sp_display = sp1['settlementPeriod']
                elif sp1 is None and sp2 is not None:
                    # Incomplete hour: missing first 30-minute settlement period
                    actual_mw = None
                    sp_display = sp2['settlementPeriod']
                else:
                    actual_mw = None
                    sp_display = dt.hour * 2 + 1

                # 2. Forecast generation: WINDFOR hourly forecast for this hour
                fc_info = selected_vintages.get(t_str)
                if fc_info:
                    forecast_mw = fc_info['forecast']
                    pub_time = fc_info['publish_time']
                    cutoff_time = fc_info['cutoff_time']
                    versions_count = fc_info.get('total_versions_count', 0)

                is_step_extended = False
                forecast_type = 'native_hourly'

            else:
                # Half-Hourly Resolution:
                # 1. Actual generation: Native FUELHH settlement period observation
                act_info = half_hour_actuals.get(t_str)
                if act_info:
                    actual_mw = act_info['actual']
                    sp_display = act_info['settlementPeriod']
                else:
                    actual_mw = None
                    sp_display = dt.hour * 2 + (1 if dt.minute < 30 else 2)

                # 2. Forecast generation: native at :00, step-extended at :30
                fc_info = selected_vintages.get(t_str)
                if fc_info:
                    forecast_mw = fc_info['forecast']
                    pub_time = fc_info['publish_time']
                    cutoff_time = fc_info['cutoff_time']
                    versions_count = fc_info.get('total_versions_count', 0)
                    is_step_extended = False
                    forecast_type = 'native_hourly'
                elif dt.minute == 30:
                    top_hour_key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
                    fc_info = selected_vintages.get(top_hour_key)
                    if fc_info:
                        forecast_mw = fc_info['forecast']
                        pub_time = fc_info['publish_time']
                        cutoff_time = fc_info['cutoff_time']
                        versions_count = fc_info.get('total_versions_count', 0)
                        is_step_extended = True
                        forecast_type = 'step_extended_hourly'
                        step_extended_count += 1

            error_mw = None
            abs_error_mw = None
            if forecast_mw is not None and actual_mw is not None:
                error_mw = round(forecast_mw - actual_mw, 1)
                abs_error_mw = round(abs(error_mw), 1)
                matched_records.append({
                    'timestamp': t_str,
                    'datetime': dt,
                    'forecast': forecast_mw,
                    'actual': actual_mw,
                    'error': error_mw,
                    'abs_error': abs_error_mw,
                    'publish_time': pub_time,
                    'settlement_period': sp_display,
                    'is_step_extended': is_step_extended,
                    'forecast_type': forecast_type
                })
            elif actual_mw is not None and forecast_mw is None:
                unmatched_actual_count += 1
            elif forecast_mw is not None and actual_mw is None:
                unmatched_forecast_count += 1

            series.append({
                'timestamp': t_str,
                'forecast': forecast_mw,
                'actual': actual_mw,
                'error': error_mw,
                'abs_error': abs_error_mw,
                'publish_time': pub_time,
                'cutoff_time': cutoff_time,
                'settlement_period': sp_display,
                'versions_count': versions_count,
                'is_step_extended': is_step_extended,
                'forecast_type': forecast_type
            })

        metrics = self._calculate_metrics(matched_records)
        daily_summary = self._calculate_daily_summary(matched_records)
        distribution = self._calculate_error_distribution(matched_records)

        total_expected_periods = len(expected_periods)
        matched_count = len(matched_records)
        coverage_pct = round((matched_count / total_expected_periods * 100), 1) if total_expected_periods > 0 else 0.0

        return {
            'status': 'ok',
            'source': 'Elexon BMRS',
            'evaluation_range': {'start_date': start_date, 'end_date': end_date},
            'resolution': self.resolution,
            'cutoff_policy': {
                'hour_utc': self.cutoff_hour,
                'description': f'D-1 {self.cutoff_hour:02d}:00 UTC day-ahead decision cutoff (configurable application default)'
            },
            'forecast_representation': (
                'step_extended_hourly' if self.resolution == 'half_hourly' else 'native_hourly'
            ),
            'forecast_representation_note': (
                'Hourly WINDFOR forecast step-extended to cover both 30-minute settlement periods (:00 and :30). Not separate forecast observations.'
                if self.resolution == 'half_hourly'
                else 'WINDFOR hourly forecast evaluated against the arithmetic mean of the two corresponding 30-minute FUELHH settlement periods.'
            ),
            'sample_count': matched_count,
            'metrics': metrics,
            'daily_summary': daily_summary,
            'distribution': distribution,
            'series': series,
            'quality': {
                'total_expected_periods': total_expected_periods,
                'total_series_periods': len(series),
                'matched': matched_count,
                'unmatched_actual': unmatched_actual_count,
                'unmatched_forecast': unmatched_forecast_count,
                'coverage_pct': coverage_pct,
                'step_extended_periods': step_extended_count
            }
        }

    def _calculate_metrics(self, matched_records: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        """
        Calculates standard power system forecasting KPIs on matched pairs:
        - error = forecast - actual (MW)
        - MAE = mean(abs(error)) (MW)
        - RMSE = sqrt(mean(error^2)) (MW)
        - Bias = mean(forecast - actual) (MW)
        - MedAE = median(abs(error)) (MW)
        - MaxAE = max(abs(error)) (MW)
        - forecast_mean, actual_mean (MW avg)
        """
        if not matched_records:
            return {
                'forecast_mean': None,
                'actual_mean': None,
                'mae': None,
                'rmse': None,
                'bias': None,
                'median_abs_error': None,
                'max_abs_error': None
            }

        # If pandas is available, we can compute via pandas DataFrame
        if HAS_PANDAS and pd is not None:
            df = pd.DataFrame(matched_records)
            errors = df['error']
            abs_errors = df['abs_error']
            mae = float(abs_errors.mean())
            rmse = float(math.sqrt((errors ** 2).mean()))
            bias = float(errors.mean())
            med_ae = float(abs_errors.median())
            max_ae = float(abs_errors.max())
            f_mean = float(df['forecast'].mean())
            a_mean = float(df['actual'].mean())
        else:
            errors = [r['error'] for r in matched_records]
            abs_errors = [r['abs_error'] for r in matched_records]
            forecasts = [r['forecast'] for r in matched_records]
            actuals = [r['actual'] for r in matched_records]

            n = len(matched_records)
            mae = sum(abs_errors) / n
            rmse = math.sqrt(sum(e * e for e in errors) / n)
            bias = sum(errors) / n
            med_ae = statistics.median(abs_errors)
            max_ae = max(abs_errors)
            f_mean = sum(forecasts) / n
            a_mean = sum(actuals) / n

        p50 = calculate_percentile(list(abs_errors), 0.50)
        p80 = calculate_percentile(list(abs_errors), 0.80)
        p90 = calculate_percentile(list(abs_errors), 0.90)
        p95 = calculate_percentile(list(abs_errors), 0.95)

        return {
            'forecast_mean': round(f_mean, 1),
            'actual_mean': round(a_mean, 1),
            'mae': round(mae, 1),
            'rmse': round(rmse, 1),
            'bias': round(bias, 1),
            'median_abs_error': round(med_ae, 1),
            'max_abs_error': round(max_ae, 1),
            'p50_abs_error': round(p50, 1) if p50 is not None else None,
            'p80_abs_error': round(p80, 1) if p80 is not None else None,
            'p90_abs_error': round(p90, 1) if p90 is not None else None,
            'p95_abs_error': round(p95, 1) if p95 is not None else None,
            'sample_size': len(matched_records)
        }

    def _calculate_daily_summary(self, matched_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Groups matched records by day and computes daily summary metrics."""
        if not matched_records:
            return []

        daily_groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in matched_records:
            d_str = r['datetime'].strftime('%Y-%m-%d')
            if d_str not in daily_groups:
                daily_groups[d_str] = []
            daily_groups[d_str].append(r)

        daily_rows = []
        for date_str, group in daily_groups.items():
            n = len(group)
            errs = [r['error'] for r in group]
            abs_errs = [r['abs_error'] for r in group]
            acts = [r['actual'] for r in group]
            fcs = [r['forecast'] for r in group]

            daily_rows.append({
                'date': date_str,
                'sample_count': n,
                'actual_mean': round(sum(acts) / n, 1),
                'forecast_mean': round(sum(fcs) / n, 1),
                'mae': round(sum(abs_errs) / n, 1),
                'rmse': round(math.sqrt(sum(e * e for e in errs) / n), 1),
                'bias': round(sum(errs) / n, 1),
                'max_error': round(max(abs_errs), 1)
            })

        return sorted(daily_rows, key=lambda x: x['date'])

    def _calculate_error_distribution(self, matched_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Computes binned histogram distribution of signed errors (forecast - actual)."""
        if not matched_records:
            return []

        bins = [
            {'range': '< -2000 MW', 'min': None, 'max': -2000.0, 'count': 0},
            {'range': '-2000 to -1000 MW', 'min': -2000.0, 'max': -1000.0, 'count': 0},
            {'range': '-1000 to 0 MW', 'min': -1000.0, 'max': 0.0, 'count': 0},
            {'range': '0 to +1000 MW', 'min': 0.0, 'max': 1000.0, 'count': 0},
            {'range': '+1000 to +2000 MW', 'min': 1000.0, 'max': 2000.0, 'count': 0},
            {'range': '> +2000 MW', 'min': 2000.0, 'max': None, 'count': 0}
        ]

        errors = [r['error'] for r in matched_records]
        total = len(errors)
        for b in bins:
            b_min, b_max = b['min'], b['max']
            if b_min is None and b_max is not None:
                count = sum(1 for e in errors if e < b_max)
            elif b_max is None and b_min is not None:
                count = sum(1 for e in errors if e >= b_min)
            else:
                count = sum(1 for e in errors if b_min <= e < b_max)
            b['count'] = count
            b['percentage'] = round((count / total * 100), 1) if total > 0 else 0.0

        return bins

    def evaluate_simulator(
        self,
        fuelhh_records: List[Dict[str, Any]],
        windfor_records: List[Dict[str, Any]],
        target_date: str,
        scenario_pct: float = 0.0,
        scenario_mw: float = 0.0,
        context_start_date: str = '2026-01-01',
        context_end_date: str = '2026-01-31'
    ) -> Dict[str, Any]:
        """
        Evaluates Day-Ahead Procurement Decision Simulator & Cutoff Replay for target_date.
        Provides:
        - Cutoff-compliant baseline forecast (MW)
        - User-adjustable hypothetical scenario generation (MW) and delta (MW)
        - Replay comparison against actual outturn and post-cutoff vintages
        - Attention heatmap flags (large errors, revisions, step-extension)
        - Empirical historical error percentiles (P50, P80, P90, P95) for context
        - Descriptive disclaimers
        """
        # 1. Target day evaluation
        selected_vintages, all_vintages = self.select_day_ahead_vintages(windfor_records, target_date, target_date)
        day_eval = self.align_and_evaluate(
            fuelhh_records=fuelhh_records,
            selected_vintages=selected_vintages,
            all_vintages=all_vintages,
            start_date=target_date,
            end_date=target_date
        )

        # 2. Context evaluation across broader historical range for empirical percentiles
        context_vintages, _ = self.select_day_ahead_vintages(windfor_records, context_start_date, context_end_date)
        context_eval = self.align_and_evaluate(
            fuelhh_records=fuelhh_records,
            selected_vintages=context_vintages,
            all_vintages={},
            start_date=context_start_date,
            end_date=context_end_date
        )

        context_metrics = context_eval['metrics']
        p50_threshold = context_metrics.get('p50_abs_error') or 1600.0
        p80_threshold = context_metrics.get('p80_abs_error') or 2900.0
        p90_threshold = context_metrics.get('p90_abs_error') or 3800.0
        p95_threshold = context_metrics.get('p95_abs_error') or 4700.0

        # 3. Cutoff metadata & presets
        target_dt = parse_utc_timestamp(f"{target_date}T00:00:00Z")
        cutoff_dt = datetime(target_dt.year, target_dt.month, target_dt.day, self.cutoff_hour, 0, 0, tzinfo=timezone.utc) - timedelta(days=1)

        presets = [
            {
                'hour_utc': 11,
                'label': '11:00 UTC — EPEX SPOT Day-Ahead Auction',
                'description': 'Common British day-ahead exchange order book closure (11:00 UK time).',
                'is_selected': self.cutoff_hour == 11
            },
            {
                'hour_utc': 12,
                'label': '12:00 UTC — Nord Pool Day-Ahead Auction',
                'description': 'Pan-European day-ahead market coupling auction closure (12:00 CET / 11:00-12:00 UK).',
                'is_selected': self.cutoff_hour == 12
            },
            {
                'hour_utc': 17,
                'label': '17:00 UTC — BMRS Day-Ahead Gate',
                'description': 'National Grid ESO operational planning and schedule nomination benchmark.',
                'is_selected': self.cutoff_hour == 17
            },
            {
                'hour_utc': 23,
                'label': '23:00 UTC — Application Default (Midnight Operational)',
                'description': "AetherGrid's configurable default, 1 hour prior to the start of delivery day.",
                'is_selected': self.cutoff_hour == 23
            }
        ]

        # 4. Process each period with scenario adjustments and attention highlights
        enriched_periods = []
        total_scenario_delta_mwh = 0.0
        period_hours = 0.5 if self.resolution == 'half_hourly' else 1.0

        for item in day_eval['series']:
            t_str = item['timestamp']
            dt = parse_utc_timestamp(t_str)

            # Look up all historical versions for this period
            vintages_list = all_vintages.get(t_str)
            if not vintages_list and dt and dt.minute == 30:
                top_hour = dt.replace(minute=0, second=0, microsecond=0).isoformat()
                vintages_list = all_vintages.get(top_hour, [])
            vintages_list = vintages_list or []

            # Baseline forecast
            baseline_mw = item['forecast']

            # Scenario generation
            scenario_mw_val = None
            scenario_delta_val = None
            if baseline_mw is not None:
                # Apply percentage shift and absolute shift
                shifted = (baseline_mw * (1.0 + scenario_pct / 100.0)) + scenario_mw
                scenario_mw_val = round(max(0.0, shifted), 1)
                scenario_delta_val = round(scenario_mw_val - baseline_mw, 1)
                total_scenario_delta_mwh += scenario_delta_val * period_hours

            # Actual outturn & errors
            actual_mw = item['actual']
            baseline_error = item['error']
            scenario_error = round(scenario_mw_val - actual_mw, 1) if (scenario_mw_val is not None and actual_mw is not None) else None
            abs_error = abs(baseline_error) if baseline_error is not None else None

            # Lookahead analysis: find latest post-cutoff vintage
            post_cutoff_vintages = [v for v in vintages_list if not v.get('is_eligible', True)]
            latest_post_cutoff = None
            lookahead_delta = None
            if post_cutoff_vintages:
                latest_v = max(post_cutoff_vintages, key=lambda v: parse_utc_timestamp(v['publish_time']) or datetime.min.replace(tzinfo=timezone.utc))
                latest_post_cutoff = {
                    'publish_time': latest_v['publish_time'],
                    'generation': latest_v['generation'],
                    'hours_before_delivery': latest_v['hours_before_delivery']
                }
                if baseline_mw is not None:
                    lookahead_delta = round(latest_v['generation'] - baseline_mw, 1)

            # Revision volatility analysis across all publications
            revisions_count = len(vintages_list)
            max_revision_mw = 0.0
            if len(vintages_list) >= 2:
                sorted_v = sorted(vintages_list, key=lambda v: parse_utc_timestamp(v['publish_time']) or datetime.min.replace(tzinfo=timezone.utc))
                for i in range(1, len(sorted_v)):
                    step_rev = abs(sorted_v[i]['generation'] - sorted_v[i-1]['generation'])
                    if step_rev > max_revision_mw:
                        max_revision_mw = round(step_rev, 1)

            # Attention highlights
            attention_flags = []
            attention_reasons = []

            if abs_error is not None:
                if abs_error >= p90_threshold:
                    attention_flags.append('severe_error')
                    attention_reasons.append(f"Severe error: {abs_error:.0f} MW error exceeds P90 threshold ({p90_threshold:.0f} MW)")
                elif abs_error >= p80_threshold:
                    attention_flags.append('high_error')
                    attention_reasons.append(f"High error: {abs_error:.0f} MW error exceeds P80 threshold ({p80_threshold:.0f} MW)")

            if max_revision_mw >= 1000.0:
                attention_flags.append('large_revision')
                attention_reasons.append(f"Large forecast revision: {max_revision_mw:.0f} MW maximum jump between published vintages")

            if lookahead_delta is not None and abs(lookahead_delta) >= 500.0:
                attention_flags.append('lookahead_shift')
                attention_reasons.append(f"Intraday revision shift: Later forecast changed by {lookahead_delta:+.0f} MW relative to cutoff baseline")

            if item.get('is_step_extended'):
                attention_flags.append('step_extended')
                attention_reasons.append("Step-extended forecast: Extended from top-of-hour WINDFOR block; not an independent observation")

            if actual_mw is None:
                attention_flags.append('missing_actual')
                attention_reasons.append("Missing actual generation outturn")
            if baseline_mw is None:
                attention_flags.append('missing_forecast')
                attention_reasons.append("Missing cutoff-compliant forecast")

            enriched_periods.append({
                'timestamp': t_str,
                'settlement_period': item.get('settlement_period'),
                'baseline_forecast': baseline_mw,
                'scenario_forecast': scenario_mw_val,
                'scenario_delta_mw': scenario_delta_val,
                'actual': actual_mw,
                'error_mw': baseline_error,
                'scenario_error_mw': scenario_error,
                'abs_error_mw': abs_error,
                'publish_time': item.get('publish_time'),
                'cutoff_time': item.get('cutoff_time') or cutoff_dt.isoformat(),
                'is_step_extended': item.get('is_step_extended', False),
                'forecast_type': item.get('forecast_type', 'native_hourly'),
                'historical_versions_count': revisions_count,
                'historical_versions': vintages_list,
                'latest_post_cutoff': latest_post_cutoff,
                'lookahead_delta_mw': lookahead_delta,
                'max_revision_mw': max_revision_mw,
                'attention_flags': attention_flags,
                'attention_reason': '; '.join(attention_reasons) if attention_reasons else 'Normal variance within baseline thresholds'
            })

        # Summary metrics
        baseline_fcs = [p['baseline_forecast'] for p in enriched_periods if p['baseline_forecast'] is not None]
        scenario_fcs = [p['scenario_forecast'] for p in enriched_periods if p['scenario_forecast'] is not None]
        actuals_list = [p['actual'] for p in enriched_periods if p['actual'] is not None]
        baseline_maes = [p['abs_error_mw'] for p in enriched_periods if p['abs_error_mw'] is not None]
        scenario_maes = [abs(p['scenario_error_mw']) for p in enriched_periods if p['scenario_error_mw'] is not None]

        return {
            'status': 'ok',
            'date': target_date,
            'resolution': self.resolution,
            'cutoff_policy': {
                'hour_utc': self.cutoff_hour,
                'cutoff_timestamp': cutoff_dt.isoformat(),
                'description': f'Evaluated using latest forecast published on or before D-1 ({cutoff_dt.strftime("%d %b %Y")}) at {self.cutoff_hour:02d}:00 UTC (configurable application default).',
                'presets': presets
            },
            'scenario_config': {
                'scenario_pct': scenario_pct,
                'scenario_mw': scenario_mw,
                'total_delta_mwh': round(total_scenario_delta_mwh, 1),
                'description': f'User-configured stress scenario ({scenario_pct:+.1f}% percentage adjustment, {scenario_mw:+.1f} MW shift).',
                'note': 'Hypothetical user-defined stress scenario; NOT an official Elexon forecast observation.'
            },
            'summary': {
                'periods_count': len(enriched_periods),
                'matched_count': day_eval['sample_count'],
                'coverage_pct': day_eval['quality']['coverage_pct'],
                'baseline_mean_mw': round(sum(baseline_fcs) / len(baseline_fcs), 1) if baseline_fcs else None,
                'scenario_mean_mw': round(sum(scenario_fcs) / len(scenario_fcs), 1) if scenario_fcs else None,
                'actual_mean_mw': round(sum(actuals_list) / len(actuals_list), 1) if actuals_list else None,
                'baseline_mae': round(sum(baseline_maes) / len(baseline_maes), 1) if baseline_maes else None,
                'scenario_mae': round(sum(scenario_maes) / len(scenario_maes), 1) if scenario_maes else None,
                'total_scenario_delta_mwh': round(total_scenario_delta_mwh, 1)
            },
            'uncertainty_context': {
                'sample_size': context_metrics.get('sample_size', 0),
                'evaluation_range': {'start_date': context_start_date, 'end_date': context_end_date},
                'resolution': self.resolution,
                'p50_mw': context_metrics.get('p50_abs_error'),
                'p80_mw': context_metrics.get('p80_abs_error'),
                'p90_mw': context_metrics.get('p90_abs_error'),
                'p95_mw': context_metrics.get('p95_abs_error'),
                'mae_mw': context_metrics.get('mae'),
                'rmse_mw': context_metrics.get('rmse'),
                'bias_mw': context_metrics.get('bias'),
                'methodology': 'Empirical absolute forecast error percentiles (|Forecast - Actual|) calculated across cutoff-eligible historical records in the evaluation period.',
                'disclaimer': f'Historical {context_start_date[:7]} empirical error percentiles for analytical context. These reflect observed winter volatility and are NOT forward-looking calibrated prediction intervals or guarantees.'
            },
            'periods': enriched_periods,
            'disclaimers': [
                "National wind generation values represent Great Britain transmission-connected and embedded wind outturn/forecasts from Elexon BMRS (FUELHH and WINDFOR).",
                "This simulator does NOT calculate a utility’s net procurement volume. Customer load demand, bilateral hedges, retail contracts, and other generation assets are excluded.",
                "Scenario adjustments are purely hypothetical analytical stress tests and must not be described as new or alternative Elexon forecasts."
            ]
        }

