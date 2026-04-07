# =============================================================================
# panels/rates.py
# Builds every chart and layout element for Panel 1: Rates & Yield Curve.
#
# Structure:
#   _add_regime_bands()       → shared helper: shades regime periods on any chart
#   build_yield_curve_bar()   → today's curve snapshot (bar chart)
#   build_historical_yields() → multi-line history of yields + FFR
#   build_ffr_vs_2y()         → Fed "behind the curve" chart
#   build_spreads_chart()     → 2Y10Y and 3M10Y spreads with z-score subplot
#   build_stats_table()       → summary DataTable with flag coloring
#   build_rates_panel()       → assembles all of the above into a Dash layout
# =============================================================================

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc, dash_table

from config import COLORS, REGIMES
from analytics.stats import (
    rolling_zscore, compute_summary_stats, regime_stats, SERIES_LABELS
)

# Shared Plotly layout defaults (applied to every chart for visual consistency)
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
    hovermode     = "x unified",
)

_AXIS_STYLE = dict(
    gridcolor  = COLORS["grid"],
    gridwidth  = 1,
    linecolor  = COLORS["border"],
    zeroline   = False,
    tickfont   = dict(size=10, color=COLORS["subtext"]),
    title_font = dict(size=11, color=COLORS["subtext"]),
)


# ── SHARED HELPER ─────────────────────────────────────────────────────────────

def _add_regime_bands(fig: go.Figure, row: int = None, col: int = None) -> None:
    """
    Shade each historical regime as a translucent rectangle on the chart.
    Called by every chart that has a time axis so context is always visible.

    Labels are small and positioned top-left to avoid obscuring data lines.
    """
    vrect_kwargs = {}
    if row is not None:
        vrect_kwargs["row"] = row
        vrect_kwargs["col"] = col

    for r in REGIMES:
        x1 = r["end"] if r["end"] else "2027-01-01"
        fig.add_vrect(
            x0                = r["start"],
            x1                = x1,
            fillcolor         = r["color"],
            layer             = "below",
            line_width        = 0,
            annotation_text   = r["label"],
            annotation_position = "top left",
            annotation_font   = dict(size=8, color=COLORS["subtext"]),
            **vrect_kwargs,
        )


# ── CHART 1: YIELD CURVE SNAPSHOT ─────────────────────────────────────────────

def build_yield_curve_bar(rates_df: pd.DataFrame) -> go.Figure:
    """
    Bar chart showing today's yield curve shape across all tenors.

    The shape of the curve (normal, flat, inverted) is one of the most
    important signals in macro. This gives you an instant visual.
    - Upward sloping = healthy (longer maturities demand more yield)
    - Flat or inverted = recession signal historically
    """
    tenors     = ["3M", "2Y", "5Y", "10Y", "30Y"]
    color_map  = {t: COLORS[f"yield_{t.lower()}"] for t in tenors}
    avail      = [t for t in tenors if t in rates_df.columns]
    values     = [rates_df[t].dropna().iloc[-1] for t in avail]
    bar_colors = [color_map[t] for t in avail]

    # Detect inversion: if 2Y > 10Y, the curve is inverted
    inverted = False
    if "2Y" in rates_df.columns and "10Y" in rates_df.columns:
        inverted = (rates_df["2Y"].dropna().iloc[-1] >
                    rates_df["10Y"].dropna().iloc[-1])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x           = avail,
        y           = values,
        marker      = dict(
            color       = bar_colors,
            line        = dict(color=COLORS["border"], width=1),
        ),
        text        = [f"{v:.2f}%" for v in values],
        textposition= "outside",
        textfont    = dict(size=12, color=COLORS["text"]),
        hovertemplate = "%{x} Yield: <b>%{y:.3f}%</b><extra></extra>",
    ))

    # Add an inversion warning annotation if applicable
    if inverted:
        fig.add_annotation(
            text      = "⚠ INVERTED",
            xref      = "paper", yref  = "paper",
            x         = 0.98,    y     = 0.95,
            showarrow = False,
            font      = dict(color=COLORS["red"], size=12, family="monospace"),
            align     = "right",
        )

    title_suffix = " — ⚠ INVERTED" if inverted else ""
    fig.update_layout(
        **_BASE_LAYOUT,
        title       = dict(text=f"Yield Curve Snapshot{title_suffix}",
                           font=dict(size=13, color=COLORS["text"])),
        yaxis       = dict(**_AXIS_STYLE, title="Yield (%)", range=[0, max(values) * 1.18]),
        xaxis       = dict(**_AXIS_STYLE),
        showlegend  = False,
        height      = 310,
        bargap      = 0.3,
        margin      = dict(l=55, r=20, t=50, b=40),
    )
    return fig


