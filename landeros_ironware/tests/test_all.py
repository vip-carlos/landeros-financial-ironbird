"""Integration test suite for the Landeros Financial Ironware workflows."""

from __future__ import annotations

import importlib
import json
import re
import sys
import types
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pytest
from click.testing import CliRunner


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _normalize_output(text: str) -> str:
    """Strip ANSI escape sequences and stray control characters."""
    return ANSI_RE.sub("", text).replace("\x13", "")


class _StubProbabilityCalculator:
    """Lightweight probability calculator used to satisfy scanner dependencies."""

    def calculate_pop_lognormal(
        self,
        *,
        underlying_price: float,
        lower_strike: float,
        upper_strike: float,
        dte: int,
        iv: float,
    ) -> float:
        return 0.72


class _StubPayoffDiagram:
    """Minimal payoff diagram implementation for CLI analysis tests."""

    saved_paths: list[Path] = []

    def __init__(self, iron_condor) -> None:
        self.iron_condor = iron_condor
        self.plot_calls = 0
        self.save_calls = 0

    def plot(self, *, show_greeks: bool = True) -> None:  # noqa: D401
        self.plot_calls += 1

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.write_text("stub plot\n", encoding="utf-8")
        self.save_calls += 1
        self.saved_path = target
        self.__class__.saved_paths.append(target)


class _StubBacktestResults:
    """Backtest result container compatible with the CLI contract."""

    last_saved_path: Path | None = None

    def __init__(self) -> None:
        self.total_return = 0.18
        self.cagr = 0.12
        self.sharpe_ratio = 1.70
        self.max_drawdown = 0.09
        self.win_rate = 0.68
        self.total_trades = 42
        self.avg_pnl_per_trade = 125.0
        self.final_capital = 112500.0

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.write_text("date,pnl\n2024-01-01,0\n", encoding="utf-8")
        self.__class__.last_saved_path = target


class _StubBacktestEngine:
    """Simplified backtest engine that records invocation details."""

    calls: list[dict[str, str | float]] = []
    last_instance: _StubBacktestEngine | None = None

    def __init__(
        self,
        *,
        start_date: str,
        end_date: str,
        underlying: str,
        initial_capital: float,
    ) -> None:
        self.params = {
            "start_date": start_date,
            "end_date": end_date,
            "underlying": underlying,
            "initial_capital": initial_capital,
        }
        self.__class__.calls.append(self.params)
        self.__class__.last_instance = self

    def run(self) -> _StubBacktestResults:
        return _StubBacktestResults()


def _module_spec(name: str, search_path: Path) -> types.ModuleType:
    """Create a module object with package semantics for importlib."""
    spec_module = types.ModuleType(name)
    spec_module.__path__ = [str(search_path)]
    spec_module.__package__ = name
    return spec_module


@pytest.fixture(scope="session", autouse=True)
def _install_stubbed_package() -> None:
    """Inject stub modules so imports succeed without full implementations."""
    package = _module_spec("landeros_ironware", PACKAGE_ROOT)
    package.__version__ = "1.0.0-test"
    package.__author__ = "Carlos Landeros"
    package.__license__ = "MIT"

    def _get_info() -> dict[str, str]:
        return {
            "name": "Landeros Financial Ironware",
            "version": package.__version__,
            "author": package.__author__,
            "email": "stub@landeros-financial.com",
            "license": package.__license__,
            "description": "Stub info for testing",
            "supported_underlyings": ", ".join(["SPX", "NDX", "RUT"]),
            "tax_treatment": "Section 1256 (60/40)",
            "python_requires": ">=3.9",
        }

    package.get_supported_underlyings = lambda: ["SPX", "NDX", "RUT"]  # type: ignore[attr-defined]
    package.get_info = _get_info  # type: ignore[attr-defined]
    sys.modules["landeros_ironware"] = package

    probability_module = types.ModuleType("landeros_ironware.risk.probability")
    probability_module.ProbabilityCalculator = _StubProbabilityCalculator
    sys.modules["landeros_ironware.risk.probability"] = probability_module

    visuals_module = types.ModuleType("landeros_ironware.visuals.payoff")
    visuals_module.PayoffDiagram = _StubPayoffDiagram
    sys.modules["landeros_ironware.visuals.payoff"] = visuals_module

    backtest_module = types.ModuleType("landeros_ironware.backtest.engine")
    backtest_module.BacktestEngine = _StubBacktestEngine
    backtest_module.BacktestResults = _StubBacktestResults
    sys.modules["landeros_ironware.backtest.engine"] = backtest_module

    yield

    for module_name in (
        "landeros_ironware",
        "landeros_ironware.risk.probability",
        "landeros_ironware.visuals.payoff",
        "landeros_ironware.backtest.engine",
    ):
        sys.modules.pop(module_name, None)


