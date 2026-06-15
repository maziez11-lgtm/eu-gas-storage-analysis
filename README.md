# EU Gas Storage Analysis

A Python + Jupyter toolkit for European natural gas storage intelligence: tracking fill rates, projecting winter adequacy, analysing TTF forward curves and calendar spreads, and correlating LNG imports with gas prices.

Notebooks 01–11 form a self-contained analysis pipeline from raw API data to a publication-ready PDF report.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/maziez11-lgtm/eu-gas-storage-analysis.git
cd eu-gas-storage-analysis

# 2. Install dependencies (Python 3.11+ recommended)
pip install -r requirements.txt

# 3. Add API keys
cp .env.example .env
# Edit .env: add AGSI_API_KEY and DATABENTO_API_KEY

# 4. Fetch storage data (required before all other notebooks)
jupyter lab notebooks/01_data_ingestion.ipynb

# 5. Run the integrated analysis and generate PDF report
jupyter lab notebooks/07_ttf_storage_analysis.ipynb
```

---

## Data Sources

| Source | URL | What it provides | Cost |
|---|---|---|---|
| **AGSI+** | [agsi.gie.eu](https://agsi.gie.eu) | EU gas storage: fill rate, injection/withdrawal (GWh/day), capacity (TWh) | Free |
| **Databento** | [databento.com](https://databento.com) | TTF forward curve M1–M24 (daily settlement, €/MWh), ICE Endex NDEX.IMPACT | $125 free credits — full history costs ~$0.01 |
| **ALSI+** | [alsi.gie.eu](https://alsi.gie.eu) | EU LNG terminal storage: gasInStorage (TWh), send-out (GWh/day), fill % | Free (same key as AGSI) |
| **EEX** | [transparency.eex.com](https://transparency.eex.com) | TTF spot and historical (alternative to Databento) | Free |

---

## Notebooks

| # | Notebook | Purpose | Key outputs |
|---|---|---|---|
| 01 | `01_data_ingestion` | Fetch and cache AGSI+ storage data for EU + major countries | `data/processed/eu_aggregate_full.parquet` |
| 02 | `02_eda_storage_levels` | Exploratory analysis: fill rates, YoY comparison, 5yr bands | Interactive charts, seasonal overview |
| 03 | `03_seasonal_analysis` | STL decomposition, injection season summaries, YoY delta table | Trend/seasonal/residual breakdown |
| 04 | `04_injection_pace_tracker` | Compare current injection pace vs 90% Nov 1 EU target | Required daily rate, achievability flag |
| 05 | `05_winter_adequacy` | 4 demand scenarios (mild → extreme) × 3 injection scenarios | Depletion curves, days-of-supply table |
| 06 | `06_ttf_correlation` | Rolling correlation between EU fill rate and TTF M1 price | 30/60/90d correlation charts |
| 07 | `07_ttf_storage_analysis` | Integrated analysis: curve shape, W-S spread, storage–price model, PDF | `reports/eu_gas_analysis_YYYYMMDD.pdf` |
| 08 | `08_time_spread_analysis` | Calendar spread dynamics with real month labels (Oct–Apr, Summer–Winter) | Spread matrix, regime table |
| 09 | `09_ttf_price_analysis` | Flat price volatility, GARCH, price distribution by fill bucket, HMM regimes | Vol charts, regime labels |
| 10 | `10_spread_deep_dive` | Roll yield, contango/backwardation streaks, seasonality, animated curve | Roll yield series, streak table |
| 11 | `11_lng_storage_analysis` | LNG fill rate, send-out trends, LNG + gas combined energy buffer | `data/processed/eu_lng_full.parquet` |
| 12 | `12_ttf_market_analysis` | Vol surface, curve shape, seasonal carry, roll yield, VaR, drawdown | Interactive charts, risk metrics table |

**Run order:** 01 must run first. Notebooks 02–06 are independent of each other. Notebooks 07–11 require 01.

---

## Project Structure

```
eu-gas-storage-analysis/
├── notebooks/
│   ├── 01_data_ingestion.ipynb
│   ├── 02_eda_storage_levels.ipynb
│   ├── 03_seasonal_analysis.ipynb
│   ├── 04_injection_pace_tracker.ipynb
│   ├── 05_winter_adequacy.ipynb
│   ├── 06_ttf_correlation.ipynb
│   ├── 07_ttf_storage_analysis.ipynb
│   ├── 08_time_spread_analysis.ipynb
│   ├── 09_ttf_price_analysis.ipynb
│   ├── 10_spread_deep_dive.ipynb
│   └── 11_lng_storage_analysis.ipynb
├── src/
│   ├── agsi_client/
│   │   ├── client.py            # AGSI+ API wrapper
│   │   ├── eex_client.py        # EEX TTF data fetcher
│   │   ├── databento_client.py  # Databento TTF forward curve client
│   │   └── alsi_client.py       # ALSI+ LNG storage client
│   ├── analysis/
│   │   ├── injection_model.py   # Injection/withdrawal projections
│   │   ├── seasonal.py          # YoY comparison, STL decomposition
│   │   ├── adequacy.py          # Winter depletion scenarios
│   │   ├── correlations.py      # TTF vs storage correlations
│   │   ├── injection_pace.py    # Pace tracking vs targets
│   │   ├── price_analysis.py    # Rolling vol, GARCH, regimes
│   │   └── spread_analysis.py   # Calendar spread, roll yield
│   └── visualization/
│       └── plots.py             # Shared Plotly chart helpers
├── data/
│   ├── raw/                     # ttf_curve.csv (Databento output)
│   ├── processed/               # eu_aggregate_full.parquet, eu_lng_full.parquet
│   └── cache/                   # API response cache (auto-managed)
├── docs/
│   └── USER_MANUAL.md
├── config/
│   └── settings.yaml
├── .env.example
└── requirements.txt
```

---

## Requirements

- **Python** 3.11 or higher
- Key packages: `pandas`, `numpy`, `plotly`, `statsmodels`, `scipy`, `scikit-learn`, `arch`, `hmmlearn`, `requests`, `tenacity`, `pyarrow`, `jupyterlab`

Install everything with:

```bash
pip install -r requirements.txt
```

---

## API Keys

Copy `.env.example` to `.env` and fill in your keys:

```env
# AGSI+ API Key — free at https://agsi.gie.eu (also works for ALSI)
AGSI_API_KEY=your_key_here

# Databento — free at https://databento.com ($125 free credits)
DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# EEX Transparency (optional alternative to Databento)
EEX_USERNAME=your_email@example.com
EEX_PASSWORD=your_password_here
```

> Notebooks 01–06 only need `AGSI_API_KEY`.
> Notebooks 07–10 additionally need `DATABENTO_API_KEY` for the TTF forward curve.
> Notebook 11 uses the same `AGSI_API_KEY` for ALSI (pass it as `api_key=` in the notebook).

---

## See Also

- [User Manual](docs/USER_MANUAL.md) — detailed guide with examples and troubleshooting
- GIE AGSI+ documentation: [agsi.gie.eu/api-documentation](https://agsi.gie.eu/api-documentation)
- Databento documentation: [databento.com/docs](https://databento.com/docs)
