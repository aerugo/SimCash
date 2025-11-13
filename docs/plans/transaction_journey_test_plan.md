# Transaction Journey Testing Plan

**Purpose**: Test how individual transactions flow through the system under different policies, tracking specific events and state transitions.

**Key Insight**: Aggregate metrics (settlement rate, queue depth) miss the story of HOW policies make decisions. Journey tests reveal policy-specific behavior.

---

## Test Categories

### Category 1: Queue Dynamics & Priority

**Scenario: Late Arrival Preempts Early Arrival**

**Setup**:
- Transaction A arrives at tick 10, amount $1,000, deadline tick 40 (30 ticks away)
- Agent has $1,500 liquidity
- Transaction B arrives at tick 15, amount $500, deadline tick 18 (3 ticks away)

**Expected Journeys by Policy**:

| Policy | Transaction A | Transaction B | Key Event |
|--------|---------------|---------------|-----------|
| **FIFO** | Settles tick 10 | Queued, settles tick 11+ | FIFO order maintained |
| **Deadline** | Queued | Settles tick 15 | Urgency=9 preempts urgency=2 |
| **LiquidityAware** | Depends on buffer | Urgency override if critical | Buffer vs urgency tradeoff |

**Events to Track**:
- `Arrival` (both transactions)
- `PolicySubmit` (which order?)
- `RtgsImmediateSettlement` or `QueueHold`
- `UrgencyOverride` (for Deadline policy)

**Metrics**:
- Time in queue for each transaction
- Final settlement tick for each
- Which settled first (policy-dependent)

---

### Category 2: Collateral & Liquidity Unlocking

**Scenario: Collateral Posted to Enable Settlement**

**Setup**:
- Agent has $500 balance, $5,000 eligible collateral (haircut 0.8 = $4,000 usable)
- Transaction A arrives: $2,000, deadline tick 20
- No other liquidity sources

**Expected Journeys by Policy**:

| Policy | Collateral Posted? | Settlement | Key Event |
|--------|-------------------|------------|-----------|
| **FIFO** | No | Queued forever | No collateral mechanism |
| **LiquidityAware (with collateral)** | Yes, posts $2,500 | Settles after posting | `CollateralPosted`, then `RtgsImmediateSettlement` |
| **Cautious** | Maybe (conservative) | May hold even with collateral | Preserves headroom |

**Events to Track**:
- `Arrival`
- `CollateralPosted` (amount, new available liquidity)
- `RtgsImmediateSettlement` (after collateral)
- `InsufficientLiquidity` (if policy refuses)

**Metrics**:
- Collateral posted amount
- Time between arrival and collateral posting
- Collateral headroom remaining

---

### Category 3: LSM Cycle Triggering

**Scenario: Bilateral Offset Resolves Gridlock**

**Setup**:
- Agent A: $100 balance, owes $500 to Agent B (queued)
- Agent B: $100 balance, owes $500 to Agent A (queued)
- Both transactions deadlocked

**Expected Journeys by Policy**:

| Policy | LSM Triggered? | Resolution | Key Event |
|--------|---------------|------------|-----------|
| **FIFO** | No | Both stuck | No LSM awareness |
| **FIFO + LSM enabled** | Yes | Bilateral offset, both settled | `LsmBilateralOffset` |
| **Deadline (LSM enabled)** | Yes, if both urgent | Offset triggered by urgency | `LsmCycleSettlement` |

**Events to Track**:
- `Arrival` (both transactions)
- `QueueHold` (both)
- `LsmBilateralOffset` (cycle detection)
- `RtgsImmediateSettlement` (both, after offset)

**Metrics**:
- Time in gridlock
- LSM cycle detection latency
- Net settlement amount (should be $0)

---

### Category 4: Credit Usage Under Pressure

**Scenario: Credit Enables Immediate Settlement**

**Setup**:
- Agent has $200 balance, $2,000 credit limit
- Transaction arrives: $1,500, deadline tick 5 (urgent!)
- Policy must decide: use credit or queue

**Expected Journeys by Policy**:

| Policy | Uses Credit? | Settlement | Key Event |
|--------|-------------|------------|-----------|
| **FIFO** | No | Queued | No credit mechanism |
| **AggressiveMarketMaker** | Yes | Settles immediately | `CreditUsed`, overdraft -$1,300 |
| **CautiousLiquidityPreserver** | No | Queued | Avoids credit |
| **BalancedCostOptimizer** | Maybe | Cost analysis | Weighs credit_cost vs delay_cost |

