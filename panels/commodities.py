# =============================================================================
# panels/commodities.py
# Builds every chart and layout element for Panel 3: Commodities.
#
# What commodities tell you:
#   GOLD        → real yield proxy, safe-haven demand, dollar stress
#   COPPER      → global industrial cycle (Dr. Copper)
#   OIL         → inflation pass-through, geopolitical risk, growth proxy
#   NATGAS      → energy inflation, regional (US-specific)
#   SILVER      → hybrid: part gold, part industrial (useful for confirmation)
#
# Key cross-asset relationships in this panel:
#   Gold vs Real Yields   → the most important: real yields drive gold inversely
#   Gold / Copper ratio   → rising = risk-off; falling = risk-on/growth
#   Oil vs Breakevens     → oil drags near-term inflation expectations
#   Real yields context   → TIPS real yield + breakeven decompose nominal yields
#
# Charts:
#   build_commodity_stats_table()  → summary table with z-scores + flags
#   build_price_history()          → normalized price index (all = 100 at start)
#   build_gold_vs_real_yields()    → gold price vs 10Y real yield (dual axis)
#   build_gold_copper_ratio()      → ratio + rolling z-score
#   build_breakeven_panel()        → 5Y + 10Y breakevens + real yields
#   build_commodity_heatmap()      → rolling return heatmap across timeframes
#   build_commodities_panel()      → assembles everything
# =============================================================================

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc, dash_table

from config import COLORS, REGIMES
from analytics.stats import rolling_zscore, historical_zscore, percentile_rank, flag_status

# ── SHARED LAYOUT DEFAULTS ────────────────────────────────────────────────────
# No 'margin' here — every chart sets its own (learned lesson from rates panel).

_BASE_LAYOUT = dict(
    paper_bgcolor = COLORS["card"],
    plot_bgcolor  = COLORS["card"],
    font          = dict(color=COLORS["text"], family="'JetBrains Mono', 'Courier New', monospace"),
    legend        = dict(
        bgcolor     = "rgba(0,0,0,0)",
        bordercolor = COLORS["border"],
        borderwidth = 1,
        font        = dict(size=11),
    ),
    hovermode = "x unified",
)

_AXIS_STYLE = dict(
    gridcolor  = COLORS["grid"],
    gridwidth  = 1,
    linecolor  = COLORS["border"],
    zeroline   = False,
    tickfont   = dict(size=10, color=COLORS["subtext"]),
    title_font = dict(size=11, color=COLORS["subtext"]),
)

# Metadata for each commodity and FRED series
COMM_META = {
    "WTI":          {"label": "WTI Crude",    "color": COLORS["wti"],       "unit": "USD/bbl"},
    "GOLD":         {"label": "Gold",         "color": COLORS["gold"],      "unit": "USD/oz"},
    "SILVER":       {"label": "Silver",       "color": COLORS["silver"],    "unit": "USD/oz"},
    "COPPER":       {"label": "Copper",       "color": COLORS["copper"],    "unit": "USD/lb"},
    "NATGAS":       {"label": "Nat Gas",      "color": COLORS["natgas"],    "unit": "USD/mmBtu"},
    "BREAKEVEN5Y":  {"label": "5Y Breakeven", "color": COLORS["breakeven"], "unit": "%"},
    "BREAKEVEN10Y": {"label": "10Y Breakeven","color": COLORS["breakeven"], "unit": "%"},
    "REALYIELD10Y": {"label": "10Y Real Yield","color": COLORS["realyield"],"unit": "%"},
    "REALYIELD5Y":  {"label": "5Y Real Yield", "color": COLORS["realyield"],"unit": "%"},
}

PRICE_COLS = ["WTI", "GOLD", "SILVER", "COPPER", "NATGAS"]
FRED_COLS  = ["BREAKEVEN5Y", "BREAKEVEN10Y", "REALYIELD10Y", "REALYIELD5Y"]


# ── SHARED HELPER: REGIME BANDS ───────────────────────────────────────────────

def _add_regime_bands(fig, row=None, col=None):
    kw = {}
    if row is not None:
        kw["row"] = row
        kw["col"] = col
    for r in REGIMES:
        x1 = r["end"] if r["end"] else "2027-01-01"
        fig.add_vrect(
            x0=r["start"], x1=x1,
            fillcolor=r["color"], layer="below", line_width=0,
            annotation_text=r["label"], annotation_position="top left",
            annotation_font=dict(size=8, color=COLORS["subtext"]),
            **kw,
        )


