# Landeros Financial Ironware

**Institutional-Grade Iron Condor Scanner & Manager for European-Style Index Options**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Overview

Landeros Financial Ironware is a production-ready Python package designed for professional quantitative traders managing iron condor strategies on European-style index options (SPX, NDX, RUT). Built with institutional rigor, this tool provides:

- **Section 1256 Tax Treatment**: Optimized exclusively for European-style index options qualifying for 60/40 long-term/short-term capital gains treatment
- **Early-Exit Discipline**: Default 50% profit target with customizable exit rules
- **Real-Time Greeks**: Black-Scholes option pricing with Delta, Gamma, Theta, Vega calculations
- **Probability Analysis**: Monte Carlo simulations and probability of profit (POP) calculations
- **Portfolio Risk Management**: Position sizing, portfolio Greeks aggregation, and risk metrics
- **Backtesting Engine**: Historical performance analysis with realistic fill assumptions
- **Visual Analytics**: Payoff diagrams, Greeks visualization, and risk profiles

## Features

### Core Capabilities

- **Iron Condor Scanning**: Automated discovery of optimal strike combinations based on:
  - Target delta ranges (default: 0.10-0.20 for short strikes)
  - Minimum credit requirements
  - Wing width specifications
  - Days to expiration (DTE) filtering

- **Greeks Calculation**: Full Black-Scholes implementation for:
  - Delta (directional risk)
  - Gamma (delta sensitivity)
  - Theta (time decay)
  - Vega (volatility risk)
  - Rho (interest rate sensitivity)

- **Risk Analytics**:
  - Probability of profit (POP) using lognormal distribution
  - Maximum loss and maximum profit calculations
  - Break-even point analysis
  - Portfolio-level Greek aggregation
  - Value at Risk (VaR) and Expected Shortfall (ES)

- **Position Management**:
  - 50% profit target exit rule (customizable)
  - 2x loss stop-loss rule (customizable)
  - DTE-based exit rules
  - Portfolio position tracking

### Supported Underlyings

- **SPX** (S&P 500 Index)
- **NDX** (Nasdaq-100 Index)
- **RUT** (Russell 2000 Index)

All European-style with PM settlement, qualifying for Section 1256 tax treatment.

## Installation

### Requirements

- Python 3.9 or higher
- pip package manager

### Install from source

```bash
git clone https://github.com/vip-carlos/landeros-financial-ironbird.git
cd landeros-financial-ironbird
pip install -e .
```

### Install dependencies

```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
from landeros_ironware import IronCondorScanner, GreeksCalculator
from landeros_ironware.config import Settings

# Initialize settings
settings = Settings(
    underlying="SPX",
    target_dte=45,
    min_credit=2.00,
    target_delta=0.16
)

# Scan for iron condors
scanner = IronCondorScanner(settings)
candidates = scanner.scan()

# Analyze top candidate
best_ic = candidates[0]
print(f"Strike Structure: {best_ic.short_put}/{best_ic.long_put} - {best_ic.short_call}/{best_ic.long_call}")
print(f"Credit: ${best_ic.credit:.2f}")
print(f"POP: {best_ic.pop:.2%}")
print(f"Max Loss: ${best_ic.max_loss:.2f}")
```

### Backtesting

```python
from landeros_ironware.backtest import BacktestEngine

# Run historical backtest
engine = BacktestEngine(
    start_date="2020-01-01",
    end_date="2023-12-31",
    initial_capital=100000
)

results = engine.run()
print(f"Total Return: {results.total_return:.2%}")
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Win Rate: {results.win_rate:.2%}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")
```

### Visualizations

```python
from landeros_ironware.visuals import PayoffDiagram

# Generate payoff diagram
diagram = PayoffDiagram(best_ic)
diagram.plot(show_greeks=True)
diagram.save("iron_condor_payoff.png")
```

## Configuration

Edit `landeros_ironware/config/settings.py` to customize:

- Default underlyings and DTE ranges
- Strike selection criteria (delta, width, credit)
- Exit rules (profit target, stop loss, DTE)
- Risk parameters (position sizing, portfolio limits)
- Data sources and API credentials

## Project Structure

```
Landeros-Financial-Ironware/
├── landeros_ironware/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # CLI entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Configuration management
│   ├── data/
│   │   ├── __init__.py
│   │   └── fetcher.py           # Market data retrieval
│   ├── greeks/
│   │   ├── __init__.py
│   │   └── black_scholes.py     # Greeks calculations
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── iron_condor.py       # Iron condor logic
│   │   └── optimizer.py         # Strike selection optimizer
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── probability.py       # POP and probability calcs
│   │   └── portfolio.py         # Portfolio risk management
│   ├── visuals/
│   │   ├── __init__.py
│   │   └── payoff.py            # Payoff diagrams
│   ├── backtest/
│   │   ├── __init__.py
│   │   └── engine.py            # Backtesting framework
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py           # Utility functions
│   └── tests/                   # Unit tests
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Build configuration
├── README.md                   # This file
└── .gitignore                  # Git exclusions
```

## Tax Considerations

This tool is specifically designed for **European-style index options** that qualify for Section 1256 treatment under U.S. tax law:

- **60/40 treatment**: 60% long-term, 40% short-term capital gains regardless of holding period
- **Mark-to-market**: Positions marked to market on December 31
- **Lower tax burden**: Typically results in lower effective tax rate vs. equity options

**Disclaimer**: This software does not provide tax advice. Consult a qualified tax professional regarding your specific situation.

## Risk Warning

Options trading involves substantial risk and is not suitable for all investors. This software is provided for informational and educational purposes only. The developers assume no responsibility for trading losses incurred through the use of this software.

**Key Risks**:
- Iron condors have limited profit potential but significant loss potential
- Volatile markets can result in rapid losses exceeding initial credit
- Assignment risk on American-style options (not applicable to SPX/NDX/RUT)
- Gap risk during market hours and overnight

Always trade with capital you can afford to lose and implement proper risk management.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

**Carlos Landeros**
Senior Quantitative Developer
Landeros Financial

## Acknowledgments

- Black-Scholes model implementation based on standard quantitative finance literature
- Market data integration inspired by institutional trading frameworks
- Backtesting methodology follows industry best practices for options strategy evaluation

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Built with precision. Deployed with discipline. Optimized for tax efficiency.**