# ── CHART 2: HISTORICAL YIELDS ─────────────────────────────────────────────────

def build_historical_yields(rates_df: pd.DataFrame) -> go.Figure:
    """
    Multi-line chart of FFR, 2Y, 10Y, and 30Y Treasury yields since 2000.

    The regime bands provide essential context — e.g., you can see how
    dramatically yields compressed during ZIRP, and how quickly they
    moved in the 2022 hiking cycle.

    FFR vs 2Y proximity tells you whether markets expect cuts or hikes:
    - 2Y significantly above FFR → market pricing in rate hikes ahead
    - 2Y significantly below FFR → market expects cuts (like 2022–23)
    """
    fig = go.Figure()
    _add_regime_bands(fig)

    series_config = [
        ("FFR",  "Fed Funds Rate", COLORS["ffr"],       dict(width=2, dash="dot")),
        ("2Y",   "2Y Treasury",    COLORS["yield_2y"],  dict(width=1.5)),
        ("10Y",  "10Y Treasury",   COLORS["yield_10y"], dict(width=2)),
        ("30Y",  "30Y Treasury",   COLORS["yield_30y"], dict(width=1.5)),
    ]

    for code, label, color, line_style in series_config:
        if code not in rates_df.columns:
            continue
        s = rates_df[code].dropna()
        fig.add_trace(go.Scatter(
            x             = s.index,
            y             = s.values,
            name          = label,
            line          = dict(color=color, **line_style),
            hovertemplate = "%{x|%b %d %Y} — <b>%{y:.2f}%</b><extra>" + label + "</extra>",
        ))

    fig.update_layout(
        **_BASE_LAYOUT,
        title  = dict(text="Historical Yields & Fed Funds Rate (2000 – Present)",
                      font=dict(size=13, color=COLORS["text"])),
        yaxis  = dict(**_AXIS_STYLE, title="Yield (%)"),
        xaxis  = dict(**_AXIS_STYLE),
        height = 360,
        margin = dict(l=55, r=20, t=50, b=40),
    )
    return fig


# ── CHART 3: FFR VS 2Y (BEHIND-THE-CURVE) ────────────────────────────────────

