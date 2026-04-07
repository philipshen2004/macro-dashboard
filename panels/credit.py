# =============================================================================
# panels/credit.py
# Builds every chart and layout element for Panel 2: Credit Markets.
#
# What credit markets tell you:
#   Spreads = the yield premium credit bonds pay over equivalent Treasuries.
#   When spreads WIDEN → markets are pricing in more default/liquidity risk.
#   When spreads TIGHTEN → risk appetite is high, credit is in demand.
#
# The quality ladder (IG → BBB → HY → CCC) tells you WHERE stress is:
#   Stress only in CCC?  → idiosyncratic / bottom-of-market problem
#   Stress reaching BBB? → systemic: IG investors starting to worry
#   Stress in IG?        → full credit crunch (GFC-level)


# Charts in this panel:
#   build_credit_stats_table()   → summary table with flags for all 4 spreads
#   build_spread_history()       → IG + HY + BBB OAS history with regime bands
#   build_hy_ig_ratio()          → HY/IG ratio + z-score (relative value signal)
#   build_quality_stack()        → IG / BBB / HY / CCC spread ladder (stress map)
#   build_stlfsi_chart()         → St. Louis Financial Stress Index
#   build_credit_panel()         → assembles everything into a Dash layout
# =============================================================================

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc, dash_table

from config import COLORS, REGIMES
from analytics.stats import rolling_zscore, historical_zscore, percentile_rank, flag_status

# ── SHARED LAYOUT DEFAULTS ────────────────────────────────────────────────────
# Identical pattern to panels/rates.py — must NOT include 'margin' here
# (each chart sets its own margin to avoid the duplicate-keyword error).

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

# Series metadata: display name, color, description used in table + tooltips
CREDIT_META = {
    "IG":     {"label": "IG OAS",       "color": COLORS["ig"],     "desc": "Investment Grade"},
    "HY":     {"label": "HY OAS",       "color": COLORS["hy"],     "desc": "High Yield"},
    "BBB":    {"label": "BBB OAS",      "color": COLORS["bbb"],    "desc": "BBB Corporate (IG floor)"},
    "CCC":    {"label": "CCC OAS",      "color": COLORS["ccc"],    "desc": "CCC & Lower (distress)"},
    "STLFSI": {"label": "Stress Index", "color": COLORS["stlfsi"], "desc": "St. Louis Fed FSI"},
}


# ── SHARED HELPER: REGIME BANDS ───────────────────────────────────────────────

def _add_regime_bands(fig, row=None, col=None):
    """Shade historical regime periods on any chart with a time axis."""
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


# ── STATS TABLE ───────────────────────────────────────────────────────────────

