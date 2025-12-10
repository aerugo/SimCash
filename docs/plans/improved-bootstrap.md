# Bootstrap-Based Monte Carlo Policy Evaluation

**Status**: Draft
**Author**: Claude
**Date**: 2025-12-10
**Version**: 1.0

---

## Overview

This plan describes the implementation of bootstrap-based Monte Carlo policy evaluation for the Castro experiment system. The current implementation incorrectly uses different random seeds to generate synthetic transaction streams. The correct approach uses bootstrap resampling from **observed historical transactions** to evaluate policies without parametric assumptions about arrival distributions.

---

## Problem Statement

### Current (Incorrect) Implementation

The current Monte Carlo evaluation in `castro/runner.py`:

```python
for sample_idx in range(num_samples):
    seed = self._seed_manager.simulation_seed(sample_idx)  # Different seed
    result = self._sim_runner.run_simulation(
        policy=policy,
        seed=seed,  # Generates NEW synthetic transactions
        ...
    )
```

**Issues**:
1. **Assumes known distribution**: Uses Poisson/LogNormal to generate new arrivals
2. **Parallel universes**: Each sample is a completely independent simulation
3. **Not realistic**: Real agents can't know the underlying arrival distribution
4. **Doesn't test policy robustness**: Tests "what if different transactions existed" rather than "how robust is this policy to uncertainty in observed data"

### Correct Bootstrap Approach

Bootstrap sampling evaluates policies by resampling from **actually observed transactions**:

1. Run ONE real simulation with current policy → observe transaction history
2. For each agent A, collect:
   - Outgoing transactions (where A is sender)
   - Incoming settlements (where A is receiver) with settlement timing
3. Bootstrap resample (with replacement) to create synthetic scenarios
4. Evaluate policy cost on each bootstrap sample
5. Aggregate statistics (mean, std, confidence intervals)

**Key insight**: Incoming settlements define **fixed "liquidity beats"** - the agent cannot control when counterparties pay them, so this timing is treated as exogenous.

---

## Design Decision: Python vs Rust

### Analysis

| Factor | Python Implementation | Rust Implementation |
|--------|----------------------|---------------------|
| **FFI complexity** | No FFI needed | Adds new FFI surface |
| **Cost model** | Re-implement simplified model | Reuse existing CostRates |
| **Multi-agent dynamics** | Not needed (single-agent eval) | Full simulation overkill |
| **Existing foundation** | TransactionSampler exists | Would start from scratch |
| **Development speed** | Fast iteration | Slower, more testing |
| **Performance** | ~1ms per eval adequate | ~0.1ms per eval possible |
| **Research flexibility** | Easy to experiment | Harder to modify |

### Decision: Python First

**Rationale**:

1. **Bootstrap evaluation is fundamentally different** from full simulation:
   - No multi-agent settlement dynamics
   - No LSM/RTGS queuing
   - No gridlock resolution
   - Single-agent perspective only

2. **FFI Boundary Principle** (from `docs/reference/architecture/04-ffi-boundary.md`):
   > "Batch operations. One FFI call per tick, not per transaction."

   Bootstrap evaluation would require either:
   - Many FFI calls to query transaction state, OR
   - A completely new Rust API for bootstrap-specific operations

   Neither aligns with the "minimal FFI surface" principle.

3. **TransactionSampler already exists** in Python with bootstrap, permutation, and stratified methods.

4. **Performance is adequate**: With 10 MC samples × 25 iterations × 2 agents × ~50 transactions, we have ~25,000 lightweight evaluations. At 1ms each, that's 25 seconds - acceptable for an LLM-driven optimization loop that takes minutes per iteration anyway.

5. **Research flexibility**: The Castro experiments are research artifacts. Python allows faster iteration on the evaluation methodology.

**Future consideration**: If bootstrap evaluation becomes a production bottleneck (e.g., thousands of samples), implement a Rust-side `BootstrapEvaluator` with a single FFI entry point.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ExperimentRunner                             │
│                                                                 │
│  1. Run real simulation ──────────────────────────────────────► │
│                                                                 │
│  2. Collect transaction history ──────────────────────────────► │
│     └─► TransactionHistoryCollector                             │
│                                                                 │
│  3. Bootstrap evaluation loop ────────────────────────────────► │
│     │                                                           │
│     ├─► BootstrapSampler (per agent)                           │
│     │   └─► Sample outgoing txns                               │
│     │   └─► Sample incoming settlements                        │
│     │                                                           │
│     └─► BootstrapPolicyEvaluator (per agent)                   │
│         └─► Simulate balance evolution                         │
│         └─► Apply policy decisions                             │
│         └─► Calculate costs                                    │
│                                                                 │
│  4. Aggregate results ────────────────────────────────────────► │
│     └─► MonteCarloContextBuilder (existing)                    │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Real Simulation
      │
      ▼
