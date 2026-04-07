# =============================================================================
# analytics/stats.py
# All statistical computations for the macro dashboard.
#
# This module is intentionally pure Python/pandas/numpy — no Dash, no Plotly.
# That separation means you can test these functions independently, and later
# reuse them for screening, alerts, or backtesting.
#
# Core ideas:
#   Rolling Z-Score  → "Is this unusual vs the past year?"
#   Historical Z-Score → "Is this unusual vs all recorded history?"
#   Percentile Rank  → "Where does this sit in the full distribution?"
#   Regime Stats     → "What did this look like in prior episodes?"
# =============================================================================

import pandas as pd
import numpy as np
from config import REGIMES, ZSCORE_WINDOW, Z_WATCH, Z_EXTREME, COLORS


# ── Z-SCORES ──────────────────────────────────────────────────────────────────

def rolling_zscore(series: pd.Series, window: int = ZSCORE_WINDOW) -> pd.Series:
    """
    Compute a rolling z-score over a trailing window.

    Formula: z = (x - rolling_mean) / rolling_std

    This answers: "Given the past `window` trading days, how many standard
    deviations away from 'normal' is today's reading?"

    A z-score of +2 means today's level is 2 standard deviations ABOVE
    the recent average — historically unusual and worth flagging.

    Args:
        series: A pandas Series of daily observations.
        window: Number of days in the rolling window (default: 252 = 1 year).

    Returns:
        A pandas Series of z-scores, same index as input.
    """
    # min_periods at 50% of window avoids NaN at the start of history
    min_p = max(30, int(window * 0.5))
    roll_mean = series.rolling(window=window, min_periods=min_p).mean()
    roll_std  = series.rolling(window=window, min_periods=min_p).std()

    # Avoid division by zero when std is 0 (e.g. ZIRP period where FFR = 0.00%)
    roll_std = roll_std.replace(0, np.nan)

    return (series - roll_mean) / roll_std


def historical_zscore(series: pd.Series) -> float:
    """
    Z-score of the most recent value relative to the ENTIRE history.

    This answers: "How unusual is today's level vs everything since 2000?"
    Complements the rolling z-score (which only looks at the past year).

    Returns a scalar float. NaN if insufficient data.
    """
    s = series.dropna()
    if len(s) < 30:
        return float("nan")
    latest = s.iloc[-1]
    mu     = s.mean()
    sigma  = s.std()
    if sigma == 0:
        return 0.0
    return float((latest - mu) / sigma)


# ── PERCENTILE RANK ───────────────────────────────────────────────────────────

def percentile_rank(series: pd.Series) -> float:
    """
    What percentile is the current reading within the full historical distribution?

    Returns a value from 0 to 100.
      - 95th percentile: today's level is higher than 95% of all prior readings
      - 5th percentile:  today's level is lower than 95% of all prior readings
      - These extremes are where opportunities tend to hide

    Example: If the 2Y10Y spread is at the 2nd percentile, the curve is
    historically inverted — a historically unusual signal.
    """
    s = series.dropna()
    if len(s) < 2:
        return float("nan")
    latest = s.iloc[-1]
    return float((s < latest).sum() / len(s) * 100)


# ── FLAG SYSTEM ───────────────────────────────────────────────────────────────

def flag_status(zscore: float) -> dict:
    """
    Convert a z-score into a traffic-light flag.

    Returns a dict with 'label' and 'color' for use in the table.

    Logic:
      |z| < 1.5  → NORMAL  (green)  — within typical range
      |z| ≥ 1.5  → WATCH   (amber)  — elevated, worth monitoring
      |z| ≥ 2.0  → EXTREME (red)    — historically unusual, high attention
    """
    if np.isnan(zscore):
        return {"label": "N/A", "color": COLORS["subtext"]}
    az = abs(zscore)
    if az >= Z_EXTREME:
        return {"label": "EXTREME", "color": COLORS["red"]}
    elif az >= Z_WATCH:
        return {"label": "WATCH",   "color": COLORS["amber"]}
    else:
        return {"label": "NORMAL",  "color": COLORS["green"]}


# ── SUMMARY STATS TABLE ───────────────────────────────────────────────────────

# Human-readable display names for each series code
SERIES_LABELS = {
    "3M":     "3M T-Bill",
    "2Y":     "2Y Treasury",
    "5Y":     "5Y Treasury",
    "10Y":    "10Y Treasury",
    "30Y":    "30Y Treasury",
    "FFR":    "Fed Funds Rate",
    "2Y10Y":  "2Y–10Y Spread",
    "3M10Y":  "3M–10Y Spread",
}

