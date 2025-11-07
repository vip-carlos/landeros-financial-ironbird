"""
Market data fetcher for option chains and underlying prices.

Defines the abstract base class for all data fetchers
and provides a default implementation for yfinance.

Author: Carlos Landeros
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
import pickle
import time

from landeros_ironware.config.settings import DataSourceConfig, Settings
from landeros_ironware.utils.helpers import calculate_dte, ensure_dir

logger = logging.getLogger(__name__)


@dataclass
class OptionQuote:
    """Single option quote data."""

    strike: float
    expiration: datetime
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None

    @property
    def mid_price(self) -> float:
        """Calculate mid-market price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last if self.last > 0 else 0.0

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0

    @property
    def spread_pct(self) -> float:
        """Calculate spread as percentage of mid price."""
        mid = self.mid_price
        if mid > 0:
            return self.spread / mid
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strike": self.strike,
            "expiration": self.expiration.isoformat() if isinstance(self.expiration, datetime) else str(self.expiration),
            "option_type": self.option_type,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "implied_volatility": self.implied_volatility,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
        }


@dataclass
class OptionChain:
    """Complete option chain for an expiration date."""

    underlying: str
    underlying_price: float
    expiration: datetime
    calls: List[OptionQuote]
    puts: List[OptionQuote]
    timestamp: datetime

    @property
    def dte(self) -> int:
        """Days to expiration."""
        return calculate_dte(self.expiration, self.timestamp)

    def get_call_by_strike(self, strike: float) -> Optional[OptionQuote]:
        """Get call option at specific strike."""
        for call in self.calls:
            if abs(call.strike - strike) < 0.01:
                return call
        return None

    def get_put_by_strike(self, strike: float) -> Optional[OptionQuote]:
        """Get put option at specific strike."""
        for put in self.puts:
            if abs(put.strike - strike) < 0.01:
                return put
        return None

    def get_strikes(self) -> List[float]:
        """Get sorted list of all available strikes."""
        strikes = set()
        for call in self.calls:
            strikes.add(call.strike)
        for put in self.puts:
            strikes.add(put.strike)
        return sorted(list(strikes))


# --- NEW: Abstract Base Class ---
class MarketDataFetcher(ABC):
    """
    Abstract interface for all market data fetchers.

    This base class ensures that all fetchers (YFinance, IBKR, etc.)
    implement the same core methods, enabling easy swapping of data sources.
    """

    @abstractmethod
    def get_underlying_price(self, symbol: str) -> float:
        """
        Get current underlying price.

        Args:
            symbol: Underlying symbol (SPX, NDX, RUT)

        Returns:
            float: Current underlying price

        Raises:
            ValueError: If unable to fetch price
        """
        pass

    @abstractmethod
    def get_option_chain(
        self,
        symbol: str,
        expiration: Optional[datetime] = None,
        dte_target: Optional[int] = None,
    ) -> OptionChain:
        """
        Get option chain for specific expiration.

        Args:
            symbol: Underlying symbol
            expiration: Specific expiration date (optional)
            dte_target: Target DTE (finds closest expiration, optional)

        Returns:
            OptionChain: Complete option chain data

        Raises:
            ValueError: If unable to fetch option chain
        """
        pass


