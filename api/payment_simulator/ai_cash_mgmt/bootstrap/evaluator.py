"""Bootstrap policy evaluator for Monte Carlo policy comparison.

This module provides the BootstrapPolicyEvaluator class for:
1. Evaluating a policy on a single bootstrap sample
2. Running Monte Carlo evaluation across multiple samples
3. Computing paired deltas between two policies
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from payment_simulator._core import Orchestrator
from payment_simulator.ai_cash_mgmt.bootstrap.models import BootstrapSample
from payment_simulator.ai_cash_mgmt.bootstrap.sandbox_config import SandboxConfigBuilder


@dataclass(frozen=True)
class EvaluationResult:
    """Result of evaluating a policy on a single bootstrap sample.

    Attributes:
        sample_idx: Index of the bootstrap sample.
        seed: RNG seed used for this sample.
        total_cost: Total cost incurred by the target agent (integer cents).
        settlement_rate: Fraction of transactions settled (0.0 to 1.0).
        avg_delay: Average delay in ticks for settled transactions.
    """

    sample_idx: int
    seed: int
    total_cost: int  # Integer cents (project invariant)
    settlement_rate: float
    avg_delay: float


@dataclass(frozen=True)
class PairedDelta:
    """Paired comparison result between two policies on same sample.

    Attributes:
        sample_idx: Index of the bootstrap sample.
        seed: RNG seed used for this sample.
        cost_a: Cost under policy A.
        cost_b: Cost under policy B.
        delta: cost_a - cost_b (positive means A is more expensive).
    """

    sample_idx: int
    seed: int
    cost_a: int
    cost_b: int
    delta: int  # cost_a - cost_b


class BootstrapPolicyEvaluator:
    """Evaluates policies using bootstrap Monte Carlo simulation.

    This evaluator:
    1. Takes bootstrap samples (from BootstrapSampler)
    2. Builds sandbox configs (using SandboxConfigBuilder)
    3. Runs simulations via FFI
    4. Extracts costs for the target agent

    Example:
        ```python
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # Single sample evaluation
        result = evaluator.evaluate_sample(sample, policy={"type": "Fifo"})
        print(f"Cost: {result.total_cost}")

        # Monte Carlo evaluation
        results = evaluator.evaluate_samples(samples, policy={"type": "Fifo"})
        mean_cost = evaluator.compute_mean_cost(results)

        # Paired comparison
        deltas = evaluator.compute_paired_deltas(
            samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "LiquidityAware", ...},
        )
        mean_delta = evaluator.compute_mean_delta(deltas)
        ```
    """

    def __init__(
        self,
        opening_balance: int,
        credit_limit: int,
        cost_rates: dict[str, float] | None = None,
    ) -> None:
        """Initialize the evaluator.

        Args:
            opening_balance: Opening balance for target agent (cents).
            credit_limit: Credit limit for target agent (cents).
            cost_rates: Optional cost rates override.
        """
        self._opening_balance = opening_balance
        self._credit_limit = credit_limit
        self._cost_rates = cost_rates
        self._config_builder = SandboxConfigBuilder()

    def evaluate_sample(
        self,
        sample: BootstrapSample,
        policy: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate a policy on a single bootstrap sample.

        Args:
            sample: BootstrapSample with remapped transactions.
            policy: Policy configuration dict.

        Returns:
            EvaluationResult with cost and metrics.
        """
        # Build sandbox config
        config = self._config_builder.build_config(
            sample=sample,
            target_policy=policy,
            opening_balance=self._opening_balance,
            credit_limit=self._credit_limit,
            cost_rates=self._cost_rates,
        )

        # Convert to FFI dict and run simulation
        ffi_config = config.to_ffi_dict()
        orchestrator = Orchestrator.new(ffi_config)

        # Run simulation to completion
        total_ticks = sample.total_ticks
        for _ in range(total_ticks):
            orchestrator.tick()

        # Extract metrics for target agent
        metrics = self._extract_agent_metrics(orchestrator, sample.agent_id)

        return EvaluationResult(
            sample_idx=sample.sample_idx,
            seed=sample.seed,
            total_cost=int(metrics["total_cost"]),
            settlement_rate=float(metrics["settlement_rate"]),
            avg_delay=float(metrics["avg_delay"]),
        )

    def evaluate_samples(
        self,
        samples: list[BootstrapSample],
        policy: dict[str, Any],
    ) -> list[EvaluationResult]:
        """Evaluate a policy across multiple bootstrap samples.

        Args:
            samples: List of BootstrapSamples.
            policy: Policy configuration dict.

        Returns:
            List of EvaluationResults, one per sample.
        """
        return [self.evaluate_sample(sample, policy) for sample in samples]

    def compute_paired_deltas(
        self,
        samples: list[BootstrapSample],
        policy_a: dict[str, Any],
        policy_b: dict[str, Any],
    ) -> list[PairedDelta]:
        """Compute paired deltas between two policies.

        Evaluates both policies on each sample and computes the
        difference. Paired comparison reduces variance.

        Args:
            samples: List of BootstrapSamples.
            policy_a: First policy configuration.
            policy_b: Second policy configuration.

        Returns:
            List of PairedDeltas, one per sample.
        """
        results_a = self.evaluate_samples(samples, policy_a)
        results_b = self.evaluate_samples(samples, policy_b)

        deltas: list[PairedDelta] = []
        for result_a, result_b in zip(results_a, results_b, strict=True):
            delta = PairedDelta(
                sample_idx=result_a.sample_idx,
                seed=result_a.seed,
                cost_a=result_a.total_cost,
                cost_b=result_b.total_cost,
                delta=result_a.total_cost - result_b.total_cost,
            )
            deltas.append(delta)

        return deltas

    def compute_mean_cost(self, results: list[EvaluationResult]) -> float:
        """Compute mean cost across evaluation results.

        Args:
            results: List of EvaluationResults.

        Returns:
            Mean total cost as float.
        """
        if not results:
            return 0.0
        return float(statistics.mean(r.total_cost for r in results))

    def compute_mean_delta(self, deltas: list[PairedDelta]) -> float:
        """Compute mean delta across paired comparisons.

        Args:
            deltas: List of PairedDeltas.

        Returns:
            Mean delta as float.
        """
        if not deltas:
            return 0.0
        return float(statistics.mean(d.delta for d in deltas))

    def _extract_agent_metrics(
        self,
        orchestrator: Orchestrator,
        agent_id: str,
    ) -> dict[str, int | float]:
        """Extract metrics for specific agent from completed simulation.

        Args:
            orchestrator: Completed Orchestrator instance.
            agent_id: ID of agent to extract metrics for.

        Returns:
            Dict with total_cost, settlement_rate, avg_delay.
        """
        # Get agent costs from orchestrator
        try:
            agent_costs = orchestrator.get_agent_accumulated_costs(agent_id)
            total_cost = int(agent_costs.get("total_cost", 0))
        except Exception:
            total_cost = 0

        # Get simulation state for metrics
        try:
            agent_state = orchestrator.get_agent_state(agent_id)

            # Calculate settlement rate from pending transactions
            # If no pending = 100% settled
            pending_count = len(agent_state.get("pending_transactions", []))
            total_txns = len(agent_state.get("all_transactions", []))

            if total_txns > 0:
                settlement_rate = 1.0 - (pending_count / total_txns)
            else:
                settlement_rate = 1.0

            avg_delay = float(agent_state.get("avg_settlement_delay", 0.0))
        except Exception:
            settlement_rate = 1.0
            avg_delay = 0.0

        return {
            "total_cost": total_cost,
            "settlement_rate": settlement_rate,
            "avg_delay": avg_delay,
        }
