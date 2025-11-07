"""
Landeros Financial Ironware - Visual Dashboard

This file runs a web-based (Plotly Dash) dashboard for
scanning and analyzing iron condor opportunities.

To run:
    python3 dashboard.py

Author: Carlos Landeros
"""

import logging
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# We will lazy-load the backend engine inside callbacks
# to prevent server startup crashes on macOS
from landeros_ironware.utils import setup_logging

# --- App Setup ---
setup_logging(logging.INFO)
logger = logging.getLogger(__name__)

# Use a clean, professional "OpenAI-style" dark theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Landeros Ironware"


# --- Helper Functions ---

def _assign_grade(score: float) -> str:
    """Translates a 0.0-1.0 optimizer score to a letter grade."""
    if score > 0.9: return "A+"
    if score > 0.85: return "A"
    if score > 0.8: return "A-"
    if score > 0.75: return "B+"
    if score > 0.7: return "B"
    if score > 0.65: return "B-"
    if score > 0.6: return "C+"
    if score > 0.55: return "C"
    if score > 0.5: return "C-"
    return "D"

def create_empty_figure():
    """Returns a blank figure for the payoff graph in dark mode."""
    fig = go.Figure()
    fig.update_layout(
        xaxis_title="Underlying Price",
        yaxis_title="Profit / Loss ($)",
        template="plotly_dark",  # <-- Dark mode graph
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white"
    )
    return fig

# --- Dark Mode Table Style ---
table_style_header = {
    'backgroundColor': 'rgb(30, 30, 30)',
    'color': 'white',
    'fontWeight': 'bold',
    'border': '1px solid #555'
}
table_style_cell = {
    'backgroundColor': 'rgb(50, 50, 50)',
    'color': 'white',
    'border': '1px solid #555',
    'padding': '8px'
}


# --- App Layout ---
app.layout = dbc.Container([

    # --- Header ---
    dbc.Row(
        dbc.Col(
            html.H1("Landeros Financial Ironware: Multi-Index Screener", className="text-center my-4"),
            width=12
        )
    ),

    # --- Controls Row ---
    dbc.Row([
        # Scan parameters
        # Underlying dropdown is REMOVED
        dbc.Col([
            dbc.Label("Target DTE:"),
            dbc.Input(id='input-dte', type='number', value=45)
        ], width=3),

        dbc.Col([
            dbc.Label("Target Delta:"),
            dbc.Input(id='input-delta', type='number', value=0.16, step=0.01)
        ], width=3),

        dbc.Col([
            dbc.Label("Min Credit ($):"),
            dbc.Input(id='input-credit', type='number', value=2.0, step=0.1)
        ], width=3),

        # The Scan Button
        dbc.Col([
            dbc.Button(
                "Scan All Indexes (SPX, NDX, RUT)",
                id='btn-scan',
                color="primary",
                className="w-100",
                style={"marginTop": "32px"}
            )
        ], width=3)

    ], className="mb-4"),

    # --- Output Area (Table and Graph) ---
    dbc.Row([

        # Left Column: Results Table
        dbc.Col([
            html.H4("Optimal Candidates (Top 10 per Index)"),
            dcc.Loading(
                id="loading-scan",
                type="default",
                children=[
                    html.Div(id='scan-status-message'), # "Scan complete"
                    # This table will be populated by the callback
                    dash_table.DataTable(
                        id='results-table',
                        columns=[
                            {"name": "Grade", "id": "grade"},
                            {"name": "Index", "id": "underlying"},
                            {"name": "Strikes", "id": "strikes"},
                            {"name": "Credit", "id": "credit"},
                            {"name": "POP", "id": "pop"},
                            {"name": "Max Loss", "id": "max_loss"},
                            {"name": "ROC", "id": "roc"},
                            {"name": "Score", "id": "score"},
                        ],
                        data=[],
                        row_selectable="single",
                        sort_action="native",
                        page_size=15,
                        style_as_list_view=True,
                        style_header=table_style_header,
                        style_cell=table_style_cell,
                    )
                ]
            )
        ], width=7),

        # Right Column: Payoff Graph
        dbc.Col([
            html.H4("Payoff Diagram"),
            dcc.Loading(
                id="loading-graph",
                type="default",
                children=[
                    dcc.Graph(
                        id='payoff-graph',
                        figure=create_empty_figure() # Start with a blank graph
                    )
                ]
            )
        ], width=5)

    ], className="mt-4"),

    # --- Hidden Data Stores ---
    # Store the full scan results (JSON)
    dcc.Store(id='store-scan-results', data=[])

], fluid=True, className="dbc") # Apply dark theme context


# --- Callbacks (The "Logic") ---

