# Clean-Slate Castro Experiments with ai_cash_mgmt

**Status**: Planning
**Created**: 2025-12-09
**Goal**: Rewrite Castro experiments from scratch using only the `ai_cash_mgmt` module. No legacy code, no backwards compatibility.

---

## Overview

The Castro experiments replicate "Estimating Policy Functions in Payment Systems Using Reinforcement Learning" (Castro et al., 2025). We'll implement these experiments using the new `ai_cash_mgmt` module exclusively.

**What we're building**:
- Three experiments (2-period, 12-period, joint optimization)
- LLM-based policy optimization using `PolicyOptimizer`
- Monte Carlo evaluation using `PolicyEvaluator` and `TransactionSampler`
- Deterministic execution via `SeedManager`
- Persistence via `GameRepository`

**What we're NOT doing**:
- No adapters or wrappers around legacy code
- No PydanticAI dependency (use standard LLM calls)
- No backwards compatibility with legacy Castro database

---

## Architecture

```
experiments/new-castro/
├── pyproject.toml              # Minimal deps: ai_cash_mgmt, anthropic/openai
├── castro/
│   ├── __init__.py
│   ├── experiments.py          # Experiment definitions (exp1, exp2, exp3)
│   ├── constraints.py          # Castro-specific ScenarioConstraints
│   ├── llm_client.py           # LLMClientProtocol implementation
│   ├── simulation.py           # SimulationRunnerProtocol implementation
│   └── runner.py               # ExperimentRunner orchestration
├── configs/                    # Scenario YAML files
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── cli.py                      # Typer CLI
└── tests/
    └── test_experiments.py
```

---

## Phase 1: Castro Constraints

Define the constraints that enforce Castro paper rules using `ai_cash_mgmt.ScenarioConstraints`.

**File**: `castro/constraints.py`

```python
"""Castro-aligned constraints for policy generation."""

from payment_simulator.ai_cash_mgmt import ParameterSpec, ScenarioConstraints

# Castro paper constraints:
# 1. Initial liquidity decision at t=0 ONLY
# 2. Payment actions: Release (x_t=1) or Hold (x_t=0) only
# 3. No LSM, no credit lines, no splitting

CASTRO_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="initial_liquidity_fraction",
            param_type="float",
            min_value=0.0,
            max_value=1.0,
            description="Fraction of collateral to post at t=0",
        ),
        ParameterSpec(
            name="urgency_threshold",
            param_type="int",
            min_value=0,
            max_value=20,
            description="Ticks before deadline to release payment",
        ),
        ParameterSpec(
            name="liquidity_buffer",
            param_type="float",
            min_value=0.5,
            max_value=3.0,
            description="Multiplier for required liquidity",
        ),
    ],
    allowed_fields=[
        # Time
        "system_tick_in_day",
        "ticks_remaining_in_day",
        # Liquidity
        "balance",
        "effective_liquidity",
        # Transaction
        "ticks_to_deadline",
        "remaining_amount",
        "amount",
        "priority",
        # Queue
        "queue1_total_value",
        "outgoing_queue_size",
        # Collateral
        "max_collateral_capacity",
        "posted_collateral",
    ],
    allowed_actions={
        "payment_tree": ["Release", "Hold"],
        "bank_tree": ["NoAction"],
        "collateral_tree": ["PostCollateral", "HoldCollateral"],
    },
)
```

---

## Phase 2: LLM Client Implementation

Implement `LLMClientProtocol` for Anthropic/OpenAI without legacy dependencies.

**File**: `castro/llm_client.py`

