"""
Bloomberg Professional API Client
===================================
Wraps the Bloomberg Python API (blpapi) for TTF and multi-asset data.

REQUIREMENTS:
  Bloomberg Terminal must be running locally.
  Install the Bloomberg Python SDK:
    pip install blpapi
  or follow the official SDK guide:
    https://www.bloomberg.com/professional/support/api-library/

CONNECTION:
  blpapi connects to the local Terminal session on localhost:8194.
  No SSL or remote credentials needed — auth is handled by the Terminal.

TTF TICKERS ON BLOOMBERG:
  Day-ahead    : TTFDA Comdty
  M+1 → M+24  : TGE1 Comdty … TGE24 Comdty
  Q+1 (quarterly): TGEA Comdty

KEY FIELDS:
  PX_LAST   — last / settlement price
  PX_OPEN, PX_HIGH, PX_LOW, PX_CLOSE — OHLC
  OPEN_INT  — open interest
  PX_VOLUME — volume

USAGE:
  >>> from src.agsi_client.bloomberg_client import BloombergClient, BloombergNotAvailableError
  >>> try:
  ...     client = BloombergClient()
  ...     curve = client.get_ttf_curve(n_months=12)
  ... except BloombergNotAvailableError as e:
  ...     print(e)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BBG_HOST = "localhost"
BBG_PORT = 8194
REFDATA_SVC = "//blp/refdata"

# TTF monthly futures on Bloomberg
TTF_MONTHLY_TICKERS = {m: f"TGE{m} Comdty" for m in range(1, 25)}
TTF_DA_TICKER = "TTFDA Comdty"
TTF_Q1_TICKER = "TGEA Comdty"

# Multi-asset tickers
MULTI_ASSET_TICKERS = {
    "TTF M1":  "TGE1 Comdty",
    "Brent M1": "CO1 Comdty",
    "JKM M1":  "JKMM1 Comdty",
    "NBP M1":  "NBPG1 Comdty",
    "EUA (CFI2)": "CFI2 Comdty",
}


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class BloombergNotAvailableError(RuntimeError):
    """Raised when blpapi is not installed or the Terminal is not reachable."""


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class BloombergClient:
    """
    Thin wrapper around blpapi for energy market data.

    Connects to a local Bloomberg Terminal session on localhost:8194.
    Raises BloombergNotAvailableError if blpapi is not installed or the
    Terminal session cannot be reached.

    Parameters
    ----------
    host : str
        Bloomberg server host (default "localhost").
    port : int
        Bloomberg server port (default 8194).

    Examples
    --------
    >>> client = BloombergClient()
    >>> curve = client.get_ttf_curve(n_months=12)
    >>> hist  = client.get_historical("TGE1 Comdty", start="2020-01-01")
    >>> ref   = client.get_field(["TGE1 Comdty"], ["PX_LAST", "OPEN_INT"])
    """

    def __init__(self, host: str = BBG_HOST, port: int = BBG_PORT):
        try:
            import blpapi  # noqa: F401
            self._blpapi = blpapi
        except ImportError:
            raise BloombergNotAvailableError(
                "blpapi package not installed.\n"
                "Install the Bloomberg Python SDK:\n"
                "  pip install blpapi\n"
                "or follow: https://www.bloomberg.com/professional/support/api-library/"
            )

        self._host = host
        self._port = port
        self._session: Optional[object] = None
        self._refdata_svc: Optional[object] = None
        self._connect()

    # ── connection ──────────────────────────────────────────────────────────

    def _connect(self) -> None:
        opts = self._blpapi.SessionOptions()
        opts.setServerHost(self._host)
        opts.setServerPort(self._port)

        session = self._blpapi.Session(opts)
        if not session.start():
            raise BloombergNotAvailableError(
                f"Could not connect to Bloomberg Terminal at {self._host}:{self._port}.\n"
                "Make sure the Bloomberg Terminal is open and logged in."
            )

        if not session.openService(REFDATA_SVC):
            session.stop()
            raise BloombergNotAvailableError(
                f"Could not open Bloomberg service {REFDATA_SVC}."
            )

        self._session = session
        self._refdata_svc = session.getService(REFDATA_SVC)
        logger.info(f"Connected to Bloomberg Terminal at {self._host}:{self._port}")

    def close(self) -> None:
        """Stop the Bloomberg session."""
        if self._session is not None:
            self._session.stop()
            self._session = None
            logger.info("Bloomberg session closed")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── helpers ─────────────────────────────────────────────────────────────

    def _send_and_collect(self, request) -> list:
        """Send a Bloomberg request and collect all response messages."""
        self._session.sendRequest(request)
        messages = []
        done = False
        while not done:
            ev = self._session.nextEvent(timeout=10_000)  # 10 s timeout
            for msg in ev:
                messages.append(msg)
            if ev.eventType() in (
                self._blpapi.Event.RESPONSE,
                self._blpapi.Event.REQUEST_STATUS,
            ):
                done = True
        return messages

    @staticmethod
    def _to_date_str(d: Union[str, date]) -> str:
        if isinstance(d, date):
            return d.strftime("%Y%m%d")
        return pd.Timestamp(d).strftime("%Y%m%d")

    # ── public API ──────────────────────────────────────────────────────────

    def get_ttf_curve(self, n_months: int = 24) -> pd.DataFrame:
        """
        Fetch the latest TTF forward curve snapshot (M1 to M{n_months}).

        Uses the BDP (Bloomberg Data Point) reference request for the most
        recent settlement price of each monthly contract.

        Parameters
        ----------
        n_months : int
            Number of monthly tenors to fetch (1-24, default 24).

        Returns
        -------
        pd.DataFrame
            Single-row DataFrame indexed by today's date.
            Columns: DA (day-ahead), M1, M2, ..., M{n_months} (€/MWh).
        """
        n_months = min(max(1, n_months), 24)
        tickers = [TTF_DA_TICKER] + [TTF_MONTHLY_TICKERS[m] for m in range(1, n_months + 1)]
        fields  = ["PX_LAST"]

        ref = self.get_field(tickers, fields)

        row: dict = {}
        if TTF_DA_TICKER in ref.index:
            row["DA"] = ref.loc[TTF_DA_TICKER, "PX_LAST"]
        for m in range(1, n_months + 1):
            tk = TTF_MONTHLY_TICKERS[m]
            if tk in ref.index:
                row[f"M{m}"] = ref.loc[tk, "PX_LAST"]

        df = pd.DataFrame([row], index=[pd.Timestamp.today().normalize()])
        df.index.name = "date"
        logger.info(f"TTF curve: {len(row)} tenors fetched")
        return df

    def get_historical(
        self,
        ticker: str,
        field: str = "PX_LAST",
        start: str = "2020-01-01",
        end: Optional[str] = None,
        periodicity: str = "DAILY",
    ) -> pd.DataFrame:
        """
        Fetch historical time series for a single ticker and field (BDH).

        Parameters
        ----------
        ticker : str
            Bloomberg ticker, e.g. "TGE1 Comdty".
        field : str
            Bloomberg field, e.g. "PX_LAST", "OPEN_INT", "PX_VOLUME".
        start : str
            Start date "YYYY-MM-DD".
        end : str, optional
            End date "YYYY-MM-DD" (default: today).
        periodicity : str
            "DAILY", "WEEKLY", "MONTHLY" (default "DAILY").

        Returns
        -------
        pd.DataFrame
            Index: date. Column: {field}.
        """
        end = end or date.today().strftime("%Y-%m-%d")

        request = self._refdata_svc.createRequest("HistoricalDataRequest")
        request.getElement("securities").appendValue(ticker)
        request.getElement("fields").appendValue(field)
        request.set("startDate", self._to_date_str(start))
        request.set("endDate",   self._to_date_str(end))
        request.set("periodicitySelection", periodicity)

        messages = self._send_and_collect(request)

        rows = []
        for msg in messages:
            if not msg.hasElement("securityData"):
                continue
            sec_data = msg.getElement("securityData")
            field_data = sec_data.getElement("fieldData")
            for i in range(field_data.numValues()):
                entry = field_data.getValueAsElement(i)
                dt  = entry.getElementAsDatetime("date")
                val = entry.getElementAsFloat(field) if entry.hasElement(field) else None
                rows.append({"date": pd.Timestamp(dt.year, dt.month, dt.day), field: val})

        if not rows:
            logger.warning(f"No historical data returned for {ticker} / {field}")
            return pd.DataFrame(columns=[field])

        df = pd.DataFrame(rows).set_index("date").sort_index()
        logger.info(f"{ticker}/{field}: {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
        return df

    def get_historical_multi(
        self,
        ticker: str,
        fields: List[str],
        start: str = "2020-01-01",
        end: Optional[str] = None,
        periodicity: str = "DAILY",
    ) -> pd.DataFrame:
        """
        Fetch historical data for a single ticker and multiple fields.

        Parameters
        ----------
        ticker : str
            Bloomberg ticker, e.g. "TGE1 Comdty".
        fields : list of str
            Bloomberg fields, e.g. ["PX_LAST", "OPEN_INT", "PX_VOLUME"].
        start : str
            Start date "YYYY-MM-DD".
        end : str, optional
            End date (default: today).
        periodicity : str
            "DAILY", "WEEKLY", "MONTHLY".

        Returns
        -------
        pd.DataFrame
            Index: date. Columns: one per field requested.
        """
        end = end or date.today().strftime("%Y-%m-%d")

        request = self._refdata_svc.createRequest("HistoricalDataRequest")
        request.getElement("securities").appendValue(ticker)
        for f in fields:
            request.getElement("fields").appendValue(f)
        request.set("startDate", self._to_date_str(start))
        request.set("endDate",   self._to_date_str(end))
        request.set("periodicitySelection", periodicity)

        messages = self._send_and_collect(request)

        rows = []
        for msg in messages:
            if not msg.hasElement("securityData"):
                continue
            sec_data  = msg.getElement("securityData")
            field_data = sec_data.getElement("fieldData")
            for i in range(field_data.numValues()):
                entry = field_data.getValueAsElement(i)
                dt = entry.getElementAsDatetime("date")
                row: dict = {"date": pd.Timestamp(dt.year, dt.month, dt.day)}
                for f in fields:
                    row[f] = entry.getElementAsFloat(f) if entry.hasElement(f) else None
                rows.append(row)

        if not rows:
            logger.warning(f"No data for {ticker} / {fields}")
            return pd.DataFrame(columns=fields)

        df = pd.DataFrame(rows).set_index("date").sort_index()
        logger.info(f"{ticker}: {len(df)} rows, fields={fields}")
        return df

    def get_field(
        self,
        tickers: List[str],
        fields: List[str],
    ) -> pd.DataFrame:
        """
        Bulk reference data request (BDP) — current values only.

        Parameters
        ----------
        tickers : list of str
            Bloomberg tickers, e.g. ["TGE1 Comdty", "TGE2 Comdty"].
        fields : list of str
            Bloomberg fields, e.g. ["PX_LAST", "OPEN_INT"].

        Returns
        -------
        pd.DataFrame
            Index: ticker. Columns: one per field.
            Returns NaN for any ticker/field combination with no data.
        """
        request = self._refdata_svc.createRequest("ReferenceDataRequest")
        for tk in tickers:
            request.getElement("securities").appendValue(tk)
        for f in fields:
            request.getElement("fields").appendValue(f)

        messages = self._send_and_collect(request)

        rows = {}
        for msg in messages:
            if not msg.hasElement("securityData"):
                continue
            sec_arr = msg.getElement("securityData")
            for i in range(sec_arr.numValues()):
                sec = sec_arr.getValueAsElement(i)
                tk  = sec.getElementAsString("security")
                fd  = sec.getElement("fieldData")
                row: dict = {}
                for f in fields:
                    if fd.hasElement(f):
                        row[f] = fd.getElementAsFloat(f)
                    else:
                        row[f] = None
                rows[tk] = row

        if not rows:
            return pd.DataFrame(index=tickers, columns=fields, dtype=float)

        df = pd.DataFrame(rows).T.reindex(tickers)
        df.index.name = "ticker"
        df = df.astype(float)
        return df

    def get_ttf_historical_curve(
        self,
        n_months: int = 24,
        start: str = "2020-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch daily historical forward curve M1–M{n_months} from Bloomberg.

        Calls get_historical for each tenor in sequence and pivots into a
        wide DataFrame (one column per tenor).

        Parameters
        ----------
        n_months : int
            Number of monthly tenors (default 24).
        start : str
            Start date "YYYY-MM-DD".
        end : str, optional
            End date (default: today).

        Returns
        -------
        pd.DataFrame
            Index: date. Columns: DA, M1, M2, ..., M{n_months} (€/MWh).
        """
        end = end or date.today().strftime("%Y-%m-%d")
        all_series: dict = {}

        logger.info(f"Fetching TTF historical curve ({n_months} months) {start} → {end}")

        # Day-ahead
        da = self.get_historical(TTF_DA_TICKER, "PX_LAST", start, end)
        if not da.empty:
            all_series["DA"] = da["PX_LAST"]

        # Monthly tenors
        for m in range(1, n_months + 1):
            tk = TTF_MONTHLY_TICKERS[m]
            hist = self.get_historical(tk, "PX_LAST", start, end)
            if not hist.empty:
                all_series[f"M{m}"] = hist["PX_LAST"]

        if not all_series:
            return pd.DataFrame()

        df = pd.DataFrame(all_series).sort_index()
        df.index.name = "date"
        return df