@callback(
    Output('store-scan-results', 'data'),
    Output('scan-status-message', 'children'),
    Input('btn-scan', 'n_clicks'),
    State('input-dte', 'value'),
    State('input-delta', 'value'),
    State('input-credit', 'value'),
    prevent_initial_call=True # Don't run on page load
)
def update_scan_results(n_clicks, dte, delta, credit):
    """
    Called when the 'Scan' button is clicked.
    Runs the main IronCondorScanner FOR ALL INDEXES and stores the results.
    """
    # Lazy-load the backend here to prevent startup crashes
    from landeros_ironware.config import Settings
    from landeros_ironware.strategies import IronCondorScanner

    SUPPORTED_UNDERLYINGS = ['SPX', 'NDX', 'RUT']
    all_candidates = []

    logger.info(f"Multi-index scan triggered for {SUPPORTED_UNDERLYINGS} @ {dte} DTE...")

    for underlying in SUPPORTED_UNDERLYINGS:
        logger.info(f"Scanning {underlying}...")
        try:
            # 1. Create settings from dashboard inputs for this index
            settings = Settings(
                underlying=underlying,
                target_dte=dte,
                target_delta=delta,
                min_credit=credit
            )

            # 2. Run our powerful backend scanner
            scanner = IronCondorScanner(settings)
            candidates = scanner.scan() # This might take 5-10 seconds

            if not candidates:
                logger.warning(f"No candidates found for {underlying}.")
                continue

            # 3. Get Top 10 for this index and add to list
            # The scanner already sorts by score
            top_10 = [ic.to_dict() for ic in candidates[:10]]
            all_candidates.extend(top_10)

        except Exception as e:
            logger.error(f"Failed to scan {underlying}: {e}")
            return [], f"Error scanning {underlying}. See terminal for details."


    if not all_candidates:
        logger.warning("Multi-index scan complete. No candidates found for any index.")
        return [], "Scan complete. No candidates found."

    logger.info(f"Multi-index scan complete. Found {len(all_candidates)} total top candidates.")

    return all_candidates, f"Scan complete. Found {len(all_candidates)} candidates from {len(SUPPORTED_UNDERLYINGS)} indexes."


@callback(
    Output('results-table', 'data'),
    Input('store-scan-results', 'data'),
    prevent_initial_call=True # Prevent running on load
)
def update_results_table(scan_results_json):
    """
    Populates the visual table from the hidden data store.
    """
    # Lazy-load IronCondor for this callback
    from landeros_ironware.strategies import IronCondor

    if not scan_results_json:
        return []

    # Format the data for the table
    table_data = []
    for ic_dict in scan_results_json:
        ic = IronCondor.from_dict(ic_dict) # Re-create object
        table_data.append({
            "underlying": ic.underlying,
            "grade": _assign_grade(ic.score),
            "strikes": f"{int(ic.short_put_strike)}P / {int(ic.short_call_strike)}C",
            "credit": f"${ic.credit:.2f}",
            "pop": f"{ic.pop:.1%}",
            "max_loss": f"${ic.max_loss:.2f}",
            "roc": f"{ic.return_on_capital:.1%}",
            "score": f"{ic.score:.3f}"
        })

    # Re-sort data by score, as we combined 3 lists
    table_data.sort(key=lambda x: x['score'], reverse=True)

    return table_data


@callback(
    Output('payoff-graph', 'figure'),
    Input('results-table', 'active_cell'),
    State('store-scan-results', 'data'),
    prevent_initial_call=True
)
def update_payoff_graph(active_cell, scan_results_json):
    """
    Called when a user clicks a row in the table.
    Generates a payoff diagram for the selected trade.
    """
    # Lazy-load for this callback
    from landeros_ironware.strategies import IronCondor
    from landeros_ironware.visuals import PayoffDiagram

    if not active_cell or not scan_results_json:
        return dash.no_update

    # Find the selected row's data.
    # We must re-build the sorted list to find the correct
    # data from the original store, as the visual table is sorted.

    table_data = []
    for ic_dict in scan_results_json:
        ic = IronCondor.from_dict(ic_dict) # Re-create object
        table_data.append({
            "original_dict": ic_dict, # Keep the original
            "score": ic.score
        })
    table_data.sort(key=lambda x: x['score'], reverse=True)

    try:
        selected_row_index = active_cell['row']
        selected_ic_dict = table_data[selected_row_index]['original_dict']
    except Exception as e:
        logger.error(f"Failed to find selected row {selected_row_index}: {e}")
        return dash.no_update


    # Re-create the IronCondor object
    ic = IronCondor.from_dict(selected_ic_dict)

    logger.info(f"Generating payoff graph for: {ic}")

    # Use our existing PayoffDiagram class
    diagram = PayoffDiagram(ic)
    fig = diagram.plot(show_greeks=True) # Generate the Plotly figure

    # Update figure for dark mode
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgb(50, 50, 50)",
        font_color="white"
    )

    return fig


# --- Run the App ---
if __name__ == '__main__':
    logger.info("Starting Dash server on http://127.0.0.1:8050")
    # Run in production mode (debug=False) to prevent yfinance crashes
    app.run(debug=False, port=8050)