**Events to Track**:
- `Arrival`
- `PolicyDecision` (use credit or queue)
- `RtgsImmediateSettlement` (with credit)
- `CreditUsed` (amount)
- `OverdraftCost` (accrued)

**Metrics**:
- Credit used
- Overdraft cost
- Settlement delay (0 if immediate, >0 if queued)

---

### Category 5: Transaction Splitting

**Scenario: Partial Settlement via Splitting**

**Setup**:
- Agent has $300 balance
- Transaction arrives: $1,000, divisible=true, deadline tick 30
- Split cost = $10 per split

**Expected Journeys by Policy**:

| Policy | Splits? | Settlement | Key Event |
|--------|--------|------------|-----------|
| **FIFO** | No | Queued | No split capability |
| **SmartSplitter** | Yes, into $300 + $700 | Partial settlement at tick N, remainder queued | `TransactionSplit`, `RtgsImmediateSettlement` (partial) |
| **BalancedCostOptimizer** | Maybe | Cost analysis: split_cost vs delay_cost | Splits only if beneficial |

**Events to Track**:
- `Arrival`
- `TransactionSplit` (parent ID, child IDs, amounts)
- `RtgsImmediateSettlement` (first child)
- `QueueHold` (second child)
- `RtgsImmediateSettlement` (second child, later)

**Metrics**:
- Number of splits
- Total split cost
- Time to full settlement (both children)
- Partial settlement ratio (300/1000 = 30%)

---

### Category 6: Time-Adaptive Buffer Adjustment

**Scenario: EOD Rush Changes Policy Behavior**

**Setup**:
- Agent has $5,000 balance, target buffer $2,000
- Transaction A arrives tick 20: $2,000 (mid-day)
- Transaction B arrives tick 95: $2,000 (EOD rush)
- Policy: GoliathNationalBank (time-adaptive buffer multipliers)

**Expected Journeys by Policy**:

| Policy | Transaction A (mid-day) | Transaction B (EOD) | Key Event |
|--------|------------------------|---------------------|-----------|
| **GoliathNationalBank** | Queued (protects 1.0× buffer = $2,000) | Settles (relaxes to 0.5× buffer = $1,000) | `TimeOfDayMultiplier` changes behavior |
| **CautiousLiquidityPreserver** | Queued (strict 2.5× buffer) | Queued (same strictness) | No time adaptation |

**Events to Track**:
- `Arrival` (both)
- `PolicyDecision` (buffer calculation with time multiplier)
- `QueueHold` or `RtgsImmediateSettlement`
- `TimeOfDayMultiplier` (if logged)

**Metrics**:
- Effective buffer at each tick
- Settlement decision reason
- Balance after settlement

---

### Category 7: Deadline Violation Recovery

**Scenario: Transaction Becomes Overdue, Policy Adapts**

**Setup**:
- Transaction arrives tick 10, deadline tick 20, amount $1,000
- Agent has $200 balance throughout
- Transaction becomes overdue at tick 21

**Expected Journeys by Policy**:

| Policy | Behavior While Pending | Behavior After Overdue | Key Event |
|--------|----------------------|----------------------|-----------|
| **FIFO** | Queued | Still queued (no change) | `DeadlineViolation` logged |
| **Deadline** | High priority | Even higher priority? | `OverdueTransaction`, increased urgency |
| **BalancedCostOptimizer** | Cost analysis | Overdue multiplier applied (5×) | `OverduePenalty`, urgency increases |

**Events to Track**:
- `Arrival`
- `QueueHold`
- `DeadlineViolation` (tick 21)
- `OverdueTransaction`
- `PolicyDecision` (urgency recalculation)
- `RtgsImmediateSettlement` (eventual)

**Metrics**:
- Ticks overdue
- Overdue penalty cost
- Total delay penalty

---

## Implementation Strategy

### Phase 1: Add Transaction Tracking to Framework

**New capability needed**: Track specific transaction IDs through events

