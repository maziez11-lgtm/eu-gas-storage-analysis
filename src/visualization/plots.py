"""Plotly chart functions for gas storage analysis."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = {"current":"#1f77b4","5yr_avg":"#ff7f0e","5yr_band":"rgba(255,127,14,0.15)",
          "injection":"#2ca02c","withdrawal":"#d62728","target":"#9467bd"}

def fig_storage_fan(pivot_df, current_year=None, title="EU Gas Storage – Seasonal Fan Chart", y_label="Fill Rate (%)"):
    fig = go.Figure()
    current_year = current_year or pivot_df.columns.max()
    hist_years = [y for y in pivot_df.columns if y!=current_year]
    recent_hist = [y for y in hist_years if y>=current_year-5]
    if recent_hist:
        band_max = pivot_df[recent_hist].max(axis=1)
        band_min = pivot_df[recent_hist].min(axis=1)
        fig.add_trace(go.Scatter(
            x=list(pivot_df.index)+list(pivot_df.index)[::-1],
            y=list(band_max)+list(band_min)[::-1],
            fill="toself",fillcolor=COLORS["5yr_band"],
            line=dict(color="rgba(255,127,14,0)"),name="5yr Min–Max"))
        avg = pivot_df[recent_hist].mean(axis=1)
        fig.add_trace(go.Scatter(x=pivot_df.index,y=avg,mode="lines",
            line=dict(color=COLORS["5yr_avg"],dash="dash",width=2),name="5yr Average"))
    for year in hist_years:
        fig.add_trace(go.Scatter(x=pivot_df.index,y=pivot_df[year],mode="lines",
            line=dict(color="rgba(150,150,150,0.3)",width=1),showlegend=False))
    if current_year in pivot_df.columns:
        fig.add_trace(go.Scatter(x=pivot_df.index,y=pivot_df[current_year],mode="lines",
            line=dict(color=COLORS["current"],width=3),name=str(current_year)))
    fig.add_hline(y=90,line=dict(color=COLORS["target"],dash="dot",width=1.5),
                  annotation_text="EU Target 90%",annotation_position="top right")
    fig.update_layout(title=title,xaxis_title="Day of Year",yaxis_title=y_label,
        yaxis=dict(range=[0,105],ticksuffix="%"),template="plotly_white",hovermode="x unified")
    return fig

def fig_injection_pace(pace_df, title="Injection Pace vs. Required & Historical"):
    fig = go.Figure()
    if "hist_p10" in pace_df.columns and "hist_p90" in pace_df.columns:
        fig.add_trace(go.Scatter(
            x=list(pace_df.index)+list(pace_df.index)[::-1],
            y=list(pace_df["hist_p90"])+list(pace_df["hist_p10"])[::-1],
            fill="toself",fillcolor="rgba(150,150,150,0.2)",
            line=dict(color="rgba(150,150,150,0)"),name="Historical P10–P90"))
    if "hist_mean" in pace_df.columns:
        fig.add_trace(go.Scatter(x=pace_df.index,y=pace_df["hist_mean"],mode="lines",
            line=dict(color="grey",dash="dash",width=1.5),name="Historical Mean"))
    if "required_pct" in pace_df.columns:
        fig.add_trace(go.Scatter(x=pace_df.index,y=pace_df["required_pct"],mode="lines",
            line=dict(color=COLORS["target"],dash="dot",width=2),name="Required (90% target)"))
    if "actual_pct" in pace_df.columns:
        fig.add_trace(go.Scatter(x=pace_df.index,y=pace_df["actual_pct"],mode="lines",
            line=dict(color=COLORS["current"],width=3),name="Actual (current year)"))
    fig.add_hline(y=90,line=dict(color="purple",dash="dot",width=1))
    fig.update_layout(title=title,xaxis_title="Date",yaxis_title="Fill Rate (%)",
        yaxis=dict(range=[0,105],ticksuffix="%"),template="plotly_white",hovermode="x unified")
    return fig

def fig_depletion_scenarios(scenarios_dict, capacity_gwh, title="Winter Depletion Scenarios"):
    fig = go.Figure()
    color_map = {"Mild":"green","Normal":"blue","Cold":"orange","Extreme":"red"}
    for label, df in scenarios_dict.items():
        color = next((v for k,v in color_map.items() if k.lower() in label.lower()),"grey")
        fill_pct = df["storage_gwh"]/capacity_gwh*100
        fig.add_trace(go.Scatter(x=df.index,y=fill_pct,mode="lines",name=label,
            line=dict(color=color,width=2)))
    fig.add_hline(y=20,line=dict(color="darkred",dash="dot"),annotation_text="Critical 20%")
    fig.update_layout(title=title,xaxis_title="Day of Winter",yaxis_title="Storage Fill (%)",
        yaxis=dict(range=[-5,105],ticksuffix="%"),template="plotly_white")
    return fig

def fig_ttf_storage_correlation(merged_df, storage_col="full", price_col="ttf_front",
                                  title="TTF Price vs. EU Storage Fill Rate"):
    df = merged_df[[storage_col,price_col]].dropna().copy()
    df["year"] = df.index.year
    fig = go.Figure()
    for year in sorted(df["year"].unique()):
        sub = df[df["year"]==year]
        fig.add_trace(go.Scatter(x=sub[storage_col],y=sub[price_col],mode="markers",
            name=str(year),marker=dict(size=4,opacity=0.6),
            text=sub.index.strftime("%Y-%m-%d"),
            hovertemplate="%{text}<br>Fill: %{x:.1f}%<br>TTF: €%{y:.2f}/MWh"))
    fig.update_layout(title=title,xaxis_title="EU Storage Fill Rate (%)",
        yaxis_title="TTF Front Month (€/MWh)",template="plotly_white",
        xaxis=dict(ticksuffix="%"))
    return fig

def fig_country_comparison(df, countries, metric="full", title="Gas Storage by Country"):
    fig = go.Figure()
    colors = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b","#e377c2","#7f7f7f"]
    for i, country in enumerate(countries):
        subset = df[df["country"]==country][[metric]].dropna()
        fig.add_trace(go.Scatter(x=subset.index,y=subset[metric],mode="lines",name=country,
            line=dict(color=colors[i%len(colors)],width=2)))
    fig.add_hline(y=90,line=dict(color="purple",dash="dot",width=1),annotation_text="90% Target")
    fig.update_layout(title=title,xaxis_title="Date",yaxis_title="Fill Rate (%)",
        yaxis=dict(range=[0,105],ticksuffix="%"),template="plotly_white",hovermode="x unified")
    return fig

def fig_injection_withdrawal(df, title="Daily Injection & Withdrawal (GWh)"):
    fig = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.7,0.3],
        subplot_titles=["Fill Rate (%)","Daily Flows (GWh)"])
    if "full" in df.columns:
        fig.add_trace(go.Scatter(x=df.index,y=df["full"],name="Fill %",
            line=dict(color=COLORS["current"],width=2)),row=1,col=1)
    if "injection" in df.columns:
        fig.add_trace(go.Bar(x=df.index,y=df["injection"],name="Injection",
            marker_color=COLORS["injection"],opacity=0.7),row=2,col=1)
    if "withdrawal" in df.columns:
        fig.add_trace(go.Bar(x=df.index,y=-df["withdrawal"].abs(),name="Withdrawal",
            marker_color=COLORS["withdrawal"],opacity=0.7),row=2,col=1)
    fig.update_layout(title=title,template="plotly_white",hovermode="x unified",barmode="relative")
    return fig
