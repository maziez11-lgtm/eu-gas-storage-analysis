"""AGSI+ API Client — see full docstring in gas-storage/src/agsi_client/client.py"""
from __future__ import annotations
import hashlib, json, logging, os, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

COUNTRY_CODES = {
    "EU":"","DE":"de","FR":"fr","IT":"it","NL":"nl","AT":"at","BE":"be",
    "ES":"es","PL":"pl","CZ":"cz","HU":"hu","SK":"sk","RO":"ro","UA":"ua",
    "GB":"gb","BG":"bg","HR":"hr","LV":"lv","PT":"pt","SE":"se","DK":"dk",
}
COLUMN_DESCRIPTIONS = {
    "gasInStorage":"Working gas volume in storage (TWh)",
    "full":"Fill rate (%) = gasInStorage / workingGasVolume × 100",
    "injection":"Gas injected (GWh/day)","withdrawal":"Gas withdrawn (GWh/day)",
    "workingGasVolume":"Total working gas volume capacity (TWh)",
    "status":"C=Confirmed E=Estimated U=Unavailable",
    "trend":"I=Injection W=Withdrawal F=Flat",
}

class AGSIClient:
    BASE_URL = "https://agsi.gie.eu/api"
    PAGE_SIZE = 300

    def __init__(self, api_key=None, cache_dir=None, cache_ttl_hours=12, ssl_verify=False):
        self.api_key = api_key or os.getenv("AGSI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key. Pass api_key= or set AGSI_API_KEY env var.")
        self.session = requests.Session()
        self.session.headers.update({"x-key": self.api_key})
        self.session.verify = ssl_verify
        if not ssl_verify:
            import urllib3; urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    def _get(self, params):
        resp = self.session.get(self.BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _cache_key(self, params):
        k = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()
        return self.cache_dir / f"{k}.parquet"

    def _load_cache(self, path):
        if path.exists():
            age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
            if age < self.cache_ttl:
                return pd.read_parquet(path)
        return None

    def _save_cache(self, df, path):
        try: df.to_parquet(path, index=True)
        except: pass

    def _fetch_all_pages(self, params, use_cache=True):
        cache_path = self._cache_key(params)
        if use_cache:
            cached = self._load_cache(cache_path)
            if cached is not None: return cached
        all_data, page = [], 1
        while True:
            pp = {**params, "page": page, "size": self.PAGE_SIZE}
            resp = self._get(pp)
            data = resp.get("data", [])
            if not data: break
            all_data.extend(data)
            if len(data) < self.PAGE_SIZE: break
            page += 1
            time.sleep(0.3)
        if not all_data:
            logger.warning(f"No data for {params}")
            return pd.DataFrame()
        df = self._parse(all_data)
        if use_cache and not df.empty: self._save_cache(df, cache_path)
        return df

    @staticmethod
    def _parse(data):
        df = pd.DataFrame(data)
        if df.empty: return df
        for date_col in ["gasDayEnd","gasDayStart","gasDay"]:
            if date_col in df.columns:
                df.index = pd.to_datetime(df[date_col])
                df.index.name = "date"
                df = df.drop(columns=[date_col])
                break
        df = df.sort_index()
        num_cols = ["gasInStorage","consumption","consumptionFull","injection","injectionFull",
                    "withdrawal","withdrawalFull","workingGasVolume","injectionCapacity",
                    "withdrawalCapacity","contractedCapacity","availableCapacity",
                    "coveredCapacity","netWithdrawal","full"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "full" not in df.columns and {"gasInStorage","workingGasVolume"}.issubset(df.columns):
            df["full"] = (df["gasInStorage"]/df["workingGasVolume"]*100).round(2)
        return df

    def get_country(self, country, start=None, end=None, use_cache=True):
        code = COUNTRY_CODES.get(country.upper(), country.lower())
        params = {"country": code}
        if start: params["from"] = start
        if end:   params["to"]   = end
        df = self._fetch_all_pages(params, use_cache=use_cache)
        if not df.empty: df["country"] = country.upper()
        return df

    def get_eu_aggregate(self, start=None, end=None, use_cache=True, countries=None):
        eu = countries or ["DE","FR","IT","NL","AT","BE","ES","PL","CZ","HU"]
        frames = []
        for c in eu:
            df_c = self.get_country(c, start=start, end=end, use_cache=use_cache)
            if not df_c.empty: frames.append(df_c)
        if not frames: return pd.DataFrame()
        num_cols = [c for c in ["gasInStorage","injection","withdrawal",
                                 "workingGasVolume","injectionCapacity","withdrawalCapacity"]
                    if c in frames[0].columns]
        df_eu = pd.concat(frames).groupby(level=0)[num_cols].sum()
        df_eu["full"] = (df_eu["gasInStorage"]/df_eu["workingGasVolume"]*100).round(2)
        df_eu["country"] = "EU"
        df_eu.index = pd.to_datetime(df_eu.index)
        return df_eu.sort_index()

    def get_multiple_countries(self, countries, start=None, end=None, use_cache=True):
        frames = [self.get_country(c, start=start, end=end, use_cache=use_cache)
                  for c in countries]
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames).sort_index() if frames else pd.DataFrame()

    def clear_cache(self):
        for f in self.cache_dir.glob("*.parquet"): f.unlink()