```python
class TransactionJourneyTest:
    """Test that tracks a specific transaction through its lifecycle."""

    def __init__(self, tx_id: str, policy, scenario):
        self.tx_id = tx_id
        self.policy = policy
        self.scenario = scenario
        self.journey = []  # List of (tick, event_type, details)

    def run(self):
        """Run simulation and extract journey for specific transaction."""
        # ... similar to PolicyScenarioTest ...

        for tick in range(duration):
            orch.tick()
            events = orch.get_tick_events(tick)

            # Filter events for this transaction
            for event in events:
                if event.get('tx_id') == self.tx_id or event.get('parent_tx_id') == self.tx_id:
                    self.journey.append({
                        'tick': tick,
                        'event_type': event['event_type'],
                        'details': event
                    })

        return TransactionJourneyResult(self.tx_id, self.journey)
```

### Phase 2: Define Journey Assertions

```python
class JourneyExpectation:
    """Expected journey for a transaction."""

    def __init__(self):
        self.must_have_events = []  # Event types that must occur
        self.must_not_have_events = []  # Event types that must NOT occur
        self.event_order = []  # Ordered sequence of events
        self.timing_constraints = {}  # e.g., {"settled_by": 50}

    def expect_event(self, event_type: str, by_tick: Optional[int] = None):
        """Transaction must have this event."""
        self.must_have_events.append((event_type, by_tick))

    def forbid_event(self, event_type: str):
        """Transaction must NOT have this event."""
        self.must_not_have_events.append(event_type)

    def expect_sequence(self, *event_types):
        """Events must occur in this order."""
        self.event_order = event_types
```

### Phase 3: Implement Journey Test Suite

**File**: `api/tests/integration/test_transaction_journeys.py`

Structure:
- `TestQueueDynamics` (5 tests)
- `TestCollateralUsage` (4 tests)
- `TestLsmCycles` (3 tests)
- `TestCreditUsage` (4 tests)
- `TestSplitting` (3 tests)
- `TestTimeAdaptive` (2 tests)
- `TestOverdueHandling` (3 tests)

**Total**: ~24 new transaction journey tests

### Phase 4: Policy Comparison Matrix

Create comparison tests that run the SAME transaction scenario under DIFFERENT policies:

```python
def test_urgent_transaction_policy_comparison():
    """How do different policies handle an urgent transaction with low liquidity?"""

    scenario = create_urgent_low_liquidity_scenario()
    tx_id = "urgent-tx-001"

    policies = {
        "FIFO": {"type": "Fifo"},
        "Deadline": {"type": "Deadline", "urgency_threshold": 5},
        "Aggressive": load_json_policy("aggressive_market_maker"),
        "Cautious": load_json_policy("cautious_liquidity_preserver"),
    }

    results = {}
    for name, policy in policies.items():
        test = TransactionJourneyTest(tx_id, policy, scenario)
        results[name] = test.run()

    # Compare journeys
    print("Policy Comparison:")
    for name, journey in results.items():
        print(f"  {name}: {journey.summary()}")

    # Assertions
    assert results["FIFO"].queued_duration > results["Deadline"].queued_duration
    assert results["Aggressive"].used_credit and not results["Cautious"].used_credit
```

---

## Integration with Existing Tests

The 50 existing tests focus on **aggregate behavior** (settlement rates, overall queue depth).
The 24 new journey tests focus on **individual transaction behavior** (specific sequences, policy decisions).

**Together**, they provide:
- **Macro view**: Does the policy achieve good overall outcomes?
- **Micro view**: How does the policy make specific decisions?

---

## Success Criteria

A complete test suite should answer:

1. ✅ **Aggregate Performance**: What's the settlement rate? (Existing tests)
2. ✅ **Queue Behavior**: How deep do queues get? (Existing tests)
3. ✅ **Policy Decisions**: Why did policy X choose action Y? (New journey tests)
4. ✅ **Resource Usage**: When is collateral/credit used? (New journey tests)
5. ✅ **Event Sequences**: What order do events occur? (New journey tests)
6. ✅ **Policy Differences**: How do policies differ on same scenario? (New comparison tests)

---

## Next Steps

1. **Implement TransactionJourneyTest framework** (extend existing framework.py)
2. **Write 24 journey tests** in new test file
3. **Calibrate existing 50 tests** with richer expectations (not just settlement rates)
4. **Create policy comparison dashboard** (visual diff of journeys)

**Estimated Effort**:
- Journey framework: 2-3 hours
- 24 journey tests: 4-6 hours
- Calibration of 50 tests: 2-3 hours
- **Total**: 8-12 hours

---

**This plan transforms testing from "did it work?" to "HOW did it work?"**