┌─────────────────┐
│ VerboseOutput   │  Contains all events by tick
│ events_by_tick  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ TransactionHistoryCollector │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ TransactionHistory (per agent)                          │
│ ┌─────────────────────┐  ┌───────────────────────────┐ │
│ │ Outgoing Txns       │  │ Incoming Settlements      │ │
│ │ - tx_id             │  │ - tx_id                   │ │
│ │ - amount            │  │ - amount                  │ │
│ │ - arrival_tick      │  │ - settlement_tick         │ │
│ │ - deadline_tick     │  │ - ticks_from_arrival      │ │
│ │ - priority          │  │   (fixed "liquidity beat")│ │
│ │ - settlement_tick?  │  │                           │ │
│ └─────────────────────┘  └───────────────────────────┘ │
└────────────────────────────────────────────────────────┘
         │
         │  Bootstrap Resample (N times)
         ▼
┌─────────────────────────────────────────────────────────┐
│ BootstrapSample (per MC iteration, per agent)           │
│ - sampled_outgoing: list[TransactionRecord]             │
│ - sampled_incoming: list[SettlementRecord]              │
│ - remapped arrival ticks (preserve relative timing)     │
└────────────────────────────────────────────────────────┘
         │
         │  Policy Evaluation
         ▼
┌─────────────────────────────────────────────────────────┐
│ BootstrapPolicyEvaluator                                │
│                                                         │
│ for tick in range(total_ticks):                         │
│   1. Add incoming liquidity (fixed beats)               │
│   2. Queue new arrivals                                 │
│   3. Apply policy → decide releases                     │
│   4. Process releases (update balance)                  │
│   5. Accrue costs (delay, overdraft, deadline)          │
│                                                         │
│ return total_cost                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Data Structures

### TransactionRecord

```python
@dataclass(frozen=True)
class TransactionRecord:
    """Complete record of a transaction's lifecycle."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents (i64 equivalent)
    priority: int
    arrival_tick: int
    deadline_tick: int
    settlement_tick: int | None  # None if never settled
    is_divisible: bool = True

    @property
    def ticks_to_settle(self) -> int | None:
        """Ticks from arrival to settlement (None if unsettled)."""
        if self.settlement_tick is None:
            return None
        return self.settlement_tick - self.arrival_tick

    @property
    def was_settled(self) -> bool:
        """Whether this transaction was settled."""
        return self.settlement_tick is not None
```

### AgentTransactionHistory

```python
@dataclass
class AgentTransactionHistory:
    """Per-agent view of historical transaction data."""

    agent_id: str
    outgoing: list[TransactionRecord]  # Transactions where agent is sender
    incoming_settlements: list[TransactionRecord]  # Settled transactions where agent is receiver

    @property
    def total_outgoing_volume(self) -> int:
        """Total outgoing amount (cents)."""
        return sum(tx.amount for tx in self.outgoing)

    @property
    def total_incoming_volume(self) -> int:
        """Total incoming settlement amount (cents)."""
        return sum(tx.amount for tx in self.incoming_settlements)
```

### BootstrapSample

```python
@dataclass
class BootstrapSample:
    """One bootstrap sample for policy evaluation."""

    agent_id: str
    outgoing_txns: list[TransactionRecord]  # Resampled outgoing
    incoming_settlements: list[TransactionRecord]  # Resampled incoming (fixed timing)
    total_ticks: int

    def get_arrivals_at_tick(self, tick: int) -> list[TransactionRecord]:
        """Get outgoing transactions arriving at this tick."""
        return [tx for tx in self.outgoing_txns if tx.arrival_tick == tick]

    def get_incoming_liquidity_at_tick(self, tick: int) -> int:
        """Get total incoming liquidity at this tick (fixed beats)."""
        return sum(
            tx.amount
            for tx in self.incoming_settlements
            if tx.settlement_tick == tick
        )
```

### PolicyEvaluationResult

