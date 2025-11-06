"""
Core Iron Condor strategy definitions.

Includes data structures for option legs, iron condor candidates,
and open positions. Provides the main `IronCondorScanner` class
for discovering trade opportunities.

Author: Carlos Landeros
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Literal
from datetime import datetime
from enum import Enum, auto
import numpy as np
import pandas as pd

# Core dependencies from the project
from landeros_ironware.config.settings import Settings
from landeros_ironware.data.fetcher import MarketDataFetcher, OptionChain, OptionQuote
from landeros_ironware.greeks.black_scholes import GreeksCalculator, OptionGreeks
from landeros_ironware.risk.probability import ProbabilityCalculator
from landeros_ironware.utils.helpers import calculate_dte, safe_divide

logger = logging.getLogger(__name__)

# --- Module-Level Constants (from review) ---
MIN_OPTION_PRICE = 0.10  # Minimum price for a liquid option
DEFAULT_IV = 0.15  # Fallback IV when data is missing
MIN_IV_THRESHOLD = 0.001  # Below this, IV is considered invalid


# --- Enums (as defined in __init__.py) ---

class PositionStatus(Enum):
    """Current state of a trade position."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"

class ExitReason(Enum):
    """Reason a position was closed."""
    PROFIT_TARGET = "PROFIT_TARGET"
    STOP_LOSS = "STOP_LOSS"
    DTE_EXIT = "DTE_EXIT"
    MANUAL = "MANUAL"
    EXPIRATION = "EXPIRATION"
    ABANDONED = "ABANDONED" # e.g., one side worthless


# --- Public Data Structure: The Candidate ---

