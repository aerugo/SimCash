# Plan: Verbose Optimizer Context for Castro Experiments

## Executive Summary

Implement full verbose simulation output capture and filtering for the Castro LLM optimizer context. This restores functionality from the original implementation where the LLM receives 50,000+ token context including tick-by-tick simulation logs filtered per agent.

## Problem Statement

The current Castro implementation sends minimal context to the LLM optimizer:
- Only iteration number and cost (~1,000 tokens)
- No verbose simulation output
- No tick-by-tick event logs
- No filtered agent-specific views

The LLM cannot make informed policy decisions without seeing what actually happened during simulations.

## Original Implementation Analysis

The old implementation (deleted in commit `c7c3513`) provided:

1. **Full verbose output** from best and worst performing seeds
2. **Per-agent filtering** via `payment-sim replay --filter-agent <agent_id>`
3. **Rich context** including:
   - Tick-by-tick event logs
   - Policy decisions made
   - Cost accruals
   - Settlement patterns
   - Queue states
   - Balance changes

## Key Invariants to Preserve

### INV-1: Agent Isolation
Each agent's LLM call MUST receive ONLY events where that agent is:
- The sender/actor (arrivals, policy decisions, cost accruals)
- The receiver (incoming settlements providing liquidity)

The agent MUST NOT see:
- Other agents' arrivals
- Other agents' policy decisions
- Other agents' cost accruals
- Other agents' queue states

**Rationale**: Each bank is "selfish" and optimizes only its own costs. Seeing opponent strategy would violate the game-theoretic setup.

### INV-2: Deterministic Replay
Same seed + same policy → identical verbose output

### INV-3: Monte Carlo Best/Worst Selection
- Best seed = seed with lowest cost for the agent being optimized
- Worst seed = seed with highest cost for the agent being optimized
- Each agent may have different best/worst seeds

### INV-4: Context Structure
The context MUST follow the `SingleAgentContext` structure from `ai_cash_mgmt.prompts.context_types`:
- `best_seed_output`: Filtered verbose output from best seed
- `worst_seed_output`: Filtered verbose output from worst seed
- `iteration_history`: List of `SingleAgentIterationRecord` for this agent only
- `cost_breakdown`: Cost breakdown for this agent only

## Implementation Approach: Option A (Persistence + Replay)

Use the existing infrastructure:
1. Run simulations with `--persist` to enable replay
2. Use `EventFilter` to filter events per agent
3. Format filtered events as verbose output text
4. Pass to `SingleAgentContextBuilder`

## Existing Infrastructure to Leverage

### Already Available:

1. **`EventFilter`** (`api/payment_simulator/cli/filters.py`)
   - Filters events by agent ID
   - Correctly handles actor vs receiver visibility
   - Already tested in `tests/integration/test_filtered_replay_for_castro.py`

2. **`SingleAgentContextBuilder`** (`api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py`)
   - Builds full context prompt with verbose output sections
   - Has `best_seed_output` and `worst_seed_output` fields
   - Already implements all formatting logic

3. **`SingleAgentContext`** (`api/payment_simulator/ai_cash_mgmt/prompts/context_types.py`)
   - Data structure for context
   - Ready to receive verbose output strings

4. **Verbose output formatting** (`api/payment_simulator/cli/execution/display.py`)
   - `display_tick_verbose_output()` formats events for display
   - Used by both `run` and `replay` commands

## TDD Implementation Plan

### Phase 1: Unit Tests for Verbose Output Capture

**File**: `experiments/castro/tests/test_verbose_output.py`

```python
class TestVerboseOutputCapture:
    """Test verbose output capture from simulations."""

    def test_can_capture_events_from_orchestrator(self):
        """Orchestrator.get_tick_events() returns all events for a tick."""

    def test_events_contain_required_fields(self):
        """Events have all fields needed for verbose display."""

    def test_events_are_deterministic(self):
        """Same seed produces identical events."""


class TestEventFiltering:
    """Test event filtering for agent isolation."""

    def test_arrivals_filtered_to_sender(self):
        """Agent only sees arrivals they initiated."""

    def test_settlements_visible_to_both_parties(self):
        """Both sender and receiver see settlement events."""

    def test_policy_events_filtered_to_actor(self):
        """Policy decisions only visible to acting agent."""

    def test_cost_accruals_filtered_to_incurring_agent(self):
        """Cost events only visible to agent incurring costs."""

    def test_no_cross_agent_leakage(self):
        """Agent A never sees Agent B's internal events."""


class TestVerboseOutputFormatting:
    """Test formatting events into verbose output text."""

    def test_format_arrival_event(self):
        """Arrival events format correctly."""

    def test_format_settlement_event(self):
        """Settlement events format correctly."""

    def test_format_policy_event(self):
        """Policy decision events format correctly."""

    def test_format_cost_accrual_event(self):
        """Cost accrual events format correctly."""

    def test_full_tick_verbose_format(self):
        """Complete tick output matches expected format."""
```

