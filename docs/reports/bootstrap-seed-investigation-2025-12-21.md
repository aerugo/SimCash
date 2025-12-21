# Bootstrap Seed Investigation Report

**Date**: 2025-12-21
**Investigator**: Claude
**Branch**: `claude/investigate-bootstrap-seeds-UhOXb`

---

## Executive Summary

**Finding**: The bootstrap seed design does NOT match the expected behavior. The current implementation reuses the same bootstrap samples across all iterations, rather than generating fresh samples per iteration.

| Aspect | Expected Design | Actual Implementation |
|--------|----------------|----------------------|
| Initial simulation seed | Per-iteration (iteration_seed) | Once (master_seed) |
| Bootstrap samples | Regenerated each iteration | Created once, reused all iterations |
| Total unique seeds | 50 iterations × 50 samples = 2,500 | 1 initial + 50 samples = 51 |
| Seed hierarchy | master → iteration → bootstrap | master → bootstrap (iteration skipped) |

---

## Expected Design (User's Specification)

The user specified the following design:

1. **Master seed**: All experiments share the same master seed for reproducibility
2. **Iteration seeds**: At experiment start, generate 50 iteration seeds from master seed
3. **Per-iteration context simulation**: Each iteration runs context simulation with its iteration-specific seed
4. **Per-iteration bootstrap seeds**: Each iteration generates 50 bootstrap seeds using the iteration seed as the base

This would result in:
- 50 different context simulations (one per iteration, each with unique seed)
- 50 × 50 = 2,500 bootstrap samples across the experiment
- Full exploration of stochastic space while maintaining reproducibility

---

## Actual Implementation (Current Code)

### SeedMatrix Structure (Correct)

The `SeedMatrix` class (`api/payment_simulator/experiments/runner/seed_matrix.py`) is correctly designed:

```python
@dataclass
class SeedMatrix:
    """Pre-generated seed matrix for deterministic bootstrap evaluation.

    Seeds are generated hierarchically:
    - master_seed -> iteration_seed (per iteration per agent)
    - iteration_seed -> bootstrap_seed (per sample within agent evaluation)
    """
```

It provides:
- `get_iteration_seed(iteration, agent_id)` - unique seed per iteration
- `get_bootstrap_seed(iteration, agent_id, sample_idx)` - unique seed per sample per iteration

### Bootstrap Mode Usage (INCORRECT)

However, bootstrap mode does NOT use this hierarchy correctly:

#### 1. Initial Simulation Uses master_seed Directly

**File**: `api/payment_simulator/experiments/runner/optimization.py`, lines 1467-1472

```python
def _run_initial_simulation(self) -> InitialSimulationResult:
    result = self._run_simulation(
        seed=self._config.master_seed,  # ❌ Uses master_seed, not iteration_seed
        purpose="init",
        iteration=0,
        is_primary=True,
    )
```

**Problem**: The context simulation runs ONCE with master_seed, not per-iteration with iteration_seed.

#### 2. Bootstrap Samples Created Once, Reused Forever

**File**: `api/payment_simulator/experiments/runner/optimization.py`, lines 1499-1530

```python
def _create_bootstrap_samples(self) -> None:
    self._bootstrap_sampler = BootstrapSampler(seed=self._config.master_seed)  # ❌ Fixed seed

    for agent_id in self.optimized_agents:
        samples = self._bootstrap_sampler.generate_samples(...)
        self._bootstrap_samples[agent_id] = list(samples)  # Stored once
```

Then in `_evaluate_policies()` (line 1768):
```python
for agent_id in self.optimized_agents:
    samples = self._bootstrap_samples.get(agent_id, [])  # ❌ Same samples every iteration
```

**Problem**: Bootstrap samples are created once at experiment start and reused for all 50 iterations.

#### 3. SeedMatrix Bootstrap Seeds Are UNUSED

Despite the SeedMatrix having `get_bootstrap_seeds()` available, bootstrap mode never calls it:

```python
# This method exists but is NEVER called in bootstrap mode:
bootstrap_seeds = self._seed_matrix.get_bootstrap_seeds(iteration, agent_id)
```

The only usage of `get_iteration_seed()` is in deterministic modes (lines 1733, 1904).

---

## Visualization: Current vs Expected

### Current Flow (Incorrect)

```
Experiment Start:
├── _run_initial_simulation()
│   └── Uses master_seed (fixed)
│
├── _create_bootstrap_samples()
│   └── Uses BootstrapSampler(master_seed)
│       └── Creates 50 samples (fixed for entire experiment)
│
└── Optimization Loop (50 iterations):
    ├── Iteration 1: Uses same 50 samples
    ├── Iteration 2: Uses same 50 samples
    ├── ...
    └── Iteration 50: Uses same 50 samples
```

### Expected Flow (Per User Spec)

