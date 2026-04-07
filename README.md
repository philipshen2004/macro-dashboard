# MACRO DASHBOARD — Week 1: Rates & Yield Curve

A U.S.-centric macro dashboard built in Python + Plotly Dash,
pulling live data from the Federal Reserve (FRED).

---

## QUICK START

### 1. Get a free FRED API key
→ https://fred.stlouisfed.org/docs/api/api_key.html
Takes 30 seconds. No credit card.

### 2. Install dependencies
```bash
cd macro_dashboard
pip install -r requirements.txt
```

### 3. Add your API key
Open `config.py` and set:
```python
FRED_API_KEY = "your_key_here"
```
Or set an environment variable (avoids hardcoding):
```bash
export FRED_API_KEY="your_key_here"   # Mac/Linux
set    FRED_API_KEY=your_key_here     # Windows
```

### 4. Run
```bash
python app.py
```
Open your browser at **http://127.0.0.1:8050**

---

## PROJECT STRUCTURE

```
macro_dashboard/
│
├── app.py                  ← Entry point. Run this.
├── config.py               ← All constants: API key, series IDs, colors, regimes
├── requirements.txt
│
├── data/
│   └── fetcher.py          ← FRED data pulls + disk caching
│
├── analytics/
│   └── stats.py            ← Z-scores, percentiles, regime stats
│
└── panels/
    └── rates.py            ← All charts + layout for Panel 1
```

---

## WHAT YOU'LL SEE (Panel 1)

| Element                       | What it tells you                                       |
|-------------------------------|----------------------------------------------------------|
| **Stats Table**               | All series: current level, 1M/3M change, z-scores, flag |
| **Yield Curve Bar**           | Today's curve shape (normal / flat / inverted)           |
| **FFR vs 2Y Chart**           | Is the Fed ahead or behind the market's expectations?    |
| **Historical Yields**         | 25 years of context with regime shading                  |
| **Spreads + Z-Score**         | 2Y10Y & 3M10Y in bps + rolling z-score bars             |

---

## FLAG SYSTEM

| Flag    | Color  | Condition                                    |
|---------|--------|----------------------------------------------|
| NORMAL  | Green  | Rolling z-score < 1.5 std devs              |
| WATCH   | Amber  | Rolling z-score ≥ 1.5 std devs (elevated)   |
| EXTREME | Red    | Rolling z-score ≥ 2.0 std devs (rare event) |

---

## DISK CACHE

FRED data is cached to `.cache/` on first run.
Cache expires after **4 hours** (configurable in `config.py → CACHE_TTL_HOURS`).
Click **↺ REFRESH DATA** in the app to force a live re-fetch anytime.

---

## ADDING WEEK 2 (Credit Markets)

1. Add FRED credit series IDs to `config.py → CREDIT_SERIES`
2. Add a fetch function to `data/fetcher.py`
3. Create `panels/credit.py` mirroring the structure of `panels/rates.py`
4. In `app.py`: enable the Credit tab and add an `elif tab == "credit"` branch

---

## DATA SOURCES

All data comes from **FRED** (Federal Reserve Bank of St. Louis).
Free, reliable, authoritative. Updated daily on business days.

Key series used:
- `DGS3MO / DGS2 / DGS5 / DGS10 / DGS30` — Treasury yields
- `FEDFUNDS` — Effective Federal Funds Rate
- `T10Y2Y` — 10Y minus 2Y spread (FRED pre-calculated)
- `T10Y3M` — 10Y minus 3M spread (FRED pre-calculated)