# --- RENAMED: YFinance Implementation ---
class YFinanceDataFetcher(MarketDataFetcher):
    """
    Market data fetcher using yfinance (Yahoo Finance API).

    Implements caching to reduce API calls and improve performance.
    This is a free data source suitable for development and backtesting.
    """

    def __init__(self, settings: Settings):
        """
        Initialize yfinance data fetcher.

        Args:
            settings: Application settings containing data source configuration
        """
        config = settings.data_source
        self.config = config
        self.cache_enabled = config.use_cache
        self.cache_dir = ensure_dir(config.cache_dir)
        self.cache_ttl = timedelta(minutes=config.cache_ttl_minutes)

        logger.info(f"Initialized YFinanceDataFetcher with cache: {config.use_cache}")

    def get_underlying_price(self, symbol: str) -> float:
        """Get current underlying price from yfinance."""
        cache_key = f"price_{symbol}"

        # Check cache
        if self.cache_enabled:
            cached_price = self._get_from_cache(cache_key)
            if cached_price is not None:
                logger.debug(f"Using cached price for {symbol}: ${cached_price:.2f}")
                return cached_price

        # Fetch from source
        try:
            # Map index symbols to ticker equivalents
            ticker_map = {
                "SPX": "^GSPC",  # S&P 500
                "NDX": "^NDX",   # Nasdaq-100
                "RUT": "^RUT",   # Russell 2000
            }

            ticker_symbol = ticker_map.get(symbol, symbol)
            ticker = yf.Ticker(ticker_symbol)

            # Try to get current price from info
            try:
                price = ticker.info.get("regularMarketPrice") or ticker.info.get("currentPrice")
            except:
                # Fallback to recent history
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                else:
                    raise ValueError(f"No price data available for {symbol}")

            if price is None or price <= 0:
                raise ValueError(f"Invalid price received for {symbol}: {price}")

            # Cache the result
            if self.cache_enabled:
                self._save_to_cache(cache_key, price)

            logger.info(f"Fetched yfinance price for {symbol}: ${price:.2f}")
            return float(price)

        except Exception as e:
            logger.error(f"Failed to fetch yfinance price for {symbol}: {e}")
            raise ValueError(f"Unable to fetch price for {symbol}: {e}")

    def get_option_chain(
        self,
        symbol: str,
        expiration: Optional[datetime] = None,
        dte_target: Optional[int] = None,
    ) -> OptionChain:
        """Get option chain from yfinance."""
        # Map index symbols to option-enabled tickers
        ticker_map = {
            "SPX": "^SPX",
            "NDX": "^NDX",
            "RUT": "^RUT",
        }

        ticker_symbol = ticker_map.get(symbol, symbol)

        try:
            ticker = yf.Ticker(ticker_symbol)

            # Get available expirations
            try:
                expirations = ticker.options
            except:
                # For symbols without options data, return mock data
                logger.warning(f"No options data available for {symbol}, using mock data")
                return self._create_mock_option_chain(symbol)

            if not expirations:
                logger.warning(f"No expirations found for {symbol}, using mock data")
                return self._create_mock_option_chain(symbol)

            # Find target expiration
            if expiration is None:
                if dte_target is not None:
                    target_date = datetime.now() + timedelta(days=dte_target)
                    expiration = self._find_closest_expiration(expirations, target_date)
                else:
                    # Use first available expiration
                    expiration = pd.to_datetime(expirations[0])

            # Format expiration for yfinance
            exp_str = expiration.strftime("%Y-%m-%d") if isinstance(expiration, datetime) else str(expiration)

            # Fetch option chain
            opt_chain = ticker.option_chain(exp_str)

            # Get underlying price
            underlying_price = self.get_underlying_price(symbol)

            # Parse calls
            calls = self._parse_option_data(
                opt_chain.calls,
                expiration,
                "call",
            )

            # Parse puts
            puts = self._parse_option_data(
                opt_chain.puts,
                expiration,
                "put",
            )

            chain = OptionChain(
                underlying=symbol,
                underlying_price=underlying_price,
                expiration=expiration,
                calls=calls,
                puts=puts,
                timestamp=datetime.now(),
            )

            logger.info(
                f"Fetched yfinance option chain for {symbol} expiring {expiration.strftime('%Y-%m-%d')} "
                f"({len(calls)} calls, {len(puts)} puts)"
            )

            return chain

        except Exception as e:
            logger.error(f"Failed to fetch yfinance option chain for {symbol}: {e}")
            # Return mock data as fallback
            return self._create_mock_option_chain(symbol)

    def _find_closest_expiration(self, expirations: List[str], target_date: datetime) -> datetime:
        """Find expiration closest to target date."""
        exp_dates = [pd.to_datetime(exp) for exp in expirations]
        closest = min(exp_dates, key=lambda x: abs((x - target_date).days))
        return closest

    def _parse_option_data(
        self,
        df: pd.DataFrame,
        expiration: datetime,
        option_type: str,
    ) -> List[OptionQuote]:
        """Parse option data from DataFrame."""
        options = []

        for _, row in df.iterrows():
            try:
                quote = OptionQuote(
                    strike=float(row.get("strike", 0)),
                    expiration=expiration,
                    option_type=option_type,
                    bid=float(row.get("bid", 0)),
                    ask=float(row.get("ask", 0)),
                    last=float(row.get("lastPrice", 0)),
                    volume=int(row.get("volume", 0)),
                    open_interest=int(row.get("openInterest", 0)),
                    implied_volatility=float(row.get("impliedVolatility", 0)),
                )
                options.append(quote)
            except Exception as e:
                logger.debug(f"Skipping option row due to error: {e}")
                continue

        return options

    def _create_mock_option_chain(self, symbol: str) -> OptionChain:
        """Create mock option chain for testing/development."""
        # Get or estimate underlying price
        try:
            underlying_price = self.get_underlying_price(symbol)
        except:
            # Use typical values
            price_map = {"SPX": 4500.0, "NDX": 15000.0, "RUT": 2000.0}
            underlying_price = price_map.get(symbol, 4500.0)

        expiration = datetime.now() + timedelta(days=45)

        # Generate strikes around current price
        strikes = []
        strike_increment = 50 if symbol == "SPX" else (100 if symbol == "NDX" else 25)

        for i in range(-10, 11):
            strikes.append(underlying_price + i * strike_increment)

        # Create mock calls and puts
        calls = []
        puts = []

        for strike in strikes:
            # Mock pricing (very simplified)
            intrinsic_call = max(0, underlying_price - strike)
            intrinsic_put = max(0, strike - underlying_price)

            time_value = 10.0  # Simplified

            calls.append(OptionQuote(
                strike=strike,
                expiration=expiration,
                option_type="call",
                bid=intrinsic_call + time_value - 0.5,
                ask=intrinsic_call + time_value + 0.5,
                last=intrinsic_call + time_value,
                volume=100,
                open_interest=500,
                implied_volatility=0.15,
                delta=0.5 if strike == underlying_price else (0.7 if strike < underlying_price else 0.3),
            ))

            puts.append(OptionQuote(
                strike=strike,
                expiration=expiration,
                option_type="put",
                bid=intrinsic_put + time_value - 0.5,
                ask=intrinsic_put + time_value + 0.5,
                last=intrinsic_put + time_value,
                volume=100,
                open_interest=500,
                implied_volatility=0.15,
                delta=-0.5 if strike == underlying_price else (-0.3 if strike < underlying_price else -0.7),
            ))

        logger.warning(f"Using mock option chain for {symbol}")

        return OptionChain(
            underlying=symbol,
            underlying_price=underlying_price,
            expiration=expiration,
            calls=calls,
            puts=puts,
            timestamp=datetime.now(),
        )

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{key}.pkl"

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            # Check if cache is expired
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if datetime.now() - mtime > self.cache_ttl:
                cache_path.unlink()
                return None

            # Load from cache
            with open(cache_path, "rb") as f:
                return pickle.load(f)

        except Exception as e:
            logger.debug(f"Cache read error for {key}: {e}")
            return None

    def _save_to_cache(self, key: str, data: Any) -> None:
        """Save data to cache."""
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.debug(f"Cache write error for {key}: {e}")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            logger.info("Cache cleared")