def build_credit_stats_table(credit_df: pd.DataFrame) -> dash_table.DataTable:
    """
    Summary table for all credit series.

    Columns: Series | Current (bps) | 1M Chg | 3M Chg | Roll Z (1Y) | Hist Z | Pctile | Flag

    Spreads are shown in basis points (OAS % × 100).
    STLFSI is shown as raw index level (not bps).

    The Flag column is based on the ROLLING z-score, which answers
    "how unusual is this vs the past year?" — more actionable than
    the full-history z-score for day-to-day monitoring.
    """
    rows = []
    for code, meta in CREDIT_META.items():
        if code not in credit_df.columns:
            continue
        s_raw = credit_df[code].dropna()
        if len(s_raw) < 30:
            continue

        # Convert OAS % → bps for spread series; STLFSI stays as-is
        is_spread = code != "STLFSI"
        s = s_raw * 100 if is_spread else s_raw
        unit = "bps" if is_spread else "idx"

        current = s.iloc[-1]
        ago_1m  = s.iloc[-22]  if len(s) > 22  else s.iloc[0]
        ago_3m  = s.iloc[-63]  if len(s) > 63  else s.iloc[0]
        chg_1m  = current - ago_1m
        chg_3m  = current - ago_3m

        rz_series = rolling_zscore(s)
        rz_now    = float(rz_series.iloc[-1]) if not rz_series.dropna().empty else float("nan")
        hz        = historical_zscore(s)
        pct       = percentile_rank(s)
        flag      = flag_status(rz_now)

        def fmt_chg(v):
            return f"+{v:.1f}" if v > 0 else f"{v:.1f}"

        rows.append({
            "Series":        meta["label"],
            "Current":       f"{current:.1f} {unit}",
            "1M Chg":        fmt_chg(chg_1m),
            "3M Chg":        fmt_chg(chg_3m),
            "Roll Z (1Y)":   round(rz_now, 2) if not np.isnan(rz_now) else "—",
            "Hist Z":        round(hz, 2)      if not np.isnan(hz)     else "—",
            "Percentile":    f"{pct:.0f}th",
            "Flag":          flag["label"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return html.Div("No credit data available.", style={"color": COLORS["subtext"]})

    return dash_table.DataTable(
        id       = "credit-stats-table",
        data     = df.to_dict("records"),
        columns  = [{"name": c, "id": c} for c in df.columns],
        sort_action = "native",
        style_table = {
            "overflowX": "auto",
            "borderRadius": "6px",
            "border": f"1px solid {COLORS['border']}",
        },
        style_header = {
            "backgroundColor": COLORS["border"],
            "color":           COLORS["subtext"],
            "fontWeight":      "600",
            "fontSize":        "11px",
            "letterSpacing":   "0.5px",
            "padding":         "10px 14px",
            "border":          "none",
            "fontFamily":      "monospace",
        },
        style_cell = {
            "backgroundColor": COLORS["card"],
            "color":           COLORS["text"],
            "fontSize":        "12px",
            "padding":         "9px 14px",
            "border":          f"1px solid {COLORS['border']}",
            "fontFamily":      "'JetBrains Mono', 'Courier New', monospace",
            "whiteSpace":      "nowrap",
        },
        style_cell_conditional = [
            {"if": {"column_id": "Series"}, "color": COLORS["subtext"], "fontWeight": "500"},
        ],
        style_data_conditional = [
            {"if": {"filter_query": '{Flag} = "NORMAL"',  "column_id": "Flag"},
             "color": COLORS["green"], "fontWeight": "600"},
            {"if": {"filter_query": '{Flag} = "WATCH"',   "column_id": "Flag"},
             "color": COLORS["amber"], "fontWeight": "600"},
            {"if": {"filter_query": '{Flag} = "EXTREME"', "column_id": "Flag"},
             "color": COLORS["red"],   "fontWeight": "600"},
            # Shade CCC row to signal it's the stress tier
            {"if": {"filter_query": '{Series} = "CCC OAS"'},
             "backgroundColor": COLORS["card_alt"]},
        ],
        page_size = 8,
    )


# ── CHART 1: SPREAD HISTORY ───────────────────────────────────────────────────

def build_spread_history(credit_df: pd.DataFrame) -> go.Figure:
    """
    Multi-line historical chart: IG, HY, and BBB OAS in basis points.

    The key thing to watch is SPREAD DIRECTION, not just level:
      - All three rising together  → broad credit stress
      - HY rising, IG flat         → selective risk-off (normal)
      - BBB rising toward HY level → fallen-angel risk building

    COVID spike (2020) and GFC spike (2008-09) visible as reference points.
    The current level relative to those spikes tells you how stressed we are.
    """
    fig = go.Figure()
    _add_regime_bands(fig)

    for code in ["IG", "BBB", "HY"]:
        if code not in credit_df.columns:
            continue
        meta = CREDIT_META[code]
        s_bps = credit_df[code].dropna() * 100
        fig.add_trace(go.Scatter(
            x=s_bps.index, y=s_bps,
            name=meta["label"],
            line=dict(color=meta["color"], width=1.8),
            hovertemplate=f"%{{x|%b %d %Y}} — {meta['label']}: <b>%{{y:.0f}} bps</b><extra></extra>",
        ))

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="Credit Spread History — IG / BBB / HY OAS (bps)",
                   font=dict(size=13, color=COLORS["text"])),
        yaxis=dict(**_AXIS_STYLE, title="OAS (bps)"),
        xaxis=dict(**_AXIS_STYLE),
        height=360,
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig


# ── CHART 2: HY / IG RATIO ───────────────────────────────────────────────────

def build_hy_ig_ratio(credit_df: pd.DataFrame) -> go.Figure:
    """
    Three-row subplot:
      Row 1 — HY spread in bps
      Row 2 — IG spread in bps (for direct comparison)
      Row 3 — HY/IG ratio + rolling z-score coloring

    The HY/IG RATIO is a relative value signal:
      High ratio  → HY is expensive relative to IG (risk-on, spreads compressed)
                    Historically a contrarian warning: HY priced for perfection
      Low ratio   → HY is cheap relative to IG (risk-off, stress in junk)

    Watching the RATIO rather than absolute levels strips out the common
    rate/macro factor and isolates pure credit differentiation.
    """
    if "HY" not in credit_df.columns or "IG" not in credit_df.columns:
        return go.Figure()

    aligned = credit_df[["HY", "IG"]].dropna()
    hy_bps  = aligned["HY"] * 100
    ig_bps  = aligned["IG"] * 100
    ratio   = hy_bps / ig_bps
    rz      = rolling_zscore(ratio)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.35, 0.35, 0.30],
        vertical_spacing=0.05,
        subplot_titles=["HY OAS (bps)", "IG OAS (bps)", "HY / IG Ratio  ·  z-score coloring"],
    )

    _add_regime_bands(fig, row=1, col=1)
    _add_regime_bands(fig, row=2, col=1)

    # HY line
    fig.add_trace(go.Scatter(
        x=hy_bps.index, y=hy_bps,
        name="HY", line=dict(color=COLORS["hy"], width=1.8),
        hovertemplate="%{x|%b %d %Y} — HY: <b>%{y:.0f} bps</b><extra></extra>",
    ), row=1, col=1)

    # IG line
    fig.add_trace(go.Scatter(
        x=ig_bps.index, y=ig_bps,
        name="IG", line=dict(color=COLORS["ig"], width=1.8),
        hovertemplate="%{x|%b %d %Y} — IG: <b>%{y:.0f} bps</b><extra></extra>",
    ), row=2, col=1)

    # Ratio bars, colored by z-score magnitude
    ratio_colors = [
        COLORS["red"]   if not np.isnan(z) and abs(z) >= 2.0 else
        COLORS["amber"] if not np.isnan(z) and abs(z) >= 1.5 else
        COLORS["accent"]
        for z in rz.reindex(ratio.index).fillna(0)
    ]
    fig.add_trace(go.Bar(
        x=ratio.index, y=ratio,
        name="HY/IG Ratio",
        marker=dict(color=ratio_colors, line=dict(width=0)),
        hovertemplate="%{x|%b %d %Y} — Ratio: <b>%{y:.2f}x</b><extra></extra>",
    ), row=3, col=1)

    # Current ratio annotation
    current_ratio = float(ratio.iloc[-1])
    current_rz    = float(rz.dropna().iloc[-1]) if not rz.dropna().empty else float("nan")
    flag_color = (COLORS["red"] if abs(current_rz) >= 2.0 else
                  COLORS["amber"] if abs(current_rz) >= 1.5 else COLORS["subtext"])
    fig.add_annotation(
        text=f"Current: {current_ratio:.2f}x  (Z={current_rz:.2f})",
        xref="paper", yref="paper", x=0.01, y=0.03,
        showarrow=False,
        font=dict(color=flag_color, size=11, family="monospace"),
    )

    for r in [1, 2, 3]:
        fig.update_yaxes(**_AXIS_STYLE, row=r, col=1)
        fig.update_xaxes(**_AXIS_STYLE, row=r, col=1)

    fig.update_yaxes(title_text="bps", row=1, col=1)
    fig.update_yaxes(title_text="bps", row=2, col=1)
    fig.update_yaxes(title_text="ratio", row=3, col=1)

    fig.update_layout(
        **_BASE_LAYOUT,
        height=500,
        showlegend=False,
        margin=dict(l=60, r=20, t=40, b=40),
    )
    fig.update_annotations(font=dict(color=COLORS["subtext"], size=11))
    return fig


