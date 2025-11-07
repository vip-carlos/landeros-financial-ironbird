"""
Generates interactive payoff diagrams for Iron Condor positions.

Uses Plotly to create rich, savable HTML charts that show
P&L at expiration, break-even points, and max profit/loss.

Author: Carlos Landeros
"""

import logging
from typing import Optional

import numpy as np
import plotly.graph_objects as go

# We must import from strategies, which is now implemented
from landeros_ironware.strategies.iron_condor import IronCondor

logger = logging.getLogger(__name__)


class PayoffDiagram:
    """
    Generates a Plotly-based payoff diagram for an IronCondor.
    """

    def __init__(self, iron_condor: IronCondor):
        """
        Initialize the diagram with an IronCondor candidate.

        Args:
            iron_condor: The IronCondor object to plot.
        """
        self.ic = iron_condor
        self.fig: Optional[go.Figure] = None
        logger.debug(f"PayoffDiagram initialized for {iron_condor}")

    def _calculate_pnl_at_price(self, price: float) -> float:
        """
        Calculates the P&L for the iron condor at expiration
        at a specific underlying price.
        """
        ic = self.ic
        pnl = 0.0

        # 1. Below the long put (max loss)
        if price <= ic.long_put_strike:
            pnl = -ic.max_loss

        # 2. Between long put and short put (put spread ramp)
        elif price < ic.short_put_strike:
            # P&L = (Price - Long Put Strike) - (Cost of Put Spread)
            # Cost of Put Spread = Width - Put Credit
            # P&L = (Price - Long Put) - (Short Put - Long Put - Put Credit)
            # A simpler way: P&L = Price - BreakEven
            pnl = price - ic.break_even_lower

        # 3. Between short put and short call (max profit)
        elif price <= ic.short_call_strike:
            pnl = ic.credit

        # 4. Between short call and long call (call spread ramp)
        elif price < ic.long_call_strike:
            # P&L = (Short Call Strike - Price) + (Credit from Call Spread)
            # A simpler way: P&L = BreakEven - Price
            pnl = ic.break_even_upper - price

        # 5. Above the long call (max loss)
        else:
            pnl = -ic.max_loss

        return pnl

    def plot(
        self,
        show_greeks: bool = False,
        show_plot: bool = False
    ) -> go.Figure:
        """
        Generate the Plotly figure object.

        Args:
            show_greeks: Whether to add annotations for greeks.
            show_plot: If True, will open the plot in a browser.

        Returns:
            go.Figure: The Plotly figure object.
        """
        ic = self.ic

        # 1. Generate price range
        # Create a wide range around the strikes
        padding = ic.call_wing_width * 2
        price_min = ic.long_put_strike - padding
        price_max = ic.long_call_strike + padding

        price_range = np.linspace(price_min, price_max, 400)

        # Add exact strike points to ensure sharp "kinks"
        strike_points = [
            ic.long_put_strike, ic.short_put_strike,
            ic.short_call_strike, ic.long_call_strike,
            ic.break_even_lower, ic.break_even_upper
        ]
        price_range = np.unique(np.concatenate([price_range, strike_points]))

        # 2. Calculate P&L for each price
        pnl_values = [self._calculate_pnl_at_price(p) for p in price_range]

        # 3. Create Plotly figure
        fig = go.Figure()

        # Add the main P&L payoff line
        fig.add_trace(go.Scatter(
            x=price_range,
            y=pnl_values,
            mode='lines',
            name='P&L at Expiration',
            line=dict(color='blue', width=3)
        ))

        # 4. Add styling and annotations

        # Add $0 line
        fig.add_hline(
            y=0,
            line=dict(color='gray', dash='dash'),
            name='$0 P&L'
        )

        # Add Max Profit line
        fig.add_hline(
            y=ic.credit,
            line=dict(color='green', dash='dot'),
            name=f'Max Profit (${ic.credit:.2f})'
        )

        # Add Max Loss line
        fig.add_hline(
            y=-ic.max_loss,
            line=dict(color='red', dash='dot'),
            name=f'Max Loss (${ic.max_loss:.2f})'
        )

        # Add vertical lines for short strikes
        fig.add_vline(
            x=ic.short_put_strike,
            line=dict(color='red', dash='dash'),
            name=f'Short Put ({int(ic.short_put_strike)})'
        )

        fig.add_vline(
            x=ic.short_call_strike,
            line=dict(color='red', dash='dash'),
            name=f'Short Call ({int(ic.short_call_strike)})'
        )

        # Add shaded rectangle for profit zone
        fig.add_shape(
            type="rect",
            xref="x", yref="y",
            x0=ic.break_even_lower, y0=0,
            x1=ic.break_even_upper, y1=ic.credit,
            fillcolor="rgba(0, 255, 0, 0.2)",
            line=dict(width=0),
            name="Profit Zone"
        )

        # Add text annotation for POP
        fig.add_annotation(
            text=f"Prob. of Profit: {ic.pop:.1%}",
            x=ic.underlying_price,
            y=ic.credit,
            yshift=20,
            showarrow=False,
            font=dict(color="green", size=14)
        )

        # Add annotation for current price
        fig.add_vline(
            x=ic.underlying_price,
            line=dict(color='black', width=2),
            name=f'Current Price (${ic.underlying_price:.2f})'
        )

        # 5. Add Greeks if requested
        if show_greeks:
            greeks_text = (
                f"<b>Position Greeks:</b><br>"
                f"Delta: {ic.delta:.4f}<br>"
                f"Gamma: {ic.gamma:.4f}<br>"
                f"Theta: {ic.theta:.4f}<br>"
                f"Vega: {ic.vega:.4f}"
            )
            fig.add_annotation(
                text=greeks_text,
                align='left',
                showarrow=False,
                xref='paper', yref='paper',
                x=0.05, y=0.05,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="black",
                borderwidth=1
            )

        # 6. Final layout
        title_structure = (
            f"{int(ic.long_put_strike)}/{int(ic.short_put_strike)} "
            f"{int(ic.short_call_strike)}/{int(ic.long_call_strike)}"
        )

        fig.update_layout(
            title=f"Iron Condor Payoff: {ic.underlying} {title_structure} ({ic.dte} DTE)",
            xaxis_title="Underlying Price at Expiration",
            yaxis_title="Profit / Loss ($ per share)",
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        self.fig = fig

        if show_plot:
            self.fig.show()

        return self.fig

    def save(self, file_path: str = "payoff.html") -> None:
        """
        Save the diagram as an interactive HTML file.

        Args:
            file_path: The path to save the HTML file.
        """
        if self.fig is None:
            self.plot()
        if self.fig:
            self.fig.write_html(file_path)
            logger.info(f"Payoff diagram saved to {file_path}")
        else:
            logger.error("Could not generate figure to save.")