def build_ffr_vs_2y(rates_df: pd.DataFrame) -> go.Figure:
    """
    Overlays the Fed Funds Rate with the 2-Year Treasury yield.

    The 2Y Treasury is the market's best real-time prediction of where
    the Fed Funds Rate will be in ~2 years. The gap between them is a
    'policy error' signal:
      - FFR >> 2Y  → Fed is AHEAD of the curve (rates likely to come down)
      - FFR << 2Y  → Fed is BEHIND the curve (market expects hikes)
      - FFR ≈  2Y  → Market expects rates to stay roughly here

    The shaded fill between them makes the gap immediately visible.
    """
    fig = go.Figure()
    _add_regime_bands(fig)

    if "FFR" not in rates_df.columns or "2Y" not in rates_df.columns:
        return fig

    df = rates_df[["FFR", "2Y"]].dropna()
    ffr_vals = df["FFR"].values
    y2_vals  = df["2Y"].values
    dates    = df.index

    # Shade the gap between the two series
    # Split into two fills: where FFR > 2Y (hawkish) and FFR < 2Y (dovish)
    ffr_above = np.where(ffr_vals >= y2_vals, ffr_vals, y2_vals)
    ffr_below = np.where(ffr_vals <= y2_vals, ffr_vals, y2_vals)

    # Fill: FFR above 2Y (Fed ahead/restrictive) in red
    fig.add_trace(go.Scatter(
        x=pd.concat([pd.Series(dates), pd.Series(dates[::-1])]),
        y=np.concatenate([ffr_above, y2_vals[::-1]]),
        fill="toself",
        fillcolor="rgba(248, 81, 73, 0.12)",
        line=dict(color="rgba(0,0,0,0)"),
        name="FFR > 2Y (Restrictive)",
        showlegend=True,
        hoverinfo="skip",
    ))

    # Fill: 2Y above FFR (Fed behind) in blue
    fig.add_trace(go.Scatter(
        x=pd.concat([pd.Series(dates), pd.Series(dates[::-1])]),
        y=np.concatenate([y2_vals, ffr_below[::-1]]),
        fill="toself",
        fillcolor="rgba(88, 166, 255, 0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        name="2Y > FFR (Behind curve)",
        showlegend=True,
        hoverinfo="skip",
    ))

    # Main lines on top
    fig.add_trace(go.Scatter(
        x=dates, y=ffr_vals,
        name="Fed Funds Rate",
        line=dict(color=COLORS["ffr"], width=2, dash="dot"),
        hovertemplate="%{x|%b %Y} — FFR: <b>%{y:.2f}%</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=y2_vals,
        name="2Y Treasury",
        line=dict(color=COLORS["yield_2y"], width=2),
        hovertemplate="%{x|%b %d %Y} — 2Y: <b>%{y:.2f}%</b><extra></extra>",
    ))

    # Current gap annotation
    gap = round(float(ffr_vals[-1] - y2_vals[-1]), 2)
    sign = "+" if gap >= 0 else ""
    direction = "FFR AHEAD" if gap > 0.1 else ("BEHIND CURVE" if gap < -0.1 else "AT CURVE")
    fig.add_annotation(
        text      = f"Gap: {sign}{gap:.2f}% — {direction}",
        xref="paper", yref="paper",
        x=0.01, y=0.04,
        showarrow = False,
        font      = dict(color=COLORS["amber"] if abs(gap) > 0.5 else COLORS["subtext"],
                         size=11, family="monospace"),
        align="left",
    )

    fig.update_layout(
        **_BASE_LAYOUT,
        title  = dict(text="Fed Funds Rate vs 2Y Treasury — Policy Positioning",
                      font=dict(size=13, color=COLORS["text"])),
        yaxis  = dict(**_AXIS_STYLE, title="Rate (%)"),
        xaxis  = dict(**_AXIS_STYLE),
        height = 310,
        margin = dict(l=55, r=20, t=50, b=40),
    )
    return fig


# ── CHART 4: SPREADS + Z-SCORE ────────────────────────────────────────────────

