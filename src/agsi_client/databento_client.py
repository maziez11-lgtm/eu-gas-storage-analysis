"""
Databento TTF Forward Curve Client
====================================
Fetches TTF Natural Gas futures settlement prices from Databento.

Two datasets available:
  - NDEX.IMPACT : ICE Endex TTF (primary TTF venue, TFM symbol)
                  History from 2018 | ~$1-3/GB historical
  - XEEE.EOBI   : EEX TTF (secondary venue, G5BM symbol)
                  History from 2018 | ~$10/GB historical

For daily settlement prices (what we need for the forward curve),
use schema="statistics" which returns settlement, OI, volume per contract.

COST ESTIMATE for our use case:
  - Daily OHLCV/statistics for 12 TTF monthly contracts, 5 years
  - Data volume: ~10-50 MB (very small — daily end-of-day only)
  - Cost: well under $1 with $125 free credits
  - Free credits cover several years of fetching

REGISTRATION:
  1. Go to https://databento.com/signup
  2. Enter email + password (credit card required to verify account)
  3. You will NOT be charged if you stay within $125 free credits
  4. Go to https://databento.com/portal/api-keys → copy your API key
  5. Add to .env: DATABENTO_API_KEY=your_key_here
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DatabentoTTFClient:
    """
    Fetches TTF Natural Gas futures daily settlement prices from Databento.

    Usage
    -----
    >>> client = DatabentoTTFClient(api_key="your_databento_key")
    >>> df = client.get_ttf_curve(start="2020-01-01", n_months=12)
    >>> df.to_csv("data/raw/ttf_curve.csv")

    The returned DataFrame has:
        index  : date (daily)
        columns: M1, M2, ..., M12  (settlement price in €/MWh)
    """

    # ICE Endex — primary TTF venue (most liquid, best history)
    NDEX_DATASET = "NDEX.IMPACT"
    NDEX_TTF_PARENT = "TFM"       # TTF Natural Gas Month Futures parent symbol

    # EEX — secondary TTF venue
    XEEE_DATASET = "XEEE.EOBI"
    XEEE_TTF_PARENT = "G5BM"      # EEX PEG Natural Gas Month Futures

    def __init__(
        self,
        api_key: Optional[str] = None,
        dataset: str = "NDEX.IMPACT",
    ):
        self.api_key = api_key or os.getenv("DATABENTO_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No Databento API key found. "
                "Set DATABENTO_API_KEY in .env or pass api_key=... "
                "Get a free key at https://databento.com/signup ($125 free credits)"
            )
        self.dataset = dataset

        # Import databento here so the module is optional
        try:
            import databento as db
            self._db = db
            self._client = db.Historical(self.api_key)
            logger.info(f"✅ Databento client ready — dataset: {dataset}")
        except ImportError:
            raise ImportError(
                "databento package not installed. Run: pip install databento"
            )

    def get_ttf_curve(
        self,
        start: str = "2020-01-01",
        end: Optional[str] = None,
        n_months: int = 12,
    ) -> pd.DataFrame:
        """
        Fetch daily TTF forward curve (M1–M{n_months}) from Databento.

        Uses the 'statistics' schema which returns:
          - Settlement price
          - Open interest
          - Volume

        Parameters
        ----------
        start : str
            Start date "YYYY-MM-DD"
        end : str, optional
            End date (default: today)
        n_months : int
            Number of forward months to fetch (default: 12)

        Returns
        -------
        pd.DataFrame
            Index: date (daily). Columns: M1, M2, ..., M{n_months} (€/MWh)

        Notes
        -----
        ICE Endex TTF contracts expire ~2 business days BEFORE the start of
        the delivery month (e.g. the July 2026 contract expires ~June 29).
        M1 is therefore the contract delivering in trade_month + 1, M2 in
        trade_month + 2, etc.  _build_curve computes tenor slots from the
        *delivery* month (expiry_month + 1), not the expiry month.
        """
        end = end or date.today().strftime("%Y-%m-%d")
        parent = self.NDEX_TTF_PARENT if "NDEX" in self.dataset else self.XEEE_TTF_PARENT

        logger.info(f"Fetching TTF curve {start} → {end} ({n_months} months)")

        # Fetch all TTF monthly contracts via parent symbol
        # stype_in="parent" expands to all active expiration months
        data = self._client.timeseries.get_range(
            dataset=self.dataset,
            symbols=parent,
            stype_in="parent",
            schema="statistics",    # includes settlement price + OI
            start=start,
            end=end,
        )

        df_raw = data.to_df()
        logger.info(f"Raw data: {len(df_raw)} rows, columns: {df_raw.columns.tolist()}")

        return self._build_curve(df_raw, n_months)

    def _build_curve(self, df_raw: pd.DataFrame, n_months: int) -> pd.DataFrame:
        """
        Transform raw Databento statistics into a wide-format forward curve.

        Databento returns one row per (date, contract_expiry). We pivot to
        one row per date with M1, M2, ..., M12 as columns.

        Settlement price field: 'close_price' or 'settle_price' in statistics schema.
        """
        if df_raw.empty:
            logger.warning("No data returned from Databento")
            return pd.DataFrame()

        # Normalise timestamp to date
        if "ts_event" in df_raw.columns:
            df_raw["date"] = pd.to_datetime(df_raw["ts_event"], utc=True).dt.date
        elif "ts_recv" in df_raw.columns:
            df_raw["date"] = pd.to_datetime(df_raw["ts_recv"], utc=True).dt.date

        # Settlement price column (schema-dependent)
        price_col = None
        for candidate in ["close_price", "settle_price", "settlement_price", "close"]:
            if candidate in df_raw.columns:
                price_col = candidate
                break

        if price_col is None:
            logger.error(f"No price column found. Available: {df_raw.columns.tolist()}")
            return pd.DataFrame()

        # Contract expiry — used to compute month offset (M+1, M+2, ...)
        expiry_col = None
        for candidate in ["expiration", "expiry", "maturity_date", "expire_ts"]:
            if candidate in df_raw.columns:
                expiry_col = candidate
                break

        if expiry_col:
            df_raw["expiry_date"] = pd.to_datetime(df_raw[expiry_col]).dt.date

        # Databento prices for TTF are in integer format (price × 1e9 for fixed-point)
        # or in float — detect and convert
        df_raw[price_col] = pd.to_numeric(df_raw[price_col], errors="coerce")
        if df_raw[price_col].dropna().mean() > 1_000_000:
            # Fixed-point encoding: divide by 1e9 for GBX, 1e4 for energy
            # TTF is quoted in €/MWh, typical range 20-200
            # Databento uses 1e9 fixed-point for prices
            df_raw[price_col] = df_raw[price_col] / 1e9
            logger.info("Applied 1e9 price normalization")

        # Pivot: for each (date, expiry) → compute month offset vs. date
        rows = []
        for _, row in df_raw.iterrows():
            d = row["date"]
            price = row[price_col]
            if pd.isna(price) or price <= 0:
                continue

            if expiry_col and "expiry_date" in df_raw.columns:
                expiry = row["expiry_date"]
                d_ts = pd.Timestamp(d)
                e_ts = pd.Timestamp(expiry)
                # ICE Endex TTF contracts expire ~2 business days BEFORE the start
                # of the delivery month (e.g. July delivery expires ~June 29).
                # Delivery month = expiry month + 1, so M1 = next calendar month.
                # Using expiry month directly would place two contracts in M1:
                #   July delivery (expiry June) → raw offset 0 → clamped to M1
                #   August delivery (expiry July) → raw offset 1 → also M1
                # which corrupts every tenor via groupby mean blending.
                if e_ts.month == 12:
                    delivery_month = 1
                    delivery_year  = e_ts.year + 1
                else:
                    delivery_month = e_ts.month + 1
                    delivery_year  = e_ts.year
                months_ahead = (delivery_year - d_ts.year) * 12 + (delivery_month - d_ts.month)
                if months_ahead < 1:
                    continue   # skip expired / current-month contracts
                if months_ahead > n_months:
                    continue
                rows.append({"date": d, f"M{months_ahead}": price})
            else:
                # No expiry info — use instrument_id or raw_symbol to determine month
                symbol = row.get("raw_symbol", row.get("symbol", ""))
                rows.append({"date": d, "price": price, "symbol": symbol})

        if not rows:
            logger.warning("No valid rows after processing")
            return pd.DataFrame()

        df_long = pd.DataFrame(rows)
        df_long["date"] = pd.to_datetime(df_long["date"])

        # Pivot to wide format
        if "M1" in df_long.columns or any(c.startswith("M") for c in df_long.columns):
            month_cols = [c for c in df_long.columns if c.startswith("M") and c[1:].isdigit()]
            if month_cols:
                df_wide = df_long.groupby("date")[month_cols].mean()
            else:
                df_wide = df_long.pivot_table(index="date", columns="symbol",
                                               values="price", aggfunc="mean")
        else:
            df_wide = df_long.pivot_table(index="date", columns="symbol",
                                           values="price", aggfunc="mean")

        df_wide.index = pd.to_datetime(df_wide.index)
        df_wide = df_wide.sort_index()

        return df_wide

    def estimate_cost(
        self,
        start: str = "2020-01-01",
        n_months: int = 12,
    ) -> dict:
        """
        Estimate the cost of fetching TTF curve data before actually fetching.
        Uses Databento's metadata API.
        """
        end = date.today().strftime("%Y-%m-%d")
        parent = self.NDEX_TTF_PARENT if "NDEX" in self.dataset else self.XEEE_TTF_PARENT

        meta = self._client.metadata.get_billable_size(
            dataset=self.dataset,
            symbols=parent,
            stype_in="parent",
            schema="statistics",
            start=start,
            end=end,
        )

        rate_per_gb = 10.0 if "XEEE" in self.dataset else 3.0  # approximate
        size_gb = meta / 1e9
        cost_usd = size_gb * rate_per_gb

        return {
            "dataset":      self.dataset,
            "size_bytes":   meta,
            "size_mb":      round(meta / 1e6, 2),
            "size_gb":      round(size_gb, 4),
            "rate_per_gb":  f"${rate_per_gb:.2f}",
            "estimated_cost": f"${cost_usd:.4f}",
            "within_free_credits": cost_usd < 125.0,
        }

    def update_ttf_csv(
        self,
        csv_path: str,
        n_months: int = 12,
    ) -> pd.DataFrame:
        """
        Incremental update: only fetch new data since the last date in the CSV.

        Parameters
        ----------
        csv_path : str
            Path to existing ttf_curve.csv (created by get_ttf_curve)

        Returns
        -------
        pd.DataFrame
            Updated full DataFrame (existing + new rows)
        """
        path = Path(csv_path)

        if path.exists():
            existing = pd.read_csv(path, index_col=0, parse_dates=True)
            last_date = existing.index.max()
            start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            logger.info(f"Last date: {last_date.date()} | Fetching from {start}")
        else:
            existing = pd.DataFrame()
            start = "2018-01-01"
            logger.info(f"No existing file — full fetch from {start}")

        new_data = self.get_ttf_curve(start=start, n_months=n_months)

        if new_data.empty:
            logger.info("No new data available")
            return existing

        logger.info(f"+{len(new_data)} new rows")

        if not existing.empty:
            combined = pd.concat([existing, new_data])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        else:
            combined = new_data

        combined.to_csv(path)
        logger.info(f"✅ Saved {len(combined)} rows → {path}")
        return combined


def load_csv_to_standard_format(csv_path: str) -> pd.DataFrame:
    """
    Load a TTF curve CSV and ensure it has standard M1-M12 column names.
    Works with both Databento output and manually-downloaded files.
    """
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # Rename columns to standard M1-M12 format if needed
    rename = {}
    for col in df.columns:
        col_str = str(col).upper()
        if col_str.startswith("M") and col_str[1:].isdigit():
            rename[col] = f"M{col_str[1:]}"
        elif "M+" in col_str:
            num = col_str.replace("M+", "").strip()
            if num.isdigit():
                rename[col] = f"M{int(num)}"

    if rename:
        df = df.rename(columns=rename)

    # Convert to numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
