# =============================================================================
# config.py
# Central config for the Macro Dashboard.
# All FRED series IDs, regime date ranges, thresholds, and colors live here.
# Change things here — nothing else needs editing.
# =============================================================================

# ── API KEY ──────────────────────────────────────────────────────────────────
# Get your free key at: https://fred.stlouisfed.org/docs/api/api_key.html
# Then paste it below (or set env var FRED_API_KEY and leave this as None).
FRED_API_KEY = "d759169e1982be9436f8c3b238f8735b"

import os
FRED_API_KEY = os.environ.get("FRED_API_KEY", FRED_API_KEY)


# ── FRED SERIES IDs ───────────────────────────────────────────────────────────
# These are the official FRED codes for each series we pull.
RATE_SERIES = {
    "3M":  "DGS3MO",    # 3-Month Treasury Constant Maturity (daily)
    "2Y":  "DGS2",      # 2-Year Treasury Constant Maturity (daily)
    "5Y":  "DGS5",      # 5-Year Treasury Constant Maturity (daily)
    "10Y": "DGS10",     # 10-Year Treasury Constant Maturity (daily)
    "30Y": "DGS30",     # 30-Year Treasury Constant Maturity (daily)
    "FFR": "FEDFUNDS",  # Effective Federal Funds Rate (monthly → forward filled)
}

# FRED pre-calculates these spread series for us (saves us doing the math)
SPREAD_SERIES = {
    "2Y10Y": "T10Y2Y",  # 10Y minus 2Y (in %)
    "3M10Y": "T10Y3M",  # 10Y minus 3M (in %)
}



# ── CREDIT SERIES ─────────────────────────────────────────────────────────────
# ICE BofA indices via FRED. All OAS values come back as % (e.g. 3.5 = 350 bps).
# We multiply by 100 in the display layer to show basis points.
#
# Quality ladder (tightest → widest spreads under normal conditions):
#   AAA → IG → BBB → BB → HY → CCC
#
# BBB sits just above junk — first IG tier to crack under stress (fallen-angel risk).
# CCC is the distress signal: when it blows out, credit stress is systemic.
CREDIT_SERIES = {
    "IG":     "BAMLC0A0CM",    # US Corporate IG OAS (all maturities)
    "HY":     "BAMLH0A0HYM2",  # US High Yield OAS
    "BBB":    "BAMLC0A4CBBB",  # BBB-rated US Corporate OAS (IG floor)
    "CCC":    "BAMLH0A3HYC",   # CCC & Lower US HY OAS (distress tier)
    "STLFSI": "STLFSI4",       # St. Louis Fed Financial Stress Index (weekly)
}


# ── COMMODITY SERIES ──────────────────────────────────────────────────────────
# Prices pulled via yfinance (free, no API key needed).
# FRED supplements with inflation/real-yield series that link to commodities.
#
# Key macro relationships to watch:
#   Gold vs Real Yields  → inverse: falling real yields = gold rises
#   Gold / Copper ratio  → rising = risk-off (gold outperforms industrial metal)
#   Oil vs Breakevens    → oil drives near-term inflation expectations
#   Copper trend         → leading indicator of global industrial activity

# yfinance tickers
COMMODITY_TICKERS = {
    "WTI":    "CL=F",   # WTI Crude Oil (front-month futures)
    "GOLD":   "GC=F",   # Gold (front-month futures)
    "SILVER": "SI=F",   # Silver (front-month futures)
    "COPPER": "HG=F",   # Copper (front-month futures, USD/lb)
    "NATGAS": "NG=F",   # Natural Gas (front-month futures)
}

# FRED series that give inflation/real-rate context for commodities
COMMODITY_FRED = {
    "BREAKEVEN5Y":  "T5YIE",   # 5-Year Inflation Breakeven (daily)
    "BREAKEVEN10Y": "T10YIE",  # 10-Year Inflation Breakeven (daily)
    "REALYIELD10Y": "DFII10",  # 10-Year TIPS Real Yield (daily)
    "REALYIELD5Y":  "DFII5",   # 5-Year TIPS Real Yield (daily)
}

# ── HISTORY ───────────────────────────────────────────────────────────────────
# How far back to pull data. 2000 gives us ~25 years of context including
# dot-com bust, GFC, ZIRP era, and hiking cycles.
START_DATE = "2000-01-01"


