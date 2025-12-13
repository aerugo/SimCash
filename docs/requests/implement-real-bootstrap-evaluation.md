# Feature Request: Implement Real Bootstrap Evaluation

**Date**: 2025-12-13
**Priority**: High
**Affects**: Experiment framework, policy evaluation, LLM context

## Summary

The current "bootstrap" evaluation in the experiment runner is **not actually bootstrap** - it's parametric Monte Carlo simulation. This request asks for implementation of the originally designed bootstrap methodology where:

1. A **single simulation run** produces historical transaction data (the SOURCE)
2. **Bootstrap samples** resample from that historical data with replacement
3. Policy evaluation uses these resampled scenarios

## Current Implementation (Incorrect)

In `api/payment_simulator/experiments/runner/optimization.py`:

```python
def _evaluate_policy_with_seed(self, policy, agent_id, seed):
    # Runs a COMPLETE NEW SIMULATION for each "sample"
    _, agent_costs = self._run_single_simulation(seed)
    return agent_costs.get(agent_id, 0)
```

The current flow:
1. For each of 50 "bootstrap samples", run a **complete independent simulation** with a different RNG seed
2. Each "sample" generates entirely new transactions via parametric distributions (Poisson arrivals, LogNormal amounts)
3. Best/worst samples are identified by cost

**This is Monte Carlo simulation, not bootstrap.**

## Intended Design (From Documentation)

### From `docs/legacy/grand_plan.md`:

```
Parametric Monte Carlo:
  "Assume arrivals follow Poisson(λ=5). Generate synthetic days."
  Problem: How do we know λ=5 is correct?

Bootstrap (what we want):
  "Use yesterday's actual arrivals. Resample them with replacement."
  Advantage: No distribution assumptions. Uses real observed data.
```

> "Bootstrap treats the empirical distribution of observed data as an approximation of the unknown true distribution."

### From `docs/game_concept_doc.md`:

> "When historical transactions are used for policy evaluation, the **timing offsets are preserved**:
> - `deadline_offset = deadline_tick - arrival_tick`
> - `settlement_offset = settlement_tick - arrival_tick`
>
> If a historical transaction took 5 ticks to settle, that 5-tick offset is preserved when the transaction is resampled."

### Key Concept: "Liquidity Beats"

From the glossary:
> **Liquidity Beats**: The sequence of incoming settlements treated as fixed external events in bootstrap evaluation—defines when an agent receives liquidity from counterparties.

This means the bootstrap should preserve the **actual timing patterns** observed in a real simulation, not generate new ones from parametric distributions.

## Existing Infrastructure (Unused)

The `TransactionSampler` class in `api/payment_simulator/ai_cash_mgmt/sampling/transaction_sampler.py` **already implements proper bootstrap**:

```python
class TransactionSampler:
    """Samples transactions from historical data for bootstrap evaluation."""

    def collect_transactions(self, transactions: list[dict]):
        """Collect transactions from simulation state."""
        # Stores HistoricalTransaction objects

    def _bootstrap_sample(self, transactions, num_samples):
        """Bootstrap resampling (with replacement)."""
        n = len(transactions)
        for _ in range(num_samples):
            indices = self._rng.integers(0, n, size=n)
            samples.append([transactions[i] for i in indices])
        return samples
```

This infrastructure exists but is **not wired into the experiment runner**.

## Requested Changes

### 1. Initial Simulation Run

Before policy optimization, run ONE canonical simulation on the scenario config:

```python
# Pseudocode for what's needed
def run_experiment(scenario_config):
    # Step 1: Run initial simulation (like `payment-sim run --verbose`)
    orchestrator = create_orchestrator(scenario_config)
    run_full_simulation(orchestrator)

    # Step 2: Collect historical transactions
    sampler = TransactionSampler(seed=master_seed)
    sampler.collect_transactions(orchestrator.get_all_transactions())

    # Step 3: Store verbose output for LLM context
    initial_simulation_output = capture_verbose_output(orchestrator)

    # Step 4: Begin optimization loop
    for iteration in range(max_iterations):
        # Bootstrap samples resample FROM the initial simulation
        samples = sampler.create_samples(agent_id, num_samples=50)
        evaluate_policy_on_bootstrap_samples(policy, samples)
```

### 2. Bootstrap Sample Evaluation

Each bootstrap sample should:
1. Start with resampled transactions from the historical data
2. Remap arrival ticks (preserving deadline offsets)
3. Run simulation with those fixed transaction arrivals
4. Measure policy cost

```python
def evaluate_on_bootstrap_sample(policy, sample: list[HistoricalTransaction]):
    """Evaluate policy against a bootstrap sample."""
    # Create orchestrator with fixed transaction schedule
    orchestrator = create_orchestrator_with_transactions(sample)
    orchestrator.set_policy(agent_id, policy)
    run_simulation(orchestrator)
    return orchestrator.get_agent_cost(agent_id)
```

### 3. LLM Context Update