# ── CHART HELPERS ─────────────────────────────────────────────────────────────

def _pct_change(s: pd.Series, periods: int) -> float:
    """Return % change over last N periods, or NaN if insufficient data."""
    s = s.dropna()
    if len(s) <= periods:
        return float("nan")
    return float((s.iloc[-1] / s.iloc[-periods] - 1) * 100)


# ── STATS TABLE ───────────────────────────────────────────────────────────────

def build_commodity_stats_table(comm_df: pd.DataFrame) -> dash_table.DataTable:
    """
    Summary table for all commodities and inflation series.

    Columns: Series | Current | 1M % | 3M % | 1Y % | Roll Z (1Y) | Hist Z | Pctile | Flag

    For price series (WTI, Gold etc.) we show % returns — that's more meaningful
    than z-scores on raw price levels which trend over time.
    For FRED series (breakevens, real yields) we show % point changes.
    """
    rows = []

    display_order = ["WTI", "GOLD", "SILVER", "COPPER", "NATGAS",
                     "BREAKEVEN5Y", "BREAKEVEN10Y", "REALYIELD10Y", "REALYIELD5Y"]

    for code in display_order:
        if code not in comm_df.columns:
            continue
        meta = COMM_META.get(code, {"label": code, "color": COLORS["text"], "unit": ""})
        s = comm_df[code].dropna()
        if len(s) < 30:
            continue

        is_price = code in PRICE_COLS
        current  = float(s.iloc[-1])

        if is_price:
            chg_1m = _pct_change(s, 22)
            chg_3m = _pct_change(s, 63)
            chg_1y = _pct_change(s, 252)
            def fmt(v): return f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
            fmt_current = f"{current:,.2f}"
        else:
            # For rate/spread series show basis-point moves
            ago_1m = float(s.iloc[-22]) if len(s) > 22 else float(s.iloc[0])
            ago_3m = float(s.iloc[-63]) if len(s) > 63 else float(s.iloc[0])
            ago_1y = float(s.iloc[-252]) if len(s) > 252 else float(s.iloc[0])
            chg_1m = (current - ago_1m) * 100   # convert % to bps
            chg_3m = (current - ago_3m) * 100
            chg_1y = (current - ago_1y) * 100
            def fmt(v): return f"+{v:.0f}bps" if v > 0 else f"{v:.0f}bps"
            fmt_current = f"{current:.2f}%"

        rz_series = rolling_zscore(s)
        rz_now    = float(rz_series.iloc[-1]) if not rz_series.dropna().empty else float("nan")
        hz        = historical_zscore(s)
        pct       = percentile_rank(s)
        flag      = flag_status(rz_now)

        rows.append({
            "Series":       meta["label"],
            "Current":      fmt_current,
            "Unit":         meta["unit"],
            "1M":           fmt(chg_1m) if not np.isnan(chg_1m) else "—",
            "3M":           fmt(chg_3m) if not np.isnan(chg_3m) else "—",
            "1Y":           fmt(chg_1y) if not np.isnan(chg_1y) else "—",
            "Roll Z (1Y)":  round(rz_now, 2) if not np.isnan(rz_now) else "—",
            "Hist Z":       round(hz, 2)      if not np.isnan(hz)     else "—",
            "Percentile":   f"{pct:.0f}th",
            "Flag":         flag["label"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return html.Div("No commodity data.", style={"color": COLORS["subtext"]})

    return dash_table.DataTable(
        id="commodity-stats-table",
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        sort_action="native",
        style_table={
            "overflowX": "auto", "borderRadius": "6px",
            "border": f"1px solid {COLORS['border']}",
        },
        style_header={
            "backgroundColor": COLORS["border"], "color": COLORS["subtext"],
            "fontWeight": "600", "fontSize": "11px", "letterSpacing": "0.5px",
            "padding": "10px 14px", "border": "none", "fontFamily": "monospace",
        },
        style_cell={
            "backgroundColor": COLORS["card"], "color": COLORS["text"],
            "fontSize": "12px", "padding": "9px 14px",
            "border": f"1px solid {COLORS['border']}",
            "fontFamily": "'JetBrains Mono', 'Courier New', monospace",
            "whiteSpace": "nowrap",
        },
        style_cell_conditional=[
            {"if": {"column_id": "Series"}, "color": COLORS["subtext"], "fontWeight": "500"},
        ],
        style_data_conditional=[
            {"if": {"filter_query": '{Flag} = "NORMAL"',  "column_id": "Flag"},
             "color": COLORS["green"], "fontWeight": "600"},
            {"if": {"filter_query": '{Flag} = "WATCH"',   "column_id": "Flag"},
             "color": COLORS["amber"], "fontWeight": "600"},
            {"if": {"filter_query": '{Flag} = "EXTREME"', "column_id": "Flag"},
             "color": COLORS["red"],   "fontWeight": "600"},
            # Shade FRED rows differently
            {"if": {"filter_query": '{Unit} = "%"'},
             "backgroundColor": COLORS["card_alt"]},
        ],
        page_size=10,
    )


# ── CHART 1: NORMALISED PRICE HISTORY ─────────────────────────────────────────

def build_price_history(comm_df: pd.DataFrame) -> go.Figure:
    """
    Index all commodity prices to 100 at START_DATE so you can directly
    compare their relative performance on a single axis.

    Why normalise?
    Gold at $2,500 and Copper at $4.50 are on completely different scales.
    Normalising shows you: "If you bought each one on day 1, which has
    performed best?" — pure relative performance stripped of price level.

    The spread between lines is the signal: Gold and Copper diverging
    signals the risk-off trade; converging = risk-on consensus.
    """
    avail = [c for c in PRICE_COLS if c in comm_df.columns]
    if not avail:
        return go.Figure()

    fig = go.Figure()
    _add_regime_bands(fig)

    for code in avail:
        s = comm_df[code].dropna()
        if s.empty:
            continue
        # Normalize: divide every value by the first valid price
        s_norm = (s / s.iloc[0]) * 100
        meta   = COMM_META[code]
        fig.add_trace(go.Scatter(
            x=s_norm.index, y=s_norm,
            name=meta["label"],
            line=dict(color=meta["color"], width=1.8),
            hovertemplate=(
                f"%{{x|%b %d %Y}} — {meta['label']}: "
                f"<b>%{{y:.1f}}</b> (base 100)<extra></extra>"
            ),
        ))

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Commodity Performance — Indexed to 100 at Start (2000)",
                   font=dict(size=13, color=COLORS["text"])),
        yaxis=dict(**_AXIS_STYLE, title="Index (base=100)"),
        xaxis=dict(**_AXIS_STYLE),
        height=360,
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig


# ── CHART 2: GOLD VS REAL YIELDS ──────────────────────────────────────────────

def build_gold_vs_real_yields(comm_df: pd.DataFrame) -> go.Figure:
    """
    Dual-axis chart: Gold price (left axis) vs 10Y TIPS Real Yield (right axis,
    inverted so the inverse relationship is visually obvious).

    This is THE most important commodity/rates cross-asset relationship:
      Falling real yields → opportunity cost of holding gold falls → gold rises
      Rising real yields  → gold becomes less attractive vs yield-bearing assets

    When gold and real yields DECOUPLE (gold rising despite rising real yields),
    it signals exceptional safe-haven demand — typically geopolitical stress
    or a loss of confidence in fiat currency/central banks.

    The right Y-axis is INVERTED so both lines moving up = same direction
    in economic terms. A visual overlap confirms the relationship is intact;
    divergence is the signal.
    """
    if "GOLD" not in comm_df.columns or "REALYIELD10Y" not in comm_df.columns:
        return go.Figure()

    aligned = comm_df[["GOLD", "REALYIELD10Y"]].dropna()
    gold    = aligned["GOLD"]
    real_y  = aligned["REALYIELD10Y"]

    # Rolling 90-day correlation for annotation
    corr_90d = gold.rolling(90).corr(real_y)
    current_corr = float(corr_90d.dropna().iloc[-1]) if not corr_90d.dropna().empty else float("nan")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    _add_regime_bands(fig)

    fig.add_trace(go.Scatter(
        x=gold.index, y=gold,
        name="Gold (USD/oz)",
        line=dict(color=COLORS["gold"], width=2),
        hovertemplate="%{x|%b %d %Y} — Gold: <b>$%{y:,.0f}</b><extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=real_y.index, y=real_y,
        name="10Y Real Yield (inverted →)",
        line=dict(color=COLORS["realyield"], width=1.8, dash="dot"),
        hovertemplate="%{x|%b %d %Y} — 10Y Real: <b>%{y:.2f}%</b><extra></extra>",
    ), secondary_y=True)

    corr_color = COLORS["green"] if current_corr < -0.3 else (
                 COLORS["amber"] if current_corr < 0 else COLORS["red"])
    fig.add_annotation(
        text=f"90d Corr(Gold, Real Yield): {current_corr:.2f}  "
             f"{'✓ intact' if current_corr < -0.3 else '⚠ decoupling'}",
        xref="paper", yref="paper", x=0.01, y=0.96,
        showarrow=False,
        font=dict(color=corr_color, size=11, family="monospace"),
    )

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Gold vs 10Y Real Yield (right axis inverted — inverse relationship)",
                   font=dict(size=13, color=COLORS["text"])),
        height=360,
        margin=dict(l=60, r=70, t=50, b=40),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=COLORS["border"],
            borderwidth=1, font=dict(size=11),
        ),
    )
    fig.update_yaxes(
        **_AXIS_STYLE, title_text="Gold (USD/oz)", secondary_y=False
    )
    fig.update_yaxes(
        **_AXIS_STYLE, title_text="10Y Real Yield (%, inverted)",
        secondary_y=True,
        autorange="reversed",   # ← invert right axis
    )
    fig.update_xaxes(**_AXIS_STYLE)
    return fig


