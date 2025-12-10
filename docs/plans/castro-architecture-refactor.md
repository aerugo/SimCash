# Castro Architecture Refactor Plan

**Status:** Ready for Implementation
**Created:** 2025-12-10
**Last Updated:** 2025-12-10
**Author:** Claude
**Related:**
- `docs/plans/bootstrap-refactor/refactor-conceptual-plan.md` (completed prerequisite)
- `docs/plans/bootstrap-refactor/development-plan.md` (completed 3-agent sandbox)
- `docs/reference/ai_cash_mgmt/` (optimization framework)
- `docs/reference/castro/` (experiment framework)

---

## Major Refactor: Module Split

> **Note:** This document focuses on immediate bug fixes and improvements. For the comprehensive module split refactor (splitting `ai_cash_mgmt` into three modules), see:
>
> - **[Conceptual Plan](./refactor/conceptual-plan.md)** - Architecture overview, goals, and module specifications
> - **[Development Plan](./refactor/development-plan.md)** - Phase-by-phase implementation with TDD tests
> - **[Work Notes](./refactor/work_notes.md)** - Progress tracking and phase checklists
>
> The module split creates:
> 1. **`ai_cash_mgmt/`** - Policy optimization core (bootstrap, constraints, sampling)
> 2. **`llm/`** - LLM integration layer (unified provider abstraction)
> 3. **`experiments/`** - Experiment framework (YAML-driven configs, runners, persistence)
>
> After the refactor, `experiments/castro/` becomes a thin layer containing only Castro-specific constraints and experiment YAML files.

---

## Executive Summary

The Castro experiment implementation has diverged from its intended architecture, resulting in:
1. **Critical bug**: Bootstrap evaluation doesn't use paired comparison (comparing OLD vs NEW policy on same samples)
2. **Context/Evaluation mismatch**: LLM receives context from full simulation, but costs are from bootstrap evaluation
3. **Duplicate infrastructure**: LLM clients, model configs, persistence layers exist in both Castro and ai_cash_mgmt
4. **Initialization waste**: Full simulation runs just to collect transaction history
5. **Underutilized abstractions**: GameOrchestrator exists but isn't used; StateProvider pattern incomplete

This plan proposes a phased refactoring to:
- Fix the bootstrap evaluation bug (Phase 0)
- Make bootstrap sandbox the single source of truth for context AND costs (Phase 0.5)
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

### Issue 5: Context/Evaluation Mismatch (Architecture Problem)

**Evidence from `runner.py` lines 780-792:**
```python
# Creating fake SimulationResults to bridge context builder
results.append(
    SimulationResult(
        total_cost=sample_total,
        per_agent_costs={...},
        settlement_rate=1.0,  # Bootstrap samples are pre-filtered
        transactions_settled=0,  # Not tracked in bootstrap
        transactions_failed=0,
    )
)
```

This adapter pattern reveals a fundamental mismatch:
- **MonteCarloContextBuilder** expects full simulation `VerboseOutput` with tick-by-tick events
- **Bootstrap evaluation** doesn't produce `VerboseOutput` - it uses the 3-agent sandbox
- **Result:** LLM receives placeholder data, not real simulation context

**Impact**: The LLM can't learn effectively because the context it sees doesn't match the costs it's optimizing.

### Issue 6: Initialization Waste

**Evidence from `runner.py` `_initialize_bootstrap()` method:**
```python
# Runs FULL simulation just to collect transaction history!
result = self._sim_runner.run_simulation(
    policy=policy,
    seed=seed,
    ticks=self._monte_carlo_config.evaluation_ticks,
    capture_verbose=True,  # Need events for history collection
)
```

**Impact**:
- Slow experiment startup
- Wasted computation
- Transaction history could be generated directly from scenario config

### Issue 7: Experiment Config in Code

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

### Phase 0.5: Add Event Tracing to Bootstrap Sandbox

**Goal:** Make bootstrap evaluation produce meaningful context for LLM prompts.

**Problem:** The 3-agent bootstrap sandbox runs simulations but doesn't capture events for LLM context. The current workaround creates placeholder `SimulationResult` objects.

