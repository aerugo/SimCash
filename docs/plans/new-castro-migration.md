# Migration Plan: Castro Experiments → ai_cash_mgmt Module

**Status**: Planning
**Created**: 2025-12-09
**Goal**: Recreate Castro experiments in `experiments/new-castro/` using the new `ai_cash_mgmt` module exclusively, eliminating legacy code duplication.

---

## Executive Summary

The legacy `experiments/castro/` directory contains ~76 Python files (2.6 MB) implementing LLM-based policy optimization. The new `api/payment_simulator/ai_cash_mgmt/` module (~1700 lines) provides a cleaner, well-tested implementation of the same functionality.

This plan migrates the three Castro experiments (exp1, exp2, exp3) to use `ai_cash_mgmt`, reducing code duplication by ~80% while maintaining full feature parity.

---

## Gap Analysis

### 1. ScenarioConstraints Schema Mismatch

| Feature | Legacy Castro | ai_cash_mgmt |
|---------|--------------|--------------|
| Payment actions | `allowed_actions: list[str]` | `allowed_actions: dict[str, list[str]]` |
| Bank actions | `allowed_bank_actions: list[str]` | Nested in dict |
| Collateral actions | `allowed_collateral_actions: list[str]` | Nested in dict |

**Migration Path**: Create adapter function to convert Castro's flat format to ai_cash_mgmt's dict format:

```python
def convert_castro_constraints(castro: CastroConstraints) -> ScenarioConstraints:
    return ScenarioConstraints(
        allowed_parameters=castro.allowed_parameters,
        allowed_fields=castro.allowed_fields,
        allowed_actions={
            "payment_tree": castro.allowed_actions,
            "bank_tree": castro.allowed_bank_actions or [],
            "collateral_tree": castro.allowed_collateral_actions or [],
        },
    )
```

### 2. LLM Integration Architecture

| Feature | Legacy Castro | ai_cash_mgmt |
|---------|--------------|--------------|
| LLM Interface | `RobustPolicyAgent` (PydanticAI structured output) | `LLMClientProtocol` |
| Schema Generation | Dynamic Pydantic models at runtime | N/A (validation-only) |
| Structured Output | Enforced via PydanticAI | Not enforced |
| Retries | Built into agent | Built into `PolicyOptimizer` |

**Migration Path**: Create `PydanticAILLMClient` adapter that implements `LLMClientProtocol` and wraps `RobustPolicyAgent`:

```python
class PydanticAILLMClient:
    """Adapter bridging RobustPolicyAgent to LLMClientProtocol."""

    def __init__(self, agent: RobustPolicyAgent) -> None:
        self._agent = agent

    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        # Extract data from context
        history = context.get("history", [])
        current_cost = history[-1].get("cost") if history else None
        settlement_rate = history[-1].get("settlement_rate") if history else None

        return await self._agent.generate_policy_async(
            instruction=prompt,
            current_policy=current_policy,
            current_cost=current_cost,
            settlement_rate=settlement_rate,
            iteration=len(history),
        )
```

### 3. Experiment Definitions vs GameConfig

| Feature | Legacy Castro | ai_cash_mgmt |
|---------|--------------|--------------|
| Definition | `ExperimentDefinition` TypedDict | `GameConfig` Pydantic model |
| Multi-seed | `num_seeds` field | Via Monte Carlo config |
| Policy paths | Explicit file paths | Via scenario config |
| Castro mode | `castro_mode: bool` flag | Via constraints |

**Migration Path**: Create `ExperimentConfig` that wraps `GameConfig` with Castro-specific extensions:

```python
@dataclass
class CastroExperiment:
    """Castro experiment definition using ai_cash_mgmt."""

    name: str
    description: str
    game_config: GameConfig
    scenario_constraints: ScenarioConstraints
    num_seeds: int = 1
    castro_mode: bool = True
```

### 4. Database Schema

| Feature | Legacy Castro | ai_cash_mgmt |
|---------|--------------|--------------|
| Repository | `ExperimentRepository` | `GameRepository` |
| Tables | 6 specialized tables | 2 tables (sessions, iterations) |
| LLM logging | `llm_interactions` table | In `PolicyIterationRecord` |
| Validation errors | `validation_errors` table | In `PolicyIterationRecord.validation_errors` |

