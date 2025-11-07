"""
Probability calculations for Landeros Financial Ironware.

Provides models for calculating Probability of Profit (POP) and
other statistical measures for option strategies.

Author: Carlos Landeros
"""

import logging
from typing import Literal

import numpy as np
from scipy.stats import norm

from landeros_ironware.config.settings import Settings

logger = logging.getLogger(__name__)


class ProbabilityCalculator:
    """
    Calculates probabilities for option strategies using lognormal distribution.
    """

    def __init__(self, settings: Settings):
        """
        Initialize the calculator with risk-free rate from settings.

        Args:
            settings: The main application Settings object.
        """
        self.risk_free_rate = settings.risk_free_rate
        logger.debug(f"ProbabilityCalculator initialized with r={self.risk_free_rate}")

    def calculate_pop_lognormal(
        self,
        underlying_price: float,
        lower_strike: float,
        upper_strike: float,
        dte: int,
        iv: float,
    ) -> float:
        """
        Calculate Probability of Profit (POP) for a strategy.

        Assumes a lognormal distribution of underlying price at expiration.
        This calculates the probability that:
        S(T) > lower_strike AND S(T) < upper_strike

        Args:
            underlying_price: Current price of the underlying (S)
            lower_strike: Lower break-even price
            upper_strike: Upper break-even price
            dte: Days to expiration
            iv: Implied volatility (annual, e.g., 0.15)

        Returns:
            float: Probability of profit (0.0 to 1.0)
        """
        if dte <= 0 or iv <= 0 or underlying_price <= 0:
            # Handle edge cases
            if lower_strike < underlying_price < upper_strike:
                return 1.0  # Already in the money at expiration
            else:
                return 0.0  # Already out of the money at expiration

        S = underlying_price
        T = dte / 365.25  # Time to expiration in years
        r = self.risk_free_rate
        sigma = iv

        # Calculate the log-normal parameters
        # Drift
        mu = (r - 0.5 * sigma**2) * T
        # Volatility (standard deviation)
        std_dev = sigma * np.sqrt(T)

        if std_dev == 0:
            return 0.0

        # Calculate d1 and d2 style parameters for each strike
        # This is d2 from Black-Scholes, which represents P(S(T) > K)
        d_lower = (np.log(S / lower_strike) + mu) / std_dev
        d_upper = (np.log(S / upper_strike) + mu) / std_dev

        # Use Cumulative Distribution Function (CDF) of standard normal
        # P(S(T) > K_lower) = N(d_lower)
        # P(S(T) > K_upper) = N(d_upper)

        prob_above_lower = norm.cdf(d_lower)
        prob_above_upper = norm.cdf(d_upper)

        # The probability of being *between* the strikes is the difference
        # P(K_lower < S(T) < K_upper) = P(S(T) > K_lower) - P(S(T) > K_upper)
        pop = prob_above_lower - prob_above_upper

        # Clamp result to ensure valid probability
        return max(0.0, min(1.0, pop))

    def calculate_itm_probability(
        self,
        underlying_price: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: Literal["call", "put"],
    ) -> float:
        """
        Calculate the probability of an option finishing In-The-Money (ITM).
        This is effectively N(d2) for a call and N(-d2) for a put.

        Args:
            underlying_price: Current price of the underlying (S)
            strike: Strike price of the option (K)
            dte: Days to expiration
            iv: Implied volatility (annual)
            option_type: 'call' or 'put'

        Returns:
            float: Probability of finishing ITM (0.0 to 1.0)
        """
        if dte <= 0:
            if option_type == "call" and underlying_price > strike:
                return 1.0
            if option_type == "put" and underlying_price < strike:
                return 1.0
            return 0.0

        S = underlying_price
        K = strike
        T = dte / 365.25
        r = self.risk_free_rate
        sigma = iv

        std_dev = sigma * np.sqrt(T)
        if std_dev == 0:
            return 1.0 if (option_type == "call" and S > K) or (option_type == "put" and S < K) else 0.0

        # This is the standard Black-Scholes d2
        d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * T) / std_dev

        if option_type == "call":
            # P(S(T) > K)
            return norm.cdf(d2)
        else:
            # P(S(T) < K)
            return norm.cdf(-d2)