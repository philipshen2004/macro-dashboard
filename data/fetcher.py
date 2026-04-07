# =============================================================================
# data/fetcher.py
# Handles all data retrieval — FRED (rates, spreads, credit, inflation) and
# yfinance (commodity prices).
#
# Key design decisions:
#   1. CACHING: All fetched data is pickled to .cache/ on disk.
#      First run fetches live; every restart after that is instant.
#   2. FORWARD FILL: FRED/yfinance report business days only.
#      We ffill short gaps so rolling windows stay continuous.
#   3. GRACEFUL FAILURE: Individual series failures are logged and skipped.
#      The dashboard renders with whatever data came through.
#   4. GENERIC FETCHER: _fetch_series_dict() handles any {name: id} dict
#      so adding a new panel is just adding series IDs to config.py.
# =============================================================================

import os
import pickle
import pandas as pd
from datetime import datetime, timedelta
from fredapi import Fred

from config import (
    FRED_API_KEY,
    RATE_SERIES, SPREAD_SERIES, CREDIT_SERIES,
    COMMODITY_TICKERS, COMMODITY_FRED,
    START_DATE, CACHE_DIR, CACHE_TTL_HOURS
)


# ── CACHE UTILITIES ───────────────────────────────────────────────────────────

def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{key}.pkl")

def _cache_is_fresh(key: str) -> bool:
    path = _cache_path(key)
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=CACHE_TTL_HOURS)

def _read_cache(key: str):
    with open(_cache_path(key), "rb") as f:
        return pickle.load(f)

def _write_cache(key: str, data) -> None:
    with open(_cache_path(key), "wb") as f:
        pickle.dump(data, f)

def clear_cache() -> None:
    import glob
    files = glob.glob(os.path.join(CACHE_DIR, "*.pkl"))
    for f in files:
        os.remove(f)
    print(f"  [cache] Cleared {len(files)} cached file(s).")


# ── FRED CONNECTION ───────────────────────────────────────────────────────────

def _get_fred() -> Fred:
    if not FRED_API_KEY or FRED_API_KEY == "YOUR_FRED_API_KEY_HERE":
        raise ValueError(
            "\n\n❌  No FRED API key found.\n"
            "    Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html\n"
            "    Then set it in config.py or as env var FRED_API_KEY.\n"
        )
    return Fred(api_key=FRED_API_KEY)


# ── GENERIC FRED FETCHER ──────────────────────────────────────────────────────

def _fetch_series_dict(
    series_dict: dict,
    cache_key: str,
    label: str,
    force: bool = False,
    ffill_limit: int = 5,
) -> pd.DataFrame:
    """
    Pull any {name: fred_id} dict from FRED, combine into a daily DataFrame,
    forward-fill, and cache. Used by rates, spreads, credit, and commodity FRED series.
    """
    if not force and _cache_is_fresh(cache_key):
        print(f"  [cache] {label} loaded from cache.")
        return _read_cache(cache_key)

    print(f"  [FRED] Fetching {label}...")
    fred = _get_fred()
    frames = {}
    for name, series_id in series_dict.items():
        try:
            s = fred.get_series(series_id, observation_start=START_DATE)
            frames[name] = s
            print(f"    ✓ {name:<14s}  ({series_id})")
        except Exception as e:
            print(f"    ✗ {name:<14s}  ({series_id}) — {e}")

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    df = df.ffill(limit=ffill_limit).dropna(how="all")
    _write_cache(cache_key, df)
    if not df.empty:
        print(f"  [FRED] {label}: {df.shape[0]} rows  ({df.index[0].date()} → {df.index[-1].date()})")
    return df


# ── PUBLIC FETCH FUNCTIONS ────────────────────────────────────────────────────

def fetch_all_rates(force: bool = False) -> pd.DataFrame:
    """Treasury yields (3M/2Y/5Y/10Y/30Y) + Fed Funds Rate. Values in %."""
    return _fetch_series_dict(RATE_SERIES, "rates_v1", "Rates", force=force)

def fetch_spreads(force: bool = False) -> pd.DataFrame:
    """FRED pre-calculated yield curve spreads. Values in % (×100 for bps)."""
    return _fetch_series_dict(SPREAD_SERIES, "spreads_v1", "Spreads", force=force)

def fetch_credit(force: bool = False) -> pd.DataFrame:
    """ICE BofA OAS spreads + St. Louis FSI. Spreads in % (×100 for bps)."""
    return _fetch_series_dict(
        CREDIT_SERIES, "credit_v1", "Credit", force=force, ffill_limit=7
    )

def fetch_commodities(force: bool = False) -> pd.DataFrame:
    """
    Commodity prices via yfinance + inflation/real-yield context from FRED.

    Returns a single DataFrame with columns:
      WTI, GOLD, SILVER, COPPER, NATGAS   — price levels (USD)
      BREAKEVEN5Y, BREAKEVEN10Y           — inflation breakevens (%)
      REALYIELD10Y, REALYIELD5Y           — TIPS real yields (%)

    Why combine them here?
    The macro insight is in the RELATIONSHIPS — e.g. gold vs real yields,
    oil vs breakevens. Having them in one DataFrame makes that trivial.

    yfinance requires no API key. It pulls from Yahoo Finance.
    Front-month futures roll periodically so there are small gaps around
    contract expiry — we ffill those (usually 1 day).
    """
    key = "commodities_v1"
    if not force and _cache_is_fresh(key):
        print("  [cache] Commodities loaded from cache.")
        return _read_cache(key)

    frames = {}

    # ── yfinance prices ──────────────────────────────────────────────────────
    print("  [yfinance] Fetching commodity prices...")
    try:
        import yfinance as yf
        for name, ticker in COMMODITY_TICKERS.items():
            try:
                raw = yf.download(
                    ticker, start=START_DATE,
                    progress=False, auto_adjust=True
                )
                if raw.empty:
                    print(f"    ✗ {name:<8s}  ({ticker}) — empty response")
                    continue
                # yfinance may return multi-level columns; flatten
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                s = raw["Close"].dropna()
                s.index = pd.to_datetime(s.index)
                # Remove timezone info if present (keeps index consistent with FRED)
                if s.index.tz is not None:
                    s.index = s.index.tz_localize(None)
                frames[name] = s
                print(f"    ✓ {name:<8s}  ({ticker})  {len(s)} obs")
            except Exception as e:
                print(f"    ✗ {name:<8s}  ({ticker}) — {e}")
    except ImportError:
        print("    ✗ yfinance not installed — run: pip install yfinance")

    # ── FRED inflation / real yield context ──────────────────────────────────
    fred_df = _fetch_series_dict(
        COMMODITY_FRED, "commodity_fred_v1", "Commodity-FRED",
        force=force, ffill_limit=5
    )
    for col in fred_df.columns:
        frames[col] = fred_df[col]

    if not frames:
        print("  ⚠  No commodity data retrieved.")
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill(limit=5).dropna(how="all")

    _write_cache(key, df)
    print(f"  Commodities combined: {df.shape[0]} rows × {df.shape[1]} cols  "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


# ── CONVENIENCE LOADER ────────────────────────────────────────────────────────

def load_all(force: bool = False) -> tuple:
    """
    Fetch all four datasets. Returns (rates_df, spreads_df, credit_df, commodities_df).
    This is the single call made at app startup and on Refresh.
    """
    if force:
        clear_cache()
    rates       = fetch_all_rates(force=force)
    spreads     = fetch_spreads(force=force)
    credit      = fetch_credit(force=force)
    commodities = fetch_commodities(force=force)
    return rates, spreads, credit, commodities
