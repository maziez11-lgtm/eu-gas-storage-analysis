from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

@dataclass
class WinterScenario:
    name: str; label: str; avg_daily_withdrawal_gwh: float
    winter_days: int=151; cold_spell_days: int=0
    cold_spell_multiplier: float=1.5; color: str="blue"

SCENARIOS = {
    "mild":    WinterScenario("mild",   "Mild Winter",           4500, color="green"),
    "normal":  WinterScenario("normal", "Normal Winter",         6000, color="blue"),
    "cold":    WinterScenario("cold",   "Cold Winter",           7500, cold_spell_days=14, cold_spell_multiplier=1.8, color="orange"),
    "extreme": WinterScenario("extreme","Extreme Winter (2021)", 9000, cold_spell_days=21, cold_spell_multiplier=2.0, color="red"),
}

def run_depletion_model(storage_start_gwh, scenario, lng_daily_gwh=400.0, pipeline_daily_gwh=800.0):
    daily_supply = lng_daily_gwh+pipeline_daily_gwh
    daily_net = scenario.avg_daily_withdrawal_gwh-daily_supply
    days=[]
    storage=storage_start_gwh
    for day in range(1, scenario.winter_days+1):
        net = daily_net*scenario.cold_spell_multiplier if day<=scenario.cold_spell_days else daily_net
        storage = max(0.0, storage-net)
        days.append({"day":day,"storage_gwh":round(storage,0),"daily_net_withdrawal":round(net,0),"depleted":storage<=0})
    return pd.DataFrame(days).set_index("day")

def adequacy_summary(current_gwh, capacity_gwh, scenarios=None, lng_daily_gwh=400.0, pipeline_daily_gwh=800.0):
    scenarios = scenarios or SCENARIOS
    rows=[]
    for key, scenario in scenarios.items():
        result = run_depletion_model(current_gwh, scenario, lng_daily_gwh, pipeline_daily_gwh)
        end_gwh = result["storage_gwh"].iloc[-1]
        depleted_day = result[result["depleted"]].index.min() if result["depleted"].any() else None
        daily_supply=lng_daily_gwh+pipeline_daily_gwh
        dos=(current_gwh/(scenario.avg_daily_withdrawal_gwh-daily_supply)
             if scenario.avg_daily_withdrawal_gwh>daily_supply else float("inf"))
        rows.append({"scenario":scenario.label,
            "start_fill_pct":round(current_gwh/capacity_gwh*100,1),
            "end_gwh":end_gwh,"end_fill_pct":round(end_gwh/capacity_gwh*100,1) if capacity_gwh else None,
            "min_storage_gwh":result["storage_gwh"].min(),"days_of_supply":round(dos,0),
            "storage_depleted":depleted_day is not None,"depletion_day":depleted_day})
    return pd.DataFrame(rows)

def hdd_sensitivity(base_storage_gwh, base_daily_withdrawal, hdd_range=(-30,30), hdd_per_gwh=50.0, capacity_gwh=None):
    rows=[]
    for delta_hdd in range(hdd_range[0], hdd_range[1]+1, 5):
        extra_daily=delta_hdd*hdd_per_gwh/151
        adjusted=base_daily_withdrawal+extra_daily
        end=max(0, base_storage_gwh-adjusted*151)
        row={"delta_hdd":delta_hdd,"adjusted_daily_withdrawal_gwh":round(adjusted,0),"end_storage_gwh":round(end,0)}
        if capacity_gwh: row["end_fill_pct"]=round(end/capacity_gwh*100,1)
        rows.append(row)
    return pd.DataFrame(rows)