# ── ROLLING WINDOW ────────────────────────────────────────────────────────────
# Number of trading days used for rolling z-score (252 ≈ 1 calendar year).
# This tells us: "is this reading unusual vs the past year?"
ZSCORE_WINDOW = 252

# Z-score thresholds for the flag system
Z_WATCH   = 1.5    # Amber: elevated, worth monitoring
Z_EXTREME = 2.0    # Red:   historically unusual, high attention


# ── REGIME DEFINITIONS ────────────────────────────────────────────────────────
# Each regime gets a label, date range, and a translucent fill color for charts.
# These shade the background of historical charts so you can instantly see
# what macro environment a data point occurred in.
REGIMES = [
    {
        "label": "Post-GFC ZIRP",
        "start": "2009-01-01",
        "end":   "2015-12-01",
        "color": "rgba(100, 149, 237, 0.12)",   # cornflower blue
    },
    {
        "label": "Tightening '15–'18",
        "start": "2015-12-01",
        "end":   "2019-01-01",
        "color": "rgba(255, 165, 0, 0.12)",      # orange
    },
    {
        "label": "Pre-COVID",
        "start": "2019-01-01",
        "end":   "2020-02-01",
        "color": "rgba(144, 238, 144, 0.12)",    # light green
    },
    {
        "label": "COVID Shock",
        "start": "2020-02-01",
        "end":   "2021-06-01",
        "color": "rgba(255, 99, 71, 0.18)",      # tomato red
    },
    {
        "label": "Inflation / Hikes",
        "start": "2022-01-01",
        "end":   "2024-01-01",
        "color": "rgba(255, 215, 0, 0.12)",      # gold
    },
    {
        "label": "Current",
        "start": "2024-01-01",
        "end":   None,                            # None = present day
        "color": "rgba(173, 216, 230, 0.08)",    # light blue
    },
]


# ── COLOR PALETTE ─────────────────────────────────────────────────────────────
# One place for all colors. Used by both the analytics layer and the UI layer.
# Inspired by Bloomberg terminal meets modern dark UI.
COLORS = {
    # Layout
    "bg":           "#080c10",      # Near-black page background
    "card":         "#0e1318",      # Slightly lighter card surfaces
    "card_alt":     "#131a21",      # Alternating card background
    "border":       "#1e2d3d",      # Subtle borders
    "border_bright":"#2a3f52",      # Hover/active borders

    # Typography
    "text":         "#cdd9e5",      # Primary text
    "subtext":      "#6e8599",      # Secondary/muted text
    "accent":       "#58a6ff",      # Highlight accent (links, active tabs)

    # Status flags
    "green":        "#3fb950",      # Normal / healthy
    "amber":        "#d29922",      # Watch / elevated
    "red":          "#f85149",      # Extreme / stressed

    # Yield curve line colors (each tenor gets its own identity)
    "yield_3m":     "#64d8cb",      # Teal
    "yield_2y":     "#58a6ff",      # Blue
    "yield_5y":     "#a371f7",      # Purple
    "yield_10y":    "#ff9d6f",      # Orange
    "yield_30y":    "#ffa657",      # Amber-orange
    "ffr":          "#f47067",      # Muted red

    # Spread colors
    "spread_2y10y": "#79c0ff",      # Light blue
    "spread_3m10y": "#56d364",      # Green


    # Credit spread colors
    "ig":          "#58a6ff",      # Blue
    "hy":          "#f47067",      # Red-orange
    "bbb":         "#a371f7",      # Purple
    "ccc":         "#ff7b72",      # Bright red
    "stlfsi":      "#ffa657",      # Amber


    # Commodity colors
    "wti":          "#f97316",   # Orange  (oil)
    "gold":         "#eab308",   # Yellow  (gold)
    "silver":       "#94a3b8",   # Slate   (silver)
    "copper":       "#c2672e",   # Copper-brown
    "natgas":       "#22d3ee",   # Cyan    (gas)
    "breakeven":    "#a78bfa",   # Violet  (inflation expectations)
    "realyield":    "#34d399",   # Emerald (real yields)

    # Chart grid
    "grid":         "#161f29",      # Very subtle gridlines
}


# ── DASHBOARD METADATA ────────────────────────────────────────────────────────
DASH_TITLE    = "MACRO DASHBOARD"
DASH_SUBTITLE = "U.S. CENTRIC · RATES · CREDIT · COMMODITIES"
DASH_PORT     = 8050
CACHE_DIR     = ".cache"
CACHE_TTL_HOURS = 4     # How many hours before cached data is considered stale
