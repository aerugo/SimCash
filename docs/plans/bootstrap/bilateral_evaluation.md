# Bilateral Bootstrap Evaluation - Development Plan

**Created**: 2025-12-13
**Status**: Planning
**Priority**: Critical - Current sandbox evaluation produces invalid results

---

## Problem Statement

### Current Architecture (Broken)

The current bootstrap evaluation uses a **3-agent sandbox**:
```
SOURCE → AGENT → SINK
```

This removes bilateral constraints that exist in the main simulation:
- SOURCE has infinite liquidity
- SINK always accepts (infinite capacity)
- No bilateral settlement interactions

### Why This Is Wrong

In the **main simulation** with 2 agents (BANK_A, BANK_B):
1. BANK_A releases payment → settles via RTGS
2. BANK_B receives liquidity from that settlement
3. BANK_B can now settle its queued payments
4. This causal chain affects timing, delays, and costs

In the **sandbox**:
1. AGENT releases payment → SINK always accepts
2. No liquidity constraints from counterparty
3. All transactions settle immediately
4. Costs only reflect collateral, not transaction timing

### Evidence of the Problem

Experiment 2 results:
- **Baseline costs vary**: $5,065 - $5,280 across samples (transaction-dependent)
- **Paired deltas identical**: -$1,764 for ALL 50 samples (purely collateral cost)

The deltas should vary because different bootstrap samples have different transactions.
Instead, they're identical because only collateral cost differs between policies.

---

## Design Requirement

**Bootstrap evaluation MUST use the same evaluation path as the main simulation.**

Specifically:
1. Same orchestrator engine (Rust FFI)
2. Same bilateral agent structure (all scenario agents)
3. Same settlement mechanics (RTGS, queuing, LSM)
4. Same cost calculation (delay, collateral, overdraft, etc.)

The ONLY difference should be:
- Main simulation: stochastic transaction arrivals (`arrival_config`)
- Bootstrap evaluation: fixed transaction arrivals (`scenario_events`)

---

## Solution Architecture

### Key Insight

We don't need a new evaluator. We need to:
1. Convert bootstrap samples to `scenario_events`
2. Run the FULL scenario config (not sandbox)
3. Extract target agent's costs

### Data Flow

```
Initial Simulation (stochastic arrivals)
    ↓
TransactionHistoryCollector extracts per-agent history
    ↓
BootstrapSampler resamples to create BootstrapSamples
    ↓
BilateralConfigBuilder converts samples to scenario_events
    ↓
Full bilateral simulation (same engine as main)
    ↓
Extract target agent costs for policy comparison
```

### Key Change: Combined Samples

Current: Per-agent samples evaluated in isolation
```python
self._bootstrap_samples = {
    "BANK_A": [sample_a_0, sample_a_1, ...],
    "BANK_B": [sample_b_0, sample_b_1, ...],
}
```

New: Combined samples for bilateral simulation
```python
self._combined_bootstrap_samples = [
    {"BANK_A": sample_a_0, "BANK_B": sample_b_0},  # Sample set 0
    {"BANK_A": sample_a_1, "BANK_B": sample_b_1},  # Sample set 1
    ...
]
```

---

## Phased Implementation Plan

### Phase 1: BilateralConfigBuilder

**Goal**: Build a SimulationConfig from bootstrap samples that uses the full bilateral structure.

**Files to create/modify**:
- `api/payment_simulator/ai_cash_mgmt/bootstrap/bilateral_config.py` (new)

**Key methods**:
```python
class BilateralConfigBuilder:
    def __init__(self, base_config: SimulationConfig) -> None:
        """Initialize with original scenario config."""

    def build_config(
        self,
        agent_samples: dict[str, BootstrapSample],
        target_agent_id: str,
        target_policy: dict[str, Any],
        seed: int,
    ) -> SimulationConfig:
        """Build bilateral config with scenario_events from samples."""
```

**TDD Tests**:
```python
def test_bilateral_config_preserves_all_agents():
    """All scenario agents appear in bilateral config."""

def test_bilateral_config_uses_scenario_events():
    """Bootstrap transactions become scenario_events, not arrival_config."""

def test_bilateral_config_applies_target_policy():
    """Target agent gets test policy, others keep original."""

def test_bilateral_config_preserves_cost_rates():
    """Cost rates match original scenario."""
```

---

### Phase 2: BilateralPolicyEvaluator

**Goal**: Evaluator that runs full bilateral simulations.

**Files to create/modify**:
- `api/payment_simulator/ai_cash_mgmt/bootstrap/bilateral_evaluator.py` (new)

**Key methods**:
```python
class BilateralPolicyEvaluator:
    def __init__(self, base_config: SimulationConfig) -> None:
        """Initialize with original scenario config."""

    def evaluate_sample(
        self,
        agent_samples: dict[str, BootstrapSample],
        target_agent_id: str,
        target_policy: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate policy using full bilateral simulation."""

    def compute_paired_deltas(
        self,
        all_agent_samples: list[dict[str, BootstrapSample]],
        target_agent_id: str,
        policy_a: dict[str, Any],
        policy_b: dict[str, Any],
    ) -> list[PairedDelta]:
        """Compute paired deltas across combined sample sets."""
```