# ── CHART 3: QUALITY STACK ────────────────────────────────────────────────────

def build_quality_stack(credit_df: pd.DataFrame) -> go.Figure:
    """
    Four-panel subplot showing the spread for each credit quality tier
    over the past 5 years (zoomed in for tactical relevance).

    IG → BBB → HY → CCC is the quality ladder from highest to lowest.

    The Z-SCORE BAND behind each line (shaded ±1 std dev) shows whether
    today's spread is inside or outside normal range for that tier.

    Reading this chart:
      - All four tiers trending up   → broad de-risking
      - Only CCC spiking             → specific distress, not systemic
      - BBB nearing HY levels        → fallen-angel risk (major signal)
    """
    codes  = ["IG", "BBB", "HY", "CCC"]
    avail  = [c for c in codes if c in credit_df.columns]
    n      = len(avail)
    if n == 0:
        return go.Figure()

    titles = [f"{CREDIT_META[c]['label']}  ({CREDIT_META[c]['desc']})" for c in avail]
    fig = make_subplots(
        rows=n, cols=1,
        shared_xaxes=True,
        row_heights=[1/n] * n,
        vertical_spacing=0.04,
        subplot_titles=titles,
    )

    # Zoom to last 5 years for tactical focus
    cutoff = pd.Timestamp.now() - pd.DateOffset(years=5)

    for i, code in enumerate(avail, start=1):
        meta  = CREDIT_META[code]
        s_bps = (credit_df[code].dropna() * 100).loc[cutoff:]
        if s_bps.empty:
            continue

        # Rolling mean and std for the ±1σ band
        win   = min(252, len(s_bps))
        r_mu  = s_bps.rolling(win, min_periods=30).mean()
        r_std = s_bps.rolling(win, min_periods=30).std()
        upper = r_mu + r_std
        lower = r_mu - r_std

        # ±1σ shaded band
        fig.add_trace(go.Scatter(
            x=pd.concat([s_bps.index.to_series(), s_bps.index.to_series().iloc[::-1]]),
            y=pd.concat([upper, lower.iloc[::-1]]),
            fill="toself",
            fillcolor=f"rgba({int(meta['color'][1:3],16)},"
                      f"{int(meta['color'][3:5],16)},"
                      f"{int(meta['color'][5:7],16)},0.08)",
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False, hoverinfo="skip",
        ), row=i, col=1)

        # Rolling mean line (dashed)
        fig.add_trace(go.Scatter(
            x=r_mu.index, y=r_mu,
            line=dict(color=meta["color"], width=1, dash="dot"),
            showlegend=False, name=f"{meta['label']} mean",
            hoverinfo="skip",
        ), row=i, col=1)

        # Main spread line
        fig.add_trace(go.Scatter(
            x=s_bps.index, y=s_bps,
            name=meta["label"],
            line=dict(color=meta["color"], width=2),
            hovertemplate=f"%{{x|%b %d %Y}} — {meta['label']}: <b>%{{y:.0f}} bps</b><extra></extra>",
        ), row=i, col=1)

        # Latest level dot
        fig.add_trace(go.Scatter(
            x=[s_bps.index[-1]], y=[s_bps.iloc[-1]],
            mode="markers",
            marker=dict(color=meta["color"], size=7, line=dict(color=COLORS["bg"], width=1)),
            showlegend=False, hoverinfo="skip",
        ), row=i, col=1)

        fig.update_yaxes(**_AXIS_STYLE, title_text="bps", row=i, col=1)
        fig.update_xaxes(**_AXIS_STYLE, row=i, col=1)

    fig.update_layout(
        **_BASE_LAYOUT,
        height=90 + n * 160,
        showlegend=False,
        title=dict(text="Credit Quality Ladder — 5Y Zoom  ·  Shaded band = ±1σ rolling window",
                   font=dict(size=13, color=COLORS["text"])),
        margin=dict(l=60, r=20, t=50, b=40),
    )
    fig.update_annotations(font=dict(color=COLORS["subtext"], size=11))
    return fig


