"""
TTF Forward Curve Data — EEX Transparency Platform
===================================================

SOURCE: EEX (European Energy Exchange) Transparency Platform
URL: https://transparency.eex.com
Registration: FREE — just email + password, no credit card
Data: Daily settlement prices for TTF futures M1–M24
Format: CSV download or API after login
History: From ~2010 onwards
License: Free for non-commercial / research use

HOW TO GET YOUR DATA:
─────────────────────
Option A — Manual CSV (quickest, no code):
  1. Go to https://transparency.eex.com
  2. Register (free, ~2 min)
  3. Natural Gas → Futures → TTF Natural Gas → Historical Data
  4. Select date range, export CSV
  5. Save as data/raw/ttf_curve_eex.csv

Option B — EEX API (automated, needs session token):
  1. Register at https://transparency.eex.com
  2. Login → My Account → API Access → generate token
  3. Use EEXClient below to fetch automatically

Option C — ICE Data (alternative, also free registration):
  1. Register at https://www.theice.com/market-data
  2. Natural Gas → TTF → Settlement Prices → Download
  History goes back to 2010, full curve M1–M12+

WHY NOT YAHOO FINANCE:
  Yahoo Finance does not carry TTF forward curves (only Henry Hub NG=F).
  TTF is a European exchange product (ICE Endex / EEX).

EXPECTED CSV FORMAT for data/raw/ttf_curve.csv:
  date,M1,M2,M3,M4,M5,M6,M7,M8,M9,M10,M11,M12
  2024-01-02,29.45,30.12,31.00,32.10,33.00,31.50,29.00,27.50,28.00,32.00,35.00,36.00
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class EEXClient:
    """
    Fetches TTF forward curve settlement prices from EEX Transparency.

    Requires a free EEX account: https://transparency.eex.com

    Usage
    -----
    >>> client = EEXClient(username="you@email.com", password="yourpassword")
    >>> df = client.get_ttf_settlements(start="2020-01-01")
    >>> df.to_csv("data/raw/ttf_curve.csv")
    """

    BASE_URL = "https://transparency.eex.com"
    LOGIN_URL = f"{BASE_URL}/api/login"
    DATA_URL  = f"{BASE_URL}/api/v1/marketdata/settlement"

    # EEX product codes for TTF futures
    TTF_PRODUCT_IDS = {
        "TTF_M1":  "TTF_GAS_M_0001",
        "TTF_M2":  "TTF_GAS_M_0002",
        # ... up to M12
    }

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl_verify: bool = False,
    ):
        self.username = username or os.getenv("EEX_USERNAME")
        self.password = password or os.getenv("EEX_PASSWORD")
        self.ssl_verify = ssl_verify
        self.session = requests.Session()
        self.session.verify = ssl_verify
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        })
        self._token = None

    def login(self) -> bool:
        """Authenticate with EEX and obtain session token."""
        if not self.username or not self.password:
            raise ValueError(
                "EEX credentials required. Set EEX_USERNAME and EEX_PASSWORD "
                "in .env or pass username= and password= to EEXClient()."
            )
        resp = self.session.post(
            self.LOGIN_URL,
            json={"username": self.username, "password": self.password},
            timeout=15,
        )
        if resp.status_code == 200:
            self._token = resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self._token}"})
            logger.info("✅ EEX login successful")
            return True
        else:
            raise ConnectionError(f"EEX login failed: {resp.status_code} — {resp.text[:200]}")

    def get_ttf_settlements(
        self,
        start: str = "2020-01-01",
        end: Optional[str] = None,
        n_months: int = 12,
    ) -> pd.DataFrame:
        """
        Fetch daily TTF settlement prices for M1 to M{n_months}.

        Returns
        -------
        pd.DataFrame
            Index: date. Columns: M1, M2, ..., M12 (€/MWh)
        """
        if not self._token:
            self.login()

        end = end or date.today().strftime("%Y-%m-%d")
        all_data = {}

        for m in range(1, n_months + 1):
            logger.info(f"Fetching TTF M{m}...")
            try:
                resp = self.session.get(
                    self.DATA_URL,
                    params={
                        "product": f"TTF_GAS_M_{m:04d}",
                        "from": start,
                        "to": end,
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    prices = {
                        row["date"]: float(row["settlement"])
                        for row in data.get("data", [])
                        if row.get("settlement") is not None
                    }
                    all_data[f"M{m}"] = prices
                else:
                    logger.warning(f"M{m}: HTTP {resp.status_code}")
                time.sleep(0.5)  # polite rate limiting
            except Exception as e:
                logger.error(f"M{m} fetch failed: {e}")

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        df.index = pd.to_datetime(df.index)
        df.index.name = "date"
        df = df.sort_index()

        return df

    @staticmethod
    def load_eex_csv_export(path: str) -> pd.DataFrame:
        """
        Parse a manually-exported EEX CSV file into the standard format.

        EEX exports typically look like:
          Date;Product;Settlement Price;Currency;Unit
          01.01.2024;TTF Natural Gas M+01;29.450;EUR;MWh

        Returns a wide DataFrame with columns M1–M12.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"EEX CSV not found: {path}")

        # Try semicolon-separated first (EEX default)
        try:
            df_raw = pd.read_csv(path, sep=";", decimal=",")
        except Exception:
            df_raw = pd.read_csv(path)

        # Detect column names
        df_raw.columns = [c.strip().lower().replace(" ", "_") for c in df_raw.columns]

        # Parse date column
        date_col = next((c for c in df_raw.columns if "date" in c), None)
        prod_col = next((c for c in df_raw.columns if "product" in c), None)
        price_col = next((c for c in df_raw.columns if "price" in c or "settlement" in c), None)

        if not all([date_col, prod_col, price_col]):
            # Assume standard wide format: date, M1, M2, ..., M12
            df_raw.columns = ["date"] + [f"M{i}" for i in range(1, len(df_raw.columns))]
            df_raw["date"] = pd.to_datetime(df_raw["date"])
            return df_raw.set_index("date").sort_index()

        # Long format → pivot to wide
        df_raw[date_col] = pd.to_datetime(df_raw[date_col], dayfirst=True)
        df_raw[price_col] = pd.to_numeric(df_raw[price_col], errors="coerce")

        # Extract month number from product name (e.g. "TTF Natural Gas M+01" → 1)
        import re
        df_raw["month_num"] = df_raw[prod_col].str.extract(r"M\+?(\d+)").astype(float)
        df_raw = df_raw.dropna(subset=["month_num"])
        df_raw["col_name"] = "M" + df_raw["month_num"].astype(int).astype(str)

        pivot = df_raw.pivot_table(
            index=date_col, columns="col_name", values=price_col, aggfunc="mean"
        )
        pivot.index.name = "date"
        return pivot.sort_index()
