# Castro Architecture Refactor Plan

## Executive Summary

The Castro experiment implementation has diverged from its intended architecture, resulting in:
1. **Critical bug**: Bootstrap evaluation doesn't use paired comparison (comparing OLD vs NEW policy on same samples)
2. **Duplicate infrastructure**: LLM clients, model configs, persistence layers exist in both Castro and ai_cash_mgmt
3. **Tight coupling**: ExperimentRunner directly depends on Castro-specific components
4. **Underutilized abstractions**: GameOrchestrator exists but isn't used; StateProvider pattern incomplete

This plan proposes a phased refactoring to:
- Fix the bootstrap evaluation bug
- Move reusable infrastructure to `ai_cash_mgmt` core
- Separate experiment configuration from code (YAML-driven)
- Create proper abstractions for experiment runners

---

## Problem Analysis

### Issue 1: Bootstrap Evaluation Not Using Paired Comparison (Critical Bug)

**Current behavior** (from `runner.py`):
```
1. _evaluate_policies() generates M bootstrap samples, evaluates OLD policy
2. LLM proposes NEW policy
3. _evaluate_policies() is called AGAIN - regenerates samples!
4. Compare mean costs (not paired deltas)
```

**Expected behavior** (from development plan):
```
1. Generate M bootstrap samples ONCE
2. For each sample:
   - Evaluate OLD policy → cost_old
   - Evaluate NEW policy → cost_new
   - delta = cost_new - cost_old
3. Accept if mean(deltas) < 0
```

**Impact**: The `compute_paired_deltas()` method EXISTS in `BootstrapPolicyEvaluator` but is NEVER called!

### Issue 2: Duplicate LLM Client Infrastructure

| Component | Castro Location | AI Cash Mgmt Location |
|-----------|-----------------|----------------------|
| LLM Client | `pydantic_llm_client.py` | Protocol in `policy_optimizer.py` |
| Model Config | `model_config.py` | `config/llm_config.py` |
| Audit Wrapper | `AuditCaptureLLMClient` | (none) |

**Impact**: Two separate implementations that should be unified.

### Issue 3: Double Database Problem

```python
# runner.py lines 246-263
with DatabaseManager(str(db_path)) as db:
    repo = GameRepository(db.conn)           # Database 1
    # ...
    castro_conn = duckdb.connect(castro_db)  # Database 2!
    exp_repo = ExperimentEventRepository(castro_conn)
```

**Impact**:
- Can't have atomic transactions across both
- Double connection management
- Data integrity risks

### Issue 4: GameOrchestrator Underutilized

The `GameOrchestrator` class in `ai_cash_mgmt/core/game_orchestrator.py` provides:
- `create_session()` - session management
- `should_optimize_at_tick()` - scheduling
- `run_optimization_step()` - optimization loop
- `check_convergence()` - convergence detection

But `ExperimentRunner` reimplements all of this instead of using `GameOrchestrator`.

### Issue 5: Experiment Config in Code

Experiments are defined as Python dataclasses with factory functions:
```python
def create_exp2(...) -> CastroExperiment:
    return CastroExperiment(
        name="exp2",
        num_samples=10,
        evaluation_ticks=12,
        ...
    )
```