```python
@dataclass
class PolicyEvaluationResult:
    """Result of evaluating a policy on a bootstrap sample."""

    agent_id: str
    sample_idx: int
    total_cost: int  # cents

    # Cost breakdown
    delay_cost: int
    overdraft_cost: int
    deadline_penalty: int
    overdue_delay_cost: int

    # Metrics
    transactions_settled: int
    transactions_unsettled: int
    avg_settlement_delay: float
    max_overdraft: int
```

---

## Implementation Plan (TDD)

### Phase 1: TransactionHistoryCollector

**Goal**: Extract transaction lifecycle data from simulation events.

#### Test 1.1: Extract arrivals from events
```python
def test_collector_extracts_arrivals():
    """Arrival events are extracted with correct fields."""
    events_by_tick = {
        0: [
            {"event_type": "Arrival", "tx_id": "tx-001", "sender_id": "BANK_A",
             "receiver_id": "BANK_B", "amount": 100000, "priority": 5,
             "deadline": 10, "tick": 0},
        ]
    }

    collector = TransactionHistoryCollector()
    history = collector.collect(events_by_tick)

    assert len(history["BANK_A"].outgoing) == 1
    tx = history["BANK_A"].outgoing[0]
    assert tx.tx_id == "tx-001"
    assert tx.amount == 100000
    assert tx.arrival_tick == 0
    assert tx.settlement_tick is None  # Not yet settled
```

#### Test 1.2: Match settlements to arrivals
```python
def test_collector_matches_settlement_to_arrival():
    """Settlement events update the transaction's settlement_tick."""
    events_by_tick = {
        0: [
            {"event_type": "Arrival", "tx_id": "tx-001", "sender_id": "BANK_A",
             "receiver_id": "BANK_B", "amount": 100000, ...},
        ],
        5: [
            {"event_type": "RtgsImmediateSettlement", "tx_id": "tx-001",
             "sender": "BANK_A", "receiver": "BANK_B", "amount": 100000, ...},
        ],
    }

    collector = TransactionHistoryCollector()
    history = collector.collect(events_by_tick)

    tx = history["BANK_A"].outgoing[0]
    assert tx.settlement_tick == 5
    assert tx.ticks_to_settle == 5
```

#### Test 1.3: Track incoming settlements for receiver
```python
def test_collector_tracks_incoming_settlements():
    """Receiver agent sees incoming settlements with timing."""
    events_by_tick = {
        0: [{"event_type": "Arrival", "tx_id": "tx-001", "sender_id": "BANK_A",
             "receiver_id": "BANK_B", ...}],
        5: [{"event_type": "RtgsImmediateSettlement", "tx_id": "tx-001", ...}],
    }

    collector = TransactionHistoryCollector()
    history = collector.collect(events_by_tick)

    # BANK_B receives liquidity at tick 5
    assert len(history["BANK_B"].incoming_settlements) == 1
    incoming = history["BANK_B"].incoming_settlements[0]
    assert incoming.settlement_tick == 5
```

#### Test 1.4: Handle LSM settlements
```python
def test_collector_handles_lsm_bilateral_offset():
    """LSM bilateral offsets are tracked as settlements."""
    events_by_tick = {
        0: [
            {"event_type": "Arrival", "tx_id": "tx-001", "sender_id": "BANK_A", ...},
            {"event_type": "Arrival", "tx_id": "tx-002", "sender_id": "BANK_B", ...},
        ],
        3: [
            {"event_type": "LsmBilateralOffset", "tx_ids": ["tx-001", "tx-002"],
             "agents": ["BANK_A", "BANK_B"], ...},
        ],
    }

    collector = TransactionHistoryCollector()
    history = collector.collect(events_by_tick)

    # Both transactions settled at tick 3
    assert history["BANK_A"].outgoing[0].settlement_tick == 3
    assert history["BANK_B"].outgoing[0].settlement_tick == 3
```

#### Implementation: TransactionHistoryCollector

```python
class TransactionHistoryCollector:
    """Extracts transaction lifecycle data from simulation events."""

    def collect(
        self,
        events_by_tick: dict[int, list[dict[str, Any]]]
    ) -> dict[str, AgentTransactionHistory]:
        """Collect transaction history from events."""
        # Track transactions by ID
        transactions: dict[str, TransactionRecord] = {}

        # First pass: collect arrivals
        for tick, events in events_by_tick.items():
            for event in events:
                if event.get("event_type") == "Arrival":
                    tx = self._create_transaction_from_arrival(event, tick)
                    transactions[tx.tx_id] = tx

        # Second pass: match settlements
        for tick, events in events_by_tick.items():
            for event in events:
                self._process_settlement_event(event, tick, transactions)

        # Group by agent
        return self._group_by_agent(transactions)
```