# ── CHART 3: GOLD / COPPER RATIO ──────────────────────────────────────────────

def build_gold_copper_ratio(comm_df: pd.DataFrame) -> go.Figure:
    """
    Three-row subplot:
      Row 1 — Gold price
      Row 2 — Copper price
      Row 3 — Gold/Copper ratio + rolling 1Y z-score coloring

    The Gold/Copper ratio is a pure risk-sentiment barometer:

      HIGH ratio (gold outperforms copper):
        → Risk-off. Markets are worried. Investors flee to gold.
          Copper demand (industrial, construction) is falling.
          Historically precedes equity drawdowns and recessions.

      LOW ratio (copper outperforms gold):
        → Risk-on. Growth optimism. Industrial demand is robust.
          Historically a supportive environment for equities.

    The z-score coloring on the ratio bars immediately tells you whether
    today's reading is historically extreme in either direction.
    """
    if "GOLD" not in comm_df.columns or "COPPER" not in comm_df.columns:
        return go.Figure()

    aligned    = comm_df[["GOLD", "COPPER"]].dropna()
    gold       = aligned["GOLD"]
    copper     = aligned["COPPER"]
    # Copper is quoted in USD/lb; Gold in USD/oz. The ratio is dimensionally
    # consistent as long as we use the same raw prices consistently.
    ratio      = gold / copper
    rz         = rolling_zscore(ratio)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.3, 0.3, 0.4],
        vertical_spacing=0.04,
        subplot_titles=["Gold (USD/oz)", "Copper (USD/lb)", "Gold / Copper Ratio  ·  z-score coloring"],
    )

    _add_regime_bands(fig, row=1, col=1)
    _add_regime_bands(fig, row=2, col=1)

    fig.add_trace(go.Scatter(
        x=gold.index, y=gold, name="Gold",
        line=dict(color=COLORS["gold"], width=1.8),
        hovertemplate="%{x|%b %d %Y} — Gold: <b>$%{y:,.0f}</b><extra></extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=copper.index, y=copper, name="Copper",
        line=dict(color=COLORS["copper"], width=1.8),
        hovertemplate="%{x|%b %d %Y} — Copper: <b>$%{y:.3f}/lb</b><extra></extra>",
    ), row=2, col=1)

    # Ratio bars colored by z-score magnitude
    ratio_colors = [
        COLORS["red"]   if not np.isnan(z) and abs(z) >= 2.0 else
        COLORS["amber"] if not np.isnan(z) and abs(z) >= 1.5 else
        COLORS["accent"]
        for z in rz.reindex(ratio.index).fillna(0)
    ]
    fig.add_trace(go.Bar(
        x=ratio.index, y=ratio,
        name="Gold/Copper",
        marker=dict(color=ratio_colors, line=dict(width=0)),
        hovertemplate="%{x|%b %d %Y} — Ratio: <b>%{y:.0f}x</b><extra></extra>",
    ), row=3, col=1)

    # Annotations: current ratio and regime interpretation
    cur_ratio = float(ratio.iloc[-1])
    cur_rz    = float(rz.dropna().iloc[-1]) if not rz.dropna().empty else float("nan")
    hist_mean = float(ratio.mean())
    sentiment = "RISK-OFF ↑" if cur_ratio > hist_mean * 1.1 else (
                "RISK-ON  ↓" if cur_ratio < hist_mean * 0.9 else "NEUTRAL")
    s_color   = COLORS["amber"] if "OFF" in sentiment else (
                COLORS["green"] if "ON" in sentiment else COLORS["subtext"])

    fig.add_annotation(
        text=f"Current: {cur_ratio:.0f}x  |  Hist avg: {hist_mean:.0f}x  |  {sentiment}",
        xref="paper", yref="paper", x=0.01, y=0.03,
        showarrow=False,
        font=dict(color=s_color, size=11, family="monospace"),
    )

    for r in [1, 2, 3]:
        fig.update_yaxes(**_AXIS_STYLE, row=r, col=1)
        fig.update_xaxes(**_AXIS_STYLE, row=r, col=1)

    fig.update_yaxes(title_text="USD/oz",  row=1, col=1)
    fig.update_yaxes(title_text="USD/lb",  row=2, col=1)
    fig.update_yaxes(title_text="ratio",   row=3, col=1)

    fig.update_layout(
        **_BASE_LAYOUT,
        height=540,
        showlegend=False,
        margin=dict(l=60, r=20, t=40, b=40),
    )
    fig.update_annotations(font=dict(color=COLORS["subtext"], size=11))
    return fig