Should be YAML-driven:
```yaml
# experiments/exp2.yaml
name: exp2
scenario: configs/exp2_12period.yaml
evaluation:
  mode: bootstrap
  num_samples: 10
convergence:
  max_iterations: 25
  stability_threshold: 0.05
```

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  experiments/castro/                                            │
│  (Experiment-specific code ONLY)                                │
│                                                                 │
│  ├── configs/              # Scenario YAML files               │
│  │   ├── exp1_2period.yaml                                     │
│  │   └── exp2_12period.yaml                                    │
│  ├── experiments/          # Experiment definition YAML        │
│  │   ├── exp1.yaml                                             │
│  │   └── exp2.yaml                                             │
│  ├── constraints.py        # Castro-specific constraints       │
│  └── cli.py                # CLI entry point                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ Uses
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  api/payment_simulator/ai_cash_mgmt/                            │
│  (Reusable infrastructure)                                      │
│                                                                 │
│  ├── config/                                                    │
│  │   ├── experiment_config.py   # ExperimentConfig (YAML→obj)  │
│  │   ├── llm_config.py          # Unified LLMConfig            │
│  │   └── evaluation_config.py   # Bootstrap/MC settings        │
│  │                                                              │
│  ├── llm/                       # NEW: LLM client layer        │
│  │   ├── protocol.py            # LLMClientProtocol            │
│  │   ├── pydantic_client.py     # PydanticAI implementation    │
│  │   ├── audit_wrapper.py       # Audit capture wrapper        │
│  │   └── providers/             # Provider-specific settings   │
│  │       ├── anthropic.py                                       │
│  │       ├── openai.py                                          │
│  │       └── google.py                                          │
│  │                                                              │
│  ├── evaluation/                # NEW: Policy evaluation       │
│  │   ├── protocol.py            # PolicyEvaluatorProtocol      │
│  │   ├── bootstrap_evaluator.py # Bootstrap with paired delta  │
│  │   ├── deterministic.py       # Single-run evaluation        │
│  │   └── monte_carlo.py         # Traditional MC evaluation    │
│  │                                                              │
│  ├── runner/                    # NEW: Experiment runners      │
│  │   ├── protocol.py            # ExperimentRunnerProtocol     │
│  │   ├── base_runner.py         # BaseExperimentRunner         │
│  │   └── optimization_loop.py   # Core optimization logic      │
│  │                                                              │
│  ├── core/                      # Enhanced existing            │
│  │   ├── game_orchestrator.py   # Use this as main controller  │
│  │   └── game_session.py        # Session state                │
│  │                                                              │
│  └── persistence/               # Single unified layer         │
│      ├── repository.py          # GameRepository (enhanced)    │
│      └── event_repository.py    # Unified event storage        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 0: Fix Bootstrap Bug (Immediate)

**Goal**: Fix the critical paired comparison bug without architectural changes.

**Changes to `experiments/castro/castro/runner.py`**:

1. Store bootstrap samples after generation
2. Use `compute_paired_deltas()` for policy comparison
3. Accept based on mean delta, not absolute cost

```python
# In _evaluate_policies(), return samples for reuse
async def _evaluate_policies(self, iteration: int, ...) -> tuple[..., list[BootstrapSample]]:
    samples = self._bootstrap_sampler.generate_samples(...)
    results = self._bootstrap_evaluator.evaluate_samples(samples, policy)
    return ..., samples

# In optimization loop
samples = None  # Store samples for paired comparison

# First evaluation with current policy
total_cost, per_agent_costs, context, seed_results, samples = await self._evaluate_policies(...)

# For each agent optimization
if result.was_accepted and result.new_policy:
    # Use SAME samples for paired comparison
    deltas = self._bootstrap_evaluator.compute_paired_deltas(
        samples=samples,
        policy_a=old_policy,  # Current
        policy_b=result.new_policy,  # Proposed
    )
    mean_delta = self._bootstrap_evaluator.compute_mean_delta(deltas)

    if mean_delta < 0:  # New policy is better
        actually_accepted = True
        self._policies[agent_id] = result.new_policy
```

**Estimated effort**: 1 day
**Risk**: Low (contained change)

---

### Phase 1: Consolidate LLM Infrastructure

**Goal**: Move LLM client code to `ai_cash_mgmt/llm/` for reuse.

**Step 1.1: Create LLM module structure**

```
api/payment_simulator/ai_cash_mgmt/llm/
├── __init__.py
├── protocol.py           # LLMClientProtocol (already exists in policy_optimizer)
├── pydantic_client.py    # Move from castro/pydantic_llm_client.py
├── audit_wrapper.py      # Move AuditCaptureLLMClient
└── config.py             # Unified ModelConfig
```

**Step 1.2: Unify model configuration**

Merge Castro's `ModelConfig` with ai_cash_mgmt's `LLMConfig`:

```python
# api/payment_simulator/ai_cash_mgmt/llm/config.py
@dataclass
class LLMConfig:
    """Unified LLM configuration."""

    # Model specification
    model: str  # "provider:model" format

    # Common settings
    temperature: float = 0.0
    max_retries: int = 3

    # Provider-specific (mutually exclusive)
    thinking_budget: int | None = None  # Anthropic
    reasoning_effort: str | None = None  # OpenAI

    @property
    def provider(self) -> str:
        return self.model.split(":")[0]

    @property
    def model_name(self) -> str:
        return self.model.split(":", 1)[1]
```