---

### Phase 2: BootstrapSampler

**Goal**: Generate bootstrap samples from historical data.

#### Test 2.1: Bootstrap samples with replacement
```python
def test_bootstrap_sampler_samples_with_replacement():
    """Bootstrap sampling allows duplicates."""
    history = AgentTransactionHistory(
        agent_id="BANK_A",
        outgoing=[tx1, tx2, tx3],  # 3 transactions
        incoming_settlements=[settle1, settle2],
    )

    sampler = BootstrapSampler(seed=42)
    sample = sampler.sample(history, num_outgoing=3, num_incoming=2)

    # With replacement: may have duplicates
    tx_ids = [tx.tx_id for tx in sample.outgoing_txns]
    # Could be [tx1, tx1, tx3] or [tx2, tx2, tx2] etc.
    assert len(tx_ids) == 3
```

#### Test 2.2: Deterministic with same seed
```python
def test_bootstrap_sampler_deterministic():
    """Same seed produces identical samples."""
    history = AgentTransactionHistory(...)

    sampler1 = BootstrapSampler(seed=42)
    sample1 = sampler1.sample(history, num_outgoing=10, num_incoming=5)

    sampler2 = BootstrapSampler(seed=42)
    sample2 = sampler2.sample(history, num_outgoing=10, num_incoming=5)

    assert sample1.outgoing_txns == sample2.outgoing_txns
    assert sample1.incoming_settlements == sample2.incoming_settlements
```

#### Test 2.3: Remap arrival ticks to preserve relative timing
```python
def test_bootstrap_sampler_preserves_relative_timing():
    """Resampled transactions have remapped but consistent timing."""
    tx1 = TransactionRecord(tx_id="tx-001", arrival_tick=5, deadline_tick=15, ...)
    tx2 = TransactionRecord(tx_id="tx-002", arrival_tick=10, deadline_tick=25, ...)

    history = AgentTransactionHistory(
        agent_id="BANK_A",
        outgoing=[tx1, tx2],
        incoming_settlements=[],
    )

    sampler = BootstrapSampler(seed=42)
    sample = sampler.sample(history, total_ticks=20)

    # Arrival ticks should be valid within sample period
    for tx in sample.outgoing_txns:
        assert 0 <= tx.arrival_tick < 20
        # Deadline should maintain relative offset
        original_deadline_offset = tx.deadline_tick - tx.arrival_tick
        assert original_deadline_offset > 0
```

#### Test 2.4: Incoming settlements preserve "beat" timing
```python
def test_bootstrap_sampler_preserves_settlement_beats():
    """Incoming settlements maintain their ticks_to_settle timing."""
    settle1 = TransactionRecord(
        arrival_tick=0, settlement_tick=5, ...  # 5 ticks to settle
    )
    settle2 = TransactionRecord(
        arrival_tick=3, settlement_tick=8, ...  # 5 ticks to settle
    )

    history = AgentTransactionHistory(
        agent_id="BANK_A",
        outgoing=[],
        incoming_settlements=[settle1, settle2],
    )

    sampler = BootstrapSampler(seed=42)
    sample = sampler.sample(history, total_ticks=20)

    # Each incoming settlement maintains its ticks_to_settle
    for settlement in sample.incoming_settlements:
        assert settlement.ticks_to_settle is not None
        # The "beat" is preserved even if remapped to different absolute tick
```

#### Implementation: BootstrapSampler

```python
class BootstrapSampler:
    """Generates bootstrap samples from transaction history."""

    def __init__(self, seed: int) -> None:
        self._rng = np.random.Generator(np.random.PCG64(seed))

    def sample(
        self,
        history: AgentTransactionHistory,
        total_ticks: int,
    ) -> BootstrapSample:
        """Generate one bootstrap sample."""
        # Sample outgoing with replacement
        outgoing = self._bootstrap_transactions(
            history.outgoing, total_ticks
        )

        # Sample incoming settlements with replacement
        # Preserve ticks_to_settle as fixed "beats"
        incoming = self._bootstrap_settlements(
            history.incoming_settlements, total_ticks
        )

        return BootstrapSample(
            agent_id=history.agent_id,
            outgoing_txns=outgoing,
            incoming_settlements=incoming,
            total_ticks=total_ticks,
        )
```

