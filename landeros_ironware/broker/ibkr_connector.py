"""
Interactive Brokers (IBKR) API Connection Handler.

Uses ib_insync to manage the connection to TWS or IB Gateway.
Handles the asyncio event loop and provides a connected IB client.

Author: Carlos Landeros
"""

import logging
import asyncio
from ib_insync import IB, util
from typing import Optional

logger = logging.getLogger(__name__)


class IBKRConnector:
    """
    Manages the connection to Interactive Brokers TWS/Gateway.
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 4001, client_id: int = 1):
        """
        Initialize the connector.

        Args:
            host: Hostname for TWS/Gateway (default: 127.0.0.1)
            port: Port for TWS/Gateway (default: 4001 for paper, 7496 for live TWS)
            client_id: Client ID for the connection (must be unique)
        """
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.is_connected = False

        # Set up ib_insync logging to play nice
        util.logToConsole(logging.WARNING)
        logger.info(f"IBKRConnector initialized for {host}:{port} with ClientID {client_id}")

    async def connect(self):
        """
        Establish the connection to IBKR.
        """
        if self.is_connected:
            logger.info("Already connected to IBKR.")
            return

        logger.info(f"Connecting to IBKR at {self.host}:{self.port}...")
        try:
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=10
            )
            self.is_connected = self.ib.isConnected()

            if self.is_connected:
                logger.info("Successfully connected to IBKR.")
                await self.ib.reqManagedAcctsAsync()
                logger.info(f"Managed accounts: {self.ib.managedAccounts()}")
            else:
                logger.error("Failed to connect to IBKR. Check if TWS/Gateway is running.")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.is_connected = False

    async def disconnect(self):
        """
        Disconnect from IBKR.
        """
        if self.is_connected:
            logger.info("Disconnecting from IBKR...")
            self.ib.disconnect()
            self.is_connected = False
            logger.info("Disconnected.")

    def run_async(self, coro):
        """
        Utility to run a single async task.
        Ensures the event loop is managed correctly.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    async def get_account_summary(self) -> dict:
        """
        Fetch a summary of the paper trading account.
        """
        if not self.is_connected:
            await self.connect()

        if not self.is_connected:
            return {"Error": "Could not connect to IBKR."}

        try:
            summary = await self.ib.accountSummaryAsync()
            return {s.tag: s.value for s in summary if s.tag == 'NetLiquidation'}
        except Exception as e:
            logger.error(f"Error fetching account summary: {e}")
            return {"Error": str(e)}