### Phase 2: Unit Tests for Per-Agent Context Building

**File**: `experiments/castro/tests/test_agent_context.py`

```python
class TestBestWorstSeedSelection:
    """Test selection of best/worst seeds per agent."""

    def test_best_seed_is_lowest_cost_for_agent(self):
        """Best seed has lowest cost for this specific agent."""

    def test_worst_seed_is_highest_cost_for_agent(self):
        """Worst seed has highest cost for this specific agent."""

    def test_different_agents_can_have_different_best_seeds(self):
        """Agents A and B may have different optimal seeds."""


class TestContextBuilding:
    """Test building SingleAgentContext from simulation results."""

    def test_context_has_best_seed_output(self):
        """Context includes filtered verbose output from best seed."""

    def test_context_has_worst_seed_output(self):
        """Context includes filtered verbose output from worst seed."""

    def test_context_has_iteration_history(self):
        """Context includes iteration history for this agent only."""

    def test_context_cost_breakdown_is_agent_specific(self):
        """Cost breakdown shows only this agent's costs."""
```

### Phase 3: Integration Tests for Full Flow

**File**: `experiments/castro/tests/test_verbose_context_integration.py`

```python
class TestVerboseContextIntegration:
    """Integration tests for full verbose context flow."""

    def test_monte_carlo_produces_verbose_context(self):
        """Running Monte Carlo samples produces verbose context per agent."""

    def test_verbose_context_is_filtered_per_agent(self):
        """Each agent receives different verbose output."""

    def test_verbose_context_respects_isolation(self):
        """Agent A's context contains no Agent B information."""

    def test_verbose_context_size_is_substantial(self):
        """Context is 30k+ tokens as expected."""

    def test_context_builder_produces_valid_prompt(self):
        """SingleAgentContextBuilder produces valid markdown prompt."""


class TestLLMPromptContent:
    """Test the actual content sent to the LLM."""

    def test_prompt_includes_tick_by_tick_output(self):
        """Prompt contains tick-by-tick event logs."""

    def test_prompt_includes_best_seed_analysis(self):
        """Prompt explains what went right in best seed."""

    def test_prompt_includes_worst_seed_analysis(self):
        """Prompt explains what went wrong in worst seed."""

    def test_prompt_includes_iteration_history(self):
        """Prompt shows policy evolution across iterations."""
```

### Phase 4: Implementation - VerboseOutputCapture

**File**: `experiments/castro/castro/verbose_capture.py`

```python
"""Capture and filter verbose output from simulations.

This module provides functionality to:
1. Capture tick-by-tick events from the Rust Orchestrator
2. Filter events per agent using EventFilter
3. Format events into verbose output text
"""

from dataclasses import dataclass
from payment_simulator._core import Orchestrator
from payment_simulator.cli.filters import EventFilter


@dataclass
class VerboseOutput:
    """Verbose output from a simulation run.

    Attributes:
        full_output: Complete unfiltered verbose output
        events_by_tick: Dict mapping tick -> list of events
        total_ticks: Number of ticks in the simulation
    """
    full_output: str
    events_by_tick: dict[int, list[dict]]
    total_ticks: int

    def filter_for_agent(self, agent_id: str) -> str:
        """Get verbose output filtered for a specific agent.

        Uses EventFilter to ensure proper agent isolation.

        Args:
            agent_id: Agent to filter for (e.g., "BANK_A")

        Returns:
            Filtered verbose output string showing only events
            relevant to this agent.
        """


class VerboseOutputCapture:
    """Captures verbose output from simulation runs.

    Integrates with the Rust Orchestrator to capture all events
    during simulation and format them as verbose output text.

    Example:
        >>> capture = VerboseOutputCapture()
        >>> output = capture.capture_from_orchestrator(orch, ticks=100)
        >>> filtered = output.filter_for_agent("BANK_A")
    """

    def capture_from_orchestrator(
        self,
        orch: Orchestrator,
        ticks: int,
    ) -> VerboseOutput:
        """Run simulation and capture all events.

        Args:
            orch: Initialized Orchestrator (call tick() internally)
            ticks: Number of ticks to run

        Returns:
            VerboseOutput with all captured events
        """

    def format_tick_events(
        self,
        tick: int,
        events: list[dict],
        orch: Orchestrator,
    ) -> str:
        """Format events for a single tick as verbose text.

        Uses the same formatting as display_tick_verbose_output()
        for consistency with CLI output.

        Args:
            tick: Tick number
            events: Events that occurred at this tick
            orch: Orchestrator for additional context (balances, etc)

        Returns:
            Formatted verbose output string for this tick
        """
```

