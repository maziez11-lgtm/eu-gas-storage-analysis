# CLAUDE.md — EU Gas Storage Analysis

## Quick Start
```bash
pip install -r requirements.txt
jupyter lab
```
Open notebooks/01_data_ingestion.ipynb first.

## API Keys
- AGSI: agsi.gie.eu (free)
- EEX: transparency.eex.com (free, for TTF forward curves)

## Key modules
- src/agsi_client/client.py — AGSI API wrapper
- src/agsi_client/eex_client.py — EEX TTF data fetcher
- src/analysis/injection_model.py — injection/withdrawal projections
- src/analysis/seasonal.py — YoY, STL decomposition
- src/analysis/adequacy.py — winter depletion scenarios
- src/analysis/correlations.py — TTF correlation

## Notebooks
1. 01_data_ingestion — fetch + cache AGSI data (run first)
2. 02_eda — exploratory analysis
3. 03_seasonal — seasonal patterns
4. 04_injection_pace — pace vs 90% target
5. 05_winter_adequacy — depletion scenarios
6. 06_ttf_correlation — TTF vs storage
7. 07_ttf_storage_analysis — integrated analysis + PDF export

## Units
- gasInStorage, workingGasVolume: TWh
- injection, withdrawal: GWh/day
- full: % (0-100)
- When passing to analysis functions: multiply TWh × 1000 to get GWh
