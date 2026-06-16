#!/usr/bin/env python3
"""
scripts/fetch_ttf_curve.py
==========================
Regenerates data/raw/ttf_curve.csv from Databento NDEX.IMPACT using the
ohlcv-1d schema and the corrected delivery-month tenor mapping.

Two-step approach (avoids the statistics schema 403 issue):
  1. Fetch instrument definitions year-by-year to build an
     instrument_id → expiration-date lookup for all outright TTF contracts.
  2. Fetch ohlcv-1d for all those instrument_ids over the full date range.
  3. Map each (date, instrument_id) to the correct tenor slot M1–M24 using
     the ICE Endex delivery-month convention (delivery = expiry month + 1).

Tenor mapping convention
------------------------
ICE Endex TTF contracts expire ~2 business days BEFORE the start of the
delivery month (e.g. the July 2026 contract expires ~June 29 2026).
Therefore:
  delivery_month = expiry_month + 1  (or 1 if expiry_month == 12)
  months_ahead   = (delivery_year - trade_year)*12 + (delivery_month - trade_month)
  M1 = first delivery month after trade date = trade_month + 1

Usage
-----
  python scripts/fetch_ttf_curve.py --api-key db-XXXX
  python scripts/fetch_ttf_curve.py            # reads DATABENTO_API_KEY from env
  python scripts/fetch_ttf_curve.py --start 2020-01-01 --n-months 12
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
DATASET     = "NDEX.IMPACT"
PARENT_SYM  = "TFM.FUT"
START_DATE  = "2018-12-23"
N_MONTHS    = 24
OUT_PATH    = Path("data/raw/ttf_curve.csv")

# One representative trading day per year to sample active contracts.
# We need at least one date per year so that contracts active only in that
# year appear in the definition scan.
DEF_SAMPLE_DATES = [
    "2019-01-02", "2020-01-02", "2021-01-04", "2022-01-03",
    "2023-01-02", "2024-01-02", "2025-01-02", "2026-01-02",
    # Also sample mid-year so contracts that start late in the year are caught
    "2019-07-01", "2020-07-01", "2021-07-01", "2022-07-01",
    "2023-07-03", "2024-07-01", "2025-07-01",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_weekday(d: str) -> str:
    """Advance d to Monday if it falls on a weekend."""
    ts = pd.Timestamp(d)
    if ts.weekday() == 5:   # Saturday
        ts += timedelta(days=2)
    elif ts.weekday() == 6: # Sunday
        ts += timedelta(days=1)
    return ts.strftime("%Y-%m-%d")


def _day_after(d: str) -> str:
    return (pd.Timestamp(d) + timedelta(days=1)).strftime("%Y-%m-%d")


def _parse_expiry(val) -> date | None:
    """
    Convert Databento expiration value to a Python date.
    The field arrives as a nanosecond integer or a Timestamp/datetime.
    """
    if pd.isna(val):
        return None
    try:
        ts = pd.Timestamp(val, unit="ns") if isinstance(val, (int, float)) else pd.Timestamp(val)
        return ts.date()
    except Exception:
        return None


def _detect_and_scale_prices(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Databento NDEX.IMPACT prices are delivered as fixed-point integers
    (price × 1e9). Detect and divide if the mean is implausibly large.
    TTF trades ~5–350 €/MWh; anything above 1 000 000 needs scaling.
    """
    series = df[col].dropna()
    if series.empty:
        return df
    if series.mean() > 1_000_000:
        df = df.copy()
        df[col] = df[col] / 1e9
        log.info(f"  Applied ÷1e9 price normalisation on column '{col}'")
    return df


# ── Step 1: Definitions ───────────────────────────────────────────────────────

def fetch_definitions(client) -> dict[int, date]:
    """
    Fetch instrument definitions for each sample date and return
    {instrument_id: expiration_date} for all outright contracts
    (raw_symbol ending with '!').
    """
    id_to_expiry: dict[int, date] = {}

    for raw_date in DEF_SAMPLE_DATES:
        d   = _next_weekday(raw_date)
        end = _day_after(d)
        log.info(f"Definitions: {d}")
        try:
            store = client.timeseries.get_range(
                dataset=DATASET,
                symbols=PARENT_SYM,
                stype_in="parent",
                schema="definition",
                start=d,
                end=end,
            )
            df = store.to_df()
            if df.empty:
                log.warning(f"  No rows for {d}")
                continue

            # Outrights only — raw_symbol ends with '!'
            outrights = df[df["raw_symbol"].str.endswith("!") == True].copy()
            if outrights.empty:
                log.warning(f"  No outright contracts for {d}")
                continue

            new = 0
            for _, row in outrights.iterrows():
                iid = int(row["instrument_id"])
                if iid in id_to_expiry:
                    continue
                exp = _parse_expiry(row["expiration"])
                if exp is not None:
                    id_to_expiry[iid] = exp
                    new += 1

            log.info(f"  {len(outrights)} outrights, +{new} new IDs → {len(id_to_expiry)} total")

        except Exception as e:
            log.warning(f"  Definition fetch failed for {d}: {e}")

    return id_to_expiry