@pytest.fixture(autouse=True)
def _reset_stub_state() -> None:
    """Ensure stub singletons are clean for each test."""
    _StubPayoffDiagram.saved_paths.clear()
    _StubBacktestEngine.calls.clear()
    _StubBacktestEngine.last_instance = None
    _StubBacktestResults.last_saved_path = None


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect home directory and silence startup output during tests."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("LANDEROS_IRONWARE_QUIET", "1")


@lru_cache(maxsize=1)
def _iron_condor_module():
    return importlib.import_module("landeros_ironware.strategies.iron_condor")


@lru_cache(maxsize=1)
def _portfolio_module():
    return importlib.import_module("landeros_ironware.risk.portfolio")


def _create_candidate(score: float = 0.82):
    module = _iron_condor_module()
    IronCondor = module.IronCondor
    expiration = datetime.utcnow().replace(microsecond=0) + timedelta(days=45)
    return IronCondor(
        underlying="SPX",
        underlying_price=4500.0,
        dte=45,
        expiration=expiration,
        short_put_strike=4400.0,
        long_put_strike=4350.0,
        short_call_strike=4600.0,
        long_call_strike=4650.0,
        credit=2.5,
        max_loss=47.5,
        pop=0.72,
        break_even_lower=4397.5,
        break_even_upper=4602.5,
        delta=0.0,
        gamma=0.01,
        theta=1.2,
        vega=-28.0,
        score=score,
    )


def test_scan_cli_generates_ranked_candidates_and_output_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    candidate = _create_candidate(score=0.91)
    module = _iron_condor_module()
    IronCondorScanner = module.IronCondorScanner

    def _fake_scan(self):  # type: ignore[override]
        return [candidate]

    monkeypatch.setattr(IronCondorScanner, "scan", _fake_scan)

    cli_module = importlib.import_module("landeros_ironware.main")
    runner = CliRunner()
    output_file = tmp_path / "scan_results.json"
    result = runner.invoke(
        cli_module.cli,
        [
            "scan",
            "--underlying",
            "SPX",
            "--dte",
            "45",
            "--max-results",
            "1",
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0, result.output
    normalized = _normalize_output(result.output)
    assert "Top 1 Iron Condor Candidates" in normalized
    assert "4400.0" in normalized and "4600.0" in normalized
    assert output_file.exists()
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload[0]["structure"]["short_put"] == pytest.approx(4400.0)
    assert payload[0]["risk_metrics"]["pop"] == pytest.approx(candidate.pop)


def test_portfolio_manager_closes_positions_on_profit_target(tmp_path: Path) -> None:
    candidate = _create_candidate()
    module = _iron_condor_module()
    IronCondorPosition = module.IronCondorPosition
    ExitReason = module.ExitReason
    position = IronCondorPosition(
        iron_condor=candidate,
        contracts=1,
        entry_credit=candidate.credit,
        entry_date=datetime.utcnow() - timedelta(days=30),
    )

    settings_module = importlib.import_module("landeros_ironware.config.settings")
    Settings = settings_module.Settings
    settings = Settings()

    portfolio_module = _portfolio_module()
    PortfolioManager = portfolio_module.PortfolioManager
    manager = PortfolioManager(settings=settings, initial_capital=100000.0)

    assert manager.add_position(position) is True
    manager.update_positions()

    assert position.status.name == "CLOSED"
    assert position.exit_reason == ExitReason.PROFIT_TARGET


def test_analyze_cli_generates_payoff_plot(tmp_path: Path) -> None:
    candidate = _create_candidate()
    payload = candidate.to_dict()
    position_file = tmp_path / "position.json"
    position_file.write_text(json.dumps(payload, default=str), encoding="utf-8")

    plot_path = tmp_path / "payoff.png"
    cli_module = importlib.import_module("landeros_ironware.main")
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "analyze",
            "--position",
            str(position_file),
            "--save-plot",
            str(plot_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert plot_path.exists()
    assert _StubPayoffDiagram.saved_paths == [plot_path]


def test_backtest_cli_uses_stub_engine_and_saves_results(tmp_path: Path) -> None:
    output_file = tmp_path / "backtest.csv"
    cli_module = importlib.import_module("landeros_ironware.main")
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "backtest",
            "--start",
            "2024-01-01",
            "--end",
            "2024-03-31",
            "--underlying",
            "SPX",
            "--capital",
            "100000",
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0, result.output
    normalized = _normalize_output(result.output)
    assert "Backtest Complete" in normalized
    assert _StubBacktestEngine.last_instance is not None
    assert _StubBacktestEngine.calls[-1]["underlying"] == "SPX"
    assert _StubBacktestResults.last_saved_path == output_file
    assert output_file.read_text(encoding="utf-8").startswith("date,pnl")


