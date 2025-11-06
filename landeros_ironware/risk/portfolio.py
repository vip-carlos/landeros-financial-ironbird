"""
Portfolio management for Landeros Financial Ironware.

Manages multiple iron condor positions, aggregates risk, and enforces rules.

Author: Carlos Landeros
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json
from pathlib import Path

from landeros_ironware.config.settings import Settings
from landeros_ironware.strategies.iron_condor import IronCondorPosition, PositionStatus, IronCondor

logger = logging.getLogger(__name__)


@dataclass
class PortfolioMetrics:
    """
    Aggregated portfolio-level metrics.

    Provides a snapshot of portfolio health, risk exposure, and performance.
    """
    # P&L and performance
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0  # As % of initial capital

    # Risk exposure
    total_delta: float = 0.0
    total_vega: float = 0.0
    total_capital_at_risk: float = 0.0

    # Position counts
    position_count: int = 0
    open_position_count: int = 0
    closed_position_count: int = 0

    # Concentration
    exposure_by_underlying: Dict[str, float] = field(default_factory=dict)

    # Performance stats (for closed positions)
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_pnl_per_trade: float = 0.0

    def __repr__(self) -> str:
        return (
            f"PortfolioMetrics(P&L=${self.total_pnl:.2f}, "
            f"Delta={self.total_delta:.2f}, "
            f"Vega={self.total_vega:.2f}, "
            f"Open={self.open_position_count})"
        )


class PortfolioManager:
    """
    Manages a portfolio of iron condor positions.

    Responsibilities:
    - Track multiple positions
    - Aggregate risk metrics (delta, vega, P&L)
    - Enforce portfolio-level rules (max positions, exposure limits)
    - Monitor for risk breaches and exit conditions
    - Persist portfolio state to disk
    """

    def __init__(self, settings: Settings, initial_capital: float = 100000.0):
        """
        Initialize the portfolio manager.

        Args:
            settings: Configuration object
            initial_capital: Starting capital for the portfolio
        """
        self.settings = settings
        self.initial_capital = initial_capital
        self.positions: List[IronCondorPosition] = []

        # Portfolio file path
        portfolio_file = getattr(settings, "portfolio_file", None)
        self.portfolio_path = Path(portfolio_file) if portfolio_file else None

        # Load existing portfolio if available
        if self.portfolio_path and self.portfolio_path.exists():
            self.load_portfolio()

        logger.info(
            f"PortfolioManager initialized | "
            f"Capital: ${self.initial_capital:,.2f} | "
            f"Positions: {len(self.positions)}"
        )

    def add_position(self, position: IronCondorPosition) -> bool:
        """
        Add a position if it passes all risk rules.

        Checks:
        1. Max positions limit
        2. Capital allocation limit
        3. Underlying concentration limit
        4. Portfolio delta/vega limits (proactive check)

        Args:
            position: IronCondorPosition to add

        Returns:
            True if added successfully, False if rejected
        """
        # Get max positions from settings (with fallback)
        max_positions = getattr(self.settings.risk_params, "max_positions", 10)

        # Count open positions
        open_count = sum(1 for p in self.positions if p.status == PositionStatus.OPEN)

        # Check 1: Max positions
        if open_count >= max_positions:
            logger.warning(f"Max open positions reached ({open_count}/{max_positions})")
            return False

        # Calculate position risk
        position_risk = position.iron_condor.max_loss * position.contracts * 100

        # Get current portfolio risk
        current_risk = sum(
            p.iron_condor.max_loss * p.contracts * 100
            for p in self.positions
            if p.status == PositionStatus.OPEN
        )

        # Check 2: Capital allocation
        max_capital_at_risk = self.initial_capital * 0.50  # Max 50% of capital at risk
        if current_risk + position_risk > max_capital_at_risk:
            logger.warning(
                f"Position risk ${position_risk:.2f} exceeds remaining allocation. "
                f"Current: ${current_risk:.2f} / Max: ${max_capital_at_risk:.2f}"
            )
            return False

        # Check 3: Underlying concentration
        underlying = position.iron_condor.underlying
        current_exposure = sum(
            p.iron_condor.max_loss * p.contracts * 100
            for p in self.positions
            if p.iron_condor.underlying == underlying and p.status == PositionStatus.OPEN
        )

        max_exposure_per_underlying = self.initial_capital * 0.30  # Max 30% per underlying
        if current_exposure + position_risk > max_exposure_per_underlying:
            logger.warning(
                f"Exceeds max exposure for {underlying}: "
                f"${current_exposure + position_risk:.2f} > ${max_exposure_per_underlying:.2f}"
            )
            return False

        # Check 4: Portfolio Greeks limits (proactive)
        metrics = self.get_metrics()
        new_delta = metrics.total_delta + position.iron_condor.delta
        new_vega = metrics.total_vega + position.iron_condor.vega

        max_portfolio_delta = getattr(self.settings.risk_params, "max_portfolio_delta", 100.0)
        max_portfolio_vega = getattr(self.settings.risk_params, "max_portfolio_vega", 500.0)

        if abs(new_delta) > max_portfolio_delta:
            logger.warning(
                f"Adding position would breach portfolio delta limit: "
                f"{new_delta:.2f} > {max_portfolio_delta}"
            )
            return False

        if abs(new_vega) > max_portfolio_vega:
            logger.warning(
                f"Adding position would breach portfolio vega limit: "
                f"{new_vega:.2f} > {max_portfolio_vega}"
            )
            return False

        # All checks passed - add position
        self.positions.append(position)
        self.save_portfolio()

        logger.info(
            f"Added position: {position.iron_condor} | "
            f"Total open: {open_count + 1} | "
            f"Capital at risk: ${current_risk + position_risk:.2f}"
        )

        return True

    def remove_position(self, position: IronCondorPosition) -> bool:
        """
        Remove a position from the portfolio.

        Args:
            position: Position to remove

        Returns:
            True if removed, False if not found
        """
        if position in self.positions:
            self.positions.remove(position)
            self.save_portfolio()
            logger.info(f"Removed position: {position.iron_condor}")
            return True

        logger.warning(f"Position not found in portfolio: {position.iron_condor}")
        return False

    def update_positions(self, market_data: Optional[Dict] = None) -> None:
        """
        Update all open positions with current market data.

        Checks exit conditions and auto-closes positions that meet criteria.

        Args:
            market_data: Optional dict of current prices/greeks by underlying
        """
        open_positions = [p for p in self.positions if p.status == PositionStatus.OPEN]

        if not open_positions:
            logger.debug("No open positions to update")
            return

        logger.info(f"Updating {len(open_positions)} open positions...")

        for pos in open_positions:
            # TODO: Integrate with MarketDataFetcher to get real prices
            # For now, use mock data or data provided
            if market_data and pos.iron_condor.underlying in market_data:
                data = market_data[pos.iron_condor.underlying]
                current_price = data.get("current_price", 1.25)
                current_greeks = data.get("greeks", {"delta": 0.05, "vega": -50.0})
            else:
                # Mock data for development
                current_price = pos.entry_credit * 0.5  # Assume 50% profit
                current_greeks = {"delta": 0.05, "vega": -50.0}

            # Update market value
            pos.update_market_value(current_price, current_greeks)

            # Calculate current DTE
            current_dte = (pos.iron_condor.expiration - datetime.now()).days

            # Check exit conditions
            exit_reason = pos.check_exit_conditions(current_dte, self.settings)

            if exit_reason:
                # Auto-close the position
                pos.close(
                    exit_debit=current_price,
                    exit_date=datetime.now(),
                    reason=exit_reason,
                    commissions=self.settings.total_transaction_cost(pos.contracts)
                )
                logger.info(
                    f"Auto-closed position {pos.iron_condor} | "
                    f"Reason: {exit_reason.value} | "
                    f"P&L: ${pos.total_pnl:.2f}"
                )

        self.save_portfolio()

    def get_metrics(self) -> PortfolioMetrics:
        """
        Calculate aggregated portfolio metrics.

        Returns:
            PortfolioMetrics with all stats
        """
        open_positions = [p for p in self.positions if p.status == PositionStatus.OPEN]
        closed_positions = [p for p in self.positions if p.status == PositionStatus.CLOSED]
        all_positions = self.positions

        # Aggregate P&L
        total_pnl = sum(p.total_pnl for p in all_positions)
        total_pnl_pct = (total_pnl / self.initial_capital) if self.initial_capital > 0 else 0.0

        # Aggregate Greeks
        total_delta = sum(p.current_delta for p in open_positions)
        total_vega = sum(p.current_vega for p in open_positions)

        # Capital at risk
        total_capital_at_risk = sum(
            p.iron_condor.max_loss * p.contracts * 100
            for p in open_positions
        )

        # Exposure by underlying
        exposure_by_underlying: Dict[str, float] = {}
        for p in open_positions:
            und = p.iron_condor.underlying
            risk = p.iron_condor.max_loss * p.contracts * 100
            exposure_by_underlying[und] = exposure_by_underlying.get(und, 0.0) + risk

        # Performance stats (closed positions only)
        win_count = sum(1 for p in closed_positions if p.total_pnl > 0)
        loss_count = sum(1 for p in closed_positions if p.total_pnl <= 0)
        win_rate = (win_count / len(closed_positions)) if closed_positions else 0.0
        avg_pnl_per_trade = (
            sum(p.total_pnl for p in closed_positions) / len(closed_positions)
            if closed_positions else 0.0
        )

        return PortfolioMetrics(
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            total_delta=total_delta,
            total_vega=total_vega,
            total_capital_at_risk=total_capital_at_risk,
            position_count=len(all_positions),
            open_position_count=len(open_positions),
            closed_position_count=len(closed_positions),
            exposure_by_underlying=exposure_by_underlying,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            avg_pnl_per_trade=avg_pnl_per_trade,
        )

    def monitor_risks(self) -> List[str]:
        """
        Check for risk breaches and return alerts.

        Returns:
            List of alert messages (empty if no breaches)
        """
        metrics = self.get_metrics()
        alerts: List[str] = []

        # Get limits from settings
        max_portfolio_delta = getattr(self.settings.risk_params, "max_portfolio_delta", 100.0)
        max_portfolio_vega = getattr(self.settings.risk_params, "max_portfolio_vega", 500.0)
        max_exposure_per_underlying = self.initial_capital * 0.30

        # Check portfolio delta
        if abs(metrics.total_delta) > max_portfolio_delta:
            alerts.append(
                f"CRITICAL: Portfolio delta breach | "
                f"{metrics.total_delta:.2f} > {max_portfolio_delta}"
            )
        elif abs(metrics.total_delta) > max_portfolio_delta * 0.8:
            alerts.append(
                f"WARNING: Portfolio delta at 80% limit | "
                f"{metrics.total_delta:.2f} / {max_portfolio_delta}"
            )

        # Check portfolio vega
        if abs(metrics.total_vega) > max_portfolio_vega:
            alerts.append(
                f"CRITICAL: Portfolio vega breach | "
                f"{metrics.total_vega:.2f} > {max_portfolio_vega}"
            )
        elif abs(metrics.total_vega) > max_portfolio_vega * 0.8:
            alerts.append(
                f"WARNING: Portfolio vega at 80% limit | "
                f"{metrics.total_vega:.2f} / {max_portfolio_vega}"
            )

        # Check underlying concentration
        for und, exposure in metrics.exposure_by_underlying.items():
            if exposure > max_exposure_per_underlying:
                alerts.append(
                    f"CRITICAL: Exposure breach for {und} | "
                    f"${exposure:.2f} > ${max_exposure_per_underlying:.2f}"
                )
            elif exposure > max_exposure_per_underlying * 0.8:
                alerts.append(
                    f"WARNING: {und} exposure at 80% limit | "
                    f"${exposure:.2f} / ${max_exposure_per_underlying:.2f}"
                )

        # Check capital at risk
        max_capital_at_risk = self.initial_capital * 0.50
        if metrics.total_capital_at_risk > max_capital_at_risk:
            alerts.append(
                f"CRITICAL: Capital at risk exceeds limit | "
                f"${metrics.total_capital_at_risk:.2f} > ${max_capital_at_risk:.2f}"
            )

        # Log all alerts
        for alert in alerts:
            if "CRITICAL" in alert:
                logger.error(alert)
            else:
                logger.warning(alert)

        return alerts

    def save_portfolio(self) -> None:
        """Serialize portfolio to JSON file."""
        if not self.portfolio_path:
            logger.debug("No portfolio path configured, skipping save")
            return

        # Ensure parent directory exists
        self.portfolio_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize positions properly
        positions_data = []
        for p in self.positions:
            pos_dict = {
                "iron_condor": p.iron_condor.to_dict(),
                "contracts": p.contracts,
                "entry_credit": p.entry_credit,
                "entry_date": p.entry_date.isoformat(),
                "status": p.status.value,
                "exit_date": p.exit_date.isoformat() if p.exit_date else None,
                "exit_debit": p.exit_debit,
                "exit_reason": p.exit_reason.value if p.exit_reason else None,
                "commissions": p.commissions,
                "current_pnl_per_share": p.current_pnl_per_share,
                "current_mid_price": p.current_mid_price,
                "current_delta": p.current_delta,
                "current_vega": p.current_vega,
            }
            positions_data.append(pos_dict)

        # Create full portfolio document
        portfolio_data = {
            "metadata": {
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat(),
                "initial_capital": self.initial_capital,
            },
            "positions": positions_data,
        }

        # Write to file
        self.portfolio_path.write_text(json.dumps(portfolio_data, indent=2))
        logger.debug(f"Saved portfolio to {self.portfolio_path} ({len(self.positions)} positions)")

    def load_portfolio(self) -> None:
        """Load portfolio from JSON file."""
        if not self.portfolio_path or not self.portfolio_path.exists():
            logger.debug("No portfolio file found to load")
            return

        try:
            data = json.loads(self.portfolio_path.read_text())

            # Load metadata
            metadata = data.get("metadata", {})
            self.initial_capital = metadata.get("initial_capital", self.initial_capital)

            # Load positions
            positions_data = data.get("positions", [])
            self.positions = []

            for pos_dict in positions_data:
                # Reconstruct IronCondor
                ic = IronCondor.from_dict(pos_dict["iron_condor"])

                # Reconstruct IronCondorPosition
                position = IronCondorPosition(
                    iron_condor=ic,
                    contracts=pos_dict["contracts"],
                    entry_credit=pos_dict["entry_credit"],
                    entry_date=datetime.fromisoformat(pos_dict["entry_date"]),
                    status=PositionStatus(pos_dict["status"]),
                    exit_date=(
                        datetime.fromisoformat(pos_dict["exit_date"])
                        if pos_dict.get("exit_date") else None
                    ),
                    exit_debit=pos_dict.get("exit_debit", 0.0),
                    exit_reason=None,  # TODO: Deserialize ExitReason enum
                    commissions=pos_dict.get("commissions", 0.0),
                    current_pnl_per_share=pos_dict.get("current_pnl_per_share", 0.0),
                    current_mid_price=pos_dict.get("current_mid_price", 0.0),
                    current_delta=pos_dict.get("current_delta", 0.0),
                    current_vega=pos_dict.get("current_vega", 0.0),
                )

                self.positions.append(position)

            logger.info(
                f"Loaded portfolio from {self.portfolio_path} | "
                f"{len(self.positions)} positions"
            )

        except Exception as e:
            logger.error(f"Failed to load portfolio: {e}")
            self.positions = []

    def export_csv(self, file_path: str) -> None:
        """
        Export portfolio positions to CSV.

        Args:
            file_path: Path to save CSV file
        """
        import pandas as pd

        if not self.positions:
            logger.warning("No positions to export")
            return

        # Convert positions to records
        records = []
        for p in self.positions:
            record = {
                "Underlying": p.iron_condor.underlying,
                "DTE": p.iron_condor.dte,
                "Strikes": f"{p.iron_condor.short_put_strike}/{p.iron_condor.long_put_strike}-{p.iron_condor.short_call_strike}/{p.iron_condor.long_call_strike}",
                "Contracts": p.contracts,
                "Entry Credit": p.entry_credit,
                "Entry Date": p.entry_date,
                "Status": p.status.value,
                "P&L": p.total_pnl,
                "Days in Trade": p.days_in_trade,
            }
            records.append(record)

        # Create DataFrame and save
        df = pd.DataFrame(records)
        df.to_csv(file_path, index=False)
        logger.info(f"Exported portfolio to {file_path}")
