"""
Injection & Withdrawal Model
=============================
Functions for analysing and projecting gas storage injection/withdrawal
profiles based on historical data and operational constraints.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd


# ── Seasonal definitions ──────────────────────────────────────────────────────
INJECTION_MONTHS  = list(range(4, 11))   # Apr–Oct inclusive
WITHDRAWAL_MONTHS = [11, 12, 1, 2, 3]   # Nov–Mar


def required_daily_rate(
    start_gwh: float,
    end_gwh: float,
    start_date: date,
    end_date: date,
) -> float:
    """
    Compute the constant daily injection/withdrawal rate needed to go
    from start_gwh to end_gwh between two dates.

    Positive = net injection required.
    Negative = net withdrawal required.
    """
    days = (end_date - start_date).days
    if days <= 0:
        return 0.0
    return (end_gwh - start_gwh) / days


def forced_injection_profile(
    start_date: date,
    end_date: date,
    start_fill_pct: float,
    target_fill_pct: float,
    capacity_gwh: float,
) -> dict:
    """
    Compute the forced injection rate to reach target_fill_pct by end_date.

    Parameters
    ----------
    start_date : date
        Date of analysis (today by default).
    end_date : date
        Target date (e.g. Nov 1).
    start_fill_pct : float
        Current fill rate (%).
    target_fill_pct : float
        Required fill rate at end_date (%).
    capacity_gwh : float
        Total working gas volume capacity (GWh).

    Returns
    -------
    dict with:
        required_daily_gwh  — constant daily injection rate needed
        total_needed_gwh    — total gas to inject
        days                — number of days
        achievable          — True if within physical injection capacity
        gap_pp              — percentage points gap to close
    """
    start_gwh  = start_fill_pct / 100 * capacity_gwh
    target_gwh = target_fill_pct / 100 * capacity_gwh
    gap_gwh    = target_gwh - start_gwh
    days       = (end_date - start_date).days

    required_daily = gap_gwh / days if days > 0 else 0.0

    # EU physical injection capacity ~13,500 GWh/day
    MAX_INJECTION_GWH_DAY = 13_500.0

    return {
        "start_fill_pct":    round(start_fill_pct, 2),
        "target_fill_pct":   round(target_fill_pct, 2),
        "gap_pp":            round(target_fill_pct - start_fill_pct, 2),
        "start_gwh":         round(start_gwh, 0),
        "target_gwh":        round(target_gwh, 0),
        "gap_gwh":           round(gap_gwh, 0),
        "days":              days,
        "required_daily_gwh": round(required_daily, 0),
        "achievable":         required_daily <= MAX_INJECTION_GWH_DAY,
        "max_injection_capacity_gwh": MAX_INJECTION_GWH_DAY,
    }


def project_storage_path(
    start_date: date,
    end_date: date,
    start_gwh: float,
    capacity_gwh: float,
    daily_injection_gwh: float,
    daily_withdrawal_gwh: float,
    injection_months: list = INJECTION_MONTHS,
    withdrawal_months: list = WITHDRAWAL_MONTHS,
) -> pd.Series:
    """
    Project storage level day-by-day from start_date to end_date.

    Parameters
    ----------
    daily_injection_gwh : float
        Net injection rate on active injection days (GWh/day).
    daily_withdrawal_gwh : float
        Net withdrawal rate on active withdrawal days (GWh/day).
    injection_months : list
        Month numbers considered injection season (default: Apr–Oct).
    withdrawal_months : list
        Month numbers considered withdrawal season (default: Nov–Mar).

    Returns
    -------
    pd.Series indexed by date, values in GWh.
    """
    dates   = pd.date_range(start_date, end_date, freq="D")
    storage = [start_gwh]

    for d in dates[1:]:
        prev = storage[-1]
        if d.month in injection_months:
            delta = +daily_injection_gwh
        elif d.month in withdrawal_months:
            delta = -daily_withdrawal_gwh
        else:
            delta = 0.0
        storage.append(max(0.0, min(capacity_gwh, prev + delta)))

    return pd.Series(storage, index=dates, name="storage_gwh")


def historical_comparable_paths(
    df_history: pd.DataFrame,
    start_date: date,
    start_fill_pct: float,
    tolerance_pp: float = 8.0,
    fill_col: str = "full",
) -> pd.DataFrame:
    """
    Find historical years where the fill rate on the same day-of-year
    was within ±tolerance_pp of start_fill_pct.

    Returns a DataFrame with columns:
        year, start_fill, oct1_fill, nov1_fill, apr1_fill, gain_to_nov1
    """
    doy = start_date.timetuple().tm_yday
    df  = df_history.copy()
    df.index = pd.to_datetime(df.index)

    rows = []
    for year in df.index.year.unique():
        yr = df[df.index.year == year]

        # Same DOY
        same_day = yr[yr.index.day_of_year == doy][fill_col]
        if same_day.empty:
            continue
        sf = float(same_day.iloc[0])

        # Skip if too far from current level
        if abs(sf - start_fill_pct) > tolerance_pp:
            continue

        def get_fill_on(month, day, yr_df, next_yr_df=None):
            mask = (yr_df.index.month == month) & (yr_df.index.day == day)
            if mask.any():
                return float(yr_df[mask][fill_col].iloc[0])
            if next_yr_df is not None:
                mask2 = (next_yr_df.index.month == month) & (next_yr_df.index.day == day)
                if mask2.any():
                    return float(next_yr_df[mask2][fill_col].iloc[0])
            return None

        next_yr = df[df.index.year == year + 1]

        oct1_f = get_fill_on(10, 1, yr)
        nov1_f = get_fill_on(11, 1, yr)
        apr1_f = get_fill_on(4,  1, next_yr if not next_yr.empty else yr)

        rows.append({
            "year":         year,
            "start_fill":   round(sf, 1),
            "oct1_fill":    round(oct1_f, 1) if oct1_f else None,
            "nov1_fill":    round(nov1_f, 1) if nov1_f else None,
            "apr1_fill":    round(apr1_f, 1) if apr1_f else None,
            "gain_to_nov1": round(nov1_f - sf, 1) if nov1_f else None,
        })

    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def injection_season_percentiles(
    df_history: pd.DataFrame,
    injection_col: str = "injection",
    injection_months: list = INJECTION_MONTHS,
    min_value: float = 100.0,
) -> dict:
    """
    Compute injection rate percentiles from historical active injection days.

    Parameters
    ----------
    min_value : float
        Minimum injection value to be considered "active" (filter out near-zero).

    Returns
    -------
    dict with P10, P25, P50, P75, P90 in GWh/day.
    """
    s = df_history[injection_col].dropna()
    active = s[
        s.index.month.isin(injection_months) & (s > min_value)
    ]

    return {
        "P10": round(float(active.quantile(0.10)), 0),
        "P25": round(float(active.quantile(0.25)), 0),
        "P50": round(float(active.quantile(0.50)), 0),
        "P75": round(float(active.quantile(0.75)), 0),
        "P90": round(float(active.quantile(0.90)), 0),
        "mean": round(float(active.mean()), 0),
        "n_days": len(active),
    }


def withdrawal_season_percentiles(
    df_history: pd.DataFrame,
    withdrawal_col: str = "withdrawal",
    withdrawal_months: list = WITHDRAWAL_MONTHS,
    min_value: float = 100.0,
) -> dict:
    """
    Compute withdrawal rate percentiles from historical active withdrawal days.
    """
    s = df_history[withdrawal_col].dropna()
    active = s[
        s.index.month.isin(withdrawal_months) & (s > min_value)
    ]

    return {
        "P10": round(float(active.quantile(0.10)), 0),
        "P25": round(float(active.quantile(0.25)), 0),
        "P50": round(float(active.quantile(0.50)), 0),
        "P75": round(float(active.quantile(0.75)), 0),
        "P90": round(float(active.quantile(0.90)), 0),
        "mean": round(float(active.mean()), 0),
        "n_days": len(active),
    }


def min_max_achievable_fill(
    start_date: date,
    end_date: date,
    start_gwh: float,
    capacity_gwh: float,
    inj_percentiles: dict,
    wit_percentiles: dict,
) -> dict:
    """
    Compute the physically achievable fill range at end_date.

    Best case: P90 injection + P10 withdrawal every day.
    Worst case: P10 injection + P90 withdrawal every day.

    Returns
    -------
    dict with: best_fill_pct, worst_fill_pct, median_fill_pct
    """
    scenarios = {
        "best":   (inj_percentiles["P90"], wit_percentiles["P10"]),
        "median": (inj_percentiles["P50"], wit_percentiles["P50"]),
        "worst":  (inj_percentiles["P10"], wit_percentiles["P90"]),
    }

    results = {}
    for name, (inj, wit) in scenarios.items():
        path = project_storage_path(
            start_date, end_date, start_gwh, capacity_gwh, inj, wit
        )
        end_fill = path.iloc[-1] / capacity_gwh * 100
        results[f"{name}_fill_pct"] = round(end_fill, 1)
        results[f"{name}_gwh"]      = round(float(path.iloc[-1]), 0)

    return results
