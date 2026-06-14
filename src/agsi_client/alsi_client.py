"""ALSI+ API Client — European LNG storage, mirroring AGSIClient."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

COUNTRY_CODES = {
    "EU": "",
    "BE": "be",
    "ES": "es",
    "FR": "fr",
    "GR": "gr",
    "IT": "it",
    "LT": "lt",
    "NL": "nl",
    "PL": "pl",
    "PT": "pt",
    "FI": "fi",
    "SE": "se",
    "GB": "gb",
}

EU_COUNTRIES = ["BE", "ES", "FR", "GR", "IT", "LT", "NL", "PL", "PT"]


class ALSIClient:
    """
    Client for the ALSI+ API (https://alsi.gie.eu/api).

    Mirrors AGSIClient interface with identical pagination logic and
    caching semantics.

    Parameters
    ----------
    api_key : str, optional
        ALSI API key. Falls back to ``ALSI_API_KEY`` env var.
    cache_dir : str or Path, optional
        Directory for parquet cache files. Defaults to ``data/cache/alsi``.
    cache_ttl_hours : int
        Cache time-to-live.
    ssl_verify : bool
        Whether to verify TLS certificates (default False to match AGSI client).
    """

    BASE_URL = "https://alsi.gie.eu/api"
    PAGE_SIZE = 300

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
        cache_ttl_hours: int = 12,
        ssl_verify: bool = False,
    ):
        self.api_key = api_key or os.getenv("ALSI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key. Pass api_key= or set ALSI_API_KEY env var."
            )
        self.session = requests.Session()
        self.session.headers.update({"x-key": self.api_key})
        self.session.verify = ssl_verify
        if not ssl_verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache/alsi")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        reraise=True,
    )
    def _get(self, params: dict) -> dict:
        resp = self.session.get(self.BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _cache_key(self, params: dict) -> Path:
        k = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
        return self.cache_dir / f"{k}.parquet"

    def _load_cache(self, path: Path) -> pd.DataFrame | None:
        if path.exists():
            age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
            if age < self.cache_ttl:
                return pd.read_parquet(path)
        return None

    def _save_cache(self, df: pd.DataFrame, path: Path) -> None:
        try:
            df.to_parquet(path, index=True)
        except Exception:
            pass

    def _fetch_all_pages(self, params: dict, use_cache: bool = True) -> pd.DataFrame:
        cache_path = self._cache_key(params)
        if use_cache:
            cached = self._load_cache(cache_path)
            if cached is not None:
                return cached

        all_data, page = [], 1
        while True:
            pp = {**params, "page": page, "size": self.PAGE_SIZE}
            resp = self._get(pp)
            data = resp.get("data", [])
            if not data:
                break
            all_data.extend(data)
            if len(data) < self.PAGE_SIZE:
                break
            page += 1
            time.sleep(0.3)

        if not all_data:
            logger.warning("No data for %s", params)
            return pd.DataFrame()

        df = self._parse(all_data)
        if use_cache and not df.empty:
            self._save_cache(df, cache_path)
        return df

    @staticmethod
    def _parse(data: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(data)
        if df.empty:
            return df

        for date_col in ["gasDayEnd", "gasDayStart", "gasDay"]:
            if date_col in df.columns:
                df.index = pd.to_datetime(df[date_col])
                df.index.name = "date"
                df = df.drop(columns=[date_col])
                break

        df = df.sort_index()

        num_cols = [
            "inventory",
            "sendOut",
            "dtmi",
            "full",
            "injection",
            "withdrawal",
            "workingGasVolume",
            "capacityLNG",
        ]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "full" not in df.columns and {
            "inventory",
            "dtmi",
        }.issubset(df.columns):
            df["full"] = (df["inventory"] / df["dtmi"] * 100).round(2)

        return df

    def get_country(
        self,
        country: str,
        start: str | None = None,
        end: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch LNG storage data for a single country.

        Parameters
        ----------
        country : str
            Two-letter country code (e.g. ``"ES"``) or ``"EU"`` for aggregate.
        start, end : str, optional
            ISO date strings (``"YYYY-MM-DD"``).

        Returns
        -------
        DataFrame with columns: inventory (TWh), sendOut (GWh/day),
        dtmi (capacity), full (%).
        """
        code = COUNTRY_CODES.get(country.upper(), country.lower())
        params: dict = {"country": code}
        if start:
            params["from"] = start
        if end:
            params["to"] = end

        df = self._fetch_all_pages(params, use_cache=use_cache)
        if not df.empty:
            df["country"] = country.upper()
        return df

    def get_eu_aggregate(
        self,
        start: str | None = None,
        end: str | None = None,
        use_cache: bool = True,
        countries: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Sum individual EU LNG country data into an EU-wide aggregate.

        Returns
        -------
        DataFrame with aggregated inventory (TWh), sendOut (GWh/day),
        dtmi (capacity TWh), full (%).
        """
        eu = countries or EU_COUNTRIES
        frames = []
        for c in eu:
            df_c = self.get_country(c, start=start, end=end, use_cache=use_cache)
            if not df_c.empty:
                frames.append(df_c)

        if not frames:
            return pd.DataFrame()

        agg_cols = [
            col
            for col in ["inventory", "sendOut", "dtmi", "injection", "withdrawal"]
            if col in frames[0].columns
        ]
        df_eu = pd.concat(frames).groupby(level=0)[agg_cols].sum()
        if "inventory" in df_eu.columns and "dtmi" in df_eu.columns:
            df_eu["full"] = (df_eu["inventory"] / df_eu["dtmi"] * 100).round(2)
        df_eu["country"] = "EU"
        df_eu.index = pd.to_datetime(df_eu.index)
        return df_eu.sort_index()

    def clear_cache(self) -> None:
        for f in self.cache_dir.glob("*.parquet"):
            f.unlink()
