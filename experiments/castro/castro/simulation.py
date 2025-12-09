"""Simulation runner for policy evaluation.

Wraps the SimCash Orchestrator for running simulations with given policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig


@dataclass
class SimulationResult:
    """Result of a single simulation run.

    All costs are in cents (integer).

    Example:
        >>> result = SimulationResult(
        ...     total_cost=150000,
        ...     per_agent_costs={"BANK_A": 75000, "BANK_B": 75000},
        ...     settlement_rate=0.95,
        ...     transactions_settled=100,
        ...     transactions_failed=5,
        ... )
    """

    total_cost: int
    per_agent_costs: dict[str, int]
    settlement_rate: float
    transactions_settled: int
    transactions_failed: int


class CastroSimulationRunner:
    """Runs SimCash simulations for Monte Carlo evaluation.

    Wraps the Rust Orchestrator to run simulations with injected policies.

    Example:
        >>> runner = CastroSimulationRunner.from_yaml(Path("configs/exp1.yaml"))
        >>> result = runner.run_simulation(policy=my_policy, seed=42)
        >>> print(f"Total cost: ${result.total_cost / 100:.2f}")
    """

    def __init__(self, scenario_config: dict[str, Any]) -> None:
        """Initialize the simulation runner.

        Args:
            scenario_config: Base scenario configuration dict.
        """
        self._base_config = scenario_config

    @classmethod
    def from_yaml(cls, path: Path) -> CastroSimulationRunner:
        """Create runner from YAML configuration file.

        Args:
            path: Path to YAML scenario config.

        Returns:
            CastroSimulationRunner instance.
        """
        with open(path) as f:
            config = yaml.safe_load(f)
        return cls(config)

    def run_simulation(
        self,
        policy: dict[str, Any],
        seed: int,
        ticks: int | None = None,
    ) -> SimulationResult:
        """Run a single simulation with the given policy.

        Args:
            policy: Policy to evaluate (applied to all agents).
            seed: RNG seed for determinism.
            ticks: Number of ticks to run (default: full day).

        Returns:
            SimulationResult with costs and metrics.
        """
        # Build config with policy and seed
        config = self._build_config(policy, seed)

        # Create and run orchestrator
        orch = Orchestrator.new(config)

        # Calculate total ticks (config is now flat format)
        ticks_per_day = config.get("ticks_per_day", 100)
        num_days = config.get("num_days", 1)
        total_ticks = ticks if ticks is not None else (ticks_per_day * num_days)

        # Run simulation
        for _ in range(total_ticks):
            orch.tick()

        # Extract metrics
        return self._extract_metrics(orch)

    def _build_config(
        self,
        policy: dict[str, Any],
        seed: int,
    ) -> dict[str, Any]:
        """Build simulation config with injected policy and seed.

        Uses SimulationConfig.to_ffi_dict() for proper conversion.

        Args:
            policy: Policy to inject into agents.
            seed: RNG seed.

        Returns:
            Complete configuration dict for Orchestrator.new().
        """
        # Deep copy base config
        base = self._deep_copy(self._base_config)

        # Update seed in simulation config
        if "simulation" in base:
            base["simulation"]["rng_seed"] = seed
        else:
            base["simulation"] = {"rng_seed": seed}

        # Inject policy into all agents using InlinePolicy type
        agents = base.get("agents", [])
        for agent in agents:
            agent["policy"] = {"type": "Inline", "decision_trees": policy}

        # Use SimulationConfig for proper conversion to FFI format
        sim_config = SimulationConfig.from_dict(base)
        return sim_config.to_ffi_dict()

    def _extract_metrics(self, orch: Orchestrator) -> SimulationResult:
        """Extract metrics from completed orchestrator.

        Args:
            orch: Completed Orchestrator instance.

        Returns:
            SimulationResult with extracted metrics.
        """
        # Get per-agent costs
        agent_ids = orch.get_agent_ids()
        per_agent_costs: dict[str, int] = {}
        total_cost = 0

        for agent_id in agent_ids:
            costs = orch.get_agent_accumulated_costs(agent_id)
            agent_cost = costs.get("total_cost", 0)
            per_agent_costs[agent_id] = agent_cost
            total_cost += agent_cost

        # Get transaction counts for settlement metrics
        tx_counts = orch.get_transaction_counts_debug()

        # Calculate settlement metrics
        settled = tx_counts.get("settled", 0)
        failed = tx_counts.get("failed", 0)
        total_tx = settled + failed

        settlement_rate = settled / total_tx if total_tx > 0 else 1.0

        return SimulationResult(
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            settlement_rate=settlement_rate,
            transactions_settled=settled,
            transactions_failed=failed,
        )

    def _deep_copy(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Deep copy a configuration dict.

        Args:
            obj: Dict to copy.

        Returns:
            Deep copy of the dict.
        """
        import copy

        return copy.deepcopy(obj)

    def get_ticks_per_simulation(self) -> int:
        """Get the number of ticks in a full simulation.

        Returns:
            Total ticks per simulation.
        """
        sim_config = self._base_config.get("simulation", {})
        ticks_per_day: int = sim_config.get("ticks_per_day", 100)
        num_days: int = sim_config.get("num_days", 1)
        return ticks_per_day * num_days

    def get_agent_ids(self) -> list[str]:
        """Get list of agent IDs from configuration.

        Returns:
            List of agent ID strings.
        """
        agents = self._base_config.get("agents", [])
        return [agent.get("id", f"agent_{i}") for i, agent in enumerate(agents)]
