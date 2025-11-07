"""
IBKR Trade Execution Bot.

This class combines the IronCondorScanner and PortfolioManager
with the IBKRConnector to find and execute trades.

Author: Carlos Landeros
"""

import logging
import asyncio

from landeros_ironware.config.settings import Settings
from landeros_ironware.strategies.iron_condor import IronCondorScanner
from landeros_ironware.risk.portfolio import PortfolioManager
from .ibkr_connector import IBKRConnector

logger = logging.getLogger(__name__)


class IBKRBot:
    """
    The main trading bot class.

    Connects to IBKR, scans for trades, checks portfolio risk,
    and executes orders.
    """

    def __init__(self, settings: Settings, live: bool = False):
        self.settings = settings
        self.live = live

        # Use the port from settings, but override for live if not already set
        port = settings.ibkr_port
        if live and port == 4001:  # Default paper port, switch to live
            port = 7496

        self.connector = IBKRConnector(port=port)
        self.scanner = IronCondorScanner(settings)
        self.portfolio = PortfolioManager(settings)

        logger.info(f"IBKRBot initialized. Live Trading: {live}, Port: {port}")

    async def run(self):
        """
        The main async run loop for the bot.
        """
        logger.info("Starting bot...")
        await self.connector.connect()

        if not self.connector.is_connected:
            logger.error("Bot cannot start. Exiting.")
            return

        try:
            while True:
                # TODO: Implement bot logic
                logger.info("Bot loop running... (logic pending)")

                # 1. Scan for trades
                # candidates = self.scanner.scan()

                # 2. Get best candidate
                # best_trade = candidates[0]

                # 3. Check portfolio manager
                # if self.portfolio.add_position(best_trade):

                # 4. Execute trade
                #    await self.execute_trade(best_trade)

                # 5. Sleep
                await asyncio.sleep(60) # Wait 1 minute

        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Bot shutting down...")
        finally:
            await self.connector.disconnect()
            logger.info("Bot stopped.")

    async def execute_trade(self, ic: "IronCondor"):
        """
        Takes an IronCondor object and places the 4-legged
        combo order on IBKR.
        """
        logger.info(f"--- EXECUTION LOGIC PENDING ---")
        # TODO:
        # 1. Create ib_insync.Contract objects for all 4 legs
        # 2. Create ib_insync.ComboOrder
        # 3. Place the order
        pass
