"""TTF calendar spread analysis: spread matrix, roll yield, regimes, seasonality."""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_spread_matrix(ttf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build all M_n – M_m spreads for every date.

    Columns follow the convention ``M{n}_M{m}`` (e.g. ``M1_M2``, ``M1_M6``).

    Parameters
    ----------
    ttf_df : pd.DataFrame
        TTF forward curve with columns ``M1`` … ``M12`` (or however many exist).

    Returns
    -------
    DataFrame indexed by date, one column per spread pair.
    """
    month_cols = [c for c in ttf_df.columns if c.startswith("M") and c[1:].isdigit()]
    month_cols = sorted(month_cols, key=lambda x: int(x[1:]))

    rows = []
    for n_col in month_cols:
        n = int(n_col[1:])
        for m_col in month_cols:
            m = int(m_col[1:])
            if m <= n:
                continue
            spread_name = f"{n_col}_{m_col}"
            rows.append(
                (ttf_df[n_col] - ttf_df[m_col]).rename(spread_name)
            )
    if not rows:
        return pd.DataFrame(index=ttf_df.index)
    return pd.concat(rows, axis=1)


def roll_yield(ttf_df: pd.DataFrame, holding_days: int = 30) -> pd.DataFrame:
    """
    Annualised roll yield for each front contract month.

    Roll yield ≈ (M1 – M2) / M1 × (252 / holding_days) × 100  (%)

    Parameters
    ----------
    holding_days : int
        Assumed holding period in calendar days before rolling.

    Returns
    -------
    DataFrame indexed by date with column ``roll_yield_pct``.
    Positive = backwardation (roll benefit), negative = contango (roll cost).
    """
    if "M1" not in ttf_df.columns or "M2" not in ttf_df.columns:
        raise KeyError("ttf_df must contain at least M1 and M2 columns.")

    ry = (
        (ttf_df["M1"] - ttf_df["M2"]) / ttf_df["M1"]
        * (252 / holding_days)
        * 100
    )
    return ry.dropna().to_frame(name="roll_yield_pct")


def spread_regime(
    ttf_df: pd.DataFrame,
    storage_df: pd.DataFrame,
    fill_col: str = "full",
    flat_threshold: float = 0.15,
) -> pd.DataFrame:
    """
    Label each date as contango / backwardation / flat based on M1–M2 spread,
    and attach the current storage fill rate.

    Parameters
    ----------
    flat_threshold : float
        Absolute spread (€/MWh) within which the market is considered "flat".

    Returns
    -------
    DataFrame with columns: ``M1``, ``M2``, ``spread``, ``fill``, ``regime``.
    """
    if "M1" not in ttf_df.columns or "M2" not in ttf_df.columns:
        raise KeyError("ttf_df must contain at least M1 and M2 columns.")

    df = ttf_df[["M1", "M2"]].copy()
    df["spread"] = df["M1"] - df["M2"]
    df = df.join(storage_df[[fill_col]].rename(columns={fill_col: "fill"}), how="inner")
    df = df.dropna()

    def _label(s: float) -> str:
        if abs(s) <= flat_threshold:
            return "flat"
        return "backwardation" if s > 0 else "contango"

    df["regime"] = df["spread"].map(_label)
    return df


def contango_duration(ttf_df: pd.DataFrame, flat_threshold: float = 0.15) -> pd.DataFrame:
    """
    Identify and measure consecutive streak lengths in each regime.

    Parameters
    ----------
    flat_threshold : float
        Same threshold as in ``spread_regime``.

    Returns
    -------
    DataFrame with columns: ``start``, ``end``, ``regime``, ``days``.
    """
    if "M1" not in ttf_df.columns or "M2" not in ttf_df.columns:
        raise KeyError("ttf_df must contain at least M1 and M2 columns.")

    spread = (ttf_df["M1"] - ttf_df["M2"]).dropna()

    def _label(s: float) -> str:
        if abs(s) <= flat_threshold:
            return "flat"
        return "backwardation" if s > 0 else "contango"

    labels = spread.map(_label)
    streaks = []
    current_regime = labels.iloc[0]
    streak_start = labels.index[0]

    for dt, regime in labels.iloc[1:].items():
        if regime != current_regime:
            streaks.append(
                {
                    "start": streak_start,
                    "end": dt,
                    "regime": current_regime,
                    "days": (dt - streak_start).days,
                }
            )
            current_regime = regime
            streak_start = dt

    # Close final streak
    streaks.append(
        {
            "start": streak_start,
            "end": labels.index[-1],
            "regime": current_regime,
            "days": (labels.index[-1] - streak_start).days,
        }
    )
    return pd.DataFrame(streaks)


def spread_seasonality(ttf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Average spreads (M1-M3, M1-M6) by calendar month.

    Returns
    -------
    DataFrame indexed by month (1-12) with columns ``M1_M3`` and ``M1_M6``.
    """
    result = pd.DataFrame(index=range(1, 13))
    result.index.name = "month"

    for near, far in [("M1", "M3"), ("M1", "M6")]:
        if near in ttf_df.columns and far in ttf_df.columns:
            spread = ttf_df[near] - ttf_df[far]
            result[f"{near}_{far}"] = spread.groupby(spread.index.month).mean()

    return result.dropna(how="all")