```python
"""LLM client for policy generation."""

from __future__ import annotations

import json
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from payment_simulator.ai_cash_mgmt import LLMConfig, LLMProviderType


class CastroLLMClient:
    """LLM client implementing ai_cash_mgmt's LLMClientProtocol."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        if config.provider == LLMProviderType.ANTHROPIC:
            self._client = AsyncAnthropic()
        elif config.provider == LLMProviderType.OPENAI:
            self._client = AsyncOpenAI()
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate improved policy via LLM."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(prompt, current_policy, context)

        if self._config.provider == LLMProviderType.ANTHROPIC:
            response = await self._call_anthropic(system_prompt, user_prompt)
        else:
            response = await self._call_openai(system_prompt, user_prompt)

        return self._parse_policy(response)

    def _build_system_prompt(self) -> str:
        return """You are an expert in payment system optimization.
Generate valid JSON policies for the SimCash payment simulator.

Policy structure:
{
  "version": "2.0",
  "parameters": { ... },
  "payment_tree": { decision tree for payment actions },
  "strategic_collateral_tree": { decision tree for collateral at t=0 }
}

Rules:
- payment_tree actions: "Release" or "Hold" only
- collateral_tree actions: "PostCollateral" at tick 0, "HoldCollateral" otherwise
- All numeric values must respect parameter bounds
- Output ONLY valid JSON, no markdown or explanation"""

    def _build_user_prompt(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        history = context.get("history", [])
        history_str = ""
        if history:
            for h in history[-5:]:
                history_str += f"  Iteration {h.get('iteration', '?')}: cost={h.get('cost', '?')}\n"

        return f"""{prompt}

Current policy:
{json.dumps(current_policy, indent=2)}

Performance history:
{history_str or '  (none)'}

Generate an improved policy that reduces total cost."""

    async def _call_anthropic(self, system: str, user: str) -> str:
        response = await self._client.messages.create(
            model=self._config.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    async def _call_openai(self, system: str, user: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content

    def _parse_policy(self, response: str) -> dict[str, Any]:
        # Strip markdown code blocks if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)
```

---

## Phase 3: Simulation Runner

Implement `SimulationRunnerProtocol` to run SimCash simulations for policy evaluation.

**File**: `castro/simulation.py`

```python
"""Simulation runner for policy evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from payment_simulator.orchestrator import Orchestrator


class CastroSimulationRunner:
    """Runs SimCash simulations for Monte Carlo evaluation."""

    def __init__(self, scenario_config: dict[str, Any]) -> None:
        self._base_config = scenario_config

    @classmethod
    def from_yaml(cls, path: Path) -> CastroSimulationRunner:
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
            policy: Policy to evaluate
            seed: RNG seed for determinism
            ticks: Number of ticks to run (default: full day)

        Returns:
            SimulationResult with costs and metrics
        """
        # Build config with policy and seed
        config = self._build_config(policy, seed)

        # Create and run orchestrator
        orch = Orchestrator.new(config)

        total_ticks = ticks or (
            config["simulation"]["ticks_per_day"] * config["simulation"]["num_days"]
        )

        for _ in range(total_ticks):
            orch.tick()

        # Extract metrics
        metrics = orch.get_metrics()
        return SimulationResult(
            total_cost=metrics["total_cost"],
            per_agent_costs=metrics["per_agent_costs"],
            settlement_rate=metrics["settlement_rate"],
            transactions_settled=metrics["transactions_settled"],
            transactions_failed=metrics["transactions_failed"],
        )

    def _build_config(self, policy: dict[str, Any], seed: int) -> dict[str, Any]:
        """Build simulation config with injected policy and seed."""
        config = self._base_config.copy()
        config["simulation"] = config.get("simulation", {}).copy()
        config["simulation"]["rng_seed"] = seed

        # Inject policy into agents
        for agent in config.get("agents", []):
            agent["policy"] = {"type": "FromDict", "policy": policy}

        return config


@dataclass
class SimulationResult:
    """Result of a single simulation run."""
    total_cost: int
    per_agent_costs: dict[str, int]
    settlement_rate: float
    transactions_settled: int
    transactions_failed: int
```

---

## Phase 4: Experiment Definitions

Define the three Castro experiments using `ai_cash_mgmt.GameConfig`.

