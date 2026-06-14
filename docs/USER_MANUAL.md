# EU Gas Storage Analysis — User Manual

**Version 1.0 · June 2026**

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Quick Start](#2-quick-start)
3. [API Keys](#3-api-keys)
4. [Notebooks Reference](#4-notebooks-reference)
5. [Key Concepts](#5-key-concepts)
6. [Example Outputs](#6-example-outputs)
7. [Workflows](#7-workflows)
8. [Data Files](#8-data-files)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Introduction

**EU Gas Storage Analysis** is a Python + Jupyter toolkit for tracking European natural gas storage fundamentals, analysing TTF forward curve dynamics, and generating publication-ready market intelligence reports. It pulls live data from the GIE AGSI+ and ALSI+ APIs and the Databento TTF futures feed, then surfaces the analysis through 11 linked notebooks and a ReportLab PDF report.

**Who it is for:** energy traders monitoring EU injection/withdrawal pace and winter adequacy; analysts building storage-to-price regression models and spread strategies; and researchers studying seasonal gas market dynamics and LNG import trends.

**What you get:**
- **11 Jupyter notebooks** covering storage EDA, seasonal decomposition, injection pace tracking, winter adequacy scenarios, TTF forward curve analysis, calendar spread dynamics, price volatility, and LNG imports
- **Automated PDF report** (notebook 07) — 8 sections, exportable for morning briefings
- **Python modules** in `src/` — reusable analysis functions for volatility, spread, correlation, regime detection and adequacy modelling

---

## 2. Quick Start

**Prerequisites:** Python 3.11+, pip, JupyterLab

```bash
# Clone
git clone https://github.com/maziez11-lgtm/eu-gas-storage-analysis
cd eu-gas-storage-analysis

# Install dependencies (~2 min)
pip install -r requirements.txt

# Add API keys (see Section 3)
cp .env.example .env
# Edit .env: add AGSI_API_KEY and DATABENTO_API_KEY

# Launch JupyterLab
jupyter lab
```

**First run:**

1. Open `notebooks/01_data_ingestion.ipynb` — paste your AGSI key in the config cell, run all cells. This fetches EU storage data and writes `data/processed/eu_aggregate_full.parquet`.
2. Open `notebooks/07_ttf_storage_analysis.ipynb` — paste your Databento key in cell 2, run all cells. This fetches the TTF forward curve and generates the PDF report.

Total time from clone to first report: **~10 minutes**.

---

## 3. API Keys

| Service | URL | Cost | What it provides |
|---|---|---|---|
| **AGSI+** | [agsi.gie.eu](https://agsi.gie.eu) | Free | EU gas storage: fill rate, injection, withdrawal (TWh / GWh/day) |
| **ALSI+** | [agsi.gie.eu](https://agsi.gie.eu) | Free (same key) | EU LNG terminal storage: fill rate, send-out (TWh / GWh/day) |
| **Databento** | [databento.com](https://databento.com) | $125 free credits; full history ~$0.01 | TTF futures M1–M24 daily settlement prices (€/MWh) |

### Getting your AGSI+ key

1. Go to [agsi.gie.eu](https://agsi.gie.eu) and register a free account
2. Log in → profile → copy the API key
3. The same key works for both AGSI (gas storage) and ALSI (LNG)
4. Paste into `.env`:

```env
AGSI_API_KEY=your_key_here
```

### Getting your Databento key

1. Go to [databento.com/signup](https://databento.com/signup) — credit card required but $125 free credits covers months of usage
2. Portal → API Keys → copy key
3. Paste into `.env`:

```env
DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Where keys are used:** Notebooks paste keys directly in the configuration cell (`API_KEY = "paste_key_here"`). There is no `dotenv` runtime dependency — set values explicitly in each notebook's config cell or export to your shell environment before launching JupyterLab.

---

## 4. Notebooks Reference

| # | Notebook | Purpose | Prerequisites | Key outputs | Est. runtime |
|---|---|---|---|---|---|
| 01 | `01_data_ingestion` | Fetch EU + country gas storage from AGSI+ and cache locally | AGSI key | `eu_aggregate_full.parquet` | 2–5 min |
| 02 | `02_eda_storage_levels` | Exploratory analysis: YoY fill rate, 5yr bands, country heatmap | NB 01 | Interactive charts | 30 s |
| 03 | `03_seasonal_analysis` | STL decomposition, injection season summaries, YoY delta | NB 01 | STL chart, season table | 1 min |
| 04 | `04_injection_pace_tracker` | Current injection vs 90% Nov 1 EU target — achievability check | NB 01 | Required daily rate, trajectory chart | 30 s |
| 05 | `05_winter_adequacy` | Depletion model: 4 demand scenarios × 3 injection rates | NB 01 | Depletion curves, days-of-supply table | 30 s |
| 06 | `06_ttf_correlation` | Rolling 30/60/90d Pearson correlation: fill rate vs TTF M1 | NB 01, NB 07 | Correlation time series, scatter | 30 s |
| 07 | `07_ttf_storage_analysis` | Integrated analysis: curve shape, W-S spread, regression, adequacy + **PDF export** | NB 01, Databento key | `gas_storage_ttf_report.pdf`, `ttf_curve.csv` | 3–5 min |
| 08 | `08_time_spread_analysis` | Calendar spreads with real month labels (e.g. Oct'26–Apr'27) | NB 07 | Spread matrix, regime table, streak chart | 1 min |
| 09 | `09_ttf_price_analysis` | Rolling vol, GARCH(1,1), price by fill bucket, seasonal avg, HMM regimes | NB 07, NB 01 | Vol chart, regime labels, violin table | 2 min |
| 10 | `10_spread_deep_dive` | Roll yield, contango/backwardation streaks, seasonality, animated curve slider | NB 07, NB 01 | Roll yield series, streak table, animated chart | 1 min |
| 11 | `11_lng_storage_analysis` | EU LNG fill rate, send-out, LNG vs gas fill dual chart, combined buffer | NB 01, ALSI key | `eu_lng_full.parquet` | 2–5 min |

**Run order:** NB 01 must run first. NB 07 must run before NB 06, 08, 09, 10. NB 11 is independent.

---

## 5. Key Concepts

### Storage Fill Rate

```
fill (%) = gasInStorage (TWh) / workingGasVolume (TWh) × 100
```

The EU regulatory target is **90% fill by November 1** each year (EU Regulation 2022/1032). At 90%, the EU holds ~950–1,000 TWh of usable gas entering winter.

| API column | Unit | Description |
|---|---|---|
| `gasInStorage` | TWh | Working gas currently in storage |
| `workingGasVolume` | TWh | Total usable capacity |
| `injection` | GWh/day | Gas injected (positive flow) |
| `withdrawal` | GWh/day | Gas withdrawn (positive flow) |
| `full` | % (0–100) | Fill rate — computed automatically if absent |

**Unit conversion:** `injection` and `withdrawal` arrive in GWh/day; `gasInStorage` and `workingGasVolume` in TWh. To convert TWh → GWh multiply by 1,000.

---

### TTF Forward Curve

TTF (Title Transfer Facility) is the primary European gas benchmark, traded at the Dutch virtual hub.

| Label | Meaning |
|---|---|
| M1 | Front month (nearest delivery) |
| M2 | Next month |
| M3–M12 | Further delivery months |
| Q2 | Calendar quarter (Apr–Jun) |
| Summer | Q2 + Q3 (Apr–Sep) |
| Winter | Q4 + Q1 next year (Oct–Mar) |

The curve structure signals market expectations:
- **Upward slope** (M1 < M2 < … < M12) → **contango** — future delivery priced higher; ample near-term supply
- **Downward slope** (M1 > M2 > … > M12) → **backwardation** — near-term tighter than forward; winter scarcity priced

---

### Contango vs Backwardation

The **M1–M2 spread** (or more broadly **Winter–Summer spread**) is the primary storage signal:

| Regime | M1 – M2 | Signal | Storage economics |
|---|---|---|---|
| Contango | Negative | Ample supply | Injection profitable (buy spot, sell forward) |
| Flat | ~0 (±€0.15) | Balanced | Marginal injection economics |
| Backwardation | Positive | Near-term tight | Injection uneconomic; holders incentivised to withdraw |

**Injection breakeven:** The Winter–Summer spread must exceed ~**€5/MWh** to cover underground storage costs (operations, gas losses, financing). Below this level commercial injection slows.

**Roll yield** (annualised):
```
roll_yield (%) = (M1 − M2) / M1 × (252 / holding_days) × 100
```
Positive = backwardation = profit from holding front-month. Negative = contango = roll cost.

---

### Winter Adequacy Model

The model in `src/analysis/adequacy.py` runs depletion from November 1 to March 31 (151 days) across four demand scenarios:

| Scenario | Net withdrawal | Cold spell |
|---|---|---|
| Mild | 4,500 GWh/day | None |
| Normal | 6,000 GWh/day | None |
| Cold | 7,500 GWh/day | 14 days at 1.8× |
| Extreme | 9,000 GWh/day | 21 days at 2.0× |

Daily supply offsets: ~400 GWh/day LNG regasification + ~800 GWh/day pipeline imports (configurable). Storage depletes when net withdrawal exceeds combined supply.

---

### Rolling Correlation

Pearson correlation between EU fill rate and TTF M1 price, computed over rolling windows:

| Correlation | Interpretation |
|---|---|
| r < −0.7 | Storage is the dominant price driver — normal regime |
| −0.7 to −0.3 | Moderate influence; LNG / geopolitics competing |
| r > −0.3 | Storage has lost explanatory power (supply shock, disruption) |

---

### LNG Columns (ALSI+)

| Column | Unit | Description |
|---|---|---|
| `gasInStorage` | TWh | LNG in terminal tanks |
| `dtmi` | TWh | Declared total maximum inventory (capacity) |
| `sendOut` | GWh/day | Regasified gas sent to the grid |
| `full` | % | Fill rate = gasInStorage / dtmi × 100 |

---

## 6. Example Outputs

### Notebook 01 — Data Ingestion

```
✅ Root: /home/user/eu-gas-storage-analysis
Fetching EU aggregate...
  DE: 1826 rows | 2020-01-01 → 2025-11-14
  FR: 1826 rows | 2020-01-01 → 2025-11-14
  ...
✅ Storage: 1826 rows | 2020-01-01 → 2025-11-14
   Analysis date  : 2025-11-14
   Fill rate      : 72.4%
   Storage        : 928.1 TWh
   Capacity       : 1082.6 TWh
```

### Notebook 07 — Integrated Analysis

```
✅ Root: /home/user/eu-gas-storage-analysis
✅ Storage: 1826 rows | latest: 2025-11-14 | fill: 72.4%
✅ TTF curve loaded: 1512 rows | 2020-01-01 → 2025-11-14
   M1: €38.42/MWh  M3: €41.18/MWh  M6: €44.91/MWh  M12: €46.23/MWh
   Winter–Summer spread: +€6.49/MWh (contango)

OLS: log(TTF M1) ~ α + β × fill%
  α = 5.8241  β = -0.0243  R² = 0.614
  A 1pp increase in fill = 2.43% decrease in TTF (R²=0.61)

Injection scenarios: Low=6,240 / Avg=8,810 / High=11,380 GWh/day
  Low  → Nov 1: 79.3%  ⚠️ -10.7pp vs target
  Avg  → Nov 1: 89.6%  ✅  -0.4pp vs target
  High → Nov 1: 97.2%  ✅  +7.2pp vs target

✅ 9 charts saved
✅ Report: data/processed/gas_storage_ttf_report.pdf
   Size  : 847 KB
```

### Notebook 08 — Time Spread Analysis

```
Analysis date: 2025-11-14
TTF rows: 1512  |  Storage rows: 1826

Spread matrix: 66 column pairs built
Latest M1–M2 spread: -€2.77/MWh (contango)
Latest M1–M12 spread: -€7.81/MWh

Longest streaks:
  start       end         regime        days
  2021-09-14  2022-06-28  backwardation  287
  2022-07-01  2023-04-11  backwardation  284
  2020-01-01  2021-09-13  contango       621
```

### Notebook 09 — TTF Price Volatility

```
Analysis date: 2025-11-14
TTF rows: 1512, Storage rows: 1826

Latest vol_21d: 34.7%   vol_63d: 28.3%
GARCH(1,1) fitted on 1511 log-returns.
Latest GARCH cond. vol: 31.2% (annualised)

regime_label
Low       412
Medium    680
High      420
Name: count, dtype: int64

Price distribution by fill bucket:
        bucket_label  count   mean  median    p10    p90
  0    20–36%     87   89.4    84.1   44.2  148.3
  1    36–52%    210   72.1    68.4   32.8  121.6
  2    52–68%    531   42.7    38.9   24.1   74.2
  3    68–84%    512   31.8    29.4   19.6   52.7
  4    84–100%   172   27.3    25.8   17.4   43.1
```

### Notebook 11 — LNG Storage

```
✅ Root: /home/user/eu-gas-storage-analysis
Setup complete. Run cell 1 to fetch LNG data.

✅ Saved 1681 rows → data/processed/eu_lng_full.parquet
Latest (2025-11-14):
  gasInStorage  sendOut     dtmi  full
        7.21    312.4      8.24  87.5%

Analysis date: 2025-11-14
Latest LNG fill: 87.5%
1-year avg send-out: 287 GWh/day

Correlation (gas fill vs LNG fill): 0.341
```

### PDF Report Cover

```
╔═══════════════════════════════════════════════════════════╗
║  [NAVY BACKGROUND — full-width banner]                    ║
║                                                           ║
║         EU Gas Storage & TTF                              ║
║         Market Analysis Report                            ║
║                                                           ║
║    As of 14 November 2025  ·  EU Fill Rate: 72.4%         ║
║                                                           ║
║  ─────────────────────────────                            ║
║  Includes: Storage · TTF Curve · Spreads · Volatility · LNG ║
║  Generated 2025-11-14                                     ║
╚═══════════════════════════════════════════════════════════╝
```

---

## 7. Workflows

### Workflow 1 — Weekly Market Brief (10 min)

Generate the full analysis PDF for a Monday morning briefing.

```
1. Pull latest data:
   > Open 01_data_ingestion.ipynb
   > Kernel → Restart & Run All
   > Confirm: "✅ Storage: N rows | latest: YYYY-MM-DD"

2. Generate report:
   > Open 07_ttf_storage_analysis.ipynb
   > Kernel → Restart & Run All
   > Confirm: "✅ Report: data/processed/gas_storage_ttf_report.pdf"

3. Download PDF:
   > Scroll to last cell → click "📄 Download" link
   OR
   > Open data/processed/gas_storage_ttf_report.pdf in JupyterLab file browser
```

**Output:** 8-section PDF covering storage snapshot, TTF curve, W-S spread, correlation, injection pace, winter adequacy, time spreads, volatility, and LNG.

---

### Workflow 2 — Winter Adequacy Tracking (5 min)

Monitor whether the EU is on track for the 90% November 1 target.

```
1. Run NB 01 (data fetch)

2. Open 04_injection_pace_tracker.ipynb → Run All
   > Read: "Required daily rate: X GWh/day | Achievable: True/False"
   > If False: physically impossible to reach 90% — model max-injection scenario

3. Open 05_winter_adequacy.ipynb → Run All
   > Read the depletion table:
     - If "storage_depleted: True" for Normal scenario → high stress alert
     - If only Extreme scenario depletes → acceptable risk

4. Cross-check in NB 07, Section 4 (Injection chart):
   > Current year path vs 90% target trajectory
```

**Trigger:** Run this workflow weekly Apr–Oct; daily if fill rate drops >2pp in a week.

---

### Workflow 3 — Spread & Roll Yield Analysis (10 min)

Analyse TTF calendar spread structure for a trading desk.

```
1. Run NB 07 (required — fetches TTF curve)

2. Open 08_time_spread_analysis.ipynb → Run All
   > Section 1: W-S spread with real month labels (e.g. Oct'26 – Apr'27)
   > Section 3: Read current regime (contango / backwardation / flat)
   > Note longest ongoing streak length

3. Open 10_spread_deep_dive.ipynb → Run All
   > Section 2: Roll yield chart — positive = backwardation premium
   > Section 4: Spread seasonality — which calendar months historically
                 show widest/narrowest spreads
   > Section 5: Animated curve slider — scrub back to compare curve shape
                 at previous stress dates (e.g. Sep 2021, Aug 2022)

4. Check PDF Section 6 for spread vs fill quintile table
```

**Key metric:** If M1–M6 spread > €8/MWh → the market is pricing significant winter risk.

---

### Workflow 4 — Historical Curve Comparison (5 min)

Compare today's forward curve against a historical stress date.

```
1. Open 10_spread_deep_dive.ipynb

2. Run all cells — go to Section 5 (Animated Forward Curve)

3. Click ▶ Play or drag the slider to the comparison date
   (e.g. 2022-08-26 — TTF M1 peak above €300/MWh)

4. Alternatively, in NB 07 Section 6 (Interactive Curve Tool):
   CURVE_DATE = date(2022, 8, 26)   # set this in the cell
   Run the cell → see historical curve vs today's shape
```

**Use case:** Quickly brief counterparties or management on "how today compares to [crisis date]."

---

### Workflow 5 — Incremental Data Update (3 min)

Update only new data since the last run without refetching history.

```python
# In a notebook or script:
from src.agsi_client.client import AGSIClient
from src.agsi_client.databento_client import DatabentoTTFClient

# Storage — client caches with 12h TTL; just re-run NB 01
# (cache handles deduplication automatically)

# TTF curve — incremental fetch since last CSV date
ttf_client = DatabentoTTFClient(api_key="your_key")
df = ttf_client.update_ttf_csv("data/raw/ttf_curve.csv", n_months=12)
# Logs: "Last date: 2025-11-07 | Fetching from 2025-11-08"
# Logs: "+5 new rows"
# Logs: "✅ Saved 1517 rows → data/raw/ttf_curve.csv"
```

**Schedule:** Run `update_ttf_csv` daily after ~18:00 CET (ICE settlement time).

---

## 8. Data Files

| Filename | Location | Created by | Contents | ~Rows |
|---|---|---|---|---|
| `eu_aggregate_full.parquet` | `data/processed/` | NB 01 | EU-wide daily: gasInStorage, injection, withdrawal, workingGasVolume, full | 1,500–2,000 |
| `eu_lng_full.parquet` | `data/processed/` | NB 11 | EU LNG daily: gasInStorage, sendOut, dtmi, full | 1,500–2,000 |
| `ttf_curve.csv` | `data/raw/` | NB 07 | TTF forward curve: columns M1–M12, daily settlement (€/MWh) | 1,500–2,000 |
| `gas_storage_ttf_report.pdf` | `data/processed/` | NB 07 | 8-section PDF report | — |
| `*.parquet` (cache) | `data/cache/` | Auto (AGSIClient) | Per-request API response cache, 12h TTL | — |
| `*.parquet` (cache) | `data/cache/alsi/` | Auto (ALSIClient) | Per-request ALSI API cache, 12h TTL | — |

**Parquet files** use PyArrow and are indexed by date. Load with:

```python
import pandas as pd
df = pd.read_parquet("data/processed/eu_aggregate_full.parquet")
df.index = pd.to_datetime(df.index).tz_localize(None)
```

---

## 9. Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `TypeError: Cannot join tz-naive and tz-aware DatetimeIndex` | Some DataFrames carry UTC timezone from API; others are tz-naive | Add `.tz_localize(None)` after `pd.to_datetime()`: `df.index = pd.to_datetime(df.index).tz_localize(None)` |
| `ModuleNotFoundError: No module named 'src'` | Notebook opened from wrong directory; Python path doesn't include project root | Run the path-fix cell at the top of every notebook first: `for _c in [Path.cwd(), ...]: if (_c / 'src' / 'agsi_client').exists(): sys.path.insert(0, str(_c)); os.chdir(_c); break` |
| `reversed() argument must be a sequence` (Python 3.14+) | Python 3.14 tightened `reversed()` protocol; some Plotly internals affected | Replace `reversed(x)` with `x[::-1]` in any custom code; the `src/visualization/plots.py` module already uses slice notation |
| ALSI `sendOut` / `dtmi` columns missing or NaN | Not all LNG terminals report all fields to GIE | `ALSIClient._parse()` uses `pd.to_numeric(..., errors="coerce")` — missing columns become NaN; guard with `lat.get('sendOut', float('nan'))` |
| Only 300 rows returned from AGSI/ALSI | API paginates at 300 rows per page | `AGSIClient` and `ALSIClient` handle pagination automatically (loop until `len(page) < 300`). If data is truncated, verify your API key is valid — invalid keys often return a single empty page |
| `FileNotFoundError: data/processed/eu_aggregate_full.parquet` | Notebook 01 has not been run yet | Run `01_data_ingestion.ipynb` first (Kernel → Restart & Run All) |
| `FileNotFoundError: data/raw/ttf_curve.csv` | Notebook 07 cell 2 (Databento fetch) has not been run | Open NB 07, run cell 2 with a valid `DATABENTO_API_KEY` |
| `ImportError: No module named 'arch'` | Optional GARCH dependency not installed | `pip install arch` (already in `requirements.txt` — re-run `pip install -r requirements.txt`) |
| `ImportError: No module named 'hmmlearn'` | Optional HMM dependency not installed | `pip install hmmlearn` (already in `requirements.txt`) |
| Charts blank / kaleido error in PDF export | `kaleido` not installed or wrong version | `pip install kaleido` — must match Plotly version. On some systems: `pip install kaleido==0.2.1` |
| Cache returning stale data | 12h TTL not yet expired | Pass `use_cache=False` to any client method, or call `client.clear_cache()` to delete all parquet cache files |

---

*EU Gas Storage Analysis · github.com/maziez11-lgtm/eu-gas-storage-analysis*