### Phase 5: Implementation - CastroSimulationRunner Enhancement

**File**: `experiments/castro/castro/simulation.py` (modify existing)

```python
@dataclass
class SimulationResult:
    """Result of a single simulation run."""
    total_cost: int
    per_agent_costs: dict[str, int]
    settlement_rate: float
    transactions_settled: int
    transactions_failed: int
    # NEW: Add verbose output
    verbose_output: VerboseOutput | None = None


class CastroSimulationRunner:
    """Runs SimCash simulations for Monte Carlo evaluation."""

    def run_simulation(
        self,
        policy: dict[str, Any],
        seed: int,
        ticks: int | None = None,
        capture_verbose: bool = False,  # NEW parameter
    ) -> SimulationResult:
        """Run a single simulation with the given policy.

        Args:
            policy: Policy to evaluate (applied to all agents).
            seed: RNG seed for determinism.
            ticks: Number of ticks to run (default: full day).
            capture_verbose: If True, capture tick-by-tick events.

        Returns:
            SimulationResult with costs, metrics, and optional verbose output.
        """
```

### Phase 6: Implementation - Monte Carlo Context Building

**File**: `experiments/castro/castro/context_builder.py`

```python
"""Build per-agent context from Monte Carlo simulation results.

This module:
1. Identifies best/worst seeds per agent
2. Extracts filtered verbose output for each
3. Builds SingleAgentContext for each agent
"""

from dataclasses import dataclass
from payment_simulator.ai_cash_mgmt.prompts import (
    SingleAgentContext,
    SingleAgentContextBuilder,
    SingleAgentIterationRecord,
)


@dataclass
class AgentSimulationContext:
    """Context data for a single agent from Monte Carlo samples.

    Attributes:
        agent_id: Agent identifier
        best_seed: Seed that produced lowest cost for this agent
        best_seed_cost: Cost at best seed
        best_seed_output: Filtered verbose output from best seed
        worst_seed: Seed that produced highest cost for this agent
        worst_seed_cost: Cost at worst seed
        worst_seed_output: Filtered verbose output from worst seed
        mean_cost: Mean cost across all samples
        cost_std: Standard deviation of costs
    """
    agent_id: str
    best_seed: int
    best_seed_cost: int
    best_seed_output: str
    worst_seed: int
    worst_seed_cost: int
    worst_seed_output: str
    mean_cost: float
    cost_std: float


class MonteCarloContextBuilder:
    """Builds per-agent context from Monte Carlo samples.

    After running multiple simulations with different seeds,
    this class:
    1. Identifies best/worst seeds per agent (by agent's cost)
    2. Extracts filtered verbose output for those seeds
    3. Computes per-agent metrics

    Example:
        >>> builder = MonteCarloContextBuilder(results, verbose_outputs)
        >>> context = builder.build_context_for_agent("BANK_A")
    """

    def __init__(
        self,
        results: list[SimulationResult],
        seeds: list[int],
    ) -> None:
        """Initialize with Monte Carlo results.

        Args:
            results: List of SimulationResult from each sample
            seeds: List of seeds used (parallel to results)
        """

    def build_context_for_agent(
        self,
        agent_id: str,
        iteration: int,
        current_policy: dict,
        iteration_history: list[SingleAgentIterationRecord],
        cost_rates: dict,
    ) -> SingleAgentContext:
        """Build complete context for a single agent.

        Args:
            agent_id: Agent to build context for
            iteration: Current iteration number
            current_policy: Agent's current policy
            iteration_history: Previous iterations for this agent
            cost_rates: Cost rate configuration

        Returns:
            SingleAgentContext ready for SingleAgentContextBuilder
        """

    def get_best_seed_for_agent(self, agent_id: str) -> tuple[int, int]:
        """Get best seed and cost for an agent.

        Returns:
            Tuple of (seed, cost) where cost is lowest for this agent
        """

    def get_worst_seed_for_agent(self, agent_id: str) -> tuple[int, int]:
        """Get worst seed and cost for an agent.

        Returns:
            Tuple of (seed, cost) where cost is highest for this agent
        """
```