**Step 1.3: Update Castro to use unified LLM module**

```python
# experiments/castro/castro/runner.py
from payment_simulator.ai_cash_mgmt.llm import (
    PydanticAILLMClient,
    AuditCaptureLLMClient,
    LLMConfig,
)
```

**Estimated effort**: 2 days
**Risk**: Medium (refactoring imports across modules)

---

### Phase 2: Unify Persistence Layer

**Goal**: Single database, unified event model.

**Step 2.1: Enhance GameRepository to store experiment events**

```python
# api/payment_simulator/ai_cash_mgmt/persistence/repository.py
class GameRepository:
    def save_experiment_event(self, event: ExperimentEvent) -> None:
        """Save experiment event (LLM call, policy change, etc.)."""
        ...

    def get_experiment_events(
        self,
        run_id: str,
        event_type: str | None = None
    ) -> list[ExperimentEvent]:
        """Get experiment events for replay."""
        ...
```

**Step 2.2: Define unified event schema**

```python
# api/payment_simulator/ai_cash_mgmt/persistence/events.py
@dataclass
class ExperimentEvent:
    """Base experiment event."""
    run_id: str
    iteration: int
    timestamp: datetime
    event_type: str
    details: dict[str, Any]  # JSON blob

# Event types:
# - iteration_start
# - monte_carlo_evaluation
# - llm_call
# - policy_proposed
# - policy_accepted
# - policy_rejected
# - convergence_reached
```

**Step 2.3: Remove Castro's ExperimentEventRepository**

Update `ExperimentRunner` to use single `GameRepository`.

**Estimated effort**: 2-3 days
**Risk**: Medium (database schema changes)

---

### Phase 3: Create Evaluation Module

**Goal**: Clean abstraction for policy evaluation strategies.

**Step 3.1: Define evaluation protocol**

```python
# api/payment_simulator/ai_cash_mgmt/evaluation/protocol.py
from typing import Protocol

class PolicyEvaluatorProtocol(Protocol):
    """Protocol for policy evaluation strategies."""

    def evaluate(
        self,
        policy: dict[str, Any],
        agent_id: str,
    ) -> EvaluationResult:
        """Evaluate a single policy."""
        ...

    def compare(
        self,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
        agent_id: str,
    ) -> ComparisonResult:
        """Compare two policies (paired comparison)."""
        ...

@dataclass
class ComparisonResult:
    """Result of comparing two policies."""
    old_cost: int
    new_cost: int
    delta: int  # new_cost - old_cost (negative = improvement)
    confidence: float  # Statistical confidence
    sample_deltas: list[int]  # Per-sample deltas
```

**Step 3.2: Implement bootstrap evaluator with proper pairing**

```python
# api/payment_simulator/ai_cash_mgmt/evaluation/bootstrap_evaluator.py
class BootstrapEvaluator:
    """Bootstrap-based policy evaluation with paired comparison."""

    def __init__(
        self,
        sampler: BootstrapSampler,
        sandbox_builder: SandboxConfigBuilder,
        num_samples: int = 10,
    ):
        self._sampler = sampler
        self._sandbox_builder = sandbox_builder
        self._num_samples = num_samples
        self._cached_samples: list[BootstrapSample] | None = None

    def generate_samples(self, agent_id: str) -> list[BootstrapSample]:
        """Generate and cache bootstrap samples."""
        self._cached_samples = self._sampler.generate_samples(
            agent_id=agent_id,
            n_samples=self._num_samples,
            ...
        )
        return self._cached_samples

    def compare(
        self,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
        agent_id: str,
    ) -> ComparisonResult:
        """Compare policies using SAME samples (paired comparison)."""
        if self._cached_samples is None:
            self.generate_samples(agent_id)

        deltas: list[int] = []
        for sample in self._cached_samples:
            old_cost = self._evaluate_on_sample(sample, old_policy)
            new_cost = self._evaluate_on_sample(sample, new_policy)
            deltas.append(new_cost - old_cost)

        return ComparisonResult(
            old_cost=sum(self._evaluate_on_sample(s, old_policy) for s in self._cached_samples),
            new_cost=sum(self._evaluate_on_sample(s, new_policy) for s in self._cached_samples),
            delta=sum(deltas),
            confidence=self._compute_confidence(deltas),
            sample_deltas=deltas,
        )
```