---

### Phase 3: BootstrapPolicyEvaluator

**Goal**: Evaluate policy cost on a bootstrap sample.

#### Test 3.1: Balance evolution with incoming liquidity
```python
def test_evaluator_credits_incoming_liquidity():
    """Incoming settlements increase balance at correct ticks."""
    sample = BootstrapSample(
        agent_id="BANK_A",
        outgoing_txns=[],
        incoming_settlements=[
            TransactionRecord(settlement_tick=5, amount=100000, ...),
        ],
        total_ticks=10,
    )

    evaluator = BootstrapPolicyEvaluator(
        opening_balance=50000,
        cost_config=CostConfig(...),
    )

    # At tick 5, balance should increase
    result = evaluator.evaluate(sample, policy=FifoPolicy())
    # Balance: 50000 → 150000 at tick 5
```

#### Test 3.2: Delay cost accrual in queue
```python
def test_evaluator_accrues_delay_cost():
    """Transactions in queue accrue delay cost per tick."""
    sample = BootstrapSample(
        agent_id="BANK_A",
        outgoing_txns=[
            TransactionRecord(arrival_tick=0, deadline_tick=10, amount=100000, ...),
        ],
        incoming_settlements=[],  # No incoming liquidity
        total_ticks=10,
    )

    evaluator = BootstrapPolicyEvaluator(
        opening_balance=0,  # Can't pay
        cost_config=CostConfig(delay_penalty_per_tick=100),
    )

    result = evaluator.evaluate(sample, policy=FifoPolicy())

    # Transaction stuck in queue for 10 ticks = 100 * 10 = 1000 cents delay cost
    assert result.delay_cost == 1000
```

#### Test 3.3: Overdraft cost when releasing without funds
```python
def test_evaluator_accrues_overdraft_cost():
    """Releasing transaction with insufficient balance incurs overdraft."""
    sample = BootstrapSample(
        agent_id="BANK_A",
        outgoing_txns=[
            TransactionRecord(arrival_tick=0, amount=100000, ...),
        ],
        incoming_settlements=[],
        total_ticks=10,
    )

    evaluator = BootstrapPolicyEvaluator(
        opening_balance=50000,  # Only half
        cost_config=CostConfig(overdraft_cost_bps=10.0, ticks_per_day=100),
    )

    # Policy releases immediately → overdraft of 50000
    result = evaluator.evaluate(sample, policy=ImmediateReleasePolicy())

    assert result.overdraft_cost > 0
    assert result.max_overdraft == 50000
```

#### Test 3.4: Deadline penalty when transaction goes overdue
```python
def test_evaluator_applies_deadline_penalty():
    """One-time penalty when transaction exceeds deadline."""
    sample = BootstrapSample(
        agent_id="BANK_A",
        outgoing_txns=[
            TransactionRecord(arrival_tick=0, deadline_tick=5, amount=100000, ...),
        ],
        incoming_settlements=[],
        total_ticks=10,
    )

    evaluator = BootstrapPolicyEvaluator(
        opening_balance=0,  # Can't pay
        cost_config=CostConfig(deadline_penalty=10000),
    )

    result = evaluator.evaluate(sample, policy=FifoPolicy())

    # At tick 6, transaction goes overdue → 10000 penalty
    assert result.deadline_penalty == 10000
```

#### Test 3.5: Policy integration with decision tree
```python
def test_evaluator_respects_policy_decisions():
    """Evaluator applies policy decisions correctly."""
    sample = BootstrapSample(
        agent_id="BANK_A",
        outgoing_txns=[
            TransactionRecord(arrival_tick=0, priority=3, amount=50000, ...),
            TransactionRecord(arrival_tick=0, priority=8, amount=50000, ...),
        ],
        incoming_settlements=[],
        total_ticks=10,
    )

    evaluator = BootstrapPolicyEvaluator(
        opening_balance=50000,  # Only enough for one
        cost_config=CostConfig(...),
    )

    # Priority policy releases high priority first
    result = evaluator.evaluate(sample, policy=PriorityPolicy())

    # High priority (8) released, low priority (3) queued
    assert result.transactions_settled == 1
    assert result.transactions_unsettled == 1
```

#### Implementation: BootstrapPolicyEvaluator