# ── CHART 4: BREAKEVENS + REAL YIELDS ─────────────────────────────────────────

def build_breakeven_panel(comm_df: pd.DataFrame) -> go.Figure:
    """
    Two-row subplot decomposing the nominal yield into its two components:

      Nominal yield = Real yield + Inflation expectation (breakeven)

      Row 1 — 5Y and 10Y inflation breakevens
      Row 2 — 5Y and 10Y TIPS real yields

    Why this matters for commodities:
      - Rising breakevens → inflation expectations rising → commodity tailwind
      - Rising real yields → tightening real conditions → commodity headwind
      - When breakevens rise AND real yields fall: goldilocks for gold/commodities
      - When both rise: growth + inflation (commodities mixed; oil often benefits)

    The shape of the breakeven curve (5Y vs 10Y) also matters:
      - 5Y > 10Y → near-term inflation fears, expect moderation later
      - 10Y > 5Y → persistent long-run inflation expectations (more concerning)
    """
    avail_be = [c for c in ["BREAKEVEN5Y", "BREAKEVEN10Y"] if c in comm_df.columns]
    avail_ry = [c for c in ["REALYIELD5Y", "REALYIELD10Y"]  if c in comm_df.columns]

    if not avail_be and not avail_ry:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.5, 0.5],
        vertical_spacing=0.06,
        subplot_titles=["Inflation Breakevens (%) — Market's Inflation Expectations",
                        "TIPS Real Yields (%) — Real Rates After Inflation"],
    )

    _add_regime_bands(fig, row=1, col=1)
    _add_regime_bands(fig, row=2, col=1)

    be_styles = {
        "BREAKEVEN5Y":  dict(color=COLORS["breakeven"], width=1.8, dash="solid"),
        "BREAKEVEN10Y": dict(color=COLORS["breakeven"], width=1.8, dash="dot"),
    }
    ry_styles = {
        "REALYIELD5Y":  dict(color=COLORS["realyield"], width=1.8, dash="solid"),
        "REALYIELD10Y": dict(color=COLORS["realyield"], width=1.8, dash="dot"),
    }

    for code in avail_be:
        s    = comm_df[code].dropna()
        meta = COMM_META[code]
        fig.add_trace(go.Scatter(
            x=s.index, y=s, name=meta["label"],
            line=be_styles[code],
            hovertemplate=f"%{{x|%b %d %Y}} — {meta['label']}: <b>%{{y:.2f}}%</b><extra></extra>",
        ), row=1, col=1)

    # Zero line on real yields
    fig.add_hline(y=0, line=dict(color=COLORS["red"], dash="dash", width=0.8), row=2, col=1)

    for code in avail_ry:
        s    = comm_df[code].dropna()
        meta = COMM_META[code]
        fig.add_trace(go.Scatter(
            x=s.index, y=s, name=meta["label"],
            line=ry_styles[code],
            hovertemplate=f"%{{x|%b %d %Y}} — {meta['label']}: <b>%{{y:.2f}}%</b><extra></extra>",
        ), row=2, col=1)

    for r in [1, 2]:
        fig.update_yaxes(**_AXIS_STYLE, title_text="%", row=r, col=1)
        fig.update_xaxes(**_AXIS_STYLE, row=r, col=1)

    fig.update_layout(
        **_BASE_LAYOUT,
        height=420,
        margin=dict(l=60, r=20, t=40, b=40),
    )
    fig.update_annotations(font=dict(color=COLORS["subtext"], size=11))
    return fig