**File**: `castro/experiments.py`

```python
"""Castro experiment definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from payment_simulator.ai_cash_mgmt import (
    AgentOptimizationConfig,
    ConvergenceCriteria,
    GameConfig,
    GameMode,
    LLMConfig,
    LLMProviderType,
    MonteCarloConfig,
    OutputConfig,
    ReasoningEffortType,
    SampleMethod,
)

from castro.constraints import CASTRO_CONSTRAINTS


@dataclass
class CastroExperiment:
    """Definition of a Castro experiment."""

    name: str
    description: str
    scenario_path: Path
    game_config: GameConfig


def create_exp1(
    output_dir: Path = Path("results"),
    model: str = "claude-sonnet-4-5-20250929",
) -> CastroExperiment:
    """Experiment 1: 2-Period Deterministic.

    Validates Nash equilibrium with deferred crediting.
    - 2 ticks per day, 1 day
    - Deterministic payment arrivals
    - Expected: Bank A posts 0, Bank B posts 20000
    """
    return CastroExperiment(
        name="exp1",
        description="2-Period Deterministic Nash Equilibrium",
        scenario_path=Path("configs/exp1_2period.yaml"),
        game_config=GameConfig(
            game_id="castro-exp1",
            scenario_config="configs/exp1_2period.yaml",
            master_seed=42,
            game_mode=GameMode.CAMPAIGN_LEARNING,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
            },
            default_llm_config=LLMConfig(
                provider=LLMProviderType.ANTHROPIC,
                model=model,
                temperature=0.0,
                max_retries=3,
            ),
            monte_carlo=MonteCarloConfig(
                num_samples=1,  # Deterministic - single seed
                sample_method=SampleMethod.BOOTSTRAP,
                evaluation_ticks=2,
            ),
            convergence=ConvergenceCriteria(
                stability_threshold=0.05,
                stability_window=5,
                max_iterations=25,
            ),
            output=OutputConfig(
                database_path=str(output_dir / "exp1.db"),
                verbose=True,
            ),
        ),
    )


def create_exp2(
    output_dir: Path = Path("results"),
    model: str = "claude-sonnet-4-5-20250929",
) -> CastroExperiment:
    """Experiment 2: 12-Period Stochastic.

    LVTS-style realistic scenario with stochastic arrivals.
    - 12 ticks per day
    - Poisson arrivals, LogNormal amounts
    - 10 seeds for Monte Carlo evaluation
    """
    return CastroExperiment(
        name="exp2",
        description="12-Period Stochastic LVTS-Style",
        scenario_path=Path("configs/exp2_12period.yaml"),
        game_config=GameConfig(
            game_id="castro-exp2",
            scenario_config="configs/exp2_12period.yaml",
            master_seed=42,
            game_mode=GameMode.CAMPAIGN_LEARNING,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
            },
            default_llm_config=LLMConfig(
                provider=LLMProviderType.ANTHROPIC,
                model=model,
                temperature=0.0,
                max_retries=3,
            ),
            monte_carlo=MonteCarloConfig(
                num_samples=10,
                sample_method=SampleMethod.BOOTSTRAP,
                evaluation_ticks=12,
            ),
            convergence=ConvergenceCriteria(
                stability_threshold=0.05,
                stability_window=5,
                max_iterations=25,
            ),
            output=OutputConfig(
                database_path=str(output_dir / "exp2.db"),
                verbose=True,
            ),
        ),
    )


def create_exp3(
    output_dir: Path = Path("results"),
    model: str = "claude-sonnet-4-5-20250929",
) -> CastroExperiment:
    """Experiment 3: Joint Liquidity & Timing.

    Optimizes both initial collateral AND payment timing jointly.
    - 3 ticks per day
    - Tests interaction between liquidity and timing decisions
    """
    return CastroExperiment(
        name="exp3",
        description="Joint Liquidity & Timing Optimization",
        scenario_path=Path("configs/exp3_joint.yaml"),
        game_config=GameConfig(
            game_id="castro-exp3",
            scenario_config="configs/exp3_joint.yaml",
            master_seed=42,
            game_mode=GameMode.CAMPAIGN_LEARNING,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
            },
            default_llm_config=LLMConfig(
                provider=LLMProviderType.ANTHROPIC,
                model=model,
                temperature=0.0,
                max_retries=3,
            ),
            monte_carlo=MonteCarloConfig(
                num_samples=10,
                sample_method=SampleMethod.BOOTSTRAP,
                evaluation_ticks=3,
            ),
            convergence=ConvergenceCriteria(
                stability_threshold=0.05,
                stability_window=5,
                max_iterations=25,
            ),
            output=OutputConfig(
                database_path=str(output_dir / "exp3.db"),
                verbose=True,
            ),
        ),
    )


EXPERIMENTS = {
    "exp1": create_exp1,
    "exp2": create_exp2,
    "exp3": create_exp3,
}
```