**Migration Path**: ai_cash_mgmt's schema is simpler but sufficient. Extend with:
- View or query for LLM interaction history
- Add `seed` field to track per-seed results

### 5. Simulation Execution

| Feature | Legacy Castro | ai_cash_mgmt |
|---------|--------------|--------------|
| Executor | `ParallelSimulationExecutor` | `PolicyEvaluator` |
| Multi-seed | 8 parallel workers | `parallel_workers` config |
| Metrics | `compute_metrics()` function | `EvaluationResult` |

**Migration Path**: Implement `SimulationRunnerProtocol` using existing SimCash CLI:

```python
class SimCashRunner:
    """Runs SimCash simulations for policy evaluation."""

    async def run_ephemeral(
        self,
        scenario_config: dict[str, Any],
        policy: dict[str, Any],
        seed: int,
        ticks: int,
    ) -> dict[str, Any]:
        # Use Orchestrator directly or subprocess
        orch = Orchestrator.new({**scenario_config, "rng_seed": seed})
        # ... run simulation, return metrics
```

---

## Directory Structure

```
experiments/new-castro/
├── README.md                           # Overview and usage
├── CLAUDE.md                           # AI assistant guidelines
├── pyproject.toml                      # Dependencies (minimal - uses ai_cash_mgmt)
├── uv.lock
│
├── castro/                             # Core experiment code
│   ├── __init__.py
│   ├── adapters/                       # Bridge layer to ai_cash_mgmt
│   │   ├── __init__.py
│   │   ├── constraints.py              # Castro → ai_cash_mgmt constraint converter
│   │   ├── llm_client.py               # PydanticAI → LLMClientProtocol adapter
│   │   └── simulation_runner.py        # SimCash runner for PolicyEvaluator
│   │
│   ├── experiments/                    # Experiment definitions
│   │   ├── __init__.py
│   │   ├── definitions.py              # exp1, exp2, exp3 as CastroExperiment
│   │   └── constraints.py              # CASTRO_CONSTRAINTS, etc. (import from legacy)
│   │
│   └── runner.py                       # Main experiment runner using ai_cash_mgmt
│
├── configs/                            # Scenario YAML files (symlink or copy)
│   ├── castro_2period_aligned.yaml
│   ├── castro_12period_aligned.yaml
│   └── castro_joint_aligned.yaml
│
├── policies/                           # Seed policies (symlink or copy)
│   └── seed_policy.json
│
├── cli.py                              # Typer CLI entry point
│
├── results/                            # Output directory
│   └── .gitkeep
│
└── tests/                              # Migration validation tests
    ├── __init__.py
    ├── conftest.py
    ├── test_adapters.py                # Adapter unit tests
    ├── test_experiment_parity.py       # Verify new matches legacy output
    └── test_determinism.py             # Reproducibility tests
```

---

## Implementation Phases

### Phase 1: Adapter Layer (Day 1)

**Goal**: Create bridge between legacy Castro components and ai_cash_mgmt APIs.

**Files**:
1. `castro/adapters/constraints.py`:
   ```python
   def convert_castro_constraints(castro: CastroScenarioConstraints) -> ScenarioConstraints:
       """Convert legacy Castro constraints to ai_cash_mgmt format."""
       ...
   ```

2. `castro/adapters/llm_client.py`:
   ```python
   class PydanticAILLMClient(LLMClientProtocol):
       """Wraps RobustPolicyAgent as LLMClientProtocol."""

       def __init__(
           self,
           constraints: ScenarioConstraints,
           model: str = "gpt-4o",
           reasoning_effort: str = "high",
           thinking_budget: int | None = None,
       ) -> None: ...

       async def generate_policy(
           self,
           prompt: str,
           current_policy: dict[str, Any],
           context: dict[str, Any],
       ) -> dict[str, Any]: ...
   ```

3. `castro/adapters/simulation_runner.py`:
   ```python
   class SimCashRunner:
       """Runs SimCash simulations for policy evaluation."""

       def __init__(self, scenario_path: str) -> None: ...

       async def run_ephemeral(
           self,
           policy: dict[str, Any],
           seed: int,
           ticks: int,
       ) -> dict[str, Any]: ...
   ```