# ── CHART 5: RETURN HEATMAP ───────────────────────────────────────────────────

def build_commodity_heatmap(comm_df: pd.DataFrame) -> go.Figure:
    """
    Heatmap: rows = commodities, columns = lookback windows (1W / 1M / 3M / 6M / 1Y / 3Y).

    This is the fastest way to scan the full commodity complex at a glance:
      - Deep red across a row → commodity under severe pressure
      - Deep green across a row → commodity in a strong trend
      - Red short-term / green long-term → recent pullback in uptrend (opportunity?)
      - Green short-term / red long-term → dead-cat bounce in downtrend (trap?)

    Colour scale is clamped at ±30% so extreme outliers (oil during COVID)
    don't wash out the rest of the heatmap.
    """
    avail = [c for c in PRICE_COLS if c in comm_df.columns]
    if not avail:
        return go.Figure()

    windows = {
        "1W":  5,
        "1M":  22,
        "3M":  63,
        "6M":  126,
        "1Y":  252,
        "3Y":  756,
    }

    z_data, labels, hover_text = [], [], []
    for code in avail:
        s = comm_df[code].dropna()
        row_z, row_hover = [], []
        for wlabel, wperiods in windows.items():
            chg = _pct_change(s, wperiods)
            row_z.append(round(chg, 1) if not np.isnan(chg) else None)
            row_hover.append(
                f"{COMM_META[code]['label']} {wlabel}: "
                f"{'N/A' if np.isnan(chg) else f'{chg:+.1f}%'}"
            )
        z_data.append(row_z)
        hover_text.append(row_hover)
        labels.append(COMM_META[code]["label"])

    fig = go.Figure(go.Heatmap(
        z=z_data,
        x=list(windows.keys()),
        y=labels,
        text=[[f"{v:+.1f}%" if v is not None else "N/A" for v in row] for row in z_data],
        texttemplate="%{text}",
        textfont=dict(size=11, family="monospace"),
        hovertext=hover_text,
        hovertemplate="%{hovertext}<extra></extra>",
        colorscale=[
            [0.0,  "rgba(248, 81, 73, 0.90)"],   # deep red   (−30%)
            [0.35, "rgba(248, 81, 73, 0.20)"],   # faded red
            [0.5,  "rgba(14, 19, 24, 0.0)"],     # neutral (transparent)
            [0.65, "rgba(63, 185, 80, 0.20)"],   # faded green
            [1.0,  "rgba(63, 185, 80, 0.90)"],   # deep green (+30%)
        ],
        zmid=0,
        zmin=-30, zmax=30,
        showscale=True,
        colorbar=dict(
            title=dict(text="%", font=dict(color=COLORS["subtext"], size=11)),
            tickfont=dict(color=COLORS["subtext"], size=10),
            thickness=12, len=0.8,
            outlinewidth=0,
        ),
    ))

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Commodity Return Heatmap  ·  % change by lookback window",
                   font=dict(size=13, color=COLORS["text"])),
        xaxis=dict(**_AXIS_STYLE, side="top"),
        yaxis=dict(
            **_AXIS_STYLE,
            autorange="reversed",  # top row = first commodity
        ),
        height=50 + len(avail) * 52,
        margin=dict(l=90, r=80, t=70, b=20),
    )
    return fig


