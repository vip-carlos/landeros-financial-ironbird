"""
Utility functions and helpers for Landeros Financial Ironware.

Provides common functionality used throughout the package including
logging setup, validation, date handling, and formatting utilities.

Author: Carlos Landeros
"""

import logging
import colorlog
from typing import Optional, Union, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from pathlib import Path


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure colored logging for the application.

    Args:
        level: Logging level (default: logging.INFO)
    """
    # Create console handler with color formatting
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(name)s%(reset)s %(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
            secondary_log_colors={},
            style="%",
        )
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers = []

    # Add our handler
    root_logger.addHandler(handler)

    # Set package logger
    package_logger = logging.getLogger("landeros_ironware")
    package_logger.setLevel(level)


def validate_underlying(underlying: str) -> str:
    """
    Validate and normalize underlying symbol.

    Args:
        underlying: Index symbol (SPX, NDX, or RUT)

    Returns:
        str: Normalized uppercase symbol

    Raises:
        ValueError: If underlying is not supported
    """
    from landeros_ironware.config import SUPPORTED_UNDERLYINGS

    underlying_upper = underlying.upper()
    if underlying_upper not in SUPPORTED_UNDERLYINGS:
        raise ValueError(
            f"Underlying '{underlying}' not supported. "
            f"Must be one of: {', '.join(SUPPORTED_UNDERLYINGS)}"
        )
    return underlying_upper


def validate_strike_price(strike: float, underlying: str) -> None:
    """
    Validate strike price is reasonable for the underlying.

    Args:
        strike: Strike price to validate
        underlying: Index symbol

    Raises:
        ValueError: If strike price is invalid
    """
    if strike <= 0:
        raise ValueError(f"Strike price must be positive, got {strike}")

    # Reasonable bounds based on historical index values
    bounds = {
        "SPX": (100, 10000),
        "NDX": (100, 25000),
        "RUT": (100, 5000),
    }

    if underlying in bounds:
        min_strike, max_strike = bounds[underlying]
        if not (min_strike <= strike <= max_strike):
            raise ValueError(
                f"Strike {strike} outside reasonable range "
                f"[{min_strike}, {max_strike}] for {underlying}"
            )


def validate_date_range(start_date: datetime, end_date: datetime) -> None:
    """
    Validate date range for backtesting.

    Args:
        start_date: Start date
        end_date: End date

    Raises:
        ValueError: If date range is invalid
    """
    if start_date >= end_date:
        raise ValueError(
            f"Start date {start_date} must be before end date {end_date}"
        )

    # Check if dates are too far in the future
    today = datetime.now()
    if start_date > today:
        raise ValueError(f"Start date {start_date} cannot be in the future")


def calculate_dte(expiration_date: Union[datetime, str], current_date: Optional[datetime] = None) -> int:
    """
    Calculate days to expiration.

    Args:
        expiration_date: Option expiration date
        current_date: Current date (default: today)

    Returns:
        int: Days to expiration
    """
    if isinstance(expiration_date, str):
        expiration_date = pd.to_datetime(expiration_date)

    if current_date is None:
        current_date = datetime.now()

    delta = expiration_date - current_date
    return max(0, delta.days)


def annualize_return(total_return: float, days: int) -> float:
    """
    Annualize a return based on holding period.

    Args:
        total_return: Total return (e.g., 0.15 for 15%)
        days: Number of days in holding period

    Returns:
        float: Annualized return
    """
    if days <= 0:
        return 0.0

    years = days / 365.25
    return (1 + total_return) ** (1 / years) - 1


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.045,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sharpe ratio from returns.

    Args:
        returns: Array of period returns
        risk_free_rate: Annual risk-free rate (default: 4.5%)
        periods_per_year: Number of periods per year (default: 252 for daily)

    Returns:
        float: Sharpe ratio
    """
    if len(returns) == 0:
        return 0.0

    excess_returns = returns - (risk_free_rate / periods_per_year)
    if excess_returns.std() == 0:
        return 0.0

    return np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std()