The LLM should receive THREE event streams:
1. **Primary simulation output** - Full verbose trace from the initial simulation
2. **Best bootstrap sample** - Events from sample with lowest cost
3. **Worst bootstrap sample** - Events from sample with highest cost

Currently only #2 and #3 are included (and they're from Monte Carlo, not bootstrap).

### 4. Transaction Remapping

When resampling, preserve relative timing:
```python
@dataclass
class RemappedTransaction:
    original: HistoricalTransaction
    new_arrival_tick: int  # Sampled uniformly or from distribution

    @property
    def deadline_tick(self):
        # Preserve deadline offset from original
        offset = self.original.deadline_tick - self.original.arrival_tick
        return self.new_arrival_tick + offset
```

## Impact on Castro Experiments

### Experiment 1 (2-Period Deterministic)

For deterministic scenarios with fixed `scenario_events`, bootstrap doesn't apply - there's only one possible transaction schedule. The current approach (running the scenario once per sample) is actually correct for this case.

**No change needed for exp1.**

### Experiment 2 & 3 (Stochastic)

For stochastic scenarios with `arrival_configs`, the flow should be:
1. Run ONE simulation with arrival generation enabled
2. Collect all generated transactions
3. Bootstrap samples resample from those transactions
4. Evaluate policy on resampled transaction schedules

This provides statistical confidence based on **observed** transaction patterns rather than **assumed** parametric distributions.

## Acceptance Criteria

1. [ ] Initial simulation produces `initial_simulation_output` for LLM context
2. [ ] `TransactionSampler.collect_transactions()` is called after initial simulation
3. [ ] Bootstrap samples use `TransactionSampler.create_samples()` with `method="bootstrap"`
4. [ ] Each bootstrap evaluation uses resampled transactions (not parametric generation)
5. [ ] LLM prompt includes all three event streams
6. [ ] Deterministic scenarios (exp1) continue to work correctly
7. [ ] Tests verify bootstrap is resampling, not regenerating

## Related Documentation

- `docs/legacy/grand_plan.md` - Section on "Theoretical Foundation: Bootstrap Resampling"
- `docs/game_concept_doc.md` - Section on "Policy Evaluation" and "Liquidity Beats"
- `api/payment_simulator/ai_cash_mgmt/sampling/transaction_sampler.py` - Existing bootstrap infrastructure

## Original Bootstrap Refactor Plans (Deleted)

The detailed implementation plans were deleted in commit `4de5753`. They can be recovered from git history:

```bash
# View the conceptual plan (comprehensive theory + architecture)
git show 4de5753^:docs/plans/bootstrap-refactor/refactor-conceptual-plan.md

# View the TDD development plan (implementation details)
git show 4de5753^:docs/plans/bootstrap-refactor/development-plan.md
```

### Key Excerpts from Original Plans

**From `refactor-conceptual-plan.md` (v2.8):**

> "Bootstrap treats the empirical distribution of observed data as an approximation of the true unknown distribution."

> **Transaction Remapping**: "When a historical transaction is bootstrapped, we preserve its **relative timing** (offsets from arrival) while assigning a **new arrival tick**"

> **Liquidity Beats**: "We treat incoming settlements as **fixed external events** that define when Agent A receives liquidity."

The original plan specified:
- **TransactionRecord** with `deadline_offset` and `settlement_offset` (relative timing)
- **RemappedTransaction** with absolute ticks after bootstrap remapping
- **BootstrapSample** containing outgoing transactions and incoming settlements ("liquidity beats")
- **3-agent sandbox** (Agent, SINK, SOURCE) for evaluation

**From `development-plan.md` (v1.1):**

The TDD plan included 6 phases:
1. Data Structures (TransactionRecord, RemappedTransaction, BootstrapSample)
2. History Collector (parse simulation events, compute offsets)
3. Bootstrap Sampler (deterministic resampling with replacement)
4. Sandbox Config Builder (3-agent setup with scenario_events)
5. Policy Evaluator (paired comparison for delta calculation)
6. Castro Integration

These plans were complete and ready for implementation but were deleted before being fully implemented.

## Related Commits

- `20423e0` - "refactor(terminology): Rename Monte Carlo to Bootstrap (Phase 4.6)"
  - Commit message: "Bootstrap resampling is the correct term for sampling with replacement from historical data, not Monte Carlo."
- `9fd1836` - "refactor(castro): Complete bootstrap terminology migration (Phase 8)"
- `082b4b6` - "feat: implement bootstrap evaluation mode in OptimizationLoop"
- `4de5753` - "Delete docs/plans/bootstrap-refactor directory" (plans deleted before completion)

## Notes

The terminology was renamed from "Monte Carlo" to "Bootstrap" in Phase 4.6, but the underlying implementation remained parametric Monte Carlo. The detailed implementation plans existed (see git history) but were deleted before the actual bootstrap resampling was implemented.

**This request is to complete the original design** by implementing actual bootstrap methodology as specified in the deleted plans.
