"""
Strike selection optimizer for Landeros Financial Ironware.

Provides a configurable scoring engine to rank iron condor candidates
based on a multi-factor weighted model.

This is the "secret sauce" for ranking trades.

Author: Carlos Landeros
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
import numpy as np

from landeros_ironware.config.settings import Settings
from landeros_ironware.utils.helpers import safe_divide, clamp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptimizationCriteria:
    """
    Weights for the scoring model. Must sum to 1.0.

    Factors:
        - pop_weight: Probability of profit (higher = better)
        - roc_weight: Return on capital (higher = better)
        - theta_risk_weight: Time decay relative to risk (higher = better)
        - vega_risk_weight: Volatility exposure relative to risk (lower = better)
        - credit_width_weight: Credit quality (higher = better)
    """
    pop_weight: float = 0.30
    roc_weight: float = 0.30
    theta_risk_weight: float = 0.20
    vega_risk_weight: float = 0.10
    credit_width_weight: float = 0.10

    def __post_init__(self) -> None:
        """Validate that weights sum to approximately 1.0."""
        total = sum([
            self.pop_weight,
            self.roc_weight,
            self.theta_risk_weight,
            self.vega_risk_weight,
            self.credit_width_weight
        ])
        if not np.isclose(total, 1.0, atol=0.001):
            logger.warning(
                f"OptimizationCriteria weights sum to {total:.3f}, not 1.0. "
                f"This may cause inconsistent scoring."
            )

    @classmethod
    def from_settings(cls, settings: Settings) -> "OptimizationCriteria":
        """
        Create criteria from Settings object.

        Falls back to defaults if settings don't have optimizer weights.
        """
        return cls(
            pop_weight=getattr(settings, "optimizer_pop_weight", 0.30),
            roc_weight=getattr(settings, "optimizer_roc_weight", 0.30),
            theta_risk_weight=getattr(settings, "optimizer_theta_weight", 0.20),
            vega_risk_weight=getattr(settings, "optimizer_vega_weight", 0.10),
            credit_width_weight=getattr(settings, "optimizer_credit_width_weight", 0.10),
        )


@dataclass(frozen=True)
class OptimizationResult:
    """
    Result of scoring a single iron condor candidate.

    Attributes:
        candidate: The IronCondor that was scored
        score: Overall score (0.0 to 1.0, higher is better)
        metrics: Breakdown of individual factor scores
    """
    candidate: Any  # Would be IronCondor but avoiding circular import
    score: float
    metrics: Dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"OptResult(score={self.score:.4f}, candidate={self.candidate})"


class StrikeOptimizer:
    """
    Multi-factor scoring engine for iron condor candidates.

    Ranks candidates based on weighted combination of:
    1. Probability of profit (POP)
    2. Return on capital (ROC)
    3. Theta efficiency (time decay / risk)
    4. Vega exposure (volatility risk / max loss)
    5. Credit quality (credit / width ratio)
    """

    def __init__(self, settings: Settings):
        """
        Initialize the optimizer.

        Args:
            settings: Configuration object containing optimizer weights
        """
        self.settings = settings
        self.criteria = OptimizationCriteria.from_settings(settings)

        logger.debug(
            f"StrikeOptimizer initialized with weights: "
            f"POP={self.criteria.pop_weight:.2f}, ROC={self.criteria.roc_weight:.2f}, "
            f"Theta={self.criteria.theta_risk_weight:.2f}, "
            f"Vega={self.criteria.vega_risk_weight:.2f}, "
            f"CreditWidth={self.criteria.credit_width_weight:.2f}"
        )

    def score_and_sort_candidates(self, candidates: List[Any]) -> List[Any]:
        """
        Score all candidates and return sorted list (best first).

        Args:
            candidates: List of IronCondor objects to score

        Returns:
            List of IronCondor objects sorted by score (highest first)
        """
        if not candidates:
            logger.warning("No candidates provided to score")
            return []

        # Import here to avoid circular dependency
        from landeros_ironware.strategies.iron_condor import IronCondor

        scored_results: List[OptimizationResult] = []

        for ic in candidates:
            score, metrics = self._score_candidate(ic)

            # Create new IronCondor with updated score
            # We use to_dict/from_dict to create a new immutable instance
            ic_data = ic.to_dict()
            ic_data["score"] = score
            scored_candidate = IronCondor.from_dict(ic_data)

            result = OptimizationResult(
                candidate=scored_candidate,
                score=score,
                metrics=metrics
            )
            scored_results.append(result)

        # Sort by score (highest first)
        scored_results.sort(key=lambda r: r.score, reverse=True)

        if scored_results:
            best = scored_results[0]
            logger.info(
                f"Scored {len(scored_results)} iron condors | "
                f"Best: {best.score:.4f} | "
                f"Worst: {scored_results[-1].score:.4f}"
            )
            logger.debug(f"Best candidate metrics: {best.metrics}")

        # Return just the IronCondor objects, not the full results
        return [r.candidate for r in scored_results]

    def _score_candidate(self, ic: Any) -> Tuple[float, Dict[str, float]]:
        """
        Calculate weighted score for a single candidate.

        Args:
            ic: IronCondor candidate to score

        Returns:
            Tuple of (total_score, metrics_breakdown)
        """
        c = self.criteria
        metrics: Dict[str, float] = {}

        # --- Factor 1: Probability of Profit (POP) ---
        # Normalize POP from min_pop to 1.0
        # Higher POP = higher score
        pop_norm = safe_divide(
            ic.pop - self.settings.min_pop,
            1.0 - self.settings.min_pop,
            default=0.0
        )
        metrics["pop_raw"] = ic.pop
        metrics["pop_norm"] = clamp(pop_norm, 0.0, 1.0)
        metrics["pop_score"] = metrics["pop_norm"] * c.pop_weight

        # --- Factor 2: Return on Capital (ROC) ---
        # Normalize ROC assuming typical range of 10% to 50%
        # Higher ROC = higher score
        # Target: 10% (min) to 50% (excellent)
        roc_norm = safe_divide(
            ic.return_on_capital - 0.10,
            0.40,  # Range: 0.50 - 0.10
            default=0.0
        )
        metrics["roc_raw"] = ic.return_on_capital
        metrics["roc_norm"] = clamp(roc_norm, 0.0, 1.0)
        metrics["roc_score"] = metrics["roc_norm"] * c.roc_weight

        # --- Factor 3: Theta Efficiency (Time Decay / Risk) ---
        # Measure how much theta we collect per dollar of risk
        # Higher ratio = more time decay = higher score
        # Typical range: 0.02 to 0.10 (2% to 10% daily decay)
        theta_ratio = safe_divide(abs(ic.theta), ic.max_loss, default=0.0)
        theta_norm = safe_divide(
            theta_ratio - 0.02,
            0.08,  # Range: 0.10 - 0.02
            default=0.0
        )
        metrics["theta_raw"] = ic.theta
        metrics["theta_ratio"] = theta_ratio
        metrics["theta_norm"] = clamp(theta_norm, 0.0, 1.0)
        metrics["theta_score"] = metrics["theta_norm"] * c.theta_risk_weight

        # --- Factor 4: Vega Risk (Volatility Exposure / Risk) ---
        # FIXED: Lower absolute vega = less vol risk = higher score
        # Iron condors are short vega (negative), so we want abs(vega) close to zero
        # Typical range: 0.0 (perfect) to 3.0 (high exposure)
        abs_vega_ratio = safe_divide(abs(ic.vega), ic.max_loss, default=0.0)
        # Invert: 0.0 → 1.0 (best), 3.0 → 0.0 (worst)
        vega_norm = 1.0 - safe_divide(abs_vega_ratio, 3.0, default=0.0)
        metrics["vega_raw"] = ic.vega
        metrics["vega_ratio"] = abs_vega_ratio
        metrics["vega_norm"] = clamp(vega_norm, 0.0, 1.0)
        metrics["vega_score"] = metrics["vega_norm"] * c.vega_risk_weight

        # --- Factor 5: Credit/Width Ratio ---
        # Measure credit quality relative to wing width
        # Higher ratio = better credit for the risk
        # Already filtered by min_credit_to_width_ratio in validation
        credit_width_ratio = safe_divide(
            ic.credit,
            ic.max_loss + ic.credit,  # Total width
            default=0.0
        )
        cw_norm = safe_divide(
            credit_width_ratio - self.settings.min_credit_to_width_ratio,
            0.33 - self.settings.min_credit_to_width_ratio,  # Max realistic ratio ~33%
            default=0.0
        )
        metrics["credit_width_raw"] = credit_width_ratio
        metrics["credit_width_norm"] = clamp(cw_norm, 0.0, 1.0)
        metrics["credit_width_score"] = metrics["credit_width_norm"] * c.credit_width_weight

        # --- Total Score ---
        total_score = (
            metrics["pop_score"] +
            metrics["roc_score"] +
            metrics["theta_score"] +
            metrics["vega_score"] +
            metrics["credit_width_score"]
        )

        # Store total in metrics for debugging
        metrics["total_score"] = total_score

        return total_score, metrics

    def get_top_candidates(
        self,
        candidates: List[Any],
        n: int = 10
    ) -> List[Any]:
        """
        Score and return top N candidates.

        Args:
            candidates: List of IronCondor objects
            n: Number of top candidates to return

        Returns:
            List of top N IronCondor objects
        """
        sorted_candidates = self.score_and_sort_candidates(candidates)
        return sorted_candidates[:n]