**Tests**:
- `test_constraints_conversion()`
- `test_llm_client_protocol_compliance()`
- `test_simulation_runner_determinism()`

### Phase 2: Experiment Definitions (Day 2)

**Goal**: Define exp1, exp2, exp3 using ai_cash_mgmt's GameConfig.

**Files**:
1. `castro/experiments/definitions.py`:
   ```python
   @dataclass
   class CastroExperiment:
       """Castro experiment definition."""
       name: str
       description: str
       scenario_config_path: str
       seed_policy_path: str
       game_config: GameConfig
       constraints: ScenarioConstraints
       num_evaluation_seeds: int
       castro_mode: bool = True

   EXPERIMENTS: dict[str, CastroExperiment] = {
       "exp1": CastroExperiment(
           name="Two-Period Deterministic",
           description="2-period Nash equilibrium validation",
           scenario_config_path="configs/castro_2period_aligned.yaml",
           seed_policy_path="policies/seed_policy.json",
           game_config=GameConfig(
               game_id="exp1",
               scenario_config="configs/castro_2period_aligned.yaml",
               master_seed=42,
               game_mode=GameMode.CAMPAIGN_LEARNING,
               optimized_agents={
                   "BANK_A": AgentOptimizationConfig(),
                   "BANK_B": AgentOptimizationConfig(),
               },
               default_llm_config=LLMConfig(
                   provider=LLMProviderType.OPENAI,
                   model="gpt-4o",
                   reasoning_effort=ReasoningEffortType.HIGH,
               ),
               monte_carlo=MonteCarloConfig(
                   num_samples=1,  # Deterministic
                   sample_method=SampleMethod.BOOTSTRAP,
               ),
               convergence=ConvergenceCriteria(
                   stability_threshold=0.05,
                   stability_window=5,
                   max_iterations=25,
               ),
           ),
           constraints=CASTRO_CONSTRAINTS,
           num_evaluation_seeds=1,
       ),
       # exp2, exp3 similarly...
   }
   ```

2. `castro/experiments/constraints.py`:
   ```python
   # Import from legacy or redefine
   from experiments.castro.parameter_sets import (
       CASTRO_CONSTRAINTS as LEGACY_CASTRO_CONSTRAINTS,
       MINIMAL_CONSTRAINTS as LEGACY_MINIMAL_CONSTRAINTS,
   )
   from castro.adapters.constraints import convert_castro_constraints

   CASTRO_CONSTRAINTS = convert_castro_constraints(LEGACY_CASTRO_CONSTRAINTS)
   MINIMAL_CONSTRAINTS = convert_castro_constraints(LEGACY_MINIMAL_CONSTRAINTS)
   ```

**Tests**:
- `test_experiment_configs_valid()`
- `test_constraints_match_legacy()`

### Phase 3: Experiment Runner (Day 3)

**Goal**: Implement main runner using ai_cash_mgmt components.

**Files**:
1. `castro/runner.py`:
   ```python
   class CastroExperimentRunner:
       """Runs Castro experiments using ai_cash_mgmt."""

       def __init__(
           self,
           experiment: CastroExperiment,
           output_dir: Path,
       ) -> None:
           self._experiment = experiment
           self._output_dir = output_dir

           # Initialize ai_cash_mgmt components
           self._orchestrator = GameOrchestrator(experiment.game_config)
           self._session = self._orchestrator.create_session()
           self._optimizer = PolicyOptimizer(
               constraints=experiment.constraints,
               max_retries=3,
           )
           self._evaluator = PolicyEvaluator(
               num_samples=experiment.num_evaluation_seeds,
               evaluation_ticks=experiment.game_config.monte_carlo.evaluation_ticks,
           )
           self._llm_client = PydanticAILLMClient(
               constraints=experiment.constraints,
               model=experiment.game_config.default_llm_config.model,
           )
           self._repo = GameRepository(self._init_database())

       async def run(self) -> ExperimentResult:
           """Run the experiment to convergence."""
           self._repo.save_game_session(self._create_session_record())

           for iteration in range(self._experiment.game_config.convergence.max_iterations):
               # 1. Run simulations across seeds
               results = await self._run_simulations(iteration)

               # 2. Compute aggregate metrics
               metrics = self._compute_metrics(results)

               # 3. Check convergence
               self._orchestrator.record_iteration_metric(metrics.total_cost)
               if self._orchestrator.check_convergence()["is_converged"]:
                   break

               # 4. Optimize policies via LLM
               for agent_id in self._experiment.game_config.optimized_agents:
                   opt_result = await self._optimizer.optimize(
                       agent_id=agent_id,
                       current_policy=self._session.get_policy(agent_id),
                       performance_history=self._session.get_agent_history(agent_id),
                       llm_client=self._llm_client,
                       llm_model=self._experiment.game_config.default_llm_config.model,
                       current_cost=metrics.per_agent_costs.get(agent_id, 0),
                   )
                   self._save_iteration(opt_result)

                   if opt_result.was_accepted:
                       self._session.set_policy(agent_id, opt_result.new_policy)

           return self._finalize()
   ```