```
Experiment Start:
└── Generate 50 iteration_seeds from master_seed

Optimization Loop (50 iterations):
├── Iteration 1:
│   ├── Run context simulation with iteration_seed[0]
│   └── Generate 50 bootstrap samples using iteration_seed[0]
│
├── Iteration 2:
│   ├── Run context simulation with iteration_seed[1]
│   └── Generate 50 bootstrap samples using iteration_seed[1]
│
├── ...
│
└── Iteration 50:
    ├── Run context simulation with iteration_seed[49]
    └── Generate 50 bootstrap samples using iteration_seed[49]
```

---

## Implications

### Statistical Impact

1. **Reduced exploration**: The same 50 transaction schedules are tested every iteration, limiting the stochastic exploration space.

2. **Potential overfitting**: Policies may optimize for the specific 50 samples rather than the underlying distribution.

3. **Variance underestimation**: The bootstrap variance reflects only the initial simulation's transaction history, not the full stochastic space.

### Why This Might Have Been Intentional

There is evidence this was a deliberate design choice for bootstrap mode:

1. **Commit 058d1bc** (Dec 20, 2025): "Fix bootstrap evaluation to use proper resampling instead of Monte Carlo"
   - Explicitly states: "LLM context comes from ONE simulation"
   - Removed Monte Carlo sampling in favor of single-simulation bootstrap

2. **Documentation** (`docs/reference/ai_cash_mgmt/evaluation-methodology.md`):
   - Section "Bootstrap vs Monte Carlo" explains why ONE initial simulation is used
   - Rationale: "Same transactions used for both policy_A and policy_B" enables paired comparison

3. **3-Agent Sandbox Architecture**:
   - Bootstrap evaluates policies on isolated sandbox (SOURCE → AGENT → SINK)
   - This is fundamentally different from full simulation

### Design Rationale (Documentation)

From `evaluation-methodology.md`:

> **Bootstrap (Non-parametric)**
>
> Resample from observed transactions:
> ```python
> # One simulation to collect history
> orch = Orchestrator.new(config_with_arrivals)
> orch.run()
> history = collect_transactions(orch.events)
>
> # Resample from history
> for sample in range(N):
>     transactions = resample_with_replacement(history)
>     # Same transactions used for both policy_A and policy_B
> ```
>
> **Advantage**: Same transactions → paired comparison → lower variance → faster convergence.

---

## Critical Questions

Before deciding whether to "fix" this, consider:

### 1. Was the Original Design Different?

The SeedMatrix was clearly designed with iteration-specific seeds in mind, suggesting the original intent matched the user's expectation. However, the bootstrap implementation was later changed (commit 058d1bc) to use a single initial simulation.

### 2. What Problem Was Commit 058d1bc Solving?

The commit message states:
> "A Rust FFI bug where seeds don't affect stochastic arrivals meant all 'different' seeds produced identical results"

This suggests there was a deeper issue with seed propagation to the Rust simulation engine.

### 3. Is the Current Design Valid for the Research Goals?

The current design is statistically valid for:
- Testing policy robustness on a fixed transaction distribution
- Enabling paired comparison for acceptance decisions
- Fast convergence through variance reduction

But it does NOT:
- Explore the full stochastic space
- Generate 2,500 unique seeds as the user expected
- Use iteration-specific context simulations

---

## Recommendations

### Option A: Keep Current Design (Documented)

If the current design is intentional and meets research goals:
1. Update CLAUDE.md to document the actual seed behavior
2. Clarify in exp2.yaml that num_samples refers to resampling, not unique simulations
3. Remove or repurpose the unused `get_bootstrap_seeds()` method from SeedMatrix

### Option B: Implement Expected Design

If the original design should be restored:
1. Modify `_run_initial_simulation()` to run per-iteration with iteration_seed
2. Modify `_create_bootstrap_samples()` to regenerate samples each iteration
3. Use SeedMatrix's `get_bootstrap_seeds()` for sample generation
4. Investigate and fix the Rust FFI seed propagation bug mentioned in 058d1bc

### Option C: Hybrid Approach

Run context simulation per-iteration (for exploration) but keep fixed bootstrap samples per-iteration (for paired comparison):
1. Run 50 context simulations (one per iteration, different seeds)
2. Each context simulation generates its own 50 bootstrap samples
3. Samples are fixed within an iteration but vary across iterations

---

## Files Analyzed

| File | Relevance |
|------|-----------|
| `api/payment_simulator/experiments/runner/optimization.py` | Core optimization loop, bootstrap logic |
| `api/payment_simulator/experiments/runner/seed_matrix.py` | Seed generation infrastructure (correctly designed) |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/sampler.py` | Bootstrap sample generation |
| `docs/reference/ai_cash_mgmt/evaluation-methodology.md` | Design rationale for bootstrap |
| Commit `058d1bc` | Change that implemented current behavior |

---

## Git History References

- **PR #328**: Introduced SeedMatrix with hierarchical seed design
- **Commit 058d1bc**: Changed bootstrap to use single simulation + resampling
- **Commit bf6e75e**: Clarified bootstrap methodology in Exp2 results

---

*Report generated during investigation of bootstrap seed behavior for exp2 experiments.*
