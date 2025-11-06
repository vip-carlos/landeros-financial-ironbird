"""
Landeros Financial Ironware

Institutional-grade iron condor scanner and manager for European-style index options.
Built for Section 1256 tax treatment and early-exit discipline.

Copyright (c) 2025 Carlos Landeros
Licensed under the MIT License.
"""

__version__ = "1.0.0"
__author__ = "Carlos Landeros"
__email__ = "carlos@landeros-financial.com"
__license__ = "MIT"

# Core imports for package-level access
from landeros_ironware.config.settings import Settings
from landeros_ironware.strategies.iron_condor import IronCondor, IronCondorScanner
from landeros_ironware.greeks.black_scholes import GreeksCalculator, BlackScholes
from landeros_ironware.risk.probability import ProbabilityCalculator
from landeros_ironware.risk.portfolio import Portfolio, PortfolioManager
from landeros_ironware.visuals.payoff import PayoffDiagram
from landeros_ironware.backtest.engine import BacktestEngine, BacktestResults
from landeros_ironware.data.fetcher import MarketDataFetcher

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    # Configuration
    "Settings",
    # Strategy components
    "IronCondor",
    "IronCondorScanner",
    # Greeks and pricing
    "GreeksCalculator",
    "BlackScholes",
    # Risk management
    "ProbabilityCalculator",
    "Portfolio",
    "PortfolioManager",
    # Visualization
    "PayoffDiagram",
    # Backtesting
    "BacktestEngine",
    "BacktestResults",
    # Data
    "MarketDataFetcher",
]


def get_version() -> str:
    """
    Return the current version of Landeros Financial Ironware.

    Returns:
        str: Version string in semantic versioning format (MAJOR.MINOR.PATCH)
    """
    return __version__


def get_supported_underlyings() -> list[str]:
    """
    Return list of supported European-style index options.

    Returns:
        list[str]: List of ticker symbols for supported underlyings
    """
    return ["SPX", "NDX", "RUT"]


def get_info() -> dict[str, str]:
    """
    Return package information dictionary.

    Returns:
        dict[str, str]: Package metadata including version, author, license, etc.
    """
    return {
        "name": "Landeros Financial Ironware",
        "version": __version__,
        "author": __author__,
        "email": __email__,
        "license": __license__,
        "description": "Institutional-grade iron condor scanner for European-style index options",
        "supported_underlyings": ", ".join(get_supported_underlyings()),
        "tax_treatment": "Section 1256 (60/40)",
        "python_requires": ">=3.9",
    }


# Module-level configuration
import logging

# Set up package-level logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Display startup message when package is imported
def _display_startup_message() -> None:
    """Display package information on import (can be disabled via environment variable)."""
    import os

    if os.getenv("LANDEROS_IRONWARE_QUIET", "").lower() not in ("1", "true", "yes"):
        return  # Silent by default

    print(f"Landeros Financial Ironware v{__version__}")
    print(f"Supported: {', '.join(get_supported_underlyings())}")


# Uncomment to enable startup message
# _display_startup_message()