**Estimated effort**: 2 days
**Risk**: Low (new code, not modifying existing)

---

### Phase 4: Extract Experiment Runner to Core

**Goal**: Reusable experiment runner that Castro (and future experiments) can use.

**Step 4.1: Define runner protocol**

```python
# api/payment_simulator/ai_cash_mgmt/runner/protocol.py
class ExperimentRunnerProtocol(Protocol):
    """Protocol for experiment runners."""

    async def run(self) -> ExperimentResult:
        """Run experiment to completion."""
        ...

    def get_current_state(self) -> ExperimentState:
        """Get current experiment state (for display/audit)."""
        ...
```

**Step 4.2: Implement base runner with optimization loop**

```python
# api/payment_simulator/ai_cash_mgmt/runner/base_runner.py
class BaseExperimentRunner:
    """Base experiment runner with core optimization loop."""

    def __init__(
        self,
        config: ExperimentConfig,
        evaluator: PolicyEvaluatorProtocol,
        llm_client: LLMClientProtocol,
        constraints: ScenarioConstraints,
        output_handler: OutputHandlerProtocol,
    ):
        self._config = config
        self._evaluator = evaluator
        self._llm_client = llm_client
        self._constraints = constraints
        self._output = output_handler

        # Use GameOrchestrator for coordination
        self._orchestrator = GameOrchestrator(
            config=config.to_game_config(),
            constraints=constraints,
        )

    async def run(self) -> ExperimentResult:
        """Run optimization loop."""
        session = self._orchestrator.create_session()

        for iteration in range(self._config.max_iterations):
            self._output.on_iteration_start(iteration)

            # Generate samples for this iteration
            samples = self._evaluator.generate_samples()

            # Evaluate current policies
            current_costs = self._evaluate_all_agents(session, samples)

            # Check convergence
            self._orchestrator.record_iteration_metric(sum(current_costs.values()))
            if self._orchestrator.check_convergence()["is_converged"]:
                break

            # Optimize each agent
            for agent_id in self._config.optimized_agents:
                result = await self._optimize_agent(
                    session=session,
                    agent_id=agent_id,
                    samples=samples,  # SAME samples for comparison
                )
                self._output.on_agent_optimized(agent_id, result)

        return self._build_result(session)

    async def _optimize_agent(
        self,
        session: GameSession,
        agent_id: str,
        samples: list[BootstrapSample],
    ) -> AgentOptimizationResult:
        """Optimize single agent using paired comparison."""
        old_policy = session.get_policy(agent_id)

        # Get LLM proposal
        proposal = await self._llm_client.generate_policy(...)

        if proposal is None:
            return AgentOptimizationResult(accepted=False, reason="llm_failed")

        # Validate constraints
        errors = self._constraints.validate(proposal)
        if errors:
            return AgentOptimizationResult(accepted=False, reason="validation_failed", errors=errors)

        # PAIRED COMPARISON on same samples
        comparison = self._evaluator.compare(
            old_policy=old_policy,
            new_policy=proposal,
            agent_id=agent_id,
        )

        if comparison.delta < 0:  # Improvement
            session.set_policy(agent_id, proposal)
            return AgentOptimizationResult(
                accepted=True,
                old_cost=comparison.old_cost,
                new_cost=comparison.new_cost,
                delta=comparison.delta,
            )
        else:
            return AgentOptimizationResult(
                accepted=False,
                reason="no_improvement",
                delta=comparison.delta,
            )
```

**Step 4.3: Simplify Castro's ExperimentRunner**

```python
# experiments/castro/castro/runner.py
class CastroExperimentRunner(BaseExperimentRunner):
    """Castro-specific experiment runner."""

    def __init__(self, experiment: CastroExperiment, ...):
        # Load Castro constraints
        constraints = CASTRO_CONSTRAINTS

        # Create Castro-specific output handler
        output = CastroVerboseOutput(console)

        super().__init__(
            config=experiment.to_experiment_config(),
            evaluator=BootstrapEvaluator(...),
            llm_client=PydanticAILLMClient(experiment.get_model_config()),
            constraints=constraints,
            output_handler=output,
        )
```

**Estimated effort**: 3-5 days
**Risk**: High (major refactoring)

---

### Phase 5: YAML-Driven Experiment Configuration

