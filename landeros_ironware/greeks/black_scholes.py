"""
Black-Scholes option pricing model and Greeks calculations.

Implements standard Black-Scholes formulas for European options
with full Greek calculations (Delta, Gamma, Theta, Vega, Rho).

Author: Carlos Landeros
"""

from typing import Literal, Optional
from dataclasses import dataclass
import numpy as np
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptionGreeks:
    """Container for option Greeks."""

    delta: float
    gamma: float
    theta: float  # Per day
    vega: float  # Per 1% change in IV
    rho: float  # Per 1% change in interest rate

    def __repr__(self) -> str:
        return (
            f"Greeks(delta={self.delta:.4f}, gamma={self.gamma:.4f}, "
            f"theta={self.theta:.4f}, vega={self.vega:.4f}, rho={self.rho:.4f})"
        )


class BlackScholes:
    """
    Black-Scholes option pricing model for European options.

    Calculates theoretical option prices and Greeks using the
    standard Black-Scholes-Merton formula.
    """

    @staticmethod
    def _d1(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate d1 parameter.

        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Implied volatility

        Returns:
            float: d1 value
        """
        if T <= 0:
            return 0.0

        return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def _d2(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate d2 parameter.

        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Implied volatility

        Returns:
            float: d2 value
        """
        if T <= 0:
            return 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        return d1 - sigma * np.sqrt(T)

    @staticmethod
    def call_price(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate European call option price.

        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate (annual)
            sigma: Implied volatility (annual)

        Returns:
            float: Theoretical call price
        """
        if T <= 0:
            return max(0, S - K)

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        d2 = BlackScholes._d2(S, K, T, r, sigma)

        call = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return max(0, call)

    @staticmethod
    def put_price(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate European put option price.

        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate (annual)
            sigma: Implied volatility (annual)

        Returns:
            float: Theoretical put price
        """
        if T <= 0:
            return max(0, K - S)

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        d2 = BlackScholes._d2(S, K, T, r, sigma)

        put = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return max(0, put)

    @staticmethod
    def call_delta(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """Calculate call delta."""
        if T <= 0:
            return 1.0 if S > K else 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        return norm.cdf(d1)

    @staticmethod
    def put_delta(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """Calculate put delta."""
        if T <= 0:
            return -1.0 if S < K else 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        return norm.cdf(d1) - 1

    @staticmethod
    def gamma(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate gamma (same for calls and puts).

        Gamma measures the rate of change in delta per $1 move in underlying.
        """
        if T <= 0:
            return 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * np.sqrt(T))

    @staticmethod
    def call_theta(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate call theta (time decay per day).

        Returns negative value (options lose value over time).
        """
        if T <= 0:
            return 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        d2 = BlackScholes._d2(S, K, T, r, sigma)

        term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        term2 = -r * K * np.exp(-r * T) * norm.cdf(d2)

        # Convert from annual to daily
        return (term1 + term2) / 365.25

    @staticmethod
    def put_theta(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate put theta (time decay per day).

        Returns negative value (options lose value over time).
        """
        if T <= 0:
            return 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        d2 = BlackScholes._d2(S, K, T, r, sigma)

        term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        term2 = r * K * np.exp(-r * T) * norm.cdf(-d2)

        # Convert from annual to daily
        return (term1 + term2) / 365.25

    @staticmethod
    def vega(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate vega (same for calls and puts).

        Vega measures price change per 1% change in implied volatility.
        """
        if T <= 0:
            return 0.0

        d1 = BlackScholes._d1(S, K, T, r, sigma)
        # Divide by 100 to get per 1% change
        return (S * norm.pdf(d1) * np.sqrt(T)) / 100

    @staticmethod
    def call_rho(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate call rho.

        Rho measures price change per 1% change in risk-free rate.
        """
        if T <= 0:
            return 0.0

        d2 = BlackScholes._d2(S, K, T, r, sigma)
        # Divide by 100 to get per 1% change
        return (K * T * np.exp(-r * T) * norm.cdf(d2)) / 100

    @staticmethod
    def put_rho(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate put rho.

        Rho measures price change per 1% change in risk-free rate.
        """
        if T <= 0:
            return 0.0

        d2 = BlackScholes._d2(S, K, T, r, sigma)
        # Divide by 100 to get per 1% change
        return (-K * T * np.exp(-r * T) * norm.cdf(-d2)) / 100


class GreeksCalculator:
    """
    High-level interface for calculating option Greeks.

    Provides convenient methods for calculating all Greeks
    for calls and puts in a single call.
    """

    def __init__(self, risk_free_rate: float = 0.045):
        """
        Initialize Greeks calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default: 4.5%)
        """
        self.risk_free_rate = risk_free_rate
        self.bs = BlackScholes()

    def calculate(
        self,
        underlying_price: float,
        strike: float,
        dte: int,
        implied_vol: float,
        option_type: Literal["call", "put"],
    ) -> OptionGreeks:
        """
        Calculate all Greeks for an option.

        Args:
            underlying_price: Current underlying price
            strike: Option strike price
            dte: Days to expiration
            implied_vol: Implied volatility (annual, e.g., 0.15 for 15%)
            option_type: 'call' or 'put'

        Returns:
            OptionGreeks: All Greeks for the option
        """
        # Convert DTE to years
        T = dte / 365.25

        if option_type.lower() == "call":
            delta = self.bs.call_delta(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
            theta = self.bs.call_theta(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
            rho = self.bs.call_rho(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
        else:  # put
            delta = self.bs.put_delta(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
            theta = self.bs.put_theta(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
            rho = self.bs.put_rho(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )

        # Gamma and Vega are the same for calls and puts
        gamma = self.bs.gamma(
            underlying_price, strike, T, self.risk_free_rate, implied_vol
        )
        vega = self.bs.vega(
            underlying_price, strike, T, self.risk_free_rate, implied_vol
        )

        return OptionGreeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
        )

    def calculate_price(
        self,
        underlying_price: float,
        strike: float,
        dte: int,
        implied_vol: float,
        option_type: Literal["call", "put"],
    ) -> float:
        """
        Calculate theoretical option price.

        Args:
            underlying_price: Current underlying price
            strike: Option strike price
            dte: Days to expiration
            implied_vol: Implied volatility (annual)
            option_type: 'call' or 'put'

        Returns:
            float: Theoretical option price
        """
        T = dte / 365.25

        if option_type.lower() == "call":
            return self.bs.call_price(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
        else:
            return self.bs.put_price(
                underlying_price, strike, T, self.risk_free_rate, implied_vol
            )