---

## Phase 5: Experiment Runner

Main runner that orchestrates the optimization loop.

**File**: `castro/runner.py`

```python
"""Experiment runner using ai_cash_mgmt."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from payment_simulator.ai_cash_mgmt import (
    ConstraintValidator,
    ConvergenceDetector,
    GameRepository,
    GameSession,
    GameSessionRecord,
    GameStatus,
    PolicyIterationRecord,
    PolicyOptimizer,
    SeedManager,
)
from payment_simulator.persistence.connection import DatabaseManager

from castro.constraints import CASTRO_CONSTRAINTS
from castro.experiments import CastroExperiment
from castro.llm_client import CastroLLMClient
from castro.simulation import CastroSimulationRunner

console = Console()


@dataclass
class ExperimentResult:
    """Result of running an experiment."""

    experiment_name: str
    final_cost: int
    best_cost: int
    num_iterations: int
    converged: bool
    convergence_reason: str
    per_agent_costs: dict[str, int]
    duration_seconds: float


class ExperimentRunner:
    """Runs Castro experiments using ai_cash_mgmt components."""

    def __init__(self, experiment: CastroExperiment) -> None:
        self._experiment = experiment
        self._config = experiment.game_config

        # Core components
        self._seed_manager = SeedManager(self._config.master_seed)
        self._convergence = ConvergenceDetector(self._config.convergence)
        self._validator = ConstraintValidator(CASTRO_CONSTRAINTS)
        self._optimizer = PolicyOptimizer(
            constraints=CASTRO_CONSTRAINTS,
            max_retries=self._config.default_llm_config.max_retries,
        )

        # LLM client
        self._llm_client = CastroLLMClient(self._config.default_llm_config)

        # Simulation runner
        self._sim_runner = CastroSimulationRunner.from_yaml(
            experiment.scenario_path
        )

        # State
        self._policies: dict[str, dict[str, Any]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._best_cost = float("inf")
        self._best_policies: dict[str, dict[str, Any]] = {}

    async def run(self) -> ExperimentResult:
        """Run the experiment to convergence."""
        start_time = datetime.now()

        # Initialize database
        db_path = Path(self._config.output.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with DatabaseManager(str(db_path)) as db:
            repo = GameRepository(db.conn)
            repo.initialize_schema()

            # Load seed policies
            self._load_seed_policies()

            # Save initial session
            session_record = self._create_session_record()
            repo.save_game_session(session_record)

            console.print(f"[bold]Starting {self._experiment.name}[/bold]")
            console.print(f"  Description: {self._experiment.description}")
            console.print(f"  Max iterations: {self._config.convergence.max_iterations}")

            # Optimization loop
            iteration = 0
            while iteration < self._config.convergence.max_iterations:
                iteration += 1
                console.print(f"\n[cyan]Iteration {iteration}[/cyan]")

                # 1. Evaluate current policies
                total_cost, per_agent_costs = await self._evaluate_policies(iteration)
                console.print(f"  Total cost: ${total_cost / 100:.2f}")

                # Track best
                if total_cost < self._best_cost:
                    self._best_cost = total_cost
                    self._best_policies = {k: v.copy() for k, v in self._policies.items()}
                    console.print(f"  [green]New best![/green]")

                # 2. Check convergence
                self._convergence.record_metric(total_cost)
                if self._convergence.is_converged:
                    console.print(f"[green]Converged: {self._convergence.convergence_reason}[/green]")
                    break

                # 3. Optimize each agent
                for agent_id in self._config.optimized_agents:
                    console.print(f"  Optimizing {agent_id}...")

                    result = await self._optimizer.optimize(
                        agent_id=agent_id,
                        current_policy=self._policies[agent_id],
                        performance_history=self._history.get(agent_id, []),
                        llm_client=self._llm_client,
                        llm_model=self._config.default_llm_config.model,
                        current_cost=per_agent_costs.get(agent_id, 0),
                    )

                    # Save iteration record
                    self._save_iteration(repo, result, iteration)

                    if result.was_accepted and result.new_policy:
                        self._policies[agent_id] = result.new_policy
                        console.print(f"    Policy updated")
                    else:
                        console.print(f"    [yellow]Policy rejected: {result.validation_errors}[/yellow]")

                    # Update history
                    if agent_id not in self._history:
                        self._history[agent_id] = []
                    self._history[agent_id].append({
                        "iteration": iteration,
                        "cost": per_agent_costs.get(agent_id, 0),
                    })

            # Finalize
            duration = (datetime.now() - start_time).total_seconds()
            session_record.completed_at = datetime.now()
            session_record.status = GameStatus.CONVERGED if self._convergence.is_converged else GameStatus.COMPLETED
            session_record.total_iterations = iteration
            session_record.converged = self._convergence.is_converged
            session_record.final_cost = self._best_cost
            repo.save_game_session(session_record)

            return ExperimentResult(
                experiment_name=self._experiment.name,
                final_cost=int(self._best_cost),
                best_cost=int(self._best_cost),
                num_iterations=iteration,
                converged=self._convergence.is_converged,
                convergence_reason=self._convergence.convergence_reason or "max_iterations",
                per_agent_costs={k: int(v) for k, v in per_agent_costs.items()},
                duration_seconds=duration,
            )

    def _load_seed_policies(self) -> None:
        """Load initial seed policies for all agents."""
        # Default seed policy - release urgent, hold otherwise
        seed_policy = {
            "version": "2.0",
            "parameters": {
                "initial_liquidity_fraction": 0.25,
                "urgency_threshold": 3,
                "liquidity_buffer": 1.0,
            },
            "payment_tree": {
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "urgency_threshold"},
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
            "strategic_collateral_tree": {
                "type": "condition",
                "condition": {
                    "op": "==",
                    "left": {"field": "system_tick_in_day"},
                    "right": {"value": 0},
                },
                "on_true": {
                    "type": "action",
                    "action": "PostCollateral",
                    "params": {"fraction": {"param": "initial_liquidity_fraction"}},
                },
                "on_false": {"type": "action", "action": "HoldCollateral"},
            },
        }

        for agent_id in self._config.optimized_agents:
            self._policies[agent_id] = seed_policy.copy()

    async def _evaluate_policies(
        self, iteration: int
    ) -> tuple[int, dict[str, int]]:
        """Evaluate current policies across Monte Carlo samples."""
        num_samples = self._config.monte_carlo.num_samples
        total_costs = []
        per_agent_totals: dict[str, list[int]] = {
            agent_id: [] for agent_id in self._config.optimized_agents
        }

        for sample_idx in range(num_samples):
            seed = self._seed_manager.simulation_seed(iteration * 1000 + sample_idx)

            # Run simulation with current policies (use first agent's policy for now)
            # In full implementation, would inject per-agent policies
            policy = list(self._policies.values())[0]
            result = self._sim_runner.run_simulation(
                policy=policy,
                seed=seed,
                ticks=self._config.monte_carlo.evaluation_ticks,
            )

            total_costs.append(result.total_cost)
            for agent_id, cost in result.per_agent_costs.items():
                if agent_id in per_agent_totals:
                    per_agent_totals[agent_id].append(cost)

        # Compute means
        mean_total = int(sum(total_costs) / len(total_costs))
        mean_per_agent = {
            agent_id: int(sum(costs) / len(costs)) if costs else 0
            for agent_id, costs in per_agent_totals.items()
        }

        return mean_total, mean_per_agent

    def _create_session_record(self) -> GameSessionRecord:
        """Create initial session record."""
        return GameSessionRecord(
            game_id=self._config.game_id,
            scenario_config=self._config.scenario_config,
            master_seed=self._config.master_seed,
            game_mode=self._config.game_mode.value,
            config_json="{}",  # TODO: serialize full config
            started_at=datetime.now(),
            status=GameStatus.RUNNING,
            optimized_agents=list(self._config.optimized_agents.keys()),
        )

    def _save_iteration(
        self,
        repo: GameRepository,
        result: Any,  # OptimizationResult
        iteration: int,
    ) -> None:
        """Save iteration record to database."""
        import json

        record = PolicyIterationRecord(
            game_id=self._config.game_id,
            agent_id=result.agent_id,
            iteration_number=iteration,
            old_policy_json=json.dumps(result.old_policy),
            new_policy_json=json.dumps(result.new_policy) if result.new_policy else "",
            old_cost=result.old_cost,
            new_cost=result.new_cost,
            was_accepted=result.was_accepted,
            validation_errors=result.validation_errors,
            llm_model=result.llm_model,
            llm_latency_seconds=result.llm_latency_seconds,
            tokens_used=result.tokens_used,
            created_at=datetime.now(),
        )
        repo.save_policy_iteration(record)
```

