"""
Settings and configuration management for Landeros Financial Ironware.

Provides Pydantic models for type-safe configuration with validation.
All settings can be overridden via environment variables or config files.

Author: Carlos Landeros
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pathlib import Path
import os
from datetime import datetime

# Supported European-style index options (Section 1256 qualified)
SUPPORTED_UNDERLYINGS = ["SPX", "NDX", "RUT"]

# Default risk-free rate (10-year Treasury as proxy)
DEFAULT_RISK_FREE_RATE = 0.045  # 4.5%


class ExitRules(BaseModel):
    """
    Position exit rules for iron condors.

    Defines profit targets, stop losses, and time-based exit criteria.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    profit_target_pct: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Take profit at X% of max credit (default: 50%)",
    )

    stop_loss_multiple: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Stop loss at X times credit received (default: 2x)",
    )

    dte_exit: int = Field(
        default=21,
        ge=0,
        le=60,
        description="Close position when DTE reaches this threshold (default: 21)",
    )

    manage_winners_early: bool = Field(
        default=True,
        description="Enable early profit-taking discipline",
    )

    trail_stop_enabled: bool = Field(
        default=False,
        description="Enable trailing stop loss",
    )

    trail_stop_pct: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Trailing stop distance as % of max profit",
    )


class RiskParameters(BaseModel):
    """
    Portfolio-level risk management parameters.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    max_portfolio_delta: float = Field(
        default=100.0,
        ge=0.0,
        description="Maximum absolute portfolio delta exposure",
    )

    max_portfolio_vega: float = Field(
        default=500.0,
        ge=0.0,
        description="Maximum absolute portfolio vega exposure",
    )

    max_positions: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of concurrent positions",
    )

    position_size_pct: float = Field(
        default=0.05,
        ge=0.01,
        le=0.20,
        description="Position size as % of portfolio (default: 5%)",
    )

    max_loss_per_position_pct: float = Field(
        default=0.02,
        ge=0.001,
        le=0.10,
        description="Max loss per position as % of portfolio (default: 2%)",
    )

    diversify_by_dte: bool = Field(
        default=True,
        description="Diversify positions across different expiration dates",
    )


class DataSourceConfig(BaseModel):
    """
    Market data source configuration.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    primary_source: Literal["yfinance", "cboe", "mock", "ibkr"] = Field(
        default="yfinance",
        description="Primary data source for option chains",
    )

    use_cache: bool = Field(
        default=True,
        description="Cache market data to reduce API calls",
    )

    cache_ttl_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Cache time-to-live in minutes (default: 15)",
    )

    cache_dir: Path = Field(
        default=Path.home() / ".landeros_ironware" / "cache",
        description="Directory for cached market data",
    )

    api_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="API request timeout in seconds",
    )


