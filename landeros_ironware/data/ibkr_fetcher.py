"""
Interactive Brokers (IBKR) data fetcher.

Provides a high-reliability, streaming-capable data source
by connecting directly to the IBKR TWS or Gateway API.

Author: Carlos Landeros
"""

import logging
import asyncio
import numpy as np
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from ib_insync import IB, util, Stock, Option, Ticker
from ib_insync.contract import Contract as IBContract

from landeros_ironware.config.settings import DataSourceConfig, Settings
from .fetcher import MarketDataFetcher, OptionChain, OptionQuote, YFinanceDataFetcher
from landeros_ironware.utils.helpers import calculate_dte

logger = logging.getLogger(__name__)


class IBKRDataFetcher(MarketDataFetcher):
    """
    MarketDataFetcher implementation for Interactive Brokers.

    Uses ib_insync to connect to TWS or IB Gateway for real-time
    market data. Falls back to yfinance for full option chain data
    (IBKR option chain fetching is complex and not yet fully implemented).
    """

    def __init__(self, settings: Settings, port=4001, client_id=10):
        """
        Initialize IBKR data fetcher.

        Args:
            settings: Application settings
            port: IBKR API port (4001 for paper trading, 7496 for live TWS)
            client_id: Unique client ID for this connection
        """
        self.settings = settings
        self.ib = IB()
        self.port = port
        self.client_id = client_id

        # We must run asyncio functions from our sync code
        self._loop = self._get_or_create_eventloop()
        self._connect()

        logger.info(f"IBKRDataFetcher initialized. Connected to port {port}")

    def _get_or_create_eventloop(self):
        """Get or create an asyncio event loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _run_async(self, coro):
        """
        Utility to run an async coroutine from sync code.

        This is the "simple" solution to the asyncio conflict mentioned
        by the user. It works but can be slower than full async refactoring.
        """
        try:
            # If we're already in an async context, just await
            if asyncio.get_running_loop():
                return self._loop.create_task(coro)
        except RuntimeError:
            pass

        # Otherwise, run until complete
        return self._loop.run_until_complete(coro)

    def _connect(self):
        """Connect to IBKR TWS or Gateway."""
        if self.ib.isConnected():
            return

        logger.info(f"Connecting to IBKR on port {self.port}...")
        try:
            self._run_async(
                self.ib.connectAsync('127.0.0.1', self.port, clientId=self.client_id, timeout=10)
            )
            if not self.ib.isConnected():
                raise ConnectionError("Failed to connect to IBKR. Is TWS/Gateway running?")
            logger.info("IBKR connection successful.")
        except Exception as e:
            logger.error(f"IBKR Connection Error: {e}")
            raise

    def get_underlying_price(self, symbol: str) -> float:
        """Get current underlying price from IBKR."""
        self._connect() # Ensure connection

        # Create a contract for the index
        # IBKR uses specific contract definitions
        if symbol == "SPX":
            contract = IBContract(symbol=symbol, secType='IND', currency='USD', exchange='CBOE')
        elif symbol == "NDX":
            contract = IBContract(symbol=symbol, secType='IND', currency='USD', exchange='NASDAQ')
        elif symbol == "RUT":
            contract = IBContract(symbol=symbol, secType='IND', currency='USD', exchange='RUSSELL')
        else:
            # Default to stock
            contract = Stock(symbol, 'SMART', 'USD')

        logger.debug(f"Fetching underlying price for {symbol} from IBKR...")

        try:
            # Request market data
            ticker = self._run_async(self.ib.reqMktDataAsync(contract, '', False, False))

            # Wait for the price to come in (max 5 seconds)
            start_time = datetime.now()
            while ticker.last is None or ticker.last <= 0 or np.isnan(ticker.last):
                self.ib.sleep(0.1) # Let IBKR process
                if (datetime.now() - start_time).seconds > 5:
                    raise TimeoutError(f"Timeout fetching IBKR price for {symbol}")

            price = ticker.last
            self.ib.cancelMktData(contract)

            logger.info(f"Fetched {symbol} price from IBKR: ${price:.2f}")
            return float(price)

        except Exception as e:
            logger.error(f"Failed to fetch IBKR price for {symbol}: {e}")
            raise ValueError(f"Unable to fetch IBKR price for {symbol}: {e}")

    def get_option_chain(
        self,
        symbol: str,
        expiration: Optional[datetime] = None,
        dte_target: Optional[int] = None,
    ) -> OptionChain:
        """
        Get option chain from IBKR.

        NOTE: Full IBKR option chain fetching is complex and requires
        multiple API calls. This implementation currently:
        1. Gets the underlying price from IBKR (real-time)
        2. Falls back to yfinance for the full option chain
        3. Overrides the underlying price with IBKR's real-time value

        This is a hybrid approach that gives us IBKR's accurate pricing
        while using yfinance's simpler chain fetching.
        """
        self._connect()

        # 1. Get underlying price from IBKR (this is our primary value)
        try:
            underlying_price = self.get_underlying_price(symbol)
        except Exception as e:
            logger.error(f"Failed to get IBKR price for {symbol}: {e}")
            # Fall back completely to yfinance
            logger.warning("Falling back to complete yfinance data")
            fallback_fetcher = YFinanceDataFetcher(self.settings)
            return fallback_fetcher.get_option_chain(symbol, expiration, dte_target)

        # 2. Get option chain from yfinance (for now)
        # TODO: Implement full IBKR option chain fetching using:
        #   - ib.reqSecDefOptParams() for available expirations/strikes
        #   - ib.qualifyContracts() to get contract details
        #   - ib.reqTickers() to get quotes for each option

        logger.warning(f"Using hybrid approach: IBKR price (${underlying_price:.2f}) + yfinance chain")
        logger.info("Full IBKR option chain fetching is complex and not yet implemented.")

        # Use yfinance for the chain structure
        yf_fetcher = YFinanceDataFetcher(self.settings)
        chain = yf_fetcher.get_option_chain(symbol, expiration, dte_target)

        # Override with IBKR's real-time underlying price
        chain.underlying_price = underlying_price
        chain.timestamp = datetime.now()

        logger.info(f"Hybrid chain complete for {symbol}: IBKR price + yfinance options")
        return chain

    def __del__(self):
        """Disconnect on object destruction."""
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
                logger.info("IBKR connection closed.")
        except:
            pass
