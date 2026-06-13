from __future__ import annotations
from datetime import date, datetime
from typing import Optional
import numpy as np
import pandas as pd

EU_TARGET_PCT = 90.0
EU_TARGET_DATE = date(datetime.now().year, 11, 1)

def days_to_target(target_date=None):
    today = date.today()
    target = target_date or EU_TARGET_DATE
    if today > target: target = target.replace(year=target.year+1)
    return (target-today).days

def required_daily_injection(current_gwh, capacity_gwh, target_pct=EU_TARGET_PCT, target_date=None):
    target_gwh = capacity_gwh*target_pct/100
    gap_gwh = max(0.0, target_gwh-current_gwh)
    days = days_to_target(target_date)
    required = gap_gwh/days if days>0 else 0.0
    current_pct = current_gwh/capacity_gwh*100 if capacity_gwh>0 else 0.0
    return {"current_fill_pct":round(current_pct,2),"target_fill_pct":target_pct,
            "current_gwh":round(current_gwh,0),"target_gwh":round(target_gwh,0),
            "capacity_gwh":round(capacity_gwh,0),"gap_gwh":round(gap_gwh,0),
            "days_remaining":days,"required_daily_gwh":round(required,0),
            "on_track":current_pct>=target_pct or required<=0}

def compute_pace_vs_history(df, metric="full", target_pct=EU_TARGET_PCT, target_date=None, n_years=5):
    df = df.copy(); df.index = pd.to_datetime(df.index)
    current_year = df.index.year.max()
    target = target_date or date(current_year,11,1)
    target_doy = target.timetuple().tm_yday
    df["doy"] = df.index.day_of_year; df["year"] = df.index.year
    rows = []
    for year in range(current_year-n_years, current_year+1):
        year_df = df[df["year"]==year]
        if year_df.empty: continue
        season = year_df[(year_df["doy"]>=91)&(year_df["doy"]<=304)]
        for _, row in season.iterrows():
            rows.append({"year":year,"doy":row["doy"],"date":row.name,"fill_pct":row[metric]})
    pace_df = pd.DataFrame(rows)
    if pace_df.empty: return pd.DataFrame()
    hist = pace_df[pace_df["year"]<current_year]
    hist_stats = hist.groupby("doy")["fill_pct"].agg(
        hist_mean="mean",hist_p10=lambda x:x.quantile(0.1),hist_p90=lambda x:x.quantile(0.9),
        hist_min="min",hist_max="max")
    current = pace_df[pace_df["year"]==current_year][["doy","date","fill_pct"]].copy()
    current = current.rename(columns={"fill_pct":"actual_pct"})
    if not current.empty:
        current_doy = current["doy"].max()
        current_fill = current[current["doy"]==current_doy]["actual_pct"].values[0]
        remaining_days = target_doy-current_doy
        gap = max(0, target_pct-current_fill)
        daily_required = gap/remaining_days if remaining_days>0 else 0
        future_doys = range(current_doy, target_doy+1)
        req_fills = [current_fill+daily_required*i for i in range(len(future_doys))]
        required_df = pd.DataFrame({"doy":list(future_doys),"required_pct":req_fills})
        current = current.merge(required_df, on="doy", how="outer")
    result = current.merge(hist_stats, on="doy", how="left")
    return result.sort_values("doy").set_index("date")

def pace_status_summary(df, metric="full", target_pct=EU_TARGET_PCT, target_date=None):
    if df.empty or metric not in df.columns: return "No data available."
    latest = df[metric].dropna().iloc[-1]
    current_date = df[metric].dropna().index[-1]
    capacity = df["workingGasVolume"].dropna().iloc[-1] if "workingGasVolume" in df.columns else None
    if capacity:
        result = required_daily_injection(latest*capacity/100, capacity, target_pct, target_date)
        status = "ON TRACK ✅" if result["on_track"] else "BEHIND PACE ⚠️"
        return (f"As of {current_date.date()}: Fill={latest:.1f}% | "
                f"Target={target_pct:.0f}% by {target_date or EU_TARGET_DATE} | "
                f"Required={result['required_daily_gwh']:,.0f} GWh/day | {status}")
    return f"As of {current_date.date()}: Fill={latest:.1f}%"
