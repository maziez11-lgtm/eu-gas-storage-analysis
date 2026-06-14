"""TTF flat price analysis: volatility, distribution, seasonality, regimes."""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd


def rolling_volatility(series: pd.Series, windows: list[int] = [5, 21, 63]) -> pd.DataFrame:
    """
    Annualised rolling volatility for each window.

    Parameters
    ----------
    series : pd.Series
        Daily price series (e.g. TTF M1 close).
    windows : list[int]
        Rolling windows in trading days.

    Returns
    -------
    DataFrame with columns like ``vol_5d``, ``vol_21d``, ``vol_63d`` (%).
    """
    log_ret = np.log(series / series.shift(1))
    result = pd.DataFrame(index=series.index)
    for w in windows:
        result[f"vol_{w}d"] = log_ret.rolling(w).std() * np.sqrt(252) * 100
    return result


def garch_volatility(series: pd.Series) -> pd.DataFrame:
    """
    Fit GARCH(1,1) to daily log-returns and return conditional volatility.

    Requires the ``arch`` package.

    Returns
    -------
    DataFrame with columns: ``log_ret``, ``cond_vol`` (annualised %).
    """
    try:
        from arch import arch_model
    except ImportError as exc:
        raise ImportError("Install arch: pip install arch") from exc

    log_ret = (np.log(series / series.shift(1)).dropna() * 100)
    am = arch_model(log_ret, vol="Garch", p=1, q=1, dist="normal", rescale=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = am.fit(disp="off")
    cond_vol = res.conditional_volatility * np.sqrt(252)
    df = pd.DataFrame({"log_ret": log_ret, "cond_vol": cond_vol}, index=log_ret.index)
    return df


def price_distribution_by_fill(
    ttf_df: pd.DataFrame,
    storage_df: pd.DataFrame,
    price_col: str = "M1",
    fill_col: str = "full",
    n_buckets: int = 5,
) -> pd.DataFrame:
    """
    Compute price statistics grouped by fill-rate buckets.

    Parameters
    ----------
    ttf_df : pd.DataFrame
        TTF forward curve data (DatetimeIndex, column ``price_col``).
    storage_df : pd.DataFrame
        Storage data (DatetimeIndex, column ``fill_col`` in %).
    n_buckets : int
        Number of equally-spaced fill buckets.

    Returns
    -------
    DataFrame indexed by fill bucket (IntervalIndex) with stats:
    count, mean, median, std, p10, p25, p75, p90, min, max.
    Also includes a ``bucket_label`` column.
    """
    prices = ttf_df[[price_col]].copy()
    fills = storage_df[[fill_col]].copy()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    fills.index = pd.to_datetime(fills.index).tz_localize(None)
    merged = prices.join(fills, how="inner").dropna()

    merged["bucket"] = pd.cut(merged[fill_col], bins=n_buckets)
    grp = merged.groupby("bucket", observed=True)[price_col]
    stats = grp.agg(
        count="count",
        mean="mean",
        median="median",
        std="std",
        p10=lambda x: x.quantile(0.10),
        p25=lambda x: x.quantile(0.25),
        p75=lambda x: x.quantile(0.75),
        p90=lambda x: x.quantile(0.90),
        min="min",
        max="max",
    )
    stats["bucket_label"] = [
        f"{iv.left:.0f}–{iv.right:.0f}%" for iv in stats.index
    ]
    return stats


def seasonal_price_pattern(
    ttf_df: pd.DataFrame,
    col: str = "M1",
) -> dict[str, pd.DataFrame]:
    """
    Average price by calendar dimension.

    Returns
    -------
    dict with keys:
      - ``by_month``        : avg price per calendar month (1-12)
      - ``by_day_of_week``  : avg price per weekday (0=Mon … 6=Sun)
      - ``by_week_of_year`` : avg price per ISO week (1-53)
    """
    s = ttf_df[col].dropna()
    idx = s.index

    by_month = s.groupby(idx.month).mean().rename_axis("month")
    by_dow = s.groupby(idx.day_of_week).mean().rename_axis("day_of_week")
    by_woy = s.groupby(idx.isocalendar().week.values).mean()
    by_woy.index.name = "week_of_year"

    return {
        "by_month": by_month.to_frame(name="avg_price"),
        "by_day_of_week": by_dow.to_frame(name="avg_price"),
        "by_week_of_year": by_woy.to_frame(name="avg_price"),
    }


def price_regime_detection(
    ttf_df: pd.DataFrame,
    col: str = "M1",
    n_regimes: int = 3,
) -> pd.DataFrame:
    """
    Detect price regimes with a Gaussian HMM.

    Requires the ``hmmlearn`` package.

    Parameters
    ----------
    n_regimes : int
        Number of hidden states (regimes).

    Returns
    -------
    DataFrame with columns: ``price``, ``log_ret``, ``regime`` (0..n_regimes-1),
    ``regime_label`` (Low / Medium / High sorted by mean price in each state).
    """
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError as exc:
        raise ImportError("Install hmmlearn: pip install hmmlearn") from exc

    s = ttf_df[col].dropna()
    log_ret = np.log(s / s.shift(1)).dropna()

    X = log_ret.values.reshape(-1, 1)
    model = GaussianHMM(
        n_components=n_regimes,
        covariance_type="full",
        n_iter=200,
        random_state=42,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X)

    raw_labels = model.predict(X)

    # Sort states by mean price so labels are consistent
    state_means = {
        i: float(s.loc[log_ret.index[raw_labels == i]].mean())
        for i in range(n_regimes)
    }
    rank = sorted(state_means, key=state_means.get)
    label_names = {rank[i]: i for i in range(n_regimes)}

    _NAMES = ["Low", "Medium", "High", "Very High", "Extreme"]
    df = pd.DataFrame(
        {
            "price": s.loc[log_ret.index],
            "log_ret": log_ret,
            "regime": [label_names[r] for r in raw_labels],
        }
    )
    df["regime_label"] = df["regime"].map(
        {i: _NAMES[i] for i in range(n_regimes)}
    )
    return df
