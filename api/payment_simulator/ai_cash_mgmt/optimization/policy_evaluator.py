"""Policy evaluator for Monte Carlo simulation.

Evaluates policies by running multiple simulations with sampled
transaction sets and aggregating the results.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Protocol

from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
    HistoricalTransaction,
)


@dataclass
class EvaluationResult:
    """Result of policy evaluation via Monte Carlo simulation.

    Stores aggregated metrics from running multiple simulations
    with different transaction samples.

    Example:
        >>> result = EvaluationResult(
        ...     agent_id="BANK_A",
        ...     policy={"payment_tree": {"root": {"action": "submit"}}},
        ...     mean_cost=1000.0,
        ...     std_cost=50.0,
        ...     min_cost=900.0,
        ...     max_cost=1100.0,
        ...     sample_costs=[950.0, 1000.0, 1050.0],
        ...     num_samples=3,
        ...     settlement_rate=0.95,
        ... )
    """

    agent_id: str
    policy: dict[str, Any]
    mean_cost: float
    std_cost: float
    min_cost: float
    max_cost: float
    sample_costs: list[float]
    num_samples: int
    settlement_rate: float

    def is_better_than(self, other: EvaluationResult) -> bool:
        """Check if this result is better than another.

        Lower mean cost is better.

        Args:
            other: The result to compare against.

        Returns:
            True if this result has lower mean cost.
        """
        return self.mean_cost < other.mean_cost

    def improvement_over(self, baseline: EvaluationResult) -> float:
        """Calculate relative improvement over a baseline.

        Args:
            baseline: The baseline result to compare against.

        Returns:
            Relative improvement (positive means this is better).
        """
        if baseline.mean_cost == 0:
            return 0.0
        return (baseline.mean_cost - self.mean_cost) / baseline.mean_cost

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dict representation of the result.
        """
        return {
            "agent_id": self.agent_id,
            "policy": self.policy,
            "mean_cost": self.mean_cost,
            "std_cost": self.std_cost,
            "min_cost": self.min_cost,
            "max_cost": self.max_cost,
            "sample_costs": self.sample_costs,
            "num_samples": self.num_samples,
            "settlement_rate": self.settlement_rate,
        }


@dataclass
class SimulationResult:
    """Result from a single ephemeral simulation run."""

    total_cost: float
    settlement_rate: float


class SimulationRunnerProtocol(Protocol):
    """Protocol for simulation runners.

    Implementations must provide run_ephemeral() which runs a simulation
    without persisting results to the database.
    """

    def run_ephemeral(
        self,
        scenario_config: dict[str, Any],
        policy: dict[str, Any],
        transactions: list[dict[str, Any]],
        num_ticks: int,
    ) -> SimulationResult:
        """Run an ephemeral simulation (no persistence).

        Args:
            scenario_config: Base scenario configuration.
            policy: Policy to evaluate.
            transactions: Pre-defined transactions to inject.
            num_ticks: Number of ticks to simulate.

        Returns:
            SimulationResult with cost and settlement metrics.
        """
        ...


class PolicyEvaluator:
    """Evaluates policies using Monte Carlo simulation.

    Runs multiple simulations with different transaction samples
    and aggregates the results to estimate policy performance.

    Key Design:
    - Ephemeral simulations: No results persisted to database
    - Deterministic: Same samples produce same results
    - Parallel-ready: Can use multiple workers (future enhancement)

    Example:
        >>> evaluator = PolicyEvaluator(
        ...     num_samples=20,
        ...     evaluation_ticks=100,
        ...     parallel_workers=4,
        ... )
        >>> result = evaluator.evaluate(
        ...     agent_id="BANK_A",
        ...     policy=my_policy,
        ...     samples=transaction_samples,
        ...     scenario_config=scenario,
        ...     simulation_runner=runner,
        ... )
    """

    def __init__(
        self,
        num_samples: int,
        evaluation_ticks: int,
        parallel_workers: int = 1,
    ) -> None:
        """Initialize the evaluator.

        Args:
            num_samples: Number of Monte Carlo samples to run.
            evaluation_ticks: Ticks to simulate per sample.
            parallel_workers: Number of parallel workers (for future use).
        """
        self._num_samples = num_samples
        self._evaluation_ticks = evaluation_ticks
        self._parallel_workers = parallel_workers

    @property
    def num_samples(self) -> int:
        """Get configured number of samples."""
        return self._num_samples

    @property
    def evaluation_ticks(self) -> int:
        """Get configured evaluation ticks."""
        return self._evaluation_ticks

    def evaluate(
        self,
        agent_id: str,
        policy: dict[str, Any],
        samples: list[list[HistoricalTransaction]],
        scenario_config: dict[str, Any],
        simulation_runner: SimulationRunnerProtocol,
    ) -> EvaluationResult:
        """Evaluate a policy using Monte Carlo simulation.

        Runs one simulation per sample and aggregates the results.

        Args:
            agent_id: The agent being evaluated.
            policy: The policy to evaluate.
            samples: List of transaction samples (one per simulation).
            scenario_config: Base scenario configuration.
            simulation_runner: Runner for ephemeral simulations.

        Returns:
            EvaluationResult with aggregated metrics.
        """
        costs: list[float] = []
        settlement_rates: list[float] = []

        for sample in samples:
            # Convert transactions to injection format
            tx_dicts = [tx.to_dict() for tx in sample]

            # Run ephemeral simulation
            result = simulation_runner.run_ephemeral(
                scenario_config=scenario_config,
                policy=policy,
                transactions=tx_dicts,
                num_ticks=self._evaluation_ticks,
            )

            costs.append(result.total_cost)
            settlement_rates.append(result.settlement_rate)

        # Aggregate results
        mean_cost = statistics.mean(costs) if costs else 0.0
        std_cost = statistics.stdev(costs) if len(costs) > 1 else 0.0
        min_cost = min(costs) if costs else 0.0
        max_cost = max(costs) if costs else 0.0
        mean_settlement = statistics.mean(settlement_rates) if settlement_rates else 0.0

        return EvaluationResult(
            agent_id=agent_id,
            policy=policy,
            mean_cost=mean_cost,
            std_cost=std_cost,
            min_cost=min_cost,
            max_cost=max_cost,
            sample_costs=costs,
            num_samples=len(samples),
            settlement_rate=mean_settlement,
        )