**Goal**: Experiment definitions in YAML, not Python code.

**Step 5.1: Define experiment YAML schema**

```yaml
# experiments/castro/experiments/exp2.yaml
name: exp2
description: "12-Period Stochastic LVTS-Style"

# Reference to scenario config
scenario: configs/exp2_12period.yaml

# Evaluation settings
evaluation:
  mode: bootstrap  # or "deterministic", "monte_carlo"
  num_samples: 10
  ticks: 12

# Convergence criteria
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5

# LLM settings (can be overridden via CLI)
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0

# Agents to optimize
optimized_agents:
  - BANK_A
  - BANK_B

# Output settings
output:
  directory: results
  verbose: true
```

**Step 5.2: Create ExperimentConfig loader**

```python
# api/payment_simulator/ai_cash_mgmt/config/experiment_config.py
@dataclass
class ExperimentConfig:
    """Experiment configuration loaded from YAML."""

    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceCriteria
    llm: LLMConfig
    optimized_agents: list[str]
    output: OutputConfig

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig:
        """Load experiment config from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(
            name=data["name"],
            description=data["description"],
            scenario_path=Path(data["scenario"]),
            evaluation=EvaluationConfig(**data["evaluation"]),
            convergence=ConvergenceCriteria(**data["convergence"]),
            llm=LLMConfig(**data["llm"]),
            optimized_agents=data["optimized_agents"],
            output=OutputConfig(**data["output"]),
        )
```

**Step 5.3: Update CLI to load from YAML**

```python
# experiments/castro/cli.py
@app.command()
def run(
    experiment: Annotated[Path, typer.Argument(help="Path to experiment YAML")],
    model: Annotated[str | None, typer.Option()] = None,
    ...
):
    config = ExperimentConfig.from_yaml(experiment)

    # CLI overrides
    if model:
        config.llm.model = model

    runner = CastroExperimentRunner(config)
    result = asyncio.run(runner.run())
```

**Estimated effort**: 2 days
**Risk**: Medium (new loader, deprecating factory functions)

---

### Phase 6: Output/Display Abstraction

**Goal**: Decouple output from runner for testing and flexibility.

**Step 6.1: Define output handler protocol**

```python
# api/payment_simulator/ai_cash_mgmt/runner/output.py
class OutputHandlerProtocol(Protocol):
    """Protocol for experiment output handling."""

    def on_experiment_start(self, config: ExperimentConfig) -> None: ...
    def on_iteration_start(self, iteration: int) -> None: ...
    def on_evaluation_complete(self, results: EvaluationResults) -> None: ...
    def on_agent_optimized(self, agent_id: str, result: AgentOptimizationResult) -> None: ...
    def on_convergence(self, reason: str) -> None: ...
    def on_experiment_complete(self, result: ExperimentResult) -> None: ...
```

**Step 6.2: Implement handlers**

```python
# Rich console output (current behavior)
class RichConsoleOutput(OutputHandlerProtocol):
    def __init__(self, console: Console, verbose: bool = True):
        self._console = console
        self._verbose = verbose

    def on_iteration_start(self, iteration: int) -> None:
        self._console.print(f"[cyan]Iteration {iteration}[/cyan]")

# JSON streaming (for API/tooling)
class JSONStreamOutput(OutputHandlerProtocol):
    def __init__(self, stream: TextIO):
        self._stream = stream

    def on_iteration_start(self, iteration: int) -> None:
        json.dump({"event": "iteration_start", "iteration": iteration}, self._stream)
        self._stream.write("\n")

# Silent (for testing)
class SilentOutput(OutputHandlerProtocol):
    def on_iteration_start(self, iteration: int) -> None:
        pass  # No output
```

**Estimated effort**: 1-2 days
**Risk**: Low (new abstraction)

---

## Migration Path

### Week 1: Critical Bug Fix + Foundation
- [ ] **Phase 0**: Fix bootstrap paired comparison bug (1 day)
- [ ] Add regression test for paired comparison
- [ ] Document the fix

### Week 2: LLM Consolidation
- [ ] **Phase 1**: Move LLM client to ai_cash_mgmt (2 days)
- [ ] Update all imports in Castro
- [ ] Verify existing tests pass