# ── CHART 4: FINANCIAL STRESS INDEX ──────────────────────────────────────────

def build_stlfsi_chart(credit_df: pd.DataFrame) -> go.Figure:
    """
    St. Louis Fed Financial Stress Index (STLFSI4).

    Published weekly by the St. Louis Fed. Constructed from 18 data series
    including: yield spreads, interest rates, and other indicators.

    Interpretation:
      = 0  →  average financial stress
      > 0  →  above-average stress (positive = bad)
      < 0  →  below-average stress (accommodative conditions)

    Key reference levels:
      +1.0  →  notable stress episode (visible spikes)
      +2.0  →  severe stress (COVID-19 peak, GFC)
      -1.0  →  very loose conditions (ZIRP / QE eras)

    This index is useful as a SUMMARY of credit conditions — it tends to
    lead equity volatility and credit spread blowouts.
    """
    if "STLFSI" not in credit_df.columns:
        return go.Figure()

    s = credit_df["STLFSI"].dropna()
    fig = go.Figure()
    _add_regime_bands(fig)

    # Fill positive (stress) in red, negative (loose) in green
    s_pos = s.where(s >= 0, 0)
    s_neg = s.where(s < 0,  0)

    fig.add_trace(go.Scatter(
        x=s.index, y=s_pos,
        fill="tozeroy",
        fillcolor="rgba(248, 81, 73, 0.18)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=s.index, y=s_neg,
        fill="tozeroy",
        fillcolor="rgba(63, 185, 80, 0.12)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=s.index, y=s,
        name="STLFSI",
        line=dict(color=COLORS["stlfsi"], width=1.8),
        hovertemplate="%{x|%b %d %Y} — STLFSI: <b>%{y:.3f}</b><extra></extra>",
    ))

    # Reference lines
    for level, label, color in [
        ( 0,    "Avg",      COLORS["subtext"]),
        ( 1.0,  "+1 Stress",COLORS["amber"]),
        ( 2.0,  "+2 Severe",COLORS["red"]),
        (-1.0,  "−1 Loose", COLORS["green"]),
    ]:
        fig.add_hline(
            y=level,
            line=dict(color=color, dash="dash" if level != 0 else "solid", width=0.8),
            annotation_text=label,
            annotation_position="right",
            annotation_font=dict(size=9, color=color),
        )

    # Current level annotation
    latest = float(s.iloc[-1])
    stress_label = ("SEVERE STRESS" if latest > 2 else
                    "ELEVATED"      if latest > 1 else
                    "MODERATE"      if latest > 0 else
                    "BELOW AVERAGE")
    stress_color = (COLORS["red"]    if latest > 1 else
                    COLORS["amber"]  if latest > 0 else
                    COLORS["green"])
    fig.add_annotation(
        text=f"Current: {latest:.3f}  —  {stress_label}",
        xref="paper", yref="paper", x=0.01, y=0.96,
        showarrow=False,
        font=dict(color=stress_color, size=11, family="monospace"),
    )

    fig.update_layout(
        **_BASE_LAYOUT,
        title=dict(text="St. Louis Fed Financial Stress Index (STLFSI4)  ·  Weekly",
                   font=dict(size=13, color=COLORS["text"])),
        yaxis=dict(**_AXIS_STYLE, title="Index"),
        xaxis=dict(**_AXIS_STYLE),
        height=300,
        showlegend=False,
        margin=dict(l=60, r=80, t=50, b=40),
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

def build_credit_panel(credit_df: pd.DataFrame) -> html.Div:
    """
    Assembles all Panel 2 components into a Dash layout.

    Layout (top to bottom):
      ┌─────────────────────────────────────────────────────────┐
      │ STATS TABLE  (IG / HY / BBB / CCC / STLFSI + flags)    │
      ├────────────────────────────┬────────────────────────────┤
      │  SPREAD HISTORY            │  FINANCIAL STRESS INDEX    │
      │  IG + BBB + HY over time   │  STLFSI with stress zones  │
      ├────────────────────────────┴────────────────────────────┤
      │  HY / IG RATIO  (3-row: HY · IG · ratio + z-score)     │
      ├─────────────────────────────────────────────────────────┤
      │  QUALITY STACK  (IG / BBB / HY / CCC last 5 years)      │
      └─────────────────────────────────────────────────────────┘
    """
    cfg = {"displayModeBar": False, "responsive": True}

    return html.Div([

        # ── Stats Table ──────────────────────────────────────────────────────
        _card([
            _section_title("CREDIT MARKET READINGS",
                           "OAS in bps · rolling 1Y z-score · percentile rank"),
            build_credit_stats_table(credit_df),
        ]),

        # ── Row: Spread History + STLFSI ────────────────────────────────────
        html.Div([
            _card([
                _section_title("SPREAD HISTORY", "IG / BBB / HY OAS · regime-shaded"),
                dcc.Graph(figure=build_spread_history(credit_df), config=cfg),
            ], extra_style={"flex": "3", "minWidth": "0", "marginBottom": "0"}),

            _card([
                _section_title("FINANCIAL STRESS INDEX", "STLFSI4 · weekly"),
                dcc.Graph(figure=build_stlfsi_chart(credit_df), config=cfg),
            ], extra_style={"flex": "2", "minWidth": "0", "marginBottom": "0"}),

        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # ── HY / IG Ratio ────────────────────────────────────────────────────
        _card([
            _section_title("HY / IG RATIO",
                           "relative value · high = HY compressed · z-score coloring"),
            dcc.Graph(figure=build_hy_ig_ratio(credit_df), config=cfg),
        ]),

        # ── Quality Stack ────────────────────────────────────────────────────
        _card([
            _section_title("CREDIT QUALITY LADDER",
                           "5-year zoom · ±1σ band · stress propagates IG → BBB → HY → CCC"),
            dcc.Graph(figure=build_quality_stack(credit_df), config=cfg),
        ]),

    ], style={"padding": "0"})