def calculate_max_drawdown(equity_curve: Union[pd.Series, np.ndarray]) -> float:
    """
    Calculate maximum drawdown from equity curve.

    Args:
        equity_curve: Series or array of portfolio values

    Returns:
        float: Maximum drawdown as a decimal (e.g., 0.15 for 15%)
    """
    if isinstance(equity_curve, np.ndarray):
        equity_curve = pd.Series(equity_curve)

    if len(equity_curve) == 0:
        return 0.0

    # Calculate running maximum
    running_max = equity_curve.expanding().max()

    # Calculate drawdown
    drawdown = (equity_curve - running_max) / running_max

    return abs(drawdown.min())


def format_currency(value: float, decimals: int = 2) -> str:
    """
    Format value as currency string.

    Args:
        value: Numeric value
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted currency string (e.g., "$1,234.56")
    """
    return f"${value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format value as percentage string.

    Args:
        value: Decimal value (e.g., 0.1234 for 12.34%)
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted percentage string (e.g., "12.34%")
    """
    return f"{value * 100:.{decimals}f}%"


def round_to_tick(price: float, tick_size: float = 0.05) -> float:
    """
    Round price to nearest valid tick.

    Args:
        price: Price to round
        tick_size: Minimum tick size (default: 0.05 for most index options)

    Returns:
        float: Rounded price
    """
    return round(price / tick_size) * tick_size


def get_third_friday(year: int, month: int) -> datetime:
    """
    Get the third Friday of a month (standard option expiration).

    Args:
        year: Year
        month: Month (1-12)

    Returns:
        datetime: Third Friday of the month
    """
    # First day of month
    first_day = datetime(year, month, 1)

    # Find first Friday
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)

    # Third Friday is 14 days after first Friday
    third_friday = first_friday + timedelta(days=14)

    return third_friday


def get_next_monthly_expiration(from_date: Optional[datetime] = None) -> datetime:
    """
    Get next monthly option expiration date (third Friday).

    Args:
        from_date: Start date (default: today)

    Returns:
        datetime: Next monthly expiration
    """
    if from_date is None:
        from_date = datetime.now()

    # Check current month
    third_friday = get_third_friday(from_date.year, from_date.month)

    if third_friday > from_date:
        return third_friday

    # Move to next month
    if from_date.month == 12:
        next_month = datetime(from_date.year + 1, 1, 1)
    else:
        next_month = datetime(from_date.year, from_date.month + 1, 1)

    return get_third_friday(next_month.year, next_month.month)


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if necessary.

    Args:
        path: Directory path

    Returns:
        Path: Path object for the directory
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if denominator is zero (default: 0.0)

    Returns:
        float: Result of division or default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Clamp value between min and max.

    Args:
        value: Value to clamp
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        float: Clamped value
    """
    return max(min_value, min(max_value, value))


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """
    Check if US equity markets are open.

    Simple check for weekdays during market hours (9:30 AM - 4:00 PM ET).
    Does not account for market holidays.

    Args:
        dt: Datetime to check (default: now)

    Returns:
        bool: True if markets are likely open
    """
    if dt is None:
        dt = datetime.now()

    # Check if weekday (Monday=0, Sunday=6)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check time (simplified, assumes ET)
    market_open = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = dt.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= dt <= market_close


class ProgressTracker:
    """Simple progress tracker for long-running operations."""

    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items
            description: Operation description
        """
        self.total = total
        self.current = 0
        self.description = description
        self.logger = logging.getLogger(__name__)

    def update(self, increment: int = 1) -> None:
        """Update progress by increment."""
        self.current += increment
        if self.current % max(1, self.total // 10) == 0 or self.current == self.total:
            pct = (self.current / self.total) * 100
            self.logger.info(f"{self.description}: {self.current}/{self.total} ({pct:.1f}%)")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            self.logger.info(f"{self.description}: Complete")
        return False