@dataclass(frozen=True)
class IronCondor:
    """
    Represents a potential iron condor trade *candidate*.
    This is an immutable, data-only "spec" discovered by the scanner.
    All values are per-share (e.t., credit 2.50) unless noted.
    """

    underlying: str
    underlying_price: float
    dte: int
    expiration: datetime

    # Put spread
    short_put_strike: float
    long_put_strike: float

    # Call spread
    short_call_strike: float
    long_call_strike: float

    # --- Key Risk & Reward Metrics ---

    # Credit from selling the spreads
    credit: float

    # Max loss (width - credit)
    max_loss: float

    # Probability of Profit (theoretical)
    pop: float

    # Break-even points
    break_even_lower: float
    break_even_upper: float

    # --- Greeks for the total position ---
    delta: float
    gamma: float
    theta: float
    vega: float

    # Score for ranking (higher is better)
    score: float = 0.0

    # Optional references to the full quotes
    # (Using 'Any' to avoid circular type hints if quotes are complex)
    leg_quotes: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def put_wing_width(self) -> float:
        return self.short_put_strike - self.long_put_strike

    @property
    def call_wing_width(self) -> float:
        return self.long_call_strike - self.short_call_strike

    @property
    def max_profit(self) -> float:
        """Max profit is the credit received."""
        return self.credit

    @property
    def return_on_capital(self) -> float:
        """Return on Capital (ROC) = Credit / Max Loss."""
        return safe_divide(self.credit, self.max_loss, default=0.0)

    def __repr__(self) -> str:
        structure = (
            f"{int(self.long_put_strike)}/"
            f"{int(self.short_put_strike)}/"
            f"{int(self.short_call_strike)}/"
            f"{int(self.long_call_strike)}"
        )
        return (
            f"IronCondor({self.underlying} @ {self.dte}DTE | "
            f"{structure} | "
            f"Credit: ${self.credit:.2f} | MaxLoss: ${self.max_loss:.2f} | "
            f"POP: {self.pop:.1%})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return {
            "underlying": self.underlying,
            "underlying_price": self.underlying_price,
            "dte": self.dte,
            "expiration": self.expiration.isoformat(),
            "structure": {
                "short_put": self.short_put_strike,
                "long_put": self.long_put_strike,
                "short_call": self.short_call_strike,
                "long_call": self.long_call_strike,
            },
            "risk_metrics": {
                "credit": self.credit,
                "max_loss": self.max_loss,
                "max_profit": self.max_profit,
                "pop": self.pop,
                "roc": self.return_on_capital,
            },
            "greeks": {
                "delta": self.delta,
                "gamma": self.gamma,
                "theta": self.theta,
                "vega": self.vega,
            },
            "break_evens": {
                "lower": self.break_even_lower,
                "upper": self.break_even_upper,
            },
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IronCondor":
        """Deserialize from dictionary."""
        s = data["structure"]
        r = data["risk_metrics"]
        g = data["greeks"]
        b = data["break_evens"]

        return cls(
            underlying=data["underlying"],
            underlying_price=data["underlying_price"],
            dte=data["dte"],
            expiration=datetime.fromisoformat(data["expiration"]),
            short_put_strike=s["short_put"],
            long_put_strike=s["long_put"],
            short_call_strike=s["short_call"],
            long_call_strike=s["long_call"],
            credit=r["credit"],
            max_loss=r["max_loss"],
            pop=r["pop"],
            delta=g["delta"],
            gamma=g["gamma"],
            theta=g["theta"],
            vega=g["vega"],
            break_even_lower=b["lower"],
            break_even_upper=b["upper"],
            score=data.get("score", 0.0),
        )


# --- Public Data Structure: The Live Trade ---

@dataclass
class IronCondorPosition:
    """
    Represents an open/closed iron condor *position* for portfolio tracking.
    This is a stateful, mutable class that wraps an IronCondor spec.
    """

    iron_condor: IronCondor  # The immutable "spec" for this trade
    contracts: int
    entry_credit: float      # Actual filled credit (per-share)
    entry_date: datetime
    status: PositionStatus = PositionStatus.OPEN

    # State for closed positions
    exit_date: Optional[datetime] = None
    exit_debit: float = 0.0  # Actual cost to close (per-share)
    exit_reason: Optional[ExitReason] = None
    commissions: float = 0.0 # Total commissions

    # Mutable P&L and risk fields (per-share)
    current_pnl_per_share: float = 0.0
    current_mid_price: float = 0.0 # Current debit to close
    current_delta: float = 0.0
    current_vega: float = 0.0
    # ... other current greeks

    @property
    def total_pnl(self) -> float:
        """
        Calculates the total P&L for the position in dollars.
        (Does not include commissions).
        """
        if self.status == PositionStatus.OPEN:
            # P&L = (Entry Credit - Current Cost to Close)
            pnl_per_share = self.entry_credit - self.current_mid_price
        else:
            # Closed position P&L is locked in
            pnl_per_share = self.entry_credit - self.exit_debit

        return pnl_per_share * 100 * self.contracts

    @property
    def net_pnl(self) -> float:
        """Total P&L after commissions."""
        return self.total_pnl - self.commissions

    @property
    def dte_at_entry(self) -> int:
        return self.iron_condor.dte

    @property
    def days_in_trade(self) -> int:
        """Holding period in days."""
        if self.exit_date:
            return (self.exit_date - self.entry_date).days
        return (datetime.now() - self.entry_date).days

    def close(
        self,
        exit_debit: float,
        exit_date: datetime,
        reason: ExitReason,
        commissions: float = 0.0
    ) -> None:
        """Close the position and lock in P&L."""
        if self.status != PositionStatus.OPEN:
            logger.warning(f"Position {self.iron_condor} is already closed.")
            return

        self.status = PositionStatus.CLOSED
        self.exit_debit = exit_debit
        self.exit_date = exit_date
        self.exit_reason = reason
        self.commissions += commissions

        # Lock final P&L
        self.current_pnl_per_share = self.entry_credit - self.exit_debit
        logger.info(f"Closed position {self.iron_condor} for {self.total_pnl:.2f} P&L")

    def update_market_value(
        self,
        current_mid_price: float,
        current_greeks: Dict
    ) -> None:
        """
        Updates the position's current P&L and greeks from live market data.

        Args:
            current_mid_price: The current mid-price (debit) to close the position.
            current_greeks: A dict of the position's current greeks.
        """
        if self.status != PositionStatus.OPEN:
            return

        self.current_mid_price = current_mid_price
        self.current_pnl_per_share = self.entry_credit - self.current_mid_price
        self.current_delta = current_greeks.get('delta', 0)
        self.current_vega = current_greeks.get('vega', 0)

    def check_exit_conditions(
        self,
        current_dte: int,
        settings: Settings
    ) -> Optional[ExitReason]:
        """
        Checks if the position should be closed based on exit rules.
        This is the core logic for the "50% profit" and "21 DTE" rules.
        """
        if self.status != PositionStatus.OPEN:
            return None

        # --- Rule 1: DTE Exit ---
        if current_dte <= settings.exit_rules.dte_exit:
            logger.debug(f"Triggering DTE exit for {self.iron_condor}")
            return ExitReason.DTE_EXIT

        # --- Rule 2: Profit Target ---
        # Profit is (Entry Credit - Current Debit)
        profit_pct_of_credit = safe_divide(
            self.current_pnl_per_share, # (Entry Credit - Current Debit)
            self.entry_credit,
            default=0.0
        )

        if profit_pct_of_credit >= settings.exit_rules.profit_target_pct:
            logger.debug(f"Triggering Profit Target exit for {self.iron_condor}")
            return ExitReason.PROFIT_TARGET

        # --- Rule 3: Stop Loss ---
        # Stop loss based on current debit vs. credit
        # e.g., credit = 2.0. stop_multiple = 2.0. Stop if loss hits 4.0
        # This means stop if current debit hits 2.0 (entry) + 4.0 (loss) = 6.0

        stop_loss_debit_price = self.entry_credit + (self.entry_credit * settings.exit_rules.stop_loss_multiple)

        if self.current_mid_price >= stop_loss_debit_price:
            logger.debug(f"Triggering Stop Loss exit for {self.iron_condor}")
            return ExitReason.STOP_LOSS

        return None


# --- Main Scanner Class ---

class IronCondorScanner:
    """
    Scans for optimal iron condor opportunities based on settings.
    """

    def __init__(self, settings: Settings):
        """
        Initialize the scanner.

        Args:
            settings: Configuration object
        """
        self.settings = settings
        self.fetcher = MarketDataFetcher(settings.data_source)
        self.greeks_calc = GreeksCalculator(settings.risk_free_rate)

        # Prob calc is not finished, so we prepare to handle its failure
        try:
            self.prob_calc = ProbabilityCalculator()
        except NotImplementedError:
            self.prob_calc = None
            logger.warning(
                "ProbabilityCalculator not implemented. POP will be estimated."
            )

        logger.info(
            f"IronCondorScanner initialized for {settings.underlying} "
            f"(Target DTE: {settings.target_dte}, Target Delta: {settings.target_delta})"
        )

    def scan(self) -> List[IronCondor]:
        """
        Run the scan to find iron condor candidates.

        Returns:
            List[IronCondor]: A list of sorted candidates.
        """
        logger.info(f"Starting scan for {self.settings.underlying}...")

        # 1. Get underlying price
        try:
            underlying_price = self.fetcher.get_underlying_price(self.settings.underlying)
            logger.info(f"Current {self.settings.underlying} price: ${underlying_price:.2f}")
        except Exception as e:
            logger.error(f"Failed to fetch underlying price: {e}")
            return []

        # 2. Get option chain for target DTE
        try:
            min_dte, max_dte = self.settings.get_dte_range()
            option_chain = self.fetcher.get_option_chain(
                self.settings.underlying, dte_target=self.settings.target_dte
            )

            # Validate DTE is within tolerance
            if not (min_dte <= option_chain.dte <= max_dte):
                logger.warning(
                    f"No expiration found within DTE range {min_dte}-{max_dte}. "
                    f"Closest found: {option_chain.dte} DTE (outside tolerance)."
                )
                return []

            logger.info(
                f"Fetched option chain for {option_chain.expiration.strftime('%Y-%m-%d')} "
                f"({option_chain.dte} DTE)"
            )

        except Exception as e:
            logger.error(f"Failed to fetch option chain: {e}")
            return []

        # 3. Calculate greeks for all legs to filter by delta
        logger.info(
            f"Calculating greeks for {len(option_chain.puts)} puts and "
            f"{len(option_chain.calls)} calls..."
        )
        self._calculate_greeks_for_chain(option_chain)

        # 4. Filter legs to find valid short strikes
        min_delta, max_delta = self.settings.get_delta_range()

        valid_short_puts = [
            p for p in option_chain.puts
            if p.delta is not None
            and abs(p.delta) >= min_delta  # e.g., |-.18| >= .13
            and abs(p.delta) <= max_delta  # e.g., |-.18| <= .19
            and p.mid_price > MIN_OPTION_PRICE
        ]

        valid_short_calls = [
            c for c in option_chain.calls
            if c.delta is not None
            and c.delta >= min_delta  # e.g., .18 >= .13
            and c.delta <= max_delta  # e.g., .18 <= .19
            and c.mid_price > MIN_OPTION_PRICE
        ]

        if not valid_short_puts or not valid_short_calls:
            logger.warning("No valid short strikes found in the target delta range.")
            return []

        logger.info(
            f"Found {len(valid_short_puts)} valid short puts and "
            f"{len(valid_short_calls)} valid short calls."
        )

        # 5. Assemble candidates
        candidates: List[IronCondor] = []
        wing_width = self.settings.wing_width

        for sp in valid_short_puts:
            # Find matching long put
            lp = option_chain.get_put_by_strike(sp.strike - wing_width)
            if not lp or lp.mid_price <= 0:
                continue  # No matching wing or invalid price

            for sc in valid_short_calls:
                # Ensure separation between strikes (e.g., short call > short put)
                if sc.strike <= sp.strike:
                    continue

                # Find matching long call
                lc = option_chain.get_call_by_strike(sc.strike + wing_width)
                if not lc or lc.mid_price <= 0:
                    continue  # No matching wing or invalid price

                # We have 4 valid legs. Build and validate.
                candidate = self._build_candidate(
                    underlying_price,
                    option_chain,
                    sp, lp, sc, lc,
                )

                if self._validate_candidate(candidate):
                    candidates.append(candidate)

        # 6. Score and sort
        if not candidates:
            logger.warning("No candidates found after assembly and validation.")
            return []

        # Score candidates using the StrikeOptimizer
        from landeros_ironware.strategies.optimizer import StrikeOptimizer

        optimizer = StrikeOptimizer(self.settings)
        candidates = optimizer.score_and_sort_candidates(candidates)

        logger.info(f"Scan complete. Found {len(candidates)} valid iron condors.")
        return candidates

    def _calculate_greeks_for_chain(self, chain: OptionChain) -> None:
        """
        Helper to calculate greeks for all quotes in a chain (in-place).
        This is a performance bottleneck and a candidate for optimization.
        """
        for quote in chain.calls + chain.puts:
            # Skip if greeks are already provided by data source
            if quote.delta is not None and quote.implied_volatility > MIN_IV_THRESHOLD:
                continue

            iv = quote.implied_volatility
            if iv <= MIN_IV_THRESHOLD:
                iv = DEFAULT_IV # Fallback IV

            try:
                greeks = self.greeks_calc.calculate(
                    underlying_price=chain.underlying_price,
                    strike=quote.strike,
                    dte=chain.dte,
                    implied_vol=iv,
                    option_type=quote.option_type,
                )
                quote.delta = greeks.delta
                quote.gamma = greeks.gamma
                quote.theta = greeks.theta
                quote.vega = greeks.vega
            except Exception as e:
                logger.debug(
                    f"Could not calculate greeks for {quote.strike} {quote.option_type}: {e}"
                )

    def _build_candidate(
        self,
        underlying_price: float,
        chain: OptionChain,
        sp: OptionQuote, # Short Put
        lp: OptionQuote, # Long Put
        sc: OptionQuote, # Short Call
        lc: OptionQuote, # Long Call
    ) -> IronCondor:
        """Assemble an IronCondor data structure from 4 legs."""

        # --- Prices (using mid-price for theoretical credit) ---
        sp_price = sp.mid_price
        lp_price = lp.mid_price
        sc_price = sc.mid_price
        lc_price = lc.mid_price

        # --- Credit ---
        # Credit = (Price of Sold) - (Price of Bought)
        put_credit = sp_price - lp_price
        call_credit = sc_price - lc_price
        total_credit = put_credit + call_credit

        # --- Max Loss (assuming equal wing widths) ---
        # Max loss is width of one spread - total credit
        # We use the *configured* wing width, not the difference in strikes
        # This handles cases where strikes aren't perfect
        max_width = self.settings.wing_width
        max_loss = max_width - total_credit

        # --- Greeks (Sum of all legs) ---
        # Convention: Short = -1 (we sold), Long = +1 (we bought)
        # BS greeks are already signed (put delta < 0, call delta > 0)
        #
        # Short Put: -1 * (put_delta) = +delta
        # Long Put: +1 * (put_delta) = -delta
        # Short Call: -1 * (call_delta) = -delta
        # Long Call: +1 * (call_delta) = +delta

        total_delta = (sp.delta * -1) + (lp.delta * 1) + (sc.delta * -1) + (lc.delta * 1)
        total_gamma = (sp.gamma * -1) + (lp.gamma * 1) + (sc.gamma * -1) + (lc.gamma * 1)
        total_theta = (sp.theta * -1) + (lp.theta * 1) + (sc.theta * -1) + (lc.theta * 1)
        total_vega  = (sp.vega * -1)  + (lp.vega * 1)  + (sc.vega * -1)  + (lc.vega * 1)

        # --- Break-evens ---
        be_lower = sp.strike - total_credit
        be_upper = sc.strike + total_credit

        # --- Probability of Profit (POP) ---
        pop = 0.0
        try:
            if self.prob_calc:
                pop = self.prob_calc.calculate_pop_lognormal(
                    underlying_price=underlying_price,
                    lower_strike=be_lower,
                    upper_strike=be_upper,
                    dte=chain.dte,
                    # Use average IV of the short strikes
                    iv=(sp.implied_volatility + sc.implied_volatility) / 2
                )
            else:
                raise NotImplementedError("prob_calc is None")
        except (NotImplementedError, AttributeError, TypeError):
            # Fallback: Estimate POP based on short deltas
            # POP approx 1 - (delta_put + delta_call)
            pop = 1.0 - (abs(sp.delta) + abs(sc.delta))
            # Clamp between 0 and 1
            pop = max(0.0, min(1.0, pop))

        # --- Store Leg Quotes ---
        leg_quotes = {
            "short_put": sp.to_dict(),
            "long_put": lp.to_dict(),
            "short_call": sc.to_dict(),
            "long_call": lc.to_dict(),
        }

        return IronCondor(
            underlying=self.settings.underlying,
            underlying_price=underlying_price,
            dte=chain.dte,
            expiration=chain.expiration,
            short_put_strike=sp.strike,
            long_put_strike=lp.strike,
            short_call_strike=sc.strike,
            long_call_strike=lc.strike,
            credit=total_credit,
            max_loss=max_loss,
            pop=pop,
            break_even_lower=be_lower,
            break_even_upper=be_upper,
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega,
            leg_quotes=leg_quotes,
        )

    def _validate_candidate(self, ic: IronCondor) -> bool:
        """Check if a candidate meets all settings criteria."""
        s = self.settings

        # 1. Credit (Min Credit)
        if ic.credit < s.min_credit:
            return False

        # 2. Credit/Width Ratio
        if ic.max_loss <= 0: return False # Bad data
        ratio = safe_divide(ic.credit, ic.max_loss + ic.credit) # Credit / Width
        if ratio < s.min_credit_to_width_ratio:
            return False

        # 3. POP (Min POP)
        if ic.pop < s.min_pop:
            return False

        # 4. Position Greeks (Max Delta, Max Vega)
        if abs(ic.delta) > s.max_position_delta:
            return False

        # FIXED: Reject if absolute vega exposure is too high
        if abs(ic.vega) > s.max_position_vega:
            return False

        # 5. Max Loss vs Credit
        # Per prompt: max loss ≤ 3× credit
        if ic.max_loss > (ic.credit * s.exit_rules.stop_loss_multiple):
            # We re-use the stop_loss_multiple (e.g., 2x or 3x)
             return False

        # 6. Check for bad math (e.g., negative credit)
        if ic.credit <= 0 or ic.max_loss <= 0:
            return False

        return True
