from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

def add_fill_rate(df):
    if "full" not in df.columns and {"gasInStorage","workingGasVolume"}.issubset(df.columns):
        df["full"] = (df["gasInStorage"]/df["workingGasVolume"]*100).round(2)
    return df

def compute_yoy_table(df, metric="full", years=5):
    df = df.copy(); df.index = pd.to_datetime(df.index)
    current_year = df.index.year.max()
    df = df[df.index.year >= current_year-years][[metric]].copy()
    df["year"] = df.index.year; df["doy"] = df.index.day_of_year
    return df.pivot_table(index="doy", columns="year", values=metric)

def compute_5yr_average(df, metric="full", reference_end_year=None):
    df = df.copy(); df.index = pd.to_datetime(df.index)
    end_year = reference_end_year or (df.index.year.max()-1)
    hist = df[(df.index.year >= end_year-4) & (df.index.year <= end_year)][[metric]]
    hist["doy"] = hist.index.day_of_year
    return hist.groupby("doy")[metric].agg(mean_5yr="mean",min_5yr="min",max_5yr="max").round(2)

def compute_yoy_delta(df, metric="full"):
    df = df.copy(); df.index = pd.to_datetime(df.index)
    avg = compute_5yr_average(df, metric)
    df["doy"] = df.index.day_of_year
    df = df.merge(avg, on="doy", how="left")
    df["delta_vs_5yr_avg"] = (df[metric]-df["mean_5yr"]).round(2)
    return df.drop(columns=["doy"])

def stl_decomposition(df, metric="full", period=365, seasonal=13):
    series = df[metric].dropna()
    if len(series) < period*2:
        raise ValueError(f"Need at least {period*2} obs for STL, got {len(series)}")
    result = STL(series, period=period, seasonal=seasonal, robust=True).fit()
    return {"observed": pd.Series(result.observed, index=series.index),
            "trend":    pd.Series(result.trend,    index=series.index),
            "seasonal": pd.Series(result.seasonal, index=series.index),
            "residual": pd.Series(result.resid,    index=series.index),
            "stl_result": result}

def label_season(date_index):
    months = date_index.month
    season = np.where(months.isin(range(4,10)), "injection", "withdrawal")
    return pd.Series(season, index=date_index, name="season")

def injection_season_summary(df):
    df = df.copy(); df.index = pd.to_datetime(df.index)
    df["season"] = label_season(df.index); df["year"] = df.index.year
    rows = []
    for year in df["year"].unique():
        inj = df[(df["year"]==year)&(df["season"]=="injection")]
        if inj.empty: continue
        rows.append({"year":year,
            "start_fill_pct": inj["full"].iloc[0] if "full" in inj.columns else None,
            "end_fill_pct":   inj["full"].iloc[-1] if "full" in inj.columns else None,
            "peak_fill_pct":  inj["full"].max()    if "full" in inj.columns else None,
            "net_injection_gwh": inj["injection"].sum() if "injection" in inj.columns else None,
            "days": len(inj)})
    summary = pd.DataFrame(rows).set_index("year")
    summary["fill_gain_pct"] = (summary["end_fill_pct"]-summary["start_fill_pct"]).round(2)
    return summary
