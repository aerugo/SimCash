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
    from payment_simulator.experiments.persistence import ExperimentRepository
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
        repository: ExperimentRepository | None = None,
        experiment_id: str | None = None,
    ) -> None:
        """Initialize the optimization loop.

        Args:
            config: ExperimentConfig with all settings.
            config_dir: Directory containing the experiment config (for resolving
                        relative scenario paths). If None, uses current directory.
            repository: Optional ExperimentRepository for persistence.
            experiment_id: Optional experiment ID for persistence.
        """
        self._config = config
        self._config_dir = config_dir or Path.cwd()
        self._repository: ExperimentRepository | None = repository
        self._experiment_id: str | None = experiment_id

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

        # Track accepted changes per iteration
        self._accepted_changes: dict[str, bool] = {}

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

        per_agent_costs: dict[str, int] = {}

        # Optimization loop
        while self._current_iteration < self.max_iterations:
            self._current_iteration += 1

            # Reset accepted changes for this iteration
            self._accepted_changes = {agent_id: False for agent_id in self.optimized_agents}

            # Evaluate current policies
            total_cost, per_agent_costs = await self._evaluate_policies()

            # Save evaluation event
            self._save_evaluation_event(total_cost, per_agent_costs)

            # Record metrics
            self._convergence.record_metric(float(total_cost))
            self._iteration_history.append(total_cost)

            # Track best
            if self._best_cost == 0 or total_cost < self._best_cost:
                self._best_cost = total_cost
                self._best_policies = {
                    k: v.copy() for k, v in self._policies.items()
                }

            # Save iteration record
            self._save_iteration_record(per_agent_costs)

            # Check convergence
            if self._convergence.is_converged:
                break

            # Optimize each agent
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
            },
            final_policies=self._policies.copy(),
            iteration_history=self._iteration_history.copy(),
        )

    def _save_iteration_record(self, per_agent_costs: dict[str, int]) -> None:
        """Save iteration record to repository.

        Args:
            per_agent_costs: Costs per agent in integer cents.
        """
        if self._repository is None or self._experiment_id is None:
            return

        from datetime import datetime

        from payment_simulator.experiments.persistence import IterationRecord

        record = IterationRecord(
            run_id=self._experiment_id,
            iteration=self._current_iteration - 1,  # 0-indexed in storage
            costs_per_agent=per_agent_costs,
            accepted_changes=self._accepted_changes.copy(),
            policies={k: v.copy() for k, v in self._policies.items()},
            timestamp=datetime.now().isoformat(),
        )
        self._repository.save_iteration(record)

    def _save_evaluation_event(
        self, total_cost: int, per_agent_costs: dict[str, int]
    ) -> None:
        """Save evaluation event to repository.

        Args:
            total_cost: Total cost in integer cents.
            per_agent_costs: Costs per agent in integer cents.
        """
        if self._repository is None or self._experiment_id is None:
            return

        from datetime import datetime

        from payment_simulator.experiments.persistence import EventRecord

        event = EventRecord(
            run_id=self._experiment_id,
            iteration=self._current_iteration - 1,  # 0-indexed
            event_type="evaluation",
            event_data={
                "total_cost": total_cost,
                "per_agent_costs": per_agent_costs,
            },
            timestamp=datetime.now().isoformat(),
        )
        self._repository.save_event(event)

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

    def _run_single_simulation(self, seed: int) -> tuple[int, dict[str, int]]:
        """Run a single simulation with the given seed.

        Args:
            seed: RNG seed for this simulation.

        Returns:
            Tuple of (total_cost, per_agent_costs) in integer cents.
        """
        # Build config with current policies
        ffi_config = self._build_simulation_config()

        # Override seed
        ffi_config["rng_seed"] = seed

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

    async def _evaluate_policies(self) -> tuple[int, dict[str, int]]:
        """Evaluate current policies by running simulation(s).

        For deterministic mode: runs a single simulation.
        For bootstrap mode: runs N simulations with different seeds and averages.

        Returns:
            Tuple of (total_cost, per_agent_costs) in integer cents.
        """
        eval_mode = self._config.evaluation.mode
        num_samples = self._config.evaluation.num_samples or 1

        if eval_mode == "deterministic" or num_samples <= 1:
            # Single simulation - deterministic mode
            seed = self._config.master_seed + self._current_iteration
            return self._run_single_simulation(seed)

        # Bootstrap mode: run multiple simulations and average
        total_costs: list[int] = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self.optimized_agents
        }

        for sample_idx in range(num_samples):
            # Use deterministic seed derivation for reproducibility
            seed = self._derive_sample_seed(sample_idx)
            cost, agent_costs = self._run_single_simulation(seed)
            total_costs.append(cost)
            for agent_id in self.optimized_agents:
                per_agent_totals[agent_id].append(agent_costs.get(agent_id, 0))

        # Compute mean costs (as integers)
        mean_total = int(sum(total_costs) / len(total_costs))
        mean_per_agent = {
            agent_id: int(sum(costs) / len(costs))
            for agent_id, costs in per_agent_totals.items()
        }

        return mean_total, mean_per_agent

    def _derive_sample_seed(self, sample_idx: int) -> int:
        """Derive a deterministic seed for a bootstrap sample.

        Uses SHA-256 for deterministic derivation, ensuring same
        sample_idx always produces the same seed (reproducibility).

        Args:
            sample_idx: Sample index.

        Returns:
            Derived seed for this sample.
        """
        import hashlib

        key = f"{self._config.master_seed}:sample:{sample_idx}"
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big") % (2**31)

    def _evaluate_policy_on_samples(
        self, policy: dict[str, Any], agent_id: str, num_samples: int
    ) -> list[int]:
        """Evaluate a policy on multiple samples for paired comparison.

        Args:
            policy: Policy dict to evaluate.
            agent_id: Agent to evaluate for.
            num_samples: Number of samples to run.

        Returns:
            List of costs (one per sample).
        """
        import copy

        # Temporarily set the policy for evaluation
        original_policy = self._policies.get(agent_id)
        self._policies[agent_id] = policy

        costs: list[int] = []
        for sample_idx in range(num_samples):
            seed = self._derive_sample_seed(sample_idx)
            _, agent_costs = self._run_single_simulation(seed)
            costs.append(agent_costs.get(agent_id, 0))

        # Restore original policy
        if original_policy is not None:
            self._policies[agent_id] = original_policy
        elif agent_id in self._policies:
            del self._policies[agent_id]

        return costs

    async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
        """Optimize policy for a single agent using LLM.

        Calls the LLM to generate an improved policy for the agent,
        validates it against constraints, and accepts/rejects based on
        paired comparison (in bootstrap mode) or direct cost comparison.

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

            # Accept/reject based on evaluation mode
            should_accept = await self._should_accept_policy(
                agent_id=agent_id,
                old_policy=current_policy,
                new_policy=new_policy,
            )

            if should_accept:
                self._policies[agent_id] = new_policy
                self._accepted_changes[agent_id] = True

        except Exception:
            # Keep current policy on error
            pass

    async def _should_accept_policy(
        self,
        agent_id: str,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
    ) -> bool:
        """Determine whether to accept a new policy.

        For deterministic mode: always accept (rely on convergence detection).
        For bootstrap mode: use paired comparison - accept if mean_delta > 0.

        Args:
            agent_id: Agent being optimized.
            old_policy: Current policy.
            new_policy: Proposed new policy.

        Returns:
            True if new policy should be accepted.
        """
        eval_mode = self._config.evaluation.mode
        num_samples = self._config.evaluation.num_samples or 1

        if eval_mode == "deterministic" or num_samples <= 1:
            # In deterministic mode, always accept - convergence detection
            # will handle stability checking
            return True

        # Bootstrap mode: paired comparison
        # Evaluate both policies on the SAME samples
        old_costs = self._evaluate_policy_on_samples(old_policy, agent_id, num_samples)
        new_costs = self._evaluate_policy_on_samples(new_policy, agent_id, num_samples)

        # Compute paired deltas: delta = old - new
        # Positive delta means new policy is cheaper (better)
        deltas = [old - new for old, new in zip(old_costs, new_costs, strict=True)]
        mean_delta = sum(deltas) / len(deltas)

        # Accept if mean_delta > 0 (new policy is cheaper on average)
        return mean_delta > 0

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