**Solution:** Enhance `BootstrapPolicyEvaluator` to capture policy decision events during evaluation.

**Step 0.5.1: Add event trace to EvaluationResult**

```python
# api/payment_simulator/ai_cash_mgmt/bootstrap/models.py

@dataclass(frozen=True)
class BootstrapEvent:
    """Event captured during bootstrap evaluation.

    Minimal format optimized for LLM consumption.
    All monetary values in integer cents (INV-1).
    """
    tick: int
    event_type: str  # "arrival", "decision", "settlement", "cost"
    details: dict[str, Any]

@dataclass(frozen=True)
class CostBreakdown:
    """Breakdown of costs by type (integer cents)."""
    delay_cost: int
    overdraft_cost: int
    deadline_penalty: int
    eod_penalty: int

    @property
    def total(self) -> int:
        return self.delay_cost + self.overdraft_cost + self.deadline_penalty + self.eod_penalty

@dataclass(frozen=True)
class EnrichedEvaluationResult:
    """Evaluation result with context for LLM prompts."""
    sample_idx: int
    seed: int
    total_cost: int  # Integer cents (INV-1)
    settlement_rate: float
    avg_delay: float
    event_trace: list[BootstrapEvent]
    cost_breakdown: CostBreakdown
```

**Step 0.5.2: Capture events during sandbox evaluation**

Modify `BootstrapPolicyEvaluator.evaluate_sample()` to capture events from the orchestrator:

```python
# api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py

def evaluate_sample_enriched(
    self,
    sample: BootstrapSample,
    policy: dict[str, Any],
) -> EnrichedEvaluationResult:
    """Evaluate with full event capture for LLM context."""
    # Build and run sandbox
    config = self._config_builder.build_config(...)
    ffi_config = config.to_ffi_dict()
    orchestrator = Orchestrator.new(ffi_config)

    # Run with event capture
    events: list[BootstrapEvent] = []
    for tick in range(sample.total_ticks):
        orchestrator.tick()

        # Capture relevant events from this tick
        tick_events = orchestrator.get_tick_events(tick)
        for event in tick_events:
            if self._is_relevant_event(event, sample.agent_id):
                events.append(self._convert_to_bootstrap_event(event))

    # Extract metrics and cost breakdown
    metrics = self._extract_agent_metrics(orchestrator, sample.agent_id)
    cost_breakdown = self._extract_cost_breakdown(orchestrator, sample.agent_id)

    return EnrichedEvaluationResult(
        sample_idx=sample.sample_idx,
        seed=sample.seed,
        total_cost=int(metrics["total_cost"]),
        settlement_rate=float(metrics["settlement_rate"]),
        avg_delay=float(metrics["avg_delay"]),
        event_trace=events,
        cost_breakdown=cost_breakdown,
    )

def _is_relevant_event(self, event: dict, agent_id: str) -> bool:
    """Filter for events relevant to the target agent."""
    relevant_types = {
        "Arrival", "PolicyDecision", "RtgsImmediateSettlement",
        "Queue2LiquidityRelease", "DelayCostAccrual", "OverdraftCostAccrual",
    }
    if event.get("event_type") not in relevant_types:
        return False
    # Check if event involves our agent
    return (event.get("sender_id") == agent_id or
            event.get("receiver_id") == agent_id or
            event.get("agent_id") == agent_id)
```

**Step 0.5.3: Create BootstrapContextBuilder**

Replace `MonteCarloContextBuilder` with a bootstrap-native version:

```python
# experiments/castro/castro/bootstrap_context.py

class BootstrapContextBuilder:
    """Builds LLM context directly from enriched bootstrap results.

    Unlike MonteCarloContextBuilder, works natively with bootstrap
    evaluation results - no adapters or placeholder data.
    """

    def __init__(
        self,
        results: list[EnrichedEvaluationResult],
        agent_id: str,
    ) -> None:
        self._results = results
        self._agent_id = agent_id

    def get_best_result(self) -> EnrichedEvaluationResult:
        """Get result with lowest cost."""
        return min(self._results, key=lambda r: r.total_cost)

    def get_worst_result(self) -> EnrichedEvaluationResult:
        """Get result with highest cost."""
        return max(self._results, key=lambda r: r.total_cost)

    def format_event_trace_for_llm(
        self,
        result: EnrichedEvaluationResult,
        max_events: int = 50,
    ) -> str:
        """Format event trace for LLM prompt.

        Filters to most informative events:
        - Policy decisions (shows decision points)
        - High-cost events (shows what to optimize)
        - Settlement failures (shows problems)
        """
        # Prioritize events by informativeness
        events = sorted(
            result.event_trace,
            key=lambda e: self._event_priority(e),
            reverse=True,
        )[:max_events]

        # Sort by tick for chronological presentation
        events = sorted(events, key=lambda e: e.tick)

        return self._format_events(events)

    def build_agent_context(self) -> AgentSimulationContext:
        """Build context matching SingleAgentContext format."""
        best = self.get_best_result()
        worst = self.get_worst_result()

        return AgentSimulationContext(
            agent_id=self._agent_id,
            best_seed=best.seed,
            best_seed_cost=best.total_cost,
            best_seed_output=self.format_event_trace_for_llm(best),
            worst_seed=worst.seed,
            worst_seed_cost=worst.total_cost,
            worst_seed_output=self.format_event_trace_for_llm(worst),
            mean_cost=self._compute_mean_cost(),
            cost_std=self._compute_cost_std(),
        )
```

**Step 0.5.4: Update runner to use enriched evaluation**

```python
# experiments/castro/castro/runner.py

async def _evaluate_policies(
    self,
    iteration: int,
) -> tuple[int, dict[str, int], dict[str, BootstrapContextBuilder], list[BootstrapSample]]:
    """Evaluate using enriched bootstrap results.

    Returns context builders per agent that have REAL event data,
    not placeholder SimulationResults.
    """
    all_results: dict[str, list[EnrichedEvaluationResult]] = {}
    all_samples: dict[str, list[BootstrapSample]] = {}

    for agent_id in self._experiment.optimized_agents:
        samples = self._bootstrap_sampler.generate_samples(...)
        all_samples[agent_id] = samples

        # Use enriched evaluation
        results = [
            self._bootstrap_evaluator.evaluate_sample_enriched(sample, self._policies[agent_id])
            for sample in samples
        ]
        all_results[agent_id] = results

    # Build context builders with REAL data
    context_builders = {
        agent_id: BootstrapContextBuilder(results, agent_id)
        for agent_id, results in all_results.items()
    }

    # Compute costs
    total_cost = sum(
        sum(r.total_cost for r in results) // len(results)
        for results in all_results.values()
    )
    per_agent_costs = {
        agent_id: sum(r.total_cost for r in results) // len(results)
        for agent_id, results in all_results.items()
    }

    # Return samples for paired comparison (Phase 0)
    samples_list = list(all_samples.values())[0]  # Same samples for all agents
    return total_cost, per_agent_costs, context_builders, samples_list
```

**Estimated effort**: 2-3 days
**Risk**: Medium (modifying core evaluation path)

**Files:**
- Modify: `api/payment_simulator/ai_cash_mgmt/bootstrap/models.py`
- Modify: `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`
- Create: `experiments/castro/castro/bootstrap_context.py`
- Modify: `experiments/castro/castro/runner.py`
- Deprecate: `experiments/castro/castro/context_builder.py`

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

## Alignment with Project Invariants

This refactor must maintain strict adherence to project invariants:

### INV-1: Money is Always i64 (Integer Cents)

All cost fields in bootstrap evaluation remain integer cents:
```python
@dataclass(frozen=True)
class CostBreakdown:
    delay_cost: int      # cents
    overdraft_cost: int  # cents
    total: int           # cents - computed property
```

**Verification:** No float arithmetic in cost calculations.

### INV-2: Determinism is Sacred

Bootstrap sampling uses `SeedManager` for deterministic seed derivation:
```python
seed = self._seed_manager.sampling_seed(iteration, agent_id)
sampler = BootstrapSampler(seed=seed)
```

**Verification:** Same master_seed → identical experiment results.

### INV-3: FFI Boundary is Minimal

