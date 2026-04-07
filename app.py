# =============================================================================
# app.py  —  Entry point for the Macro Dashboard
#
# Run:   python app.py
# URL:   http://127.0.0.1:8050
#
# Panels:
#   Tab 1 — Rates & Yield Curve   (Week 1)
#   Tab 2 — Credit Markets        (Week 2)
#   Tab 3 — Commodities           (Week 3)
# =============================================================================

import dash
from dash import html, dcc, Input, Output
from datetime import datetime

from config import COLORS, DASH_TITLE, DASH_SUBTITLE, DASH_PORT
from data.fetcher import load_all
from panels.rates import build_rates_panel
from panels.credit import build_credit_panel
from panels.commodities import build_commodities_panel


# ── APP ───────────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="Macro Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True,
)


# ── DATA LOAD ─────────────────────────────────────────────────────────────────
# load_all() returns four DataFrames: rates, spreads, credit, commodities.

print("\n" + "=" * 60)
print("  MACRO DASHBOARD  —  starting up")
print("=" * 60)
rates_df, spreads_df, credit_df, commodities_df = load_all()
_last_updated = datetime.now()
print(f"\n  ✓ Ready  →  http://127.0.0.1:{DASH_PORT}\n")


# ── TAB STYLE ─────────────────────────────────────────────────────────────────

def _tab_style(active=False, disabled=False):
    if disabled:
        return {
            "backgroundColor": COLORS["bg"], "color": COLORS["border"],
            "border": "none", "borderTop": "2px solid transparent",
            "padding": "10px 20px", "fontSize": "11px",
            "fontFamily": "monospace", "cursor": "not-allowed",
        }
    return {
        "backgroundColor": COLORS["card"] if active else COLORS["bg"],
        "color":           COLORS["text"] if active else COLORS["subtext"],
        "border":          "none",
        "borderTop":       f"2px solid {COLORS['accent']}" if active else "2px solid transparent",
        "padding":         "10px 20px", "fontSize": "11px",
        "fontWeight":      "600" if active else "400",
        "letterSpacing":   "0.8px", "fontFamily": "monospace",
    }


# ── LAYOUT ────────────────────────────────────────────────────────────────────

app.layout = html.Div([

    # ── STICKY NAVBAR ─────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Span(DASH_TITLE, style={
                "color": COLORS["text"], "fontSize": "14px",
                "fontWeight": "700", "letterSpacing": "3px", "fontFamily": "monospace",
            }),
            html.Br(),
            html.Span(DASH_SUBTITLE, style={
                "color": COLORS["subtext"], "fontSize": "10px",
                "letterSpacing": "1.5px", "fontFamily": "monospace",
            }),
        ]),
        html.Div([
            html.Span(
                id="last-updated-label",
                children=f"Updated {_last_updated.strftime('%Y-%m-%d  %H:%M')}",
                style={"color": COLORS["subtext"], "fontSize": "11px",
                       "fontFamily": "monospace", "marginRight": "16px"},
            ),
            html.Button("↺  REFRESH DATA", id="refresh-btn", n_clicks=0, style={
                "backgroundColor": "transparent", "color": COLORS["accent"],
                "border": f"1px solid {COLORS['accent']}", "padding": "6px 16px",
                "borderRadius": "4px", "cursor": "pointer", "fontSize": "11px",
                "fontWeight": "600", "fontFamily": "monospace", "letterSpacing": "1px",
            }),
        ], style={"display": "flex", "alignItems": "center"}),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "backgroundColor": COLORS["card"], "padding": "14px 28px",
        "borderBottom": f"1px solid {COLORS['border']}",
        "position": "sticky", "top": "0", "zIndex": "200",
    }),

    # ── TAB BAR ───────────────────────────────────────────────────────────────
    dcc.Tabs(
        id="main-tabs", value="rates", persistence=True,
        style={"backgroundColor": COLORS["bg"], "borderBottom": f"1px solid {COLORS['border']}"},
        colors={"border": COLORS["border"], "primary": COLORS["accent"], "background": COLORS["bg"]},
        children=[
            dcc.Tab(label="📈  RATES & YIELD CURVE", value="rates",
                    style=_tab_style(), selected_style=_tab_style(active=True)),
            dcc.Tab(label="💳  CREDIT MARKETS", value="credit",
                    style=_tab_style(), selected_style=_tab_style(active=True)),
            dcc.Tab(label="🛢️  COMMODITIES", value="commodities",
                    style=_tab_style(), selected_style=_tab_style(active=True)),
        ],
    ),

    # ── MAIN CONTENT ──────────────────────────────────────────────────────────
    html.Div(id="page-content", style={
        "backgroundColor": COLORS["bg"], "padding": "24px 28px",
        "minHeight": "calc(100vh - 110px)",
    }),

], style={
    "backgroundColor": COLORS["bg"],
    "fontFamily": "'JetBrains Mono', 'Courier New', monospace",
    "minHeight": "100vh", "margin": "0", "padding": "0",
})


# ── CALLBACK ──────────────────────────────────────────────────────────────────

@app.callback(
    Output("page-content",       "children"),
    Output("last-updated-label", "children"),
    Input("main-tabs",           "value"),
    Input("refresh-btn",         "n_clicks"),
    prevent_initial_call=False,
)
def render_panel(tab, n_clicks):
    global rates_df, spreads_df, credit_df, commodities_df, _last_updated

    ctx       = dash.callback_context
    triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    if "refresh-btn" in triggered and n_clicks:
        print(f"\n  [Refresh] at {datetime.now().strftime('%H:%M:%S')}")
        rates_df, spreads_df, credit_df, commodities_df = load_all(force=True)
        _last_updated = datetime.now()

    label = f"Updated {_last_updated.strftime('%Y-%m-%d  %H:%M')}"

    if tab == "rates":
        return build_rates_panel(rates_df, spreads_df), label
    if tab == "credit":
        return build_credit_panel(credit_df), label
    if tab == "commodities":
        return build_commodities_panel(commodities_df), label

    return html.Div("Unknown tab.", style={"color": COLORS["subtext"], "padding": "40px"}), label


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=DASH_PORT)
