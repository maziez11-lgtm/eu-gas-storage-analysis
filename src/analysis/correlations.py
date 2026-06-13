from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd
from scipy import stats

def merge_storage_price(storage_df, price_df, storage_col="full", price_col="ttf_front"):
    return storage_df[[storage_col]].join(price_df[[price_col]], how="inner").dropna()

def rolling_correlation(df, x_col, y_col, windows=[30,60,90]):
    result = pd.DataFrame(index=df.index)
    for w in windows:
        result[f"corr_{w}d"] = df[x_col].rolling(w).corr(df[y_col])
    return result

def storage_price_regression(df, x_col="full", y_col="ttf_front", log_price=True):
    df = df[[x_col,y_col]].dropna()
    x = df[x_col].values
    y = np.log(df[y_col].values) if log_price else df[y_col].values
    slope,intercept,r_value,p_value,std_err = stats.linregress(x,y)
    y_pred = np.exp(slope*x+intercept) if log_price else slope*x+intercept
    return {"slope":round(slope,4),"intercept":round(intercept,4),"r_squared":round(r_value**2,4),
            "p_value":round(p_value,6),"std_err":round(std_err,4),"log_form":log_price,
            "n_obs":len(df),"regression_line":pd.Series(y_pred,index=df.index,name="predicted"),
            "interpretation":(f"A 1pp increase in fill = {abs(slope)*100:.1f}% {'decrease' if slope<0 else 'increase'} in TTF (R²={r_value**2:.2f})"
                              if log_price else f"A 1pp increase in fill = €{abs(slope):.2f}/MWh change in TTF (R²={r_value**2:.2f})")}

def detect_regime(df, price_col="ttf_front", spread_col=None):
    df = df.copy()
    if spread_col and spread_col in df.columns:
        df["regime"] = np.where(df[spread_col]>0,"contango","backwardation")
    else:
        rolling_mean = df[price_col].rolling(252).mean()
        df["regime"] = np.where(df[price_col]>rolling_mean*1.5,"stress",
                        np.where(df[price_col]>rolling_mean,"tight","normal"))
    return df

def storage_surprise_impact(storage_df, price_df, storage_col="gasInStorage", price_col="ttf_front", window=5):
    df = storage_df[[storage_col]].copy()
    df = df.join(price_df[[price_col]], how="inner").dropna()
    df["storage_wow"] = df[storage_col].diff(7)
    df["surprise"] = df["storage_wow"]
    df["price_change_1d"] = df[price_col].pct_change(1)*100
    df["price_change_5d"] = df[price_col].pct_change(5)*100
    return df[["storage_wow","surprise","price_change_1d","price_change_5d"]].dropna()