# ── LAYOUT HELPERS ────────────────────────────────────────────────────────────

def _card(children, extra_style=None):
    style = {
        "backgroundColor": COLORS["card"],
        "border":          f"1px solid {COLORS['border']}",
        "borderRadius":    "8px",
        "padding":         "16px 20px",
        "marginBottom":    "16px",
    }
    if extra_style:
        style.update(extra_style)
    return html.Div(children, style=style)

def _section_title(text, sub=""):
    return html.Div([
        html.Span(text, style={
            "color": COLORS["text"], "fontSize": "12px",
            "fontWeight": "600", "letterSpacing": "0.8px", "fontFamily": "monospace",
        }),
        html.Span(f"  {sub}", style={
            "color": COLORS["subtext"], "fontSize": "11px",
        }) if sub else None,
    ], style={"marginBottom": "10px"})


# ── PANEL ASSEMBLER ───────────────────────────────────────────────────────────

def build_commodities_panel(comm_df: pd.DataFrame) -> html.Div:
    """
    Assembles all Panel 3 components into a Dash layout.

    Layout:
      ┌─────────────────────────────────────────────────────────┐
      │ STATS TABLE  (all commodities + inflation context)      │
      ├──────────────────────────┬──────────────────────────────┤
      │  RETURN HEATMAP          │  BREAKEVEN + REAL YIELDS     │
      ├──────────────────────────┴──────────────────────────────┤
      │  NORMALISED PRICE HISTORY  (all indexed to 100)         │
      ├──────────────────────────┬──────────────────────────────┤
      │  GOLD vs REAL YIELDS     │  GOLD / COPPER RATIO         │
      └──────────────────────────┴──────────────────────────────┘
    """
    cfg = {"displayModeBar": False, "responsive": True}

    if comm_df is None or comm_df.empty:
        return html.Div(
            "⚠  No commodity data available. Check yfinance is installed "
            "(pip install yfinance) and restart the app.",
            style={"color": COLORS["amber"], "padding": "40px",
                   "fontFamily": "monospace", "fontSize": "13px"},
        )

    return html.Div([

        # ── Stats Table ──────────────────────────────────────────────────────
        _card([
            _section_title("COMMODITY & INFLATION READINGS",
                           "prices · % returns · z-scores · flags"),
            build_commodity_stats_table(comm_df),
        ]),

        # ── Row: Heatmap + Breakevens ────────────────────────────────────────
        html.Div([
            _card([
                _section_title("RETURN HEATMAP",
                               "% change · red=loss · green=gain · clamped ±30%"),
                dcc.Graph(figure=build_commodity_heatmap(comm_df), config=cfg),
            ], extra_style={"flex": "2", "minWidth": "0", "marginBottom": "0"}),

            _card([
                _section_title("BREAKEVENS & REAL YIELDS",
                               "inflation expectations · real rate context"),
                dcc.Graph(figure=build_breakeven_panel(comm_df), config=cfg),
            ], extra_style={"flex": "3", "minWidth": "0", "marginBottom": "0"}),

        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # ── Normalised History ───────────────────────────────────────────────
        _card([
            _section_title("NORMALISED PRICE HISTORY",
                           "all indexed to 100 at 2000 · regime-shaded"),
            dcc.Graph(figure=build_price_history(comm_df), config=cfg),
        ]),

        # ── Row: Gold vs Real Yields + Gold/Copper ───────────────────────────
        html.Div([
            _card([
                _section_title("GOLD vs 10Y REAL YIELD",
                               "right axis inverted · divergence = safe-haven demand"),
                dcc.Graph(figure=build_gold_vs_real_yields(comm_df), config=cfg),
            ], extra_style={"flex": "1", "minWidth": "0", "marginBottom": "0"}),

            _card([
                _section_title("GOLD / COPPER RATIO",
                               "rising = risk-off · falling = risk-on / growth"),
                dcc.Graph(figure=build_gold_copper_ratio(comm_df), config=cfg),
            ], extra_style={"flex": "1", "minWidth": "0", "marginBottom": "0"}),

        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

    ], style={"padding": "0"})