### Week 3: Persistence + Evaluation
- [ ] **Phase 2**: Unify persistence layer (2-3 days)
- [ ] **Phase 3**: Create evaluation module (2 days)
- [ ] Migrate bootstrap evaluator

### Week 4: Runner Extraction
- [ ] **Phase 4**: Extract base runner (3-5 days)
- [ ] Simplify CastroExperimentRunner
- [ ] Full integration testing

### Week 5: Configuration + Output
- [ ] **Phase 5**: YAML-driven config (2 days)
- [ ] **Phase 6**: Output abstraction (1-2 days)
- [ ] Deprecate Python factory functions

### Week 6: Cleanup + Documentation
- [ ] Remove deprecated code
- [ ] Update all documentation
- [ ] Performance benchmarking
- [ ] Final testing

---

## File Changes Summary

### New Files to Create

```
api/payment_simulator/ai_cash_mgmt/
├── llm/
│   ├── __init__.py
│   ├── protocol.py
│   ├── pydantic_client.py
│   ├── audit_wrapper.py
│   └── config.py
├── evaluation/
│   ├── __init__.py
│   ├── protocol.py
│   ├── bootstrap_evaluator.py
│   └── deterministic.py
├── runner/
│   ├── __init__.py
│   ├── protocol.py
│   ├── base_runner.py
│   └── output.py
└── config/
    └── experiment_config.py

experiments/castro/experiments/
├── exp1.yaml
├── exp2.yaml
└── exp3.yaml
```

### Files to Modify

```
experiments/castro/castro/
├── runner.py           # Simplify to use BaseExperimentRunner
├── experiments.py      # Deprecate factory functions
└── cli.py              # Load from YAML

api/payment_simulator/ai_cash_mgmt/
├── __init__.py         # Export new modules
├── core/game_orchestrator.py  # Enhance for runner integration
└── persistence/repository.py  # Add experiment events
```

### Files to Delete (after migration)

```
experiments/castro/castro/
├── pydantic_llm_client.py   # Moved to ai_cash_mgmt/llm/
├── model_config.py          # Merged into ai_cash_mgmt/llm/config.py
└── persistence/
    ├── models.py            # Merged into ai_cash_mgmt/persistence/
    └── repository.py        # Merged into ai_cash_mgmt/persistence/
```

---

## Success Criteria

1. **Bootstrap bug fixed**: Paired comparison verified with test
2. **Single database**: No more castro.db, all in main database
3. **Reusable infrastructure**: Future experiments can use ai_cash_mgmt without copying Castro code
4. **YAML-driven**: New experiments defined in YAML, not Python
5. **Testable**: Output handlers allow unit testing without console I/O
6. **Documented**: Architecture docs updated to reflect new structure

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing experiments | Comprehensive regression tests before each phase |
| Database migration issues | Write migration script, test on copy first |
| LLM client compatibility | Test with all providers (Anthropic, OpenAI, Google) |
| Performance regression | Benchmark before/after each phase |
| Documentation drift | Update docs as part of each phase, not after |

---

## Appendix: Current vs Target Comparison

### Bootstrap Evaluation Flow

**Current (Broken)**:
```
Iteration N:
  1. Generate samples S1
  2. Evaluate old_policy on S1 → cost_old
  3. LLM proposes new_policy
  4. Generate samples S2 (DIFFERENT!)
  5. Evaluate new_policy on S2 → cost_new
  6. Accept if cost_new < cost_old
```

**Target (Correct)**:
```
Iteration N:
  1. Generate samples S
  2. LLM proposes new_policy
  3. For each sample in S:
     - Evaluate old_policy → cost_old_i
     - Evaluate new_policy → cost_new_i
     - delta_i = cost_new_i - cost_old_i
  4. Accept if mean(delta) < 0
```

### Module Dependencies

**Current**:
```
Castro → ai_cash_mgmt (partial)
       → Rust FFI
       → Rich console (tight coupling)
       → DuckDB (two connections!)
```

**Target**:
```
Castro → ai_cash_mgmt/runner (BaseRunner)
       → ai_cash_mgmt/llm (LLMClient)
       → ai_cash_mgmt/evaluation (Evaluator)
       → ai_cash_mgmt/persistence (single repo)
       → ai_cash_mgmt/config (YAML loader)
```

---

*Plan created: 2024-12-10*
*Author: Claude Code*
*Status: Draft - awaiting review*