```python
class BootstrapPolicyEvaluator:
    """Evaluates policy cost on a bootstrap sample."""

    def __init__(
        self,
        opening_balance: int,
        cost_config: CostConfig,
    ) -> None:
        self._opening_balance = opening_balance
        self._cost_config = cost_config

    def evaluate(
        self,
        sample: BootstrapSample,
        policy: PolicyExecutor,
    ) -> PolicyEvaluationResult:
        """Evaluate policy on sample, return cost."""
        balance = self._opening_balance
        queue: list[TransactionRecord] = []
        costs = CostAccumulator()

        for tick in range(sample.total_ticks):
            # 1. Credit incoming liquidity (fixed beats)
            balance += sample.get_incoming_liquidity_at_tick(tick)

            # 2. Queue new arrivals
            queue.extend(sample.get_arrivals_at_tick(tick))

            # 3. Apply policy to decide releases
            context = PolicyContext(balance=balance, tick=tick, queue=queue)
            decisions = policy.evaluate(context)

            # 4. Process releases
            for decision in decisions:
                if decision.action == "release" and balance >= decision.tx.amount:
                    balance -= decision.tx.amount
                    queue.remove(decision.tx)
                    costs.record_settlement(decision.tx, tick)

            # 5. Accrue costs
            costs.accrue_tick_costs(tick, balance, queue, self._cost_config)

        return costs.to_result(sample.agent_id)
```

---

### Phase 4: Integration with ExperimentRunner

**Goal**: Replace current MC loop with bootstrap evaluation.

#### Test 4.1: Bootstrap evaluation uses observed transactions
```python
def test_runner_uses_bootstrap_evaluation():
    """ExperimentRunner uses bootstrap instead of synthetic arrivals."""
    runner = ExperimentRunner(experiment, ...)

    # Mock simulation to return known transactions
    mock_result = SimulationResult(
        verbose_output=VerboseOutput(events_by_tick={
            0: [arrival_event_1, arrival_event_2],
            5: [settlement_event_1],
        }),
        ...
    )

    with patch.object(runner._sim_runner, 'run_simulation', return_value=mock_result):
        result = await runner._evaluate_policies_bootstrap(iteration=1)

    # Should have collected transactions from the single simulation
    assert runner._history_collector.transaction_count > 0
```

#### Test 4.2: Each agent sees only their own costs
```python
def test_bootstrap_evaluation_isolates_agent_costs():
    """Each agent's context only includes their own costs."""
    runner = ExperimentRunner(experiment, ...)

    result = await runner._evaluate_policies_bootstrap(iteration=1)

    # Agent A's context should not include Agent B's costs
    context_a = result.context_builder.get_agent_context("BANK_A")
    assert "BANK_B" not in context_a.cost_summary
```

#### Test 4.3: System metrics sum agent costs
```python
def test_bootstrap_evaluation_aggregates_system_costs():
    """System metrics are sum of all agent costs."""
    runner = ExperimentRunner(experiment, ...)

    result = await runner._evaluate_policies_bootstrap(iteration=1)

    agent_a_cost = result.per_agent_costs["BANK_A"]
    agent_b_cost = result.per_agent_costs["BANK_B"]

    assert result.total_cost == agent_a_cost + agent_b_cost
```

---

### Phase 5: Policy Adapter

**Goal**: Evaluate Castro policy trees within bootstrap evaluator.

#### Test 5.1: Parse Castro policy JSON into executable
```python
def test_policy_adapter_parses_castro_policy():
    """Castro policy JSON converts to executable policy."""
    castro_policy = {
        "version": "2.0",
        "payment_tree": {
            "root": {
                "type": "decision",
                "condition": {"field": "priority", "operator": ">=", "value": 5},
                "if_true": {"type": "action", "action": "Submit"},
                "if_false": {"type": "action", "action": "Hold"},
            }
        }
    }

    adapter = CastroPolicyAdapter()
    policy = adapter.from_json(castro_policy)

    # High priority → release
    high_priority_tx = TransactionRecord(priority=8, ...)
    assert policy.should_release(high_priority_tx, balance=100000) is True

    # Low priority → hold
    low_priority_tx = TransactionRecord(priority=3, ...)
    assert policy.should_release(low_priority_tx, balance=100000) is False
```

---

## File Structure

