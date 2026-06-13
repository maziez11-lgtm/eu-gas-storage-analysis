# EU Gas Storage Analysis — User Manual

A complete guide to installing, configuring and using the analysis toolkit.

---

## Table of Contents

1. [Installation & Setup](#1-installation--setup)
2. [Data Sources](#2-data-sources)
3. [Notebook Guide](#3-notebook-guide)
4. [Key Concepts](#4-key-concepts)
5. [Analysis Examples](#5-analysis-examples)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Installation & Setup

### Clone the repository

```bash
git clone https://github.com/maziez11-lgtm/eu-gas-storage-analysis.git
cd eu-gas-storage-analysis
```

### Install dependencies

Python 3.11 or higher is required.

```bash
pip install -r requirements.txt
```

Key packages installed:

| Package | Version | Purpose |
|---|---|---|
| `pandas` | ≥2.0 | Data manipulation |
| `plotly` | ≥5.18 | Interactive charts |
| `statsmodels` | ≥0.14 | STL decomposition, regression |
| `arch` | ≥5.3 | GARCH volatility models |
| `hmmlearn` | ≥0.3 | Hidden Markov regime detection |
| `scipy` | ≥1.11 | Statistical tests |
| `scikit-learn` | ≥1.3 | Machine learning utilities |
| `tenacity` | ≥8.2 | API retry logic |
| `pyarrow` | ≥14.0 | Parquet file I/O |
| `jupyterlab` | ≥4.0 | Notebook interface |

### Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys (see [Section 2](#2-data-sources) for where to get them):

```env
AGSI_API_KEY=your_agsi_key_here
DATABENTO_API_KEY=db-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EEX_USERNAME=your_email@example.com
EEX_PASSWORD=your_password_here
```

> **Note:** Notebooks do **not** use `python-dotenv` at runtime. Paste keys directly into the notebook configuration cells where indicated, or set them as shell environment variables before launching JupyterLab.

### Launch JupyterLab

```bash
jupyter lab
```

Open `notebooks/01_data_ingestion.ipynb` first — it creates the parquet files that all other notebooks depend on.

---

## 2. Data Sources

### AGSI+ (Gas Storage)

**What it is:** The Gas Infrastructure Europe (GIE) AGSI+ platform aggregates daily storage transparency data from European gas storage operators.

**How to get a key:**
1. Go to [agsi.gie.eu](https://agsi.gie.eu)
2. Register for a free account
3. Copy your API key from the profile page
4. The same key also works for ALSI (LNG storage)

**What the data provides:**

| Column | Unit | Description |
|---|---|---|
| `gasInStorage` | TWh | Working gas currently in storage |
| `workingGasVolume` | TWh | Total storage capacity |
| `full` | % (0–100) | Fill rate = gasInStorage / workingGasVolume × 100 |
| `injection` | GWh/day | Gas injected into storage |
| `withdrawal` | GWh/day | Gas withdrawn from storage |
| `injectionCapacity` | GWh/day | Physical injection capacity |
| `withdrawalCapacity` | GWh/day | Physical withdrawal capacity |

**Unit conversion:** When passing storage volumes to analysis functions, the convention is:
- `gasInStorage` and `workingGasVolume` are in **TWh** in the raw API
- `injection` and `withdrawal` are in **GWh/day**
- To convert TWh → GWh: multiply by 1000

**Coverage:** EU countries + UK, Ukraine. Typical delay: 1–2 days.

### Databento (TTF Forward Curve)

**What it is:** Databento provides access to ICE Endex TTF Natural Gas futures settlement prices via the `NDEX.IMPACT` dataset. This is the primary source for the M1–M24 forward curve used in notebooks 07–10.

**How to get a key:**
1. Go to [databento.com/signup](https://databento.com/signup)
2. Create an account (credit card required, but you will not be charged within free credits)
3. You receive **$125 in free credits** — the full TTF history costs approximately **$0.01**
4. Go to [databento.com/portal/api-keys](https://databento.com/portal/api-keys) and copy your key

**What the data provides:**
- Daily settlement prices for TTF monthly futures contracts (M1 = front month, M2 = next month, …, M24)
- Prices in €/MWh
- History from 2018
- The `DatabentoTTFClient` normalises Databento's fixed-point price encoding (÷ 1e9) automatically

**Fetching data (notebook 07, cell 2):**

```python
from src.agsi_client.databento_client import DatabentoTTFClient

client = DatabentoTTFClient(api_key="db-your-key-here")

# Estimate cost before fetching (optional)
print(client.estimate_cost(start="2020-01-01"))
# → {'estimated_cost': '$0.0089', 'within_free_credits': True, ...}

# Fetch the full forward curve
df = client.get_ttf_curve(start="2020-01-01", n_months=12)
df.to_csv("data/raw/ttf_curve.csv")
```

**Incremental updates:**

```python
# Only fetch new rows since the last date in the CSV
df = client.update_ttf_csv("data/raw/ttf_curve.csv", n_months=12)
```

### ALSI+ (LNG Storage)

**What it is:** The GIE ALSI+ platform provides LNG terminal transparency data — the LNG equivalent of AGSI+.

**How to get a key:** Same key as AGSI+. Register at [agsi.gie.eu](https://agsi.gie.eu).

**What the data provides:**

| Column | Unit | Description |
|---|---|---|
| `gasInStorage` | TWh | LNG in terminal tanks |
| `dtmi` | TWh | Declared total maximum inventory (capacity) |
| `sendOut` | GWh/day | Gas regasified and sent out to grid |
| `full` | % | Fill rate = gasInStorage / dtmi × 100 |

**Usage (notebook 11):**

```python
from src.agsi_client.alsi_client import ALSIClient

client = ALSIClient(api_key="your_agsi_key", ssl_verify=False)
lng_df = client.get_eu_aggregate(start="2020-01-01")
lng_df.to_parquet("data/processed/eu_lng_full.parquet")
```

---

## 3. Notebook Guide

### Notebook 01 — Data Ingestion

**Purpose:** Fetch EU and country-level gas storage data from AGSI+ and cache it locally.

**Prerequisites:** AGSI API key configured.

**Key outputs:**
- `data/processed/eu_aggregate_full.parquet` — EU-wide daily storage data (run all other notebooks after this)
- `data/cache/*.parquet` — per-country response cache (auto-managed, TTL 12h)

**Configuration:**

```python
AGSI_API_KEY = "paste_key_here"   # in the notebook config cell
START_DATE   = "2020-01-01"
COUNTRIES    = ["DE","FR","IT","NL","AT","BE","ES","PL","CZ","HU"]
```

**Example output:**

```
✅ EU aggregate: 1826 rows | 2020-01-01 → 2025-01-01
Latest fill: 72.3% (2025-01-01)
```

---

### Notebook 02 — EDA: Storage Levels

**Purpose:** Exploratory analysis of storage fill rates across countries and time.

**Prerequisites:** Notebook 01.

**Key outputs:**
- Year-over-year fill rate chart (5 years of history with bands)
- Country-level heatmap
- Injection/withdrawal flow chart

**Configuration:** `ANALYSIS_DATE`, `START_DATE` at top of setup cell.

**Example output description:** An interactive Plotly chart showing the current year's fill rate (solid line) overlaid on the 5-year min/max band (shaded), with a dashed line for the EU 90% target.

---

### Notebook 03 — Seasonal Analysis

**Purpose:** Decompose storage patterns into trend, seasonal and residual components using STL.

**Prerequisites:** Notebook 01.

**Key outputs:**
- STL decomposition chart (4-panel: observed, trend, seasonal, residual)
- Injection season summary table (by year: start fill, peak fill, end fill, net injection)
- Year-over-year delta vs 5-year average

**Configuration:**

```python
STL_PERIOD   = 365   # days (annual seasonality)
STL_SEASONAL = 13    # smoother window (odd number, ≥7)
```

---

### Notebook 04 — Injection Pace Tracker

**Purpose:** Compare the current injection pace against the rate needed to hit the EU's 90% fill target by November 1.

**Prerequisites:** Notebook 01.

**Key outputs:**
- Required daily injection rate (GWh/day) to reach target
- Achievability flag (True if within physical capacity of ~13,500 GWh/day)
- Projection chart: current trajectory vs required trajectory

**Configuration:**

```python
TARGET_FILL_PCT = 90.0     # EU regulatory target
TARGET_DATE     = date(current_year, 11, 1)
```

**Example output:**

```
Current fill: 58.3% | Target: 90.0% | Days remaining: 147
Required daily rate: 8,412 GWh/day
Achievable: True (max capacity: 13,500 GWh/day)
```

---

### Notebook 05 — Winter Adequacy

**Purpose:** Model storage depletion under 4 demand scenarios from November 1 through March 31.

**Prerequisites:** Notebook 01.

**Key outputs:**
- Depletion curves for 4 scenarios: Mild (4,500 GWh/day withdrawal), Normal (6,000), Cold (7,500), Extreme (9,000)
- Days-of-supply table per scenario
- HDD sensitivity table (how end-of-winter storage changes with warmer/colder weather)

**Configuration:**

```python
LNG_DAILY_GWH      = 400.0   # daily LNG regasification contribution
PIPELINE_DAILY_GWH = 800.0   # daily pipeline import contribution
```

---

### Notebook 06 — TTF Correlation

**Purpose:** Quantify the time-varying correlation between EU storage fill rate and TTF M1 price.

**Prerequisites:** Notebooks 01 and 07 (for TTF data file).

**Key outputs:**
- Rolling 30/60/90-day correlation chart
- Scatter plot: fill rate vs TTF M1
- Linear regression: slope, R², p-value

---

### Notebook 07 — TTF & Storage Analysis (Main Report)

**Purpose:** Integrated analysis combining storage, forward curve, spread analysis, price modelling and a PDF export.

**Prerequisites:** Notebooks 01 + TTF data fetched (cell 2 in this notebook fetches it).

**Key outputs:**
- `data/raw/ttf_curve.csv` — TTF forward curve CSV
- `reports/eu_gas_analysis_YYYYMMDD.pdf` — PDF report

**Configuration:**

```python
DATABENTO_API_KEY = "paste_key_here"
ANALYSIS_DATE     = None          # None = last available date
START_DATE        = "2020-01-01"
```

**Sections:**
1. TTF Forward Curve shape (current vs historical)
2. Winter-Summer spread with injection breakeven line
3. Storage vs price regression
4. Injection pace (current year vs 90% target path)
5. Winter depletion scenarios
6. Rolling correlation
7. PDF export

---

### Notebook 08 — Time Spread Analysis

**Purpose:** Deep-dive into calendar spreads using real delivery month labels (e.g. *Jul'26–Oct'26*) rather than M+N offsets.

**Prerequisites:** Notebook 07 (for `ttf_curve.csv`).

**Key outputs:**
- Spread matrix table (near month × far month, for latest date)
- Summer–Winter spread time series
- Spread vs fill rate chart with regime shading

---

### Notebook 09 — TTF Price Analysis

**Purpose:** Flat-price volatility, GARCH conditional volatility, price distribution by fill bucket, seasonality and HMM regime detection.

**Prerequisites:** Notebook 07 (for `ttf_curve.csv`) and Notebook 01 (for storage parquet).

**Key outputs:**
- Rolling volatility chart (5d/21d/63d annualised, %)
- GARCH(1,1) conditional volatility series
- Violin plots: TTF M1 distribution split by fill-rate bucket
- Seasonal bar chart (avg price by calendar month)
- HMM regime scatter (Low / Medium / High price states)

**Dependencies:** `arch` and `hmmlearn` (both in `requirements.txt`).

---

### Notebook 10 — Spread Deep Dive

**Purpose:** Roll yield, contango/backwardation streak analysis, spread seasonality and an animated forward curve slider.

**Prerequisites:** Notebook 07 (for `ttf_curve.csv`) and Notebook 01 (for storage parquet).

**Key outputs:**
- Full M×M spread matrix heatmap (for the analysis date)
- Annualised roll yield bar chart (green = backwardation, red = contango)
- Regime timeline: contango/backwardation/flat coloured by period
- Longest streak table
- Animated forward curve with play/pause and date slider

---

### Notebook 11 — LNG Storage Analysis

**Purpose:** Fetch EU LNG terminal data, analyse send-out trends, correlate with TTF price, and build a combined gas + LNG energy buffer chart.

**Prerequisites:** Notebook 01.

**Key outputs:**
- `data/processed/eu_lng_full.parquet`
- LNG fill rate vs TTF M1 dual chart (with Pearson r)
- Send-out rate time series with 30d rolling average
- Dual fill chart: LNG fill % vs gas storage fill %
- Combined energy buffer: gas + LNG (TWh)

**Configuration (cell 0):**

```python
API_KEY = "paste_your_agsi_key_here"   # same key as notebook 01
```

---

## 4. Key Concepts

### Storage Fill Rate

The fill rate measures how full European underground gas storage is relative to its working capacity.

**Formula:**

```
fill (%) = gasInStorage (TWh) / workingGasVolume (TWh) × 100
```

**EU regulatory target:** EU member states must reach **90% fill by November 1** each year (Regulation 2022/1032). At 90%, the EU has roughly 950–1,000 TWh of usable gas reserves entering winter.

**Key dates:**
- **April 1** — start of injection season (storage typically at seasonal low)
- **October 1** — late-season injection checkpoint
- **November 1** — regulatory target date
- **March 31** — end of withdrawal season (storage typically at seasonal low)

---

### TTF Forward Curve

TTF (Title Transfer Facility) is the primary European natural gas benchmark, traded at the Dutch virtual hub.

**Month offsets:**
- **M1** = front month (closest delivery contract, rolls ~3 days before expiry)
- **M2** = next month
- **M3–M12** = progressively farther delivery months

**Quarters and seasons:**
- **Q1** ≈ M1–M3 (winter, Jan–Mar)
- **Q2** ≈ M4–M6 (spring/injection, Apr–Jun)
- **Q3** ≈ M7–M9 (summer/peak injection, Jul–Sep)
- **Q4** ≈ M10–M12 (autumn/winter onset, Oct–Dec)
- **Summer** ≈ Q2+Q3 (Apr–Sep)
- **Winter** ≈ Q4+Q1 next year (Oct–Mar)

**Reading the curve:**
- Upward slope (M1 < M2 < M3…) = **contango** — market expects prices to rise; storage owners earn a spread by buying now and selling forward
- Downward slope (M1 > M2 > M3…) = **backwardation** — market expects prices to fall; current supply is tight

---

### Time Spreads: Contango vs Backwardation

The most watched spread is **M1–M2** (or more broadly, **Winter–Summer**).

| Regime | M1–M2 spread | What it signals |
|---|---|---|
| **Backwardation** | Positive (M1 > M2) | Current supply tight; immediate delivery priced at premium |
| **Contango** | Negative (M1 < M2) | Ample current supply; forward prices higher (storage-friendly) |
| **Flat** | ~0 (within ±€0.15/MWh) | Market indifferent between delivery periods |

**Injection breakeven:** For gas storage to be economically viable, the Winter–Summer spread (typically Q4/Q1 vs Q2/Q3) must exceed the **all-in cost of storage** (~€3–5/MWh for EU underground storage, covering operating costs, gas losses, and financing). A W–S spread below ~€5/MWh discourages commercial injection.

**Roll yield:**

```
Roll yield (% annualised) = (M1 − M2) / M1 × (252 / holding_days) × 100
```

Positive roll yield = backwardation = profit from being long M1 and rolling forward. Negative = contango = roll cost.

---

### Winter Adequacy Model

The adequacy model (`src/analysis/adequacy.py`) simulates storage depletion from November 1 through March 31 under 4 demand scenarios:

| Scenario | Net withdrawal | Description |
|---|---|---|
| Mild | 4,500 GWh/day | Unusually warm winter |
| Normal | 6,000 GWh/day | Average historical demand |
| Cold | 7,500 GWh/day | Cold spell included (14 days at 1.8× rate) |
| Extreme | 9,000 GWh/day | 2021-style cold snap (21 days at 2.0× rate) |

**Supply offsets:** LNG regasification (~400 GWh/day) and pipeline imports (~800 GWh/day) are subtracted from gross withdrawal to arrive at net withdrawal from storage.

**Injection scenarios:** The projection model uses P10/P50/P90 injection rates derived from historical AGSI data.

**Depletion day:** If storage hits zero before March 31 under a given scenario, the model reports the day of depletion — the point at which the EU would face supply gaps without emergency measures.

---

### Rolling Correlation

The rolling Pearson correlation between storage fill rate and TTF M1 price is computed over windows of 30, 60, and 90 days.

**Interpretation:**
- **r < −0.7** — strong negative relationship: higher fill = significantly lower prices. This is the "normal" regime when storage is the primary price signal.
- **−0.7 < r < −0.3** — moderate relationship: other factors (LNG imports, demand, geopolitics) are competing with storage as price drivers.
- **r > −0.3 or positive** — storage fill has lost its explanatory power for prices. This typically occurs during supply disruptions or extreme geopolitical events where the forward curve decouples from fundamentals.

---

## 5. Analysis Examples

### Example 1 — Is the EU on track for winter?

**Question:** Given today's fill rate and injection pace, will the EU reach the 90% target by November 1?

**Steps:**

1. Run notebook 01 to get current fill data:
   ```bash
   jupyter nbconvert --to notebook --execute notebooks/01_data_ingestion.ipynb
   ```

2. Open notebook 04. Check the output table:
   ```
   Current fill: 62.1% | Target: 90.0% | Days remaining: 120
   Required daily rate: 9,280 GWh/day
   Achievable: True (physical max: 13,500 GWh/day)
   ```

3. If `Achievable: False`, the EU cannot physically reach 90% — look at what fill is achievable at max injection rate.

4. Cross-check in notebook 07, Section 4: the injection trajectory chart shows the current year's path vs the required path vs historical years that achieved 90%.

**Verdict:** If current pace ≥ required rate AND fill rate is above the 5-year average for this date, the EU is on track.

---

### Example 2 — Is the forward curve pricing winter scarcity?

**Question:** Are forward prices signalling that the market expects winter gas to be scarce?

**Steps:**

1. Open notebook 07, Section 2 (Winter–Summer Spread).

2. Read the current W–S spread (Q4 vs Q3, or Oct/Nov vs Jun/Jul):
   - **W–S > €10/MWh** → market pricing significant winter risk
   - **W–S €5–10/MWh** → normal winter premium, storage injection economical
   - **W–S < €5/MWh** → market not concerned about winter; injection economics weak
   - **W–S < 0** → backwardation; market expects gas to be more valuable now than in winter

3. Cross-check with the curve shape chart: a steep upward curve with a pronounced Q4 hump relative to Q2 confirms winter scarcity pricing.

4. In notebook 10, Section 2, the animated curve slider lets you compare today's curve shape against historical dates (e.g. the Sep 2021 stress period).

---

### Example 3 — What does low storage mean for TTF prices?

**Question:** At what storage fill rate does TTF price behaviour change most sharply?

**Steps:**

1. Open notebook 08, Section 3 (Storage–Price Regression).

2. Look at the regression chart: the storage–price relationship is typically non-linear (log-linear). The steepest part of the curve (where a 1pp drop in fill causes the largest price spike) is the **inflection point**.

3. Read the regression output:
   ```
   A 1pp increase in fill = 2.4% decrease in TTF (R² = 0.61)
   Inflection zone: 55–65% fill (estimated)
   ```

4. Compare the current fill rate against the inflection zone. If fill is **below** the inflection zone, price sensitivity is heightened — small changes in storage news will have amplified price impact.

5. Check the rolling correlation in notebook 06: correlation becomes strongly negative (< −0.7) when fill enters the inflection zone.

---

### Example 4 — Generate the weekly report

**Question:** How do I produce a PDF snapshot of the current gas market situation?

**Steps:**

1. Ensure data is current:
   ```bash
   # In terminal
   jupyter nbconvert --to notebook --execute notebooks/01_data_ingestion.ipynb
   ```

2. Open notebook 07 in JupyterLab.

3. In the setup cell, verify:
   ```python
   ANALYSIS_DATE = None    # auto-selects latest date
   START_DATE    = "2020-01-01"
   ```

4. Run all cells: **Kernel → Restart & Run All**

5. Scroll to Section 7 (Export). Run the PDF export cell. The report is saved to:
   ```
   reports/eu_gas_analysis_YYYYMMDD.pdf
   ```

6. The PDF includes: current fill rate, injection pace chart, forward curve, W–S spread, depletion scenarios, and a one-page summary table.

---

## 6. Troubleshooting

### SSL certificate errors

```
requests.exceptions.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Fix:** All API clients default to `ssl_verify=False`. If you see this, check you are using the client classes from `src/agsi_client/` and not calling `requests` directly with verify=True.

```python
client = AGSIClient(api_key="...", ssl_verify=False)   # default — already set
```

---

### `ModuleNotFoundError: No module named 'src'`

```
ModuleNotFoundError: No module named 'src'
```

**Cause:** The notebook was opened from the wrong directory, so Python cannot find the `src/` package.

**Fix:** Every notebook contains a path-fix cell at the top:

```python
for _c in [Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent]:
    if (_c / 'src' / 'agsi_client').exists():
        sys.path.insert(0, str(_c)); os.chdir(_c)
        print(f"✅ Root: {_c}"); break
```

Run this cell first. If it prints `✅ Root: /path/to/eu-gas-storage-analysis`, imports will work.

---

### API returns only 300 rows (pagination)

**Cause:** The AGSI and ALSI APIs paginate responses at 300 rows per page.

**Fix:** The `AGSIClient` and `ALSIClient` handle pagination automatically — they iterate pages until a response contains fewer than 300 rows. You do not need to do anything. If you see truncated data, check the API key is valid and the `from`/`to` date parameters are correctly formatted as `"YYYY-MM-DD"`.

---

### Databento prices in billions

```
M1    1234567890.0
M2    1189000000.0
```

**Cause:** Databento uses a fixed-point price encoding (price × 1,000,000,000 for integer storage).

**Fix:** The `DatabentoTTFClient._build_curve` method automatically detects when the mean price exceeds 1,000,000 and divides by 1e9. If you load a raw Databento file manually and see billion-scale prices, divide the price columns by 1e9:

```python
for col in df.columns:
    if df[col].mean() > 1_000_000:
        df[col] = df[col] / 1e9
```

---

### `reversed() argument must be a sequence` (Python 3.14+)

**Cause:** Python 3.14 tightened the `reversed()` protocol. Some older Plotly/matplotlib code passes a generator.

**Fix:** Already addressed in `src/visualization/plots.py` using `[::-1]` slice notation instead of `reversed()`. If you encounter this in a notebook cell directly, replace:

```python
# Old (breaks on Python 3.14)
list(reversed(some_list))

# New (works everywhere)
some_list[::-1]
```

---

### GARCH or HMM `ImportError`

```
ImportError: Install arch: pip install arch
ImportError: Install hmmlearn: pip install hmmlearn
```

**Fix:**

```bash
pip install arch hmmlearn
```

Both packages are listed in `requirements.txt` and installed by `pip install -r requirements.txt`. If you skipped that step or are using a different environment, install them manually.

---

### Parquet file not found

```
FileNotFoundError: data/processed/eu_aggregate_full.parquet
```

**Fix:** Run notebook 01 first. It creates all the processed parquet files. If you are running from a CI or script context:

```bash
jupyter nbconvert --to notebook --execute notebooks/01_data_ingestion.ipynb --output notebooks/01_data_ingestion.ipynb
```

---

### Cache returning stale data

**Cause:** API responses are cached in `data/cache/` with a 12-hour TTL.

**Fix:** To force a fresh fetch, either:

```python
# Option A: pass use_cache=False
df = client.get_eu_aggregate(start="2020-01-01", use_cache=False)

# Option B: clear all cache files
client.clear_cache()
```

Or delete `data/cache/*.parquet` manually.