def build_spreads_chart(spreads_df: pd.DataFrame) -> go.Figure:
    """
    Four-row subplot:
      Row 1 — 2Y10Y spread in bps + zero line
      Row 2 — Rolling 1Y z-score of 2Y10Y
      Row 3 — 3M10Y spread in bps + zero line
      Row 4 — Rolling 1Y z-score of 3M10Y

    Why show z-scores separately?
    Seeing that the 2Y10Y spread is -30 bps tells you the curve is inverted.
    Seeing that its z-score is -2.3 tells you this inversion is historically
    extreme — a fundamentally different piece of information.
    """
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.35, 0.15, 0.35, 0.15],
        vertical_spacing=0.04,
        subplot_titles=[
            "2Y – 10Y Spread (bps)", "Rolling Z-Score (1Y)",
            "3M – 10Y Spread (bps)", "Rolling Z-Score (1Y)",
        ],
    )

    spread_config = [
        ("2Y10Y", COLORS["spread_2y10y"], 1, 2),
        ("3M10Y", COLORS["spread_3m10y"], 3, 4),
    ]

    for name, color, spread_row, z_row in spread_config:
        if name not in spreads_df.columns:
            continue

        # Convert % to basis points (1% = 100 bps)
        s_bps = spreads_df[name] * 100
        rz    = rolling_zscore(spreads_df[name])

        # Regime bands on spread rows only (z-score rows are too small)
        _add_regime_bands(fig, row=spread_row, col=1)

        # ── Spread trace with positive/negative color fill ──
        pos = s_bps.where(s_bps >= 0, 0)
        neg = s_bps.where(s_bps < 0,  0)

        fig.add_trace(go.Scatter(
            x=s_bps.index, y=pos,
            fill="tozeroy",
            fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ), row=spread_row, col=1)

        fig.add_trace(go.Scatter(
            x=s_bps.index, y=neg,
            fill="tozeroy",
            fillcolor="rgba(248, 81, 73, 0.15)",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ), row=spread_row, col=1)

        # Main spread line
        fig.add_trace(go.Scatter(
            x=s_bps.index, y=s_bps,
            name=f"{name} (bps)",
            line=dict(color=color, width=1.8),
            hovertemplate=f"%{{x|%b %d %Y}} — {name}: <b>%{{y:.0f}} bps</b><extra></extra>",
        ), row=spread_row, col=1)

        # Zero line (inversion threshold)
        fig.add_hline(
            y=0,
            line=dict(color=COLORS["red"], dash="dash", width=1),
            row=spread_row, col=1,
        )

        # ── Z-score bars ──
        z_colors = [
            COLORS["red"]   if abs(v) >= 2.0 else
            COLORS["amber"] if abs(v) >= 1.5 else
            COLORS["green"]
            for v in rz.fillna(0)
        ]
        fig.add_trace(go.Bar(
            x=rz.index, y=rz,
            name=f"{name} Z-score",
            marker=dict(color=z_colors, line=dict(width=0)),
            hovertemplate=f"%{{x|%b %d %Y}} — Z: <b>%{{y:.2f}}</b><extra></extra>",
        ), row=z_row, col=1)

        # Z threshold lines
        for threshold, dash in [(2.0, "dot"), (-2.0, "dot"), (1.5, "dash"), (-1.5, "dash")]:
            color_t = COLORS["red"] if abs(threshold) == 2.0 else COLORS["amber"]
            fig.add_hline(
                y=threshold,
                line=dict(color=color_t, dash=dash, width=0.8),
                row=z_row, col=1,
            )

    # Apply consistent axis styling to all rows
    for r in [1, 2, 3, 4]:
        fig.update_yaxes(**_AXIS_STYLE, row=r, col=1)
        fig.update_xaxes(**_AXIS_STYLE, row=r, col=1)

    # Specific y-axis labels
    fig.update_yaxes(title_text="bps",     row=1, col=1)
    fig.update_yaxes(title_text="Z",       row=2, col=1)
    fig.update_yaxes(title_text="bps",     row=3, col=1)
    fig.update_yaxes(title_text="Z",       row=4, col=1)

    fig.update_layout(
        **_BASE_LAYOUT,
        height     = 620,
        showlegend = False,
        margin     = dict(l=55, r=20, t=40, b=40),
    )
    fig.update_annotations(font=dict(color=COLORS["subtext"], size=11))
    return fig


# ── STATS TABLE ───────────────────────────────────────────────────────────────