class Settings(BaseModel):
    """
    Main settings class for Landeros Financial Ironware.

    Combines all configuration aspects with sensible defaults for
    institutional iron condor trading on European-style index options.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    # Underlying selection
    underlying: str = Field(
        default="SPX",
        description="Index symbol (SPX, NDX, or RUT)",
    )

    # Days to expiration parameters
    target_dte: int = Field(
        default=45,
        ge=7,
        le=90,
        description="Target days to expiration for new positions",
    )

    dte_tolerance: int = Field(
        default=5,
        ge=0,
        le=15,
        description="Acceptable DTE range (+/- days from target)",
    )

    # Strike selection criteria
    target_delta: float = Field(
        default=0.16,
        ge=0.05,
        le=0.30,
        description="Target delta for short strikes (default: 16-delta)",
    )

    delta_tolerance: float = Field(
        default=0.03,
        ge=0.01,
        le=0.10,
        description="Acceptable delta range (+/- from target)",
    )

    wing_width: int = Field(
        default=50,
        ge=5,
        le=200,
        description="Points between short and long strikes",
    )

    # Credit requirements
    min_credit: float = Field(
        default=2.0,
        ge=0.5,
        description="Minimum credit per contract in dollars",
    )

    min_credit_to_width_ratio: float = Field(
        default=0.25,
        ge=0.1,
        le=0.5,
        description="Min ratio of credit to total wing width (default: 25%)",
    )

    # Probability requirements
    min_pop: float = Field(
        default=0.65,
        ge=0.50,
        le=0.95,
        description="Minimum probability of profit (default: 65%)",
    )

    # Greeks constraints
    max_position_delta: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description="Maximum absolute delta per position",
    )

    max_position_vega: float = Field(
        default=100.0,
        ge=0.0,
        description="Maximum vega per position",
    )

    # Volatility parameters
    use_historical_vol: bool = Field(
        default=False,
        description="Use historical volatility instead of implied vol",
    )

    vol_lookback_days: int = Field(
        default=30,
        ge=10,
        le=252,
        description="Lookback period for historical volatility calculation",
    )

    # Risk-free rate
    risk_free_rate: float = Field(
        default=DEFAULT_RISK_FREE_RATE,
        ge=0.0,
        le=0.20,
        description="Risk-free rate for options pricing (default: 4.5%)",
    )

    # Transaction costs
    commission_per_contract: float = Field(
        default=0.65,
        ge=0.0,
        le=10.0,
        description="Commission per contract (default: $0.65)",
    )

    slippage_per_contract: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Expected slippage per contract (default: $0.05)",
    )

    # Sub-configurations
    exit_rules: ExitRules = Field(
        default_factory=ExitRules,
        description="Position exit rules",
    )

    risk_params: RiskParameters = Field(
        default_factory=RiskParameters,
        description="Portfolio risk parameters",
    )

    data_source: DataSourceConfig = Field(
        default_factory=DataSourceConfig,
        description="Market data configuration",
    )

    # Logging and output
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging verbosity level",
    )

    output_dir: Path = Field(
        default=Path.cwd() / "output",
        description="Directory for output files and reports",
    )

    # Broker configuration
    ibkr_port: int = Field(
        default=4001,
        description="IBKR port (4001 for paper, 7496 for live TWS)",
    )

    # Validators
    @field_validator("underlying")
    @classmethod
    def validate_underlying(cls, v: str) -> str:
        """Ensure underlying is supported and uppercase."""
        v_upper = v.upper()
        if v_upper not in SUPPORTED_UNDERLYINGS:
            raise ValueError(
                f"Underlying must be one of {SUPPORTED_UNDERLYINGS}, got {v}"
            )
        return v_upper

    @field_validator("target_dte", "dte_tolerance", "wing_width")
    @classmethod
    def validate_positive(cls, v: int, info) -> int:
        """Ensure values are positive."""
        if v <= 0:
            raise ValueError(f"{info.field_name} must be positive, got {v}")
        return v

    @field_validator("output_dir", "data_source")
    @classmethod
    def ensure_directory_exists(cls, v) -> Path:
        """Create output directory if it doesn't exist."""
        if isinstance(v, DataSourceConfig):
            v.cache_dir.mkdir(parents=True, exist_ok=True)
            return v
        elif isinstance(v, Path):
            v.mkdir(parents=True, exist_ok=True)
            return v
        return v

    def get_dte_range(self) -> tuple[int, int]:
        """
        Get acceptable DTE range.

        Returns:
            tuple[int, int]: (min_dte, max_dte)
        """
        return (
            self.target_dte - self.dte_tolerance,
            self.target_dte + self.dte_tolerance,
        )

    def get_delta_range(self) -> tuple[float, float]:
        """
        Get acceptable delta range for short strikes.

        Returns:
            tuple[float, float]: (min_delta, max_delta)
        """
        return (
            self.target_delta - self.delta_tolerance,
            self.target_delta + self.delta_tolerance,
        )

    def total_transaction_cost(self, num_contracts: int = 1) -> float:
        """
        Calculate total transaction cost for opening a position.

        Args:
            num_contracts: Number of iron condor contracts (default: 1)

        Returns:
            float: Total cost in dollars (4 legs per iron condor)
        """
        legs = 4  # Iron condor has 4 legs
        cost_per_leg = self.commission_per_contract + self.slippage_per_contract
        return num_contracts * legs * cost_per_leg

    @classmethod
    def from_env(cls) -> "Settings":
        """
        Create Settings instance from environment variables.

        Environment variables should be prefixed with LANDEROS_IRONWARE_
        Example: LANDEROS_IRONWARE_UNDERLYING=NDX

        Returns:
            Settings: Configured settings instance
        """
        prefix = "LANDEROS_IRONWARE_"
        config = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                setting_name = key[len(prefix) :].lower()
                config[setting_name] = value

        return cls(**config)

    def to_dict(self) -> dict:
        """
        Export settings to dictionary.

        Returns:
            dict: All settings as a dictionary
        """
        return self.model_dump()

    def __repr__(self) -> str:
        """Pretty string representation."""
        return (
            f"Settings(underlying={self.underlying}, "
            f"target_dte={self.target_dte}, "
            f"target_delta={self.target_delta}, "
            f"min_credit={self.min_credit})"
        )


# Default settings instance
DEFAULT_SETTINGS = Settings()