The 3-agent sandbox config builder already handles FFI conversion:
```python
config = self._config_builder.build_config(sample, policy, ...)
ffi_config = config.to_ffi_dict()  # Clean conversion
orchestrator = Orchestrator.new(ffi_config)
```

**Verification:** All FFI calls go through `SimulationConfig.to_ffi_dict()`.

### INV-5: Event Completeness (Replay Identity)

Bootstrap events must be self-contained for replay:
```python
@dataclass(frozen=True)
class BootstrapEvent:
    tick: int
    event_type: str
    details: dict[str, Any]  # All data needed for display
```

**Verification:** `castro replay` produces identical output to `castro run`.

---

## Migration Path

### Week 1: Critical Bug Fix + Context Improvement
- [ ] **Phase 0**: Fix bootstrap paired comparison bug (1 day)
- [ ] Add regression test for paired comparison
- [ ] **Phase 0.5**: Add event tracing to bootstrap (2-3 days)
- [ ] Create BootstrapContextBuilder
- [ ] Document the fixes

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
├── bootstrap/
│   └── models.py             # Enhanced with BootstrapEvent, CostBreakdown, EnrichedEvaluationResult
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

experiments/castro/
├── castro/
│   └── bootstrap_context.py  # NEW: BootstrapContextBuilder (Phase 0.5)
└── experiments/
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
├── context_builder.py       # Replaced by bootstrap_context.py (Phase 0.5)
├── pydantic_llm_client.py   # Moved to ai_cash_mgmt/llm/
├── model_config.py          # Merged into ai_cash_mgmt/llm/config.py
├── simulation.py            # No longer needed (bootstrap replaces full sim)
└── persistence/
    ├── models.py            # Merged into ai_cash_mgmt/persistence/
    └── repository.py        # Merged into ai_cash_mgmt/persistence/
```

---

## Success Criteria

1. **Bootstrap bug fixed**: Paired comparison verified with test
2. **Context matches costs**: LLM context derived from same evaluation that produces costs
3. **Single database**: No more castro.db, all in main database
4. **Reusable infrastructure**: Future experiments can use ai_cash_mgmt without copying Castro code
5. **YAML-driven**: New experiments defined in YAML, not Python
6. **Testable**: Output handlers allow unit testing without console I/O
7. **Invariants maintained**: Integer cents, determinism, minimal FFI, replay identity
8. **Documented**: Architecture docs updated to reflect new structure

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

### Bootstrap Evaluation Flow (Issue 1 - Bug)

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

### Context/Evaluation Flow (Issue 5 - Architecture)

**Current (Broken)**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Evaluation Path                   Context Path                 │
│                                                                 │
│  BootstrapSampler                  Full Simulation              │
│       ↓                                 ↓                       │
│  3-Agent Sandbox                   VerboseOutputCapture         │
│       ↓                                 ↓                       │
│  EvaluationResult                  MonteCarloContextBuilder     │
│  (actual costs)                    (placeholder data!)          │
│       ↓                                 ↓                       │
│  Accept/Reject Decision       →    LLM Prompt                   │
│                                                                 │
│  PROBLEM: Context doesn't match what produced the costs!        │
└─────────────────────────────────────────────────────────────────┘
```

**Target (Correct)**:
```
┌─────────────────────────────────────────────────────────────────┐
│  Single Evaluation + Context Path                               │
│                                                                 │
│  BootstrapSampler                                               │
│       ↓                                                         │
│  3-Agent Sandbox (with event capture)                           │
│       ↓                                                         │
│  EnrichedEvaluationResult                                       │
│  ├── total_cost (for accept/reject)                             │
│  ├── event_trace (for LLM context)                              │
│  └── cost_breakdown (for LLM learning)                          │
│       ↓                                                         │
│  BootstrapContextBuilder                                        │
│       ↓                                                         │
│  LLM Prompt (context matches costs!)                            │
│                                                                 │
│  GOAL: Single source of truth for both evaluation and context   │
└─────────────────────────────────────────────────────────────────┘
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

*Plan created: 2025-12-10*
*Author: Claude Code*
*Status: Ready for Implementation*