# ── Step 2: OHLCV ─────────────────────────────────────────────────────────────

def fetch_ohlcv(client, instrument_ids: list[int], start: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV for all instrument_ids from `start` to today.
    Returns DataFrame with columns [date, instrument_id, close, volume].
    """
    end = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    syms = [str(iid) for iid in instrument_ids]

    log.info(f"OHLCV: {len(syms)} instruments, {start} → {end}")
    store = client.timeseries.get_range(
        dataset=DATASET,
        symbols=syms,
        stype_in="instrument_id",
        schema="ohlcv-1d",
        start=start,
        end=end,
    )
    df = store.to_df()
    if df.empty:
        log.warning("No OHLCV rows returned")
        return pd.DataFrame()

    log.info(f"  Raw rows: {len(df)}")

    # Normalise timestamp → date
    df["date"] = pd.to_datetime(df["ts_event"], utc=True).dt.date

    # Scale prices if needed
    df = _detect_and_scale_prices(df, "close")

    return df[["date", "instrument_id", "close", "volume"]].copy()


# ── Step 3: Build curve ───────────────────────────────────────────────────────

def build_curve(
    ohlcv: pd.DataFrame,
    id_to_expiry: dict[int, date],
    n_months: int = N_MONTHS,
) -> pd.DataFrame:
    """
    Map each OHLCV row to a tenor slot M1–M{n_months} and pivot to wide.

    ICE Endex TTF delivery-month convention:
      delivery_month = expiry_month + 1  (year rollover when expiry_month == 12)
      months_ahead   = (delivery_year - trade_year)*12 + (delivery_month - trade_month)

    When multiple contracts map to the same (date, tenor) — which can happen
    near roll dates — keep the row with the highest volume (most liquid).
    """
    rows = []
    skipped_no_expiry = 0

    for _, row in ohlcv.iterrows():
        iid    = int(row["instrument_id"])
        expiry = id_to_expiry.get(iid)
        if expiry is None:
            skipped_no_expiry += 1
            continue

        price = row["close"]
        vol   = row.get("volume", 0) or 0
        if pd.isna(price) or price <= 0:
            continue

        d_ts = pd.Timestamp(row["date"])
        e_ts = pd.Timestamp(expiry)

        # Corrected delivery-month mapping
        if e_ts.month == 12:
            delivery_month = 1
            delivery_year  = e_ts.year + 1
        else:
            delivery_month = e_ts.month + 1
            delivery_year  = e_ts.year

        months_ahead = (
            (delivery_year - d_ts.year) * 12
            + (delivery_month - d_ts.month)
        )
        if months_ahead < 1 or months_ahead > n_months:
            continue

        rows.append({
            "date":   d_ts.normalize(),
            "tenor":  f"M{months_ahead}",
            "close":  price,
            "volume": vol,
        })

    if skipped_no_expiry:
        log.info(f"  Skipped {skipped_no_expiry} rows with no expiry in definition map")

    if not rows:
        log.error("build_curve: no valid rows — check definition/OHLCV join")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Per (date, tenor): keep the highest-volume contract
    df = (
        df.sort_values("volume", ascending=False)
          .drop_duplicates(subset=["date", "tenor"])
          .drop(columns=["volume"])
    )

    # Pivot to wide format
    wide = df.pivot_table(
        index="date", columns="tenor", values="close", aggfunc="first"
    )
    wide.columns.name = None

    # Ensure columns are ordered M1 … M{n_months}
    ordered = [f"M{m}" for m in range(1, n_months + 1) if f"M{m}" in wide.columns]
    wide = wide[ordered].sort_index()
    wide.index.name = "date"

    log.info(f"  Curve shape before ffill: {wide.shape}")
    return wide


# ── Sanity check ──────────────────────────────────────────────────────────────

def sanity_check(curve: pd.DataFrame) -> None:
    """Print sanity checks on the rebuilt curve."""
    print(f"\n{'='*55}")
    print(f"  Shape      : {curve.shape}")
    print(f"  Date range : {curve.index.min().date()} → {curve.index.max().date()}")
    print(f"  Columns    : {list(curve.columns[:6])} ...")

    # Check 2026-06-09 specifically
    target = "2026-06-09"
    target_ts = pd.Timestamp(target)
    tenor_cols = [c for c in ["M1", "M2", "M3", "M4", "M5", "M6"] if c in curve.columns]

    if target_ts in curve.index:
        row = curve.loc[target_ts, tenor_cols]
        print(f"\n  Row {target} (M1–M6):")
        for col, val in row.items():
            print(f"    {col}: €{val:.3f}/MWh" if not pd.isna(val) else f"    {col}: NaN")

        m1 = curve.loc[target_ts, "M1"] if "M1" in curve.columns else None
        m2 = curve.loc[target_ts, "M2"] if "M2" in curve.columns else None
        if m1 is not None and m2 is not None and not pd.isna(m1) and not pd.isna(m2):
            rel = "backwardation ✅" if m1 > m2 else "contango ⚠️"
            print(f"\n  M1 vs M2 : {rel}  (M1={m1:.2f}  M2={m2:.2f})")
        # Sanity bounds
        if m1 is not None and not pd.isna(m1):
            if 5 < m1 < 500:
                print(f"  M1 price : within plausible range (€5–€500/MWh) ✅")
            else:
                print(f"  M1 price : {m1:.2f} — OUTSIDE expected range ⚠️")
    else:
        print(f"\n  {target} not in index — printing latest row instead:")
        row = curve.iloc[-1][tenor_cols]
        for col, val in row.items():
            print(f"    {col}: €{val:.3f}/MWh" if not pd.isna(val) else f"    {col}: NaN")

    print(f"{'='*55}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch TTF forward curve (M1–M24) from Databento NDEX.IMPACT"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=os.getenv("DATABENTO_API_KEY"),
        help="Databento API key (or set DATABENTO_API_KEY env var)",
    )
    parser.add_argument("--start",    default=START_DATE, help=f"Start date (default: {START_DATE})")
    parser.add_argument("--n-months", type=int, default=N_MONTHS, help=f"Curve depth (default: {N_MONTHS})")
    parser.add_argument("--out",      default=str(OUT_PATH), help=f"Output CSV path (default: {OUT_PATH})")
    args = parser.parse_args()

    if not args.api_key:
        sys.exit(
            "Error: Databento API key required.\n"
            "  Pass --api-key <KEY>  or  set DATABENTO_API_KEY in the environment."
        )

    try:
        import databento as db
    except ImportError:
        sys.exit("Error: databento not installed. Run: pip install databento")

    client = db.Historical(args.api_key)
    log.info(f"Databento client ready ({db.__version__})")

    # ── 1. Definitions ───────────────────────────────────────────────────────
    log.info("\n=== Step 1: instrument definitions ===")
    id_to_expiry = fetch_definitions(client)
    if not id_to_expiry:
        sys.exit("No instrument definitions — check API key and that hist.databento.com is reachable")
    log.info(f"Total unique instrument IDs: {len(id_to_expiry)}")

    # ── 2. OHLCV ─────────────────────────────────────────────────────────────
    log.info("\n=== Step 2: ohlcv-1d ===")
    ohlcv = fetch_ohlcv(client, list(id_to_expiry.keys()), start=args.start)
    if ohlcv.empty:
        sys.exit("No OHLCV data returned")

    # ── 3. Build curve ────────────────────────────────────────────────────────
    log.info("\n=== Step 3: build forward curve ===")
    curve = build_curve(ohlcv, id_to_expiry, n_months=args.n_months)
    if curve.empty:
        sys.exit("Curve is empty after build — see warnings above")

    # ── 4. Forward-fill sparse far months ────────────────────────────────────
    curve = curve.ffill(axis=1)

    # ── 5. Save ───────────────────────────────────────────────────────────────
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    curve.to_csv(out)
    log.info(f"\n=== Saved → {out} ===")

    # ── 6. Sanity check ───────────────────────────────────────────────────────
    sanity_check(curve)


if __name__ == "__main__":
    main()
