"""
Strategies module for Landeros Financial Ironware.

Contains the core logic for iron condor strategy definition, scanning,
optimization, and position management.

Main Classes:
    - IronCondor: Defines the structure of an iron condor candidate.
    - IronCondorScanner: Scans market data for optimal trade opportunities.
    - IronCondorPosition: Tracks a live, open iron condor position.
    - StrikeOptimizer: Core engine for optimizing strike selection.
    - PositionStatus: Enum for the state of a position (OPEN, CLOSED).

Usage:
    >>> from landeros_ironware.strategies import IronCondorScanner
    >>> from landeros_ironware.config import Settings
    >>>
    >>> settings = Settings(underlying="SPX", target_dte=45)
    >>> scanner = IronCondorScanner(settings)
    >>> candidates = scanner.scan()
    >>> best_trade = candidates[0]
    >>>
    >>> from landeros_ironware.strategies import IronCondorPosition
    >>> position = IronCondorPosition(
    >>>     iron_condor=best_trade,
    >>>     contracts=10,
    >>>     entry_credit=best_trade.credit
    >>> )
"""

# Import Enums first
from landeros_ironware.strategies.iron_condor import (
    PositionStatus,
    ExitReason,
)

# Import main data structures
from landeros_ironware.strategies.iron_condor import (
    IronCondor,
    IronCondorPosition,
)

# Import tools and scanners
from landeros_ironware.strategies.iron_condor import (
    IronCondorScanner
)
from landeros_ironware.strategies.optimizer import (
    StrikeOptimizer,
    OptimizationResult,
    OptimizationCriteria,
)

__all__ = [
    # Enums
    "PositionStatus",
    "ExitReason",

    # Core strategy classes
    "IronCondor",
    "IronCondorScanner",
    "IronCondorPosition",

    # Optimization
    "StrikeOptimizer",
    "OptimizationResult",
    "OptimizationCriteria",
]