def build_stats_table(
    rates_df: pd.DataFrame,
    spreads_df: pd.DataFrame,
) -> dash_table.DataTable:
    """
    Summary DataTable shown at the top of the panel.

    Each row = one series.
    Color coding:
      - Flag column: green/amber/red text based on status
      - Roll Z column: colored based on magnitude
      - 1M/3M change: sign-colored (positive = red for yields going up)
    """
    df = compute_summary_stats(rates_df, spreads_df)

    # Columns to display (drop internal _flag_color column)
    display_cols = [c for c in df.columns if not c.startswith("_") and c != "Code"]
    col_defs = [{"name": c, "id": c} for c in display_cols]

    # Conditional styling rules
    style_conditions = [
        # Flag column colors
        {"if": {"filter_query": '{Flag} = "NORMAL"',  "column_id": "Flag"},
         "color": COLORS["green"], "fontWeight": "600"},
        {"if": {"filter_query": '{Flag} = "WATCH"',   "column_id": "Flag"},
         "color": COLORS["amber"], "fontWeight": "600"},
        {"if": {"filter_query": '{Flag} = "EXTREME"', "column_id": "Flag"},
         "color": COLORS["red"],   "fontWeight": "600"},
        # Shade spreads rows differently
        {"if": {"filter_query": '{Series} contains "Spread"'},
         "backgroundColor": COLORS["card_alt"]},
    ]

    return dash_table.DataTable(
        id       = "rates-stats-table",
        data     = df[display_cols].to_dict("records"),
        columns  = col_defs,
        sort_action = "native",
        style_table = {
            "overflowX":    "auto",
            "borderRadius": "6px",
            "border":       f"1px solid {COLORS['border']}",
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
        style_data_conditional = style_conditions,
        page_size = 10,
    )


# ── PANEL ASSEMBLER ───────────────────────────────────────────────────────────

def _card(children, extra_style=None):
    """Wrap content in a styled card div."""
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


def _section_title(text: str, sub: str = "") -> html.Div:
    """Small section header above a chart."""
    return html.Div([
        html.Span(text, style={
            "color":       COLORS["text"],
            "fontSize":    "12px",
            "fontWeight":  "600",
            "letterSpacing": "0.8px",
            "fontFamily":  "monospace",
        }),
        html.Span(f"  {sub}", style={
            "color":    COLORS["subtext"],
            "fontSize": "11px",
        }) if sub else None,
    ], style={"marginBottom": "10px"})


def build_rates_panel(
    rates_df: pd.DataFrame,
    spreads_df: pd.DataFrame,
) -> html.Div:
    """
    Assembles all Panel 1 components into a Dash layout.

    Layout (top to bottom):
      ┌─────────────────────────────────────────┐
      │ STATS SUMMARY TABLE (all series, flags) │
      ├──────────────────┬──────────────────────┤
      │ YIELD CURVE BAR  │  FFR vs 2Y CHART     │
      ├──────────────────┴──────────────────────┤
      │ HISTORICAL YIELDS (multi-line)           │
      ├─────────────────────────────────────────┤
      │ SPREADS + Z-SCORE (4-row subplot)        │
      └─────────────────────────────────────────┘
    """
    graph_config = {"displayModeBar": False, "responsive": True}

    return html.Div([

        # ── Stats Table ──────────────────────────────────────────────────────
        _card([
            _section_title("CURRENT READINGS",
                           "rolling 1Y z-score · historical z-score · percentile rank"),
            build_stats_table(rates_df, spreads_df),
        ]),

        # ── Row: Yield Curve Snapshot + FFR vs 2Y ───────────────────────────
        html.Div([
            _card([
                _section_title("YIELD CURVE SNAPSHOT", "today's shape"),
                dcc.Graph(
                    figure=build_yield_curve_bar(rates_df),
                    config=graph_config,
                ),
            ], extra_style={"flex": "1", "minWidth": "0", "marginBottom": "0"}),

            _card([
                _section_title("POLICY POSITIONING", "FFR vs 2Y Treasury"),
                dcc.Graph(
                    figure=build_ffr_vs_2y(rates_df),
                    config=graph_config,
                ),
            ], extra_style={"flex": "2", "minWidth": "0", "marginBottom": "0"}),

        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

        # ── Historical Yields ────────────────────────────────────────────────
        _card([
            _section_title("HISTORICAL YIELDS", "regime-shaded · 2000–present"),
            dcc.Graph(
                figure=build_historical_yields(rates_df),
                config=graph_config,
            ),
        ]),

        # ── Spreads ──────────────────────────────────────────────────────────
        _card([
            _section_title("YIELD CURVE SPREADS",
                           "bps · zero = inversion threshold · z-score color: green/amber/red"),
            dcc.Graph(
                figure=build_spreads_chart(spreads_df),
                config=graph_config,
            ),
        ]),

    ], style={"padding": "0"})