**Tests**:
- `test_runner_completes_exp1()`
- `test_runner_saves_to_database()`
- `test_runner_respects_convergence()`

### Phase 4: CLI Implementation (Day 4)

**Goal**: Create command-line interface matching legacy Castro CLI.

**Files**:
1. `cli.py`:
   ```python
   import typer
   from castro.experiments.definitions import EXPERIMENTS, get_experiment
   from castro.runner import CastroExperimentRunner

   app = typer.Typer(help="Castro experiments using ai_cash_mgmt")

   @app.command()
   def run(
       experiment: str = typer.Argument(..., help="Experiment key (exp1, exp2, exp3)"),
       model: str = typer.Option("gpt-4o", help="LLM model to use"),
       max_iter: int = typer.Option(25, help="Maximum iterations"),
       output: Path = typer.Option(None, help="Output directory"),
   ) -> None:
       """Run a Castro experiment."""
       exp = get_experiment(experiment)
       # Override config as needed
       if max_iter != 25:
           exp.game_config.convergence.max_iterations = max_iter

       runner = CastroExperimentRunner(exp, output or Path("results"))
       result = asyncio.run(runner.run())

       # Print summary
       console.print(f"[green]Experiment completed![/green]")
       console.print(f"Final cost: ${result.final_cost / 100:.2f}")

   @app.command()
   def list_experiments() -> None:
       """List available experiments."""
       for key, exp in EXPERIMENTS.items():
           typer.echo(f"{key}: {exp.name}")
           typer.echo(f"  {exp.description}")

   @app.command()
   def replay(database: Path) -> None:
       """Replay an experiment from database."""
       # Use ai_cash_mgmt GameRepository
       ...
   ```

**Tests**:
- `test_cli_run_exp1()`
- `test_cli_list_experiments()`
- `test_cli_replay()`

### Phase 5: Parity Testing (Day 5)

**Goal**: Verify new implementation matches legacy output.

**Files**:
1. `tests/test_experiment_parity.py`:
   ```python
   @pytest.mark.slow
   def test_exp1_parity():
       """Verify new-castro exp1 matches legacy castro exp1."""
       # Run legacy
       legacy_result = run_legacy_experiment("exp1", seed=42, max_iter=5)

       # Run new
       new_result = run_new_experiment("exp1", seed=42, max_iter=5)

       # Compare
       assert new_result.final_cost == pytest.approx(legacy_result.final_cost, rel=0.01)
       assert new_result.settlement_rate == legacy_result.settlement_rate
       assert new_result.num_iterations == legacy_result.num_iterations

   @pytest.mark.slow
   def test_determinism_across_runs():
       """Verify same seed produces identical results."""
       result1 = run_new_experiment("exp1", seed=42, max_iter=3)
       result2 = run_new_experiment("exp1", seed=42, max_iter=3)

       assert result1.costs_per_iteration == result2.costs_per_iteration
       assert result1.policies_per_iteration == result2.policies_per_iteration
   ```

**Tests**:
- `test_exp1_parity()`
- `test_exp2_parity()`
- `test_exp3_parity()`
- `test_determinism_across_runs()`

### Phase 6: Documentation & Cleanup (Day 6)

**Goal**: Complete documentation and mark legacy as deprecated.

**Files**:
1. `README.md`:
   - Overview of new-castro
   - Migration guide from legacy castro
   - Usage examples
   - API reference