---

## Phase 6: CLI

Simple Typer CLI for running experiments.

**File**: `cli.py`

```python
"""CLI for Castro experiments."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from castro.experiments import EXPERIMENTS, CastroExperiment
from castro.runner import ExperimentRunner

app = typer.Typer(
    name="castro",
    help="Castro experiments using ai_cash_mgmt",
)
console = Console()


@app.command()
def run(
    experiment: Annotated[str, typer.Argument(help="Experiment: exp1, exp2, exp3")],
    model: Annotated[str, typer.Option(help="LLM model")] = "claude-sonnet-4-5-20250929",
    max_iter: Annotated[int, typer.Option(help="Max iterations")] = 25,
    output: Annotated[Path | None, typer.Option(help="Output directory")] = None,
) -> None:
    """Run a Castro experiment."""
    if experiment not in EXPERIMENTS:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        console.print(f"Available: {', '.join(EXPERIMENTS.keys())}")
        raise typer.Exit(1)

    output_dir = output or Path("results")
    exp = EXPERIMENTS[experiment](output_dir=output_dir, model=model)

    if max_iter != 25:
        exp.game_config.convergence.max_iterations = max_iter

    runner = ExperimentRunner(exp)
    result = asyncio.run(runner.run())

    # Print results
    console.print()
    table = Table(title=f"Results: {exp.name}")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Final Cost", f"${result.final_cost / 100:.2f}")
    table.add_row("Best Cost", f"${result.best_cost / 100:.2f}")
    table.add_row("Iterations", str(result.num_iterations))
    table.add_row("Converged", str(result.converged))
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    console.print(table)


@app.command("list")
def list_experiments() -> None:
    """List available experiments."""
    table = Table(title="Castro Experiments")
    table.add_column("Key")
    table.add_column("Name")
    table.add_column("Description")

    for key, factory in EXPERIMENTS.items():
        exp = factory()
        table.add_row(key, exp.name, exp.description)

    console.print(table)


@app.command()
def info(
    experiment: Annotated[str, typer.Argument(help="Experiment key")],
) -> None:
    """Show experiment details."""
    if experiment not in EXPERIMENTS:
        console.print(f"[red]Unknown experiment: {experiment}[/red]")
        raise typer.Exit(1)

    exp = EXPERIMENTS[experiment]()
    config = exp.game_config

    console.print(f"[bold]{exp.name}[/bold]")
    console.print(f"Description: {exp.description}")
    console.print()
    console.print("Configuration:")
    console.print(f"  Game ID: {config.game_id}")
    console.print(f"  Master Seed: {config.master_seed}")
    console.print(f"  Monte Carlo Samples: {config.monte_carlo.num_samples}")
    console.print(f"  Max Iterations: {config.convergence.max_iterations}")
    console.print(f"  Convergence Threshold: {config.convergence.stability_threshold}")
    console.print(f"  LLM Model: {config.default_llm_config.model}")


if __name__ == "__main__":
    app()
```

