"""
Landeros Financial Ironware - Main CLI Entry Point

Command-line interface for scanning, analyzing, and managing iron condor positions
on European-style index options (SPX, NDX, RUT).

Usage:
    landeros-ironware scan --underlying SPX --dte 45
    landeros-ironware backtest --start 2020-01-01 --end 2023-12-31
    landeros-ironware analyze --position position.json
    ironware scan --underlying NDX  # Short alias

Author: Carlos Landeros
License: MIT
"""

import sys
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import logging
from datetime import datetime, timedelta

from landeros_ironware import __version__, get_supported_underlyings
from landeros_ironware.config.settings import Settings
from landeros_ironware.strategies.iron_condor import IronCondorScanner
from landeros_ironware.backtest.engine import BacktestEngine
from landeros_ironware.visuals.payoff import PayoffDiagram
from landeros_ironware.utils.helpers import setup_logging, validate_underlying

# Initialize Rich console for beautiful CLI output
console = Console()

# Setup logging
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="Landeros Financial Ironware")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging output",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress all output except errors",
)
def cli(verbose: bool, quiet: bool) -> None:
    """
    Landeros Financial Ironware - Institutional-grade iron condor scanner.

    European-style index options (SPX, NDX, RUT) with Section 1256 tax treatment.
    Built for professional quantitative traders.
    """
    # Configure logging based on verbosity
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    setup_logging(log_level)