def compute_summary_stats(
    rates_df: pd.DataFrame,
    spreads_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Build the summary statistics table shown at the top of Panel 1.

    For each series computes:
      - Current:     latest available value
      - 1M Change:   change vs ~22 trading days ago (approx 1 calendar month)
      - 3M Change:   change vs ~63 trading days ago
      - Roll Z:      rolling 1Y z-score of the current reading
      - Hist Z:      z-score vs full history since 2000
      - Percentile:  current reading's percentile rank in full history
      - Flag:        NORMAL / WATCH / EXTREME based on rolling z-score

    Returns a DataFrame ready to pass into a Dash DataTable.
    """
    # Merge all series into one dict for uniform processing
    all_series: dict[str, pd.Series] = {}
    for col in rates_df.columns:
        all_series[col] = rates_df[col].dropna()
    for col in spreads_df.columns:
        all_series[col] = spreads_df[col].dropna()

    # Preserve a logical display order
    display_order = ["3M", "2Y", "5Y", "10Y", "30Y", "FFR", "2Y10Y", "3M10Y"]
    ordered_series = {k: all_series[k] for k in display_order if k in all_series}

    rows = []
    for code, s in ordered_series.items():
        if len(s) < 30:
            continue  # Not enough data to compute meaningful stats

        current    = s.iloc[-1]
        ago_1m     = s.iloc[-22]  if len(s) > 22  else s.iloc[0]
        ago_3m     = s.iloc[-63]  if len(s) > 63  else s.iloc[0]
        chg_1m     = current - ago_1m
        chg_3m     = current - ago_3m

        rz_series  = rolling_zscore(s)
        rz_now     = rz_series.iloc[-1] if not rz_series.dropna().empty else float("nan")
        hz         = historical_zscore(s)
        pct        = percentile_rank(s)
        flag       = flag_status(rz_now)

        # Format sign for change columns
        def fmt_chg(v):
            return f"+{v:.2f}" if v > 0 else f"{v:.2f}"

        rows.append({
            "Series":       SERIES_LABELS.get(code, code),
            "Code":         code,                    # Hidden; used for conditional styling
            "Current (%)":  f"{current:.3f}",
            "1M Chg":       fmt_chg(chg_1m),
            "3M Chg":       fmt_chg(chg_3m),
            "Roll Z (1Y)":  round(rz_now, 2) if not np.isnan(rz_now) else "—",
            "Hist Z":       round(hz, 2)     if not np.isnan(hz)     else "—",
            "Percentile":   f"{pct:.0f}th",
            "Flag":         flag["label"],
            "_flag_color":  flag["color"],           # Used by style_data_conditional
        })

    return pd.DataFrame(rows)


# ── REGIME STATISTICS ─────────────────────────────────────────────────────────

def regime_stats(series: pd.Series) -> pd.DataFrame:
    """
    Slice a series by historical regime and compute descriptive stats.

    This provides the context layer: "In the 2022–2023 hiking cycle,
    the 10Y yield averaged X with a std of Y. Today it's Z."

    Returns a DataFrame with one row per regime, columns:
      Regime | Mean | Std | Min | Max | Obs
    """
    rows = []
    for r in REGIMES:
        mask = series.index >= r["start"]
        if r["end"]:
            mask &= series.index < r["end"]
        seg = series[mask].dropna()
        if len(seg) < 5:
            continue
        rows.append({
            "Regime":  r["label"],
            "Mean":    round(seg.mean(), 3),
            "Std":     round(seg.std(),  3),
            "Min":     round(seg.min(),  3),
            "Max":     round(seg.max(),  3),
            "Obs":     len(seg),
        })
    return pd.DataFrame(rows).set_index("Regime")


def rolling_correlation(
    s1: pd.Series,
    s2: pd.Series,
    window: int = 63
) -> pd.Series:
    """
    Rolling Pearson correlation between two series.

    Useful for detecting regime shifts — e.g. when the correlation between
    Gold and real yields flips sign, that's a signal worth investigating.

    Args:
        s1, s2: Input series (aligned by index).
        window: Rolling window in days (63 ≈ 3 months).
    """
    aligned = pd.concat([s1, s2], axis=1).dropna()
    if aligned.empty or aligned.shape[1] < 2:
        return pd.Series(dtype=float)
    return aligned.iloc[:, 0].rolling(window=window, min_periods=30).corr(aligned.iloc[:, 1])



def compute_curve_slope_regimes(rates_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience: compute regime stats for the two most-watched spreads,
    derived directly from the rates DataFrame.

    Returns a dict of DataFrames keyed by spread name.
    """
    out = {}
    if "10Y" in rates_df.columns and "2Y" in rates_df.columns:
        spread = (rates_df["10Y"] - rates_df["2Y"]).dropna()
        out["2Y10Y (derived)"] = regime_stats(spread)
    if "10Y" in rates_df.columns and "3M" in rates_df.columns:
        spread = (rates_df["10Y"] - rates_df["3M"]).dropna()
        out["3M10Y (derived)"] = regime_stats(spread)
    return out