---

## Phase 7: Scenario Configs

YAML configurations for each experiment (simplified from legacy).

**File**: `configs/exp1_2period.yaml`

```yaml
# Experiment 1: 2-Period Deterministic
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 42

deferred_crediting: true
deadline_cap_at_eod: true

cost_rates:
  collateral_cost_per_tick_bps: 500
  delay_cost_per_tick_per_cent: 0.001
  overdraft_bps_per_tick: 2000
  eod_penalty_per_transaction: 0
  deadline_penalty: 0
  split_friction_cost: 0

lsm_config:
  enable_bilateral: false
  enable_cycles: false

agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 50000
    max_collateral_capacity: 10000000

  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 50000
    max_collateral_capacity: 10000000

scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 15000
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 1

  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 15000
    priority: 5
    deadline: 1
    schedule:
      type: OneTime
      tick: 0

  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 5000
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 1
```

---

## Implementation Checklist

### Phase 1: Setup
- [ ] Create `experiments/new-castro/` directory
- [ ] Create `pyproject.toml` with dependencies
- [ ] Create `castro/__init__.py`

### Phase 2: Constraints
- [ ] Implement `castro/constraints.py` with CASTRO_CONSTRAINTS
- [ ] Test constraint validation

### Phase 3: LLM Client
- [ ] Implement `castro/llm_client.py`
- [ ] Support Anthropic and OpenAI
- [ ] Test policy generation