```
api/payment_simulator/ai_cash_mgmt/
├── sampling/
│   ├── __init__.py
│   ├── seed_manager.py          # Existing
│   ├── transaction_sampler.py   # Existing
│   ├── bootstrap_sampler.py     # NEW
│   └── transaction_history.py   # NEW
├── evaluation/
│   ├── __init__.py              # NEW
│   ├── bootstrap_evaluator.py   # NEW
│   ├── cost_calculator.py       # NEW
│   └── policy_adapter.py        # NEW

experiments/castro/castro/
├── runner.py                    # MODIFY: Add bootstrap evaluation method
├── context_builder.py           # MODIFY: Adapt for bootstrap results
└── bootstrap_integration.py     # NEW: Integration layer
```

---

## Configuration

### New MonteCarloConfig Fields

```python
@dataclass
class MonteCarloConfig:
    # Existing fields
    num_samples: int = 10
    evaluation_ticks: int = 100
    deterministic: bool = False
    sample_method: SampleMethod = SampleMethod.BOOTSTRAP

    # NEW: Bootstrap-specific
    use_bootstrap_evaluation: bool = True
    """Use bootstrap resampling from observed transactions (recommended)."""

    arrival_remapping: ArrivalRemapping = ArrivalRemapping.PRESERVE_RELATIVE
    """How to remap arrival ticks in bootstrap samples."""
```

### ArrivalRemapping Options

```python
class ArrivalRemapping(str, Enum):
    PRESERVE_RELATIVE = "preserve_relative"
    """Keep relative timing between transactions."""

    UNIFORM_SPREAD = "uniform_spread"
    """Spread arrivals uniformly across ticks."""

    ORIGINAL_TICKS = "original_ticks"
    """Keep original arrival ticks (may cause clustering)."""
```

---

## Migration Plan

### Phase 1: Parallel Implementation (Non-Breaking)
1. Implement new bootstrap components
2. Add `use_bootstrap_evaluation` flag (default: False)
3. Test alongside existing implementation
4. Validate results match expected behavior

### Phase 2: Feature Flag Rollout
1. Enable bootstrap for exp2 (stochastic scenario)
2. Keep synthetic arrivals for exp1 (deterministic scenario makes no sense for bootstrap)
3. Collect comparison data

### Phase 3: Default Enablement
1. Set `use_bootstrap_evaluation=True` as default
2. Deprecate synthetic arrival Monte Carlo
3. Update documentation

---

## Testing Strategy

### Unit Tests
- `test_transaction_history_collector.py`
- `test_bootstrap_sampler.py`
- `test_bootstrap_policy_evaluator.py`
- `test_policy_adapter.py`
- `test_cost_calculator.py`

### Integration Tests
- `test_bootstrap_runner_integration.py`
- `test_bootstrap_determinism.py`

### Property-Based Tests
- Bootstrap samples have correct size
- Resampling preserves amount distribution
- Cost calculation is non-negative
- Determinism with same seed

### Acceptance Tests
- exp2 with bootstrap produces reasonable cost variance
- LLM receives meaningful agent-specific context
- Optimization converges to stable policy

---

## Success Criteria

1. **Correctness**
   - Bootstrap samples are reproducible with same seed
   - Costs match expected formulas from cost model
   - Policy decisions match Castro policy tree semantics

2. **Performance**
   - Bootstrap evaluation < 100ms per sample
   - Total MC evaluation < 5s for 10 samples × 2 agents

3. **Research Value**
   - Cost variance reflects transaction uncertainty
   - LLM can reason about bootstrap results
   - Policy improvements generalize to held-out seeds

---

## Open Questions

1. **How to handle unsettled transactions in history?**
   - Option A: Exclude from bootstrap pool
   - Option B: Include with settlement_tick=None (never settles in eval)
   - **Recommendation**: Option B - more realistic

2. **Should bootstrap samples have same size as original?**
   - Option A: Same size (standard bootstrap)
   - Option B: Variable size (Poisson bootstrap)
   - **Recommendation**: Option A for simplicity

3. **How to remap arrival ticks?**
   - Option A: Preserve original ticks (may cluster)
   - Option B: Spread uniformly
   - Option C: Preserve relative timing only
   - **Recommendation**: Option C - maintains transaction relationships

---

## References

- [Patterns and Conventions](../reference/patterns-and-conventions.md)
- [Cost Model](../reference/architecture/12-cost-model.md)
- [FFI Boundary](../reference/architecture/04-ffi-boundary.md)
- [Sampling Components](../reference/ai_cash_mgmt/sampling.md)
- [Tick Loop Anatomy](../reference/architecture/11-tick-loop-anatomy.md)
