"""Generic optimization loop for experiments.

Provides a config-driven optimization loop that can be used by any experiment.
All behavior is determined by ExperimentConfig - no hardcoded experiment logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from payment_simulator.experiments.config import ExperimentConfig
    from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints

from payment_simulator._core import Orchestrator
from payment_simulator.ai_cash_mgmt import ConvergenceDetector
from payment_simulator.config import SimulationConfig


@dataclass(frozen=True)
class OptimizationResult:
    """Result of running the optimization loop.

    Captures the final state after optimization completes.
    All costs are integer cents (INV-1).

    Attributes:
        num_iterations: Total iterations executed.
        converged: Whether optimization converged.
        convergence_reason: Reason for convergence (stability, max_iterations, etc).
        final_cost: Final total cost in integer cents.
        best_cost: Best (lowest) cost achieved in integer cents.
        per_agent_costs: Final cost per agent in integer cents.
        final_policies: Final policy dict per agent.
        iteration_history: History of costs per iteration.

    Example:
        >>> result = OptimizationResult(
        ...     num_iterations=10,
        ...     converged=True,
        ...     convergence_reason="stability_reached",
        ...     final_cost=15000,  # $150.00 in cents
        ...     best_cost=14500,
        ...     per_agent_costs={"BANK_A": 7500, "BANK_B": 7000},
        ...     final_policies={"BANK_A": {...}, "BANK_B": {...}},
        ...     iteration_history=[15000, 14800, 14500],
        ... )
    """

    num_iterations: int
    converged: bool
    convergence_reason: str
    final_cost: int  # INV-1: Integer cents
    best_cost: int  # INV-1: Integer cents
    per_agent_costs: dict[str, int]  # INV-1: Integer cents
    final_policies: dict[str, dict[str, Any]]
    iteration_history: list[int] = field(default_factory=list)


class OptimizationLoop:
    """Generic optimization loop for experiments.

    Executes the standard policy optimization algorithm:
    1. Evaluate current policies via simulation
    2. Check convergence criteria
    3. For each agent, generate new policy via LLM
    4. Accept/reject based on paired comparison
    5. Repeat until converged or max iterations

    All configuration is read from ExperimentConfig:
    - system_prompt: From config.llm.system_prompt
    - constraints: From config.get_constraints()
    - convergence: From config.convergence
    - agents: From config.optimized_agents

    Example:
        >>> from payment_simulator.experiments.config import ExperimentConfig
        >>> config = ExperimentConfig.from_yaml(Path("exp1.yaml"))
        >>> loop = OptimizationLoop(config=config)
        >>> result = await loop.run()
        >>> print(f"Converged: {result.converged}")

    Note:
        The actual LLM calls and simulation require external dependencies.
        This class provides the loop structure; actual execution needs
        a SimulationRunner to be injected or created from config.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        config_dir: Path | None = None,
    ) -> None:
        """Initialize the optimization loop.

        Args:
            config: ExperimentConfig with all settings.
            config_dir: Directory containing the experiment config (for resolving
                        relative scenario paths). If None, uses current directory.
        """
        self._config = config
        self._config_dir = config_dir or Path.cwd()

        # Get convergence settings
        conv = config.convergence
        self._convergence = ConvergenceDetector(
            stability_threshold=conv.stability_threshold,
            stability_window=conv.stability_window,
            max_iterations=conv.max_iterations,
            improvement_threshold=conv.improvement_threshold,
        )

        # Get constraints from config
        self._constraints: ScenarioConstraints | None = config.get_constraints()

        # Initialize state
        self._current_iteration = 0
        self._policies: dict[str, dict[str, Any]] = {}
        self._best_cost: int = 0
        self._best_policies: dict[str, dict[str, Any]] = {}
        self._iteration_history: list[int] = []

        # Load scenario config once
        self._scenario_dict: dict[str, Any] | None = None

        # LLM client (lazy initialized)
        self._llm_client: Any = None

    @property
    def max_iterations(self) -> int:
        """Get max iterations from config."""
        return self._config.convergence.max_iterations

    @property
    def stability_threshold(self) -> float:
        """Get stability threshold from config."""
        return self._config.convergence.stability_threshold

    @property
    def is_converged(self) -> bool:
        """Check if optimization has converged."""
        return self._convergence.is_converged

    @property
    def optimized_agents(self) -> tuple[str, ...]:
        """Get list of agents being optimized."""
        return self._config.optimized_agents

    @property
    def current_policies(self) -> dict[str, dict[str, Any]]:
        """Get current policies per agent."""
        return self._policies.copy()

    @property
    def master_seed(self) -> int:
        """Get master seed for determinism."""
        return self._config.master_seed

    @property
    def current_iteration(self) -> int:
        """Get current iteration count."""
        return self._current_iteration

    async def run(self) -> OptimizationResult:
        """Run the optimization loop to convergence.

        Returns:
            OptimizationResult with final state and metrics.

        Note:
            This base implementation provides the loop structure.
            Subclasses or the GenericExperimentRunner should implement
            actual evaluation and policy generation.
        """
        # Initialize policies if not set
        for agent_id in self.optimized_agents:
            if agent_id not in self._policies:
                self._policies[agent_id] = self._create_default_policy(agent_id)

        # Optimization loop
        while self._current_iteration < self.max_iterations:
            self._current_iteration += 1

            # Evaluate current policies (to be implemented by subclass)
            total_cost, per_agent_costs = await self._evaluate_policies()

            # Record metrics
            self._convergence.record_metric(float(total_cost))
            self._iteration_history.append(total_cost)

            # Track best
            if self._best_cost == 0 or total_cost < self._best_cost:
                self._best_cost = total_cost
                self._best_policies = {
                    k: v.copy() for k, v in self._policies.items()
                }

            # Check convergence
            if self._convergence.is_converged:
                break

            # Optimize each agent (to be implemented by subclass)
            for agent_id in self.optimized_agents:
                await self._optimize_agent(agent_id, per_agent_costs.get(agent_id, 0))

        return OptimizationResult(
            num_iterations=self._current_iteration,
            converged=self._convergence.is_converged,
            convergence_reason=self._convergence.convergence_reason or "max_iterations",
            final_cost=self._iteration_history[-1] if self._iteration_history else 0,
            best_cost=self._best_cost,
            per_agent_costs={
                agent_id: per_agent_costs.get(agent_id, 0)
                for agent_id in self.optimized_agents
            } if "per_agent_costs" in dir() else {},
            final_policies=self._policies.copy(),
            iteration_history=self._iteration_history.copy(),
        )

    def _load_scenario_config(self) -> dict[str, Any]:
        """Load scenario configuration from YAML file.

        Resolves the scenario path relative to the experiment config directory.

        Returns:
            Scenario configuration dictionary.

        Raises:
            FileNotFoundError: If scenario file doesn't exist.
        """
        if self._scenario_dict is not None:
            return self._scenario_dict

        scenario_path = self._config.scenario_path
        if not scenario_path.is_absolute():
            scenario_path = self._config_dir / scenario_path

        if not scenario_path.exists():
            msg = f"Scenario file not found: {scenario_path}"
            raise FileNotFoundError(msg)

        with open(scenario_path) as f:
            self._scenario_dict = yaml.safe_load(f)

        return self._scenario_dict

    def _build_simulation_config(self) -> dict[str, Any]:
        """Build FFI-compatible simulation config with current policies.

        Merges the base scenario config with current agent policies.

        Returns:
            FFI-compatible configuration dictionary.
        """
        import copy

        # Deep copy to avoid mutating the cached scenario config
        scenario_dict = copy.deepcopy(self._load_scenario_config())

        # Update agent policies in the scenario
        if "agents" in scenario_dict:
            for agent_config in scenario_dict["agents"]:
                agent_id = agent_config.get("id")
                if agent_id in self._policies:
                    agent_config["policy"] = self._policies[agent_id]

        # Convert to FFI format
        sim_config = SimulationConfig.from_dict(scenario_dict)
        return sim_config.to_ffi_dict()

    async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
        """Evaluate current policies by running a simulation.

        Runs a full simulation with the current policies and extracts
        total cost and per-agent costs.

        Returns:
            Tuple of (total_cost, per_agent_costs) in integer cents.
        """
        # Build config with current policies
        ffi_config = self._build_simulation_config()

        # Override seed with iteration-specific seed for reproducibility
        ffi_config["rng_seed"] = self._config.master_seed + self._current_iteration

        # Create orchestrator
        orch = Orchestrator.new(ffi_config)

        # Run simulation for the configured number of ticks
        total_ticks = self._config.evaluation.ticks
        for _ in range(total_ticks):
            orch.tick()

        # Extract total cost and per-agent costs
        total_cost = 0
        per_agent_costs: dict[str, int] = {}

        for agent_id in self.optimized_agents:
            try:
                agent_costs = orch.get_agent_accumulated_costs(agent_id)
                agent_total = int(agent_costs.get("total_cost", 0))
                per_agent_costs[agent_id] = agent_total
                total_cost += agent_total
            except Exception:
                per_agent_costs[agent_id] = 0

        return total_cost, per_agent_costs

    async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
        """Optimize policy for a single agent using LLM.

        Calls the LLM to generate an improved policy for the agent,
        validates it against constraints, and updates if valid.

        Args:
            agent_id: Agent to optimize.
            current_cost: Current cost for this agent in integer cents.
        """
        # Skip LLM optimization if no system prompt configured
        if self._config.llm.system_prompt is None:
            return

        # Lazy initialize LLM client
        if self._llm_client is None:
            from payment_simulator.experiments.runner.llm_client import (
                ExperimentLLMClient,
            )

            self._llm_client = ExperimentLLMClient(self._config.llm)

        # Get current policy
        current_policy = self._policies.get(agent_id, self._create_default_policy(agent_id))

        # Build context for LLM
        context: dict[str, Any] = {
            "iteration": self._current_iteration,
            "history": [
                {"iteration": i + 1, "cost": cost}
                for i, cost in enumerate(self._iteration_history)
            ],
        }

        # Build optimization prompt
        prompt = f"""Optimize policy for agent {agent_id}.
Current cost: ${current_cost / 100:.2f}
Iteration: {self._current_iteration}

Your goal is to minimize total cost while ensuring payments are settled on time.
"""

        try:
            # Generate new policy
            new_policy = await self._llm_client.generate_policy(
                prompt=prompt,
                current_policy=current_policy,
                context=context,
            )

            # Validate against constraints if configured
            if self._constraints is not None:
                from payment_simulator.ai_cash_mgmt.optimization.constraint_validator import (
                    ConstraintValidator,
                )

                validator = ConstraintValidator(self._constraints)
                result = validator.validate(new_policy)
                if not result.is_valid:
                    # Keep current policy if validation fails
                    return

            # Update policy
            self._policies[agent_id] = new_policy

        except Exception:
            # Keep current policy on error
            pass

    def _create_default_policy(self, agent_id: str) -> dict[str, Any]:
        """Create a default/seed policy for an agent.

        Creates a simple Release-always policy as a starting point.

        Args:
            agent_id: Agent ID.

        Returns:
            Default policy dict.
        """
        return {
            "version": "2.0",
            "policy_id": f"{agent_id}_default",
            "parameters": {
                "initial_liquidity_fraction": 0.5,
                "urgency_threshold": 5,
                "liquidity_buffer_factor": 1.0,
            },
            "payment_tree": {
                "type": "action",
                "node_id": "default_release",
                "action": "Release",
            },
            "strategic_collateral_tree": {
                "type": "action",
                "node_id": "default_collateral",
                "action": "HoldCollateral",
                "parameters": {
                    "amount": {"value": 0},
                    "reason": {"value": "InitialAllocation"},
                },
            },
        }