### Phase 4: Simulation Runner
- [ ] Implement `castro/simulation.py`
- [ ] Integrate with Orchestrator
- [ ] Test determinism

### Phase 5: Experiments
- [ ] Implement `castro/experiments.py`
- [ ] Define exp1, exp2, exp3
- [ ] Create scenario YAML files

### Phase 6: Runner
- [ ] Implement `castro/runner.py`
- [ ] Integration with all ai_cash_mgmt components
- [ ] Test full optimization loop

### Phase 7: CLI
- [ ] Implement `cli.py`
- [ ] Commands: run, list, info
- [ ] Test CLI execution

### Phase 8: Testing
- [ ] Unit tests for each component
- [ ] Integration test for exp1
- [ ] Determinism verification

---

## Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| 1-2 | 0.5 day | Setup + Constraints |
| 3-4 | 1 day | LLM Client + Simulation |
| 5-6 | 1 day | Experiments + Runner |
| 7-8 | 0.5 day | CLI + Testing |

**Total**: ~3 days

---

## Dependencies

```toml
[project]
name = "new-castro"
dependencies = [
    "payment-simulator",  # Includes ai_cash_mgmt
    "anthropic>=0.18",
    "openai>=1.0",
    "typer>=0.9",
    "rich>=13.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

---

## Success Criteria

1. All three experiments (exp1, exp2, exp3) run successfully
2. Deterministic: same seed produces identical results
3. No legacy Castro code dependencies
4. Clean, readable code following project conventions
5. Full test coverage on new code