### Phase 7: Implementation - ExperimentRunner Integration

**File**: `experiments/castro/castro/runner.py` (modify existing)

Changes to `ExperimentRunner`:

1. Enable verbose capture in Monte Carlo evaluation
2. Build per-agent context using `MonteCarloContextBuilder`
3. Use `SingleAgentContextBuilder` to create prompts
4. Pass verbose context to `PolicyOptimizer`

```python
async def _evaluate_policies(
    self, iteration: int
) -> tuple[int, dict[str, int], MonteCarloContextBuilder]:
    """Evaluate current policies across Monte Carlo samples.

    Now returns MonteCarloContextBuilder for accessing verbose context.
    """

async def _optimize_agent_policy(
    self,
    agent_id: str,
    iteration: int,
    context_builder: MonteCarloContextBuilder,
) -> OptimizationResult:
    """Optimize policy for a single agent with full verbose context."""

    # Build agent-specific context
    agent_context = context_builder.build_context_for_agent(
        agent_id=agent_id,
        iteration=iteration,
        current_policy=self._policies[agent_id],
        iteration_history=self._iteration_history.get(agent_id, []),
        cost_rates=self._get_cost_rates(),
    )

    # Build prompt using SingleAgentContextBuilder
    prompt_builder = SingleAgentContextBuilder(agent_context)
    full_prompt = prompt_builder.build()

    # Pass to optimizer
    ...
```

### Phase 8: Implementation - LLM Client Enhancement

**File**: `experiments/castro/castro/llm_client.py` (modify existing)

Replace minimal prompt building with `SingleAgentContextBuilder` integration:

```python
async def generate_policy(
    self,
    prompt: str,  # Now receives full context from SingleAgentContextBuilder
    current_policy: dict[str, Any],
    context: dict[str, Any],  # Kept for backwards compatibility
) -> dict[str, Any]:
    """Generate improved policy via LLM.

    The prompt now contains the full verbose context built by
    SingleAgentContextBuilder, including tick-by-tick simulation output.
    """
```

## Test Execution Order

1. Run Phase 1 tests first (verbose capture unit tests)
2. Run Phase 2 tests (agent context unit tests)
3. Implement Phase 4 (VerboseOutputCapture)
4. Run Phase 1 tests - should pass
5. Implement Phase 5 (SimulationRunner enhancement)
6. Run Phase 2 tests - should pass
7. Implement Phase 6 (MonteCarloContextBuilder)
8. Implement Phase 7 (ExperimentRunner integration)
9. Run Phase 3 integration tests
10. Implement Phase 8 (LLM client enhancement)
11. Run full test suite

## Verification Checklist

After implementation, verify:

- [ ] Verbose output is captured during simulation
- [ ] Events are correctly filtered per agent
- [ ] Agent A never sees Agent B's arrivals
- [ ] Agent A sees settlements where it receives money
- [ ] Best/worst seeds are selected per agent
- [ ] Context contains 30k+ tokens of verbose output
- [ ] SingleAgentContextBuilder produces valid prompts
- [ ] LLM receives full context in API calls
- [ ] Same seed produces identical verbose output (determinism)
- [ ] Integration tests pass

## Risk Mitigation

### Risk: Performance overhead of verbose capture
**Mitigation**: Only capture verbose for best/worst seeds after identifying them, not all samples.

### Risk: Context too large for LLM
**Mitigation**: Models with 200k+ context windows (Claude, GPT-4) can handle 50k tokens easily. Monitor token counts.

### Risk: EventFilter doesn't handle all event types
**Mitigation**: Existing tests in `test_filtered_replay_for_castro.py` verify filter correctness. Add tests for any new event types.

## Success Criteria

1. All unit tests pass
2. All integration tests pass
3. LLM prompt contains tick-by-tick verbose output
4. Each agent's context is properly isolated
5. Verbose output is deterministic (same seed = same output)
6. Context size is 30k-80k tokens (verified by logging)

## Timeline

No time estimates provided per project guidelines. Implementation should follow TDD principles with tests written before each phase.

---

*Plan created: 2025-12-09*
*Based on analysis of original implementation in commit c7c3513^*