**TDD Tests**:
```python
def test_bilateral_evaluator_uses_full_simulation():
    """Evaluation runs through Orchestrator, not sandbox."""

def test_bilateral_evaluator_preserves_bilateral_interactions():
    """Settlement from A→B affects B's liquidity."""

def test_bilateral_evaluator_costs_match_main_simulation():
    """Same transactions produce same costs as main simulation."""
```

---

### Phase 3: Combined Bootstrap Samples

**Goal**: Modify sample creation to produce combined sample sets.

**Files to modify**:
- `api/payment_simulator/experiments/runner/optimization.py`

**Changes**:
```python
# Current
self._bootstrap_samples: dict[str, list[BootstrapSample]] = {}

# New (add)
self._combined_samples: list[dict[str, BootstrapSample]] = []

def _create_combined_bootstrap_samples(self) -> None:
    """Create combined sample sets for bilateral evaluation."""
    num_samples = self._config.evaluation.num_samples or 1

    for i in range(num_samples):
        sample_set = {}
        for agent_id in self.optimized_agents:
            if agent_id in self._bootstrap_samples:
                sample_set[agent_id] = self._bootstrap_samples[agent_id][i]
        self._combined_samples.append(sample_set)
```

**TDD Tests**:
```python
def test_combined_samples_include_all_agents():
    """Each combined sample set includes all agent samples."""

def test_combined_samples_match_by_index():
    """Sample index i from each agent maps to combined set i."""
```

---

### Phase 4: Wire Bilateral Evaluator into OptimizationLoop

**Goal**: Replace sandbox evaluation with bilateral evaluation.

**Files to modify**:
- `api/payment_simulator/experiments/runner/optimization.py`

**Changes to `_evaluate_policy_pair`**:
```python
def _evaluate_policy_pair(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> tuple[list[int], int]:
    if self._combined_samples:
        evaluator = BilateralPolicyEvaluator(self._base_scenario_config)
        paired_deltas = evaluator.compute_paired_deltas(
            all_agent_samples=self._combined_samples,
            target_agent_id=agent_id,
            policy_a=old_policy,
            policy_b=new_policy,
        )
        deltas = [d.delta for d in paired_deltas]
        return deltas, sum(deltas)
```

**TDD Tests**:
```python
def test_evaluate_policy_pair_uses_bilateral_evaluator():
    """Policy pair evaluation uses BilateralPolicyEvaluator."""

def test_evaluate_policy_pair_produces_varied_deltas():
    """Different samples produce different deltas (not all identical)."""
```

---

### Phase 5: Validation - Evaluation Path Equivalence

**Goal**: Prove that bilateral evaluation produces the same results as main simulation.

**Validation approach**:
1. Run main simulation with seed S, collect transactions
2. Create bootstrap sample with those exact transactions
3. Run bilateral evaluation with seed S
4. Costs must match exactly

**TDD Tests**:
```python
def test_bilateral_evaluation_matches_main_simulation():
    """Same transactions produce identical costs."""
    # Run main simulation
    main_cost = run_main_simulation(seed=12345)

    # Extract transactions as bootstrap sample
    sample = extract_transactions_as_sample(events)

    # Run bilateral evaluation with same seed
    bilateral_cost = bilateral_evaluator.evaluate_sample(sample, policy)

    assert main_cost == bilateral_cost
```

---

## Files Changed Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `bootstrap/bilateral_config.py` | New | Builds bilateral configs from samples |
| `bootstrap/bilateral_evaluator.py` | New | Runs bilateral simulations |
| `experiments/runner/optimization.py` | Modify | Wire new evaluator, combined samples |
| `tests/integration/test_bilateral_bootstrap.py` | New | TDD tests for bilateral evaluation |

---

## Success Criteria

- [ ] All TDD tests pass
- [ ] Bilateral evaluation produces varied deltas across samples
- [ ] Same transactions produce identical costs in main vs bilateral evaluation
- [ ] Experiment 2 shows meaningful policy comparisons (not just collateral cost)

---

## Risk Assessment

### Risk 1: Performance
**Concern**: Bilateral simulation is heavier than sandbox (more agents, interactions)
**Mitigation**: 50 samples × 2 policies × 12 ticks is still fast (<1s per sample)

### Risk 2: Sample Alignment
**Concern**: Agent samples might have different counts or indices
**Mitigation**: Validate alignment in `_create_combined_bootstrap_samples()`

### Risk 3: Base Config Access
**Concern**: OptimizationLoop needs the original SimulationConfig
**Mitigation**: Store `self._base_scenario_config` when building FFI config

---

## Next Steps

1. Create `tests/integration/test_bilateral_bootstrap.py` with Phase 1 tests
2. Implement `BilateralConfigBuilder` to pass tests
3. Continue phases sequentially with TDD

---

## References

- Current sandbox implementation: `bootstrap/sandbox_config.py`
- Current evaluator: `bootstrap/evaluator.py`
- OptimizationLoop: `experiments/runner/optimization.py`
- Feature request: `docs/requests/implement-real-bootstrap-evaluation.md`