2. `CLAUDE.md`:
   - AI guidelines for new-castro
   - Invariants and constraints
   - Development workflow

3. Update `experiments/castro/README.md`:
   - Add deprecation notice
   - Point to new-castro

---

## Migration Checklist

### Phase 1: Adapter Layer
- [ ] Create `experiments/new-castro/` directory
- [ ] Implement `constraints.py` adapter
- [ ] Implement `llm_client.py` adapter
- [ ] Implement `simulation_runner.py` adapter
- [ ] Write adapter unit tests
- [ ] Verify adapters pass mypy

### Phase 2: Experiment Definitions
- [ ] Define `CastroExperiment` dataclass
- [ ] Create exp1, exp2, exp3 definitions
- [ ] Convert constraint sets
- [ ] Symlink/copy config files
- [ ] Write definition tests

### Phase 3: Experiment Runner
- [ ] Implement `CastroExperimentRunner`
- [ ] Integrate with `GameOrchestrator`
- [ ] Integrate with `PolicyOptimizer`
- [ ] Integrate with `PolicyEvaluator`
- [ ] Integrate with `GameRepository`
- [ ] Write runner tests

### Phase 4: CLI Implementation
- [ ] Create `cli.py` with Typer
- [ ] Implement `run` command
- [ ] Implement `list` command
- [ ] Implement `replay` command
- [ ] Write CLI tests

### Phase 5: Parity Testing
- [ ] Create parity test framework
- [ ] Test exp1 parity
- [ ] Test exp2 parity
- [ ] Test exp3 parity
- [ ] Test determinism

### Phase 6: Documentation
- [ ] Write README.md
- [ ] Write CLAUDE.md
- [ ] Add deprecation notice to legacy
- [ ] Update top-level CLAUDE.md

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| PydanticAI structured output differs from legacy | High | Thorough parity testing, gradual rollout |
| Performance regression in multi-seed runs | Medium | Benchmark before/after, optimize hot paths |
| Database schema incompatibility | Low | Use ai_cash_mgmt schema, migrate views if needed |
| Missing features in ai_cash_mgmt | Medium | Identify gaps in Phase 1, extend module if needed |

---

## Success Criteria

1. **Functional Parity**: All three experiments (exp1, exp2, exp3) produce statistically equivalent results
2. **Code Reduction**: ~80% reduction in Castro-specific code (from 76 files to ~15)
3. **Test Coverage**: >90% coverage on new code
4. **Determinism**: Same seed produces identical output across runs
5. **Performance**: No more than 10% slower than legacy implementation

---

## Dependencies

### Required from ai_cash_mgmt
- `GameConfig`, `GameOrchestrator`, `GameSession` - core orchestration
- `PolicyOptimizer`, `PolicyEvaluator` - optimization loop
- `ConstraintValidator`, `ScenarioConstraints` - validation
- `SeedManager`, `TransactionSampler` - deterministic sampling
- `GameRepository` - persistence

### Required from legacy Castro
- `RobustPolicyAgent` - PydanticAI structured output (wrapped)
- `ScenarioConstraints` (legacy format) - for conversion
- Config YAML files - copied/symlinked
- Seed policy JSON - copied/symlinked

### Optional (Can Be Reimplemented)
- Dynamic schema generation - complex, wrap instead
- Visualization/charts - defer to post-migration
- Parallel execution - use ai_cash_mgmt's `parallel_workers`

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Adapters | 1 day | None |
| Phase 2: Definitions | 1 day | Phase 1 |
| Phase 3: Runner | 1 day | Phase 2 |
| Phase 4: CLI | 0.5 day | Phase 3 |
| Phase 5: Parity | 1.5 days | Phase 4 |
| Phase 6: Docs | 0.5 day | Phase 5 |

**Total**: ~6 days of focused development

---

## Open Questions

1. **Should we vendor RobustPolicyAgent or import from legacy?**
   - Recommendation: Import from legacy initially, vendor later if castro/ is archived

2. **Should database schema be extended for multi-seed tracking?**
   - Recommendation: Add `seed` column to iteration records, defer views

3. **How to handle visualization/charting?**
   - Recommendation: Defer to separate tool, not critical for migration

4. **Should we support both legacy and new CLI during transition?**
   - Recommendation: Yes, add `--use-legacy` flag for comparison