@cli.command()
@click.option(
    "--underlying",
    "-u",
    type=click.Choice(get_supported_underlyings(), case_sensitive=False),
    required=True,
    help="Index to scan (SPX, NDX, or RUT)",
)
@click.option(
    "--dte",
    "-d",
    type=int,
    default=45,
    help="Target days to expiration (default: 45)",
)
@click.option(
    "--min-credit",
    "-c",
    type=float,
    default=2.0,
    help="Minimum credit per contract (default: 2.00)",
)
@click.option(
    "--target-delta",
    "-t",
    type=float,
    default=0.16,
    help="Target delta for short strikes (default: 0.16)",
)
@click.option(
    "--wing-width",
    "-w",
    type=int,
    default=50,
    help="Width between short and long strikes (default: 50)",
)
@click.option(
    "--max-results",
    "-n",
    type=int,
    default=10,
    help="Maximum number of results to display (default: 10)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Save results to JSON file",
)
def scan(
    underlying: str,
    dte: int,
    min_credit: float,
    target_delta: float,
    wing_width: int,
    max_results: int,
    output: Optional[str],
) -> None:
    """
    Scan for optimal iron condor opportunities.

    Analyzes option chains to identify iron condor structures meeting
    specified criteria for delta, credit, and days to expiration.

    Example:
        landeros-ironware scan -u SPX -d 45 -c 2.5 -t 0.16
    """
    console.print(
        Panel.fit(
            f"[bold cyan]Scanning {underlying} Iron Condors[/bold cyan]\n"
            f"Target DTE: {dte} | Min Credit: ${min_credit:.2f} | Delta: {target_delta}",
            border_style="cyan",
        )
    )

    try:
        # Create settings
        settings = Settings(
            underlying=underlying.upper(),
            target_dte=dte,
            min_credit=min_credit,
            target_delta=target_delta,
            wing_width=wing_width,
        )

        # Initialize scanner
        with console.status("[bold green]Fetching market data...", spinner="dots"):
            scanner = IronCondorScanner(settings)

        # Perform scan
        with console.status("[bold green]Analyzing option chains...", spinner="dots"):
            candidates = scanner.scan()

        if not candidates:
            console.print("[yellow]No iron condor opportunities found matching criteria.[/yellow]")
            return

        # Display results
        table = Table(
            title=f"Top {min(max_results, len(candidates))} Iron Condor Candidates",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Strike Structure", style="green", width=25)
        table.add_column("Credit", justify="right", style="yellow")
        table.add_column("Max Loss", justify="right", style="red")
        table.add_column("POP", justify="right", style="cyan")
        table.add_column("DTE", justify="right")
        table.add_column("Score", justify="right", style="magenta")

        for idx, ic in enumerate(candidates[:max_results], 1):
            table.add_row(
                str(idx),
                f"{ic.short_put}/{ic.long_put} - {ic.short_call}/{ic.long_call}",
                f"${ic.credit:.2f}",
                f"${ic.max_loss:.2f}",
                f"{ic.pop:.1%}",
                str(ic.dte),
                f"{ic.score:.2f}",
            )

        console.print(table)

        # Save to file if requested
        if output:
            import json
            with open(output, "w") as f:
                json.dump([ic.to_dict() for ic in candidates[:max_results]], f, indent=2)
            console.print(f"\n[green] Results saved to {output}[/green]")

        # Display summary stats
        best = candidates[0]
        console.print(
            Panel(
                f"[bold]Best Candidate:[/bold]\n"
                f"Structure: {best.short_put}/{best.long_put} - {best.short_call}/{best.long_call}\n"
                f"Credit: ${best.credit:.2f} | Max Loss: ${best.max_loss:.2f}\n"
                f"POP: {best.pop:.1%} | ROC: {best.return_on_capital:.1%}\n"
                f"Break-evens: {best.break_even_lower:.2f} - {best.break_even_upper:.2f}",
                title="[bold green]Recommendation[/bold green]",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.exception("Scan command failed")
        sys.exit(1)


@cli.command()
@click.option(
    "--start",
    "-s",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="Backtest start date (YYYY-MM-DD)",
)
@click.option(
    "--end",
    "-e",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="Backtest end date (YYYY-MM-DD)",
)
@click.option(
    "--underlying",
    "-u",
    type=click.Choice(get_supported_underlyings(), case_sensitive=False),
    default="SPX",
    help="Index to backtest (default: SPX)",
)
@click.option(
    "--capital",
    "-c",
    type=float,
    default=100000.0,
    help="Initial capital (default: 100,000)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Save backtest results to file",
)
def backtest(
    start: datetime,
    end: datetime,
    underlying: str,
    capital: float,
    output: Optional[str],
) -> None:
    """
    Run historical backtest of iron condor strategy.

    Simulates trading iron condors over a historical period with
    realistic fill assumptions and transaction costs.

    Example:
        landeros-ironware backtest -s 2020-01-01 -e 2023-12-31 -u SPX
    """
    console.print(
        Panel.fit(
            f"[bold cyan]Backtesting {underlying} Iron Condors[/bold cyan]\n"
            f"Period: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}\n"
            f"Initial Capital: ${capital:,.2f}",
            border_style="cyan",
        )
    )

    try:
        # Initialize backtest engine
        with console.status("[bold green]Loading historical data...", spinner="dots"):
            engine = BacktestEngine(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                underlying=underlying.upper(),
                initial_capital=capital,
            )

        # Run backtest
        with console.status("[bold green]Running backtest simulation...", spinner="dots"):
            results = engine.run()

        # Display results
        console.print("\n[bold green] Backtest Complete[/bold green]\n")

        # Performance metrics table
        metrics_table = Table(title="Performance Metrics", box=box.ROUNDED)
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", justify="right", style="yellow")

        metrics_table.add_row("Total Return", f"{results.total_return:.2%}")
        metrics_table.add_row("CAGR", f"{results.cagr:.2%}")
        metrics_table.add_row("Sharpe Ratio", f"{results.sharpe_ratio:.2f}")
        metrics_table.add_row("Max Drawdown", f"{results.max_drawdown:.2%}")
        metrics_table.add_row("Win Rate", f"{results.win_rate:.2%}")
        metrics_table.add_row("Total Trades", str(results.total_trades))
        metrics_table.add_row("Avg P&L per Trade", f"${results.avg_pnl_per_trade:.2f}")
        metrics_table.add_row("Final Capital", f"${results.final_capital:,.2f}")

        console.print(metrics_table)

        # Save results if requested
        if output:
            results.save(output)
            console.print(f"\n[green] Results saved to {output}[/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.exception("Backtest command failed")
        sys.exit(1)


@cli.command()
@click.option(
    "--position",
    "-p",
    type=click.Path(exists=True),
    required=True,
    help="Path to position JSON file",
)
@click.option(
    "--save-plot",
    "-s",
    type=click.Path(),
    help="Save payoff diagram to file",
)
def analyze(position: str, save_plot: Optional[str]) -> None:
    """
    Analyze an existing iron condor position.

    Displays Greeks, risk metrics, and payoff diagram for a position.

    Example:
        landeros-ironware analyze -p my_position.json -s diagram.png
    """
    console.print("[bold cyan]Analyzing Iron Condor Position[/bold cyan]\n")

    try:
        import json
        from landeros_ironware.strategies.iron_condor import IronCondor

        # Load position
        with open(position, "r") as f:
            position_data = json.load(f)

        ic = IronCondor.from_dict(position_data)

        # Display position details
        console.print(f"[bold]Structure:[/bold] {ic.short_put}/{ic.long_put} - {ic.short_call}/{ic.long_call}")
        console.print(f"[bold]Credit:[/bold] ${ic.credit:.2f}")
        console.print(f"[bold]Max Loss:[/bold] ${ic.max_loss:.2f}")
        console.print(f"[bold]POP:[/bold] {ic.pop:.1%}\n")

        # Greeks table
        greeks_table = Table(title="Position Greeks", box=box.ROUNDED)
        greeks_table.add_column("Greek", style="cyan")
        greeks_table.add_column("Value", justify="right", style="yellow")

        greeks_table.add_row("Delta", f"{ic.delta:.4f}")
        greeks_table.add_row("Gamma", f"{ic.gamma:.4f}")
        greeks_table.add_row("Theta", f"{ic.theta:.4f}")
        greeks_table.add_row("Vega", f"{ic.vega:.4f}")

        console.print(greeks_table)

        # Generate payoff diagram
        if save_plot:
            diagram = PayoffDiagram(ic)
            diagram.plot(show_greeks=True)
            diagram.save(save_plot)
            console.print(f"\n[green] Payoff diagram saved to {save_plot}[/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.exception("Analyze command failed")
        sys.exit(1)


@cli.command()
def info() -> None:
    """
    Display package information and supported underlyings.
    """
    from landeros_ironware import get_info

    info_data = get_info()

    console.print(
        Panel.fit(
            f"[bold cyan]{info_data['name']}[/bold cyan]\n"
            f"Version: {info_data['version']}\n"
            f"Author: {info_data['author']}\n"
            f"License: {info_data['license']}\n\n"
            f"[bold]Supported Underlyings:[/bold] {info_data['supported_underlyings']}\n"
            f"[bold]Tax Treatment:[/bold] {info_data['tax_treatment']}\n"
            f"[bold]Python:[/bold] {info_data['python_requires']}",
            title="[bold green]Package Information[/bold green]",
            border_style="green",
        )
    )


def main() -> None:
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/bold red] {str(e)}")
        logger.exception("Unhandled exception in main")
        sys.exit(1)


if __name__ == "__main__":
    main()
