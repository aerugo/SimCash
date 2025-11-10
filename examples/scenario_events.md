# Scenario Events: Complete Guide & Examples

## Overview

**Scenario events** are deterministic interventions that allow precise control over simulation state at specific ticks. They enable researchers to model shock scenarios, policy changes, and controlled experiments with full reproducibility.

### Key Benefits

- **Deterministic Timing**: Events execute at exact ticks (not probabilistic)
- **Reproducible Research**: Same config + same seed = identical behavior
- **Stress Testing**: Model liquidity crises, operational shocks, regulatory changes
- **Policy Validation**: Test how agent policies respond to known conditions
- **Replay Identity**: Events persist to database with full details

---

## Event Type Reference

### 1. DirectTransfer

**Purpose**: Instantly transfer funds between agents, bypassing normal settlement path.

**Use Cases**:
- Central bank emergency liquidity injections
- Interbank loans
- Margin calls to clearing houses
- End-of-day position squaring

**Parameters**:
```yaml
type: DirectTransfer
from_agent: <string>      # Source agent ID
to_agent: <string>        # Destination agent ID
amount: <int>             # Amount in cents (must be positive)
schedule: <EventSchedule> # When to execute (see Scheduling)
```

**Example: Emergency Liquidity Injection**
```yaml
scenario_events:
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: BANK_A
    amount: 1000000  # $10,000
    schedule:
      type: OneTime
      tick: 75
```

**Behavior**:
- Immediate balance change (no queue, no settlement delay)
- Bypasses Queue 1 (no policy evaluation)
- Bypasses Queue 2 (no RTGS processing)
- Does NOT trigger transaction arrival events
- Balance conservation maintained (sum of all balances unchanged)

---

### 2. CustomTransactionArrival

**Purpose**: Create a transaction that goes through normal arrival → settlement flow.

**Use Cases**:
- Testing settlement behavior with precise timing
- Controlled stress tests (large payment at specific tick)
- Policy evaluation (how does policy handle known transaction?)
- Gridlock scenario construction

**Parameters**:
```yaml
type: CustomTransactionArrival
from_agent: <string>        # Source agent ID
to_agent: <string>          # Destination agent ID
amount: <int>               # Amount in cents (must be positive)
priority: <int>             # Optional: 0-10 (default: 5)
deadline: <int>             # Optional: relative ticks (default: auto-calculated)
is_divisible: <bool>        # Optional: can be split? (default: false)
schedule: <EventSchedule>   # When to execute
```

**Example: Large Priority Payment**
```yaml
scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 500000    # $5,000
    priority: 9       # High urgency
    deadline: 15      # Must settle within 15 ticks
    is_divisible: false
    schedule:
      type: OneTime
      tick: 25
```

**Behavior**:
- Arrives at Queue 1 (agent's internal queue)
- Policy evaluates and decides: submit now, hold, or split
- If submitted, goes to Queue 2 (RTGS central queue)
- Attempts RTGS settlement (immediate if liquidity available)
- If queued, LSM may optimize (bilateral offset or cycle detection)
- Costs accrue: delay costs in Queue 1, no costs in Queue 2

**Key Difference from DirectTransfer**:
- **DirectTransfer**: Instant balance change, bypasses all queues
- **CustomTransactionArrival**: Normal settlement path, tests policy behavior

---

### 3. CollateralAdjustment

**Purpose**: Modify agent's posted collateral, affecting available credit.

**Use Cases**:
- Margin calls (reduce collateral)
- Collateral haircut shocks (regulatory changes)
- Intraday repo transactions (increase collateral)
- Stress testing credit constraints

**Parameters**:
```yaml
type: CollateralAdjustment
agent: <string>           # Agent ID
delta: <int>              # Change in collateral (can be negative)
schedule: <EventSchedule> # When to execute
```

**Example: Margin Call (Collateral Reduction)**
```yaml
scenario_events:
  - type: CollateralAdjustment
    agent: BANK_A
    delta: -200000  # Reduce by $2,000
    schedule:
      type: OneTime
      tick: 50
```

**Behavior**:
- Immediately adjusts agent's available collateral
- Affects credit capacity: `credit_limit = base_limit + collateral_value`
- May trigger liquidity pressure if agent was near credit limit
- Collateral costs update (opportunity cost calculation)

---

### 4. GlobalArrivalRateChange

**Purpose**: Scale all agents' transaction arrival rates by a multiplier.

**Use Cases**:
- Market-wide activity surges (end-of-quarter payments)
- Holiday slowdowns (reduced trading volumes)
- Regulatory deadlines (simultaneous submissions)
- Stress testing system capacity

**Parameters**:
```yaml
type: GlobalArrivalRateChange
multiplier: <float>       # Scaling factor (1.0 = no change)
schedule: <EventSchedule> # When to execute
```

**Example: Market Surge (Double All Arrivals)**
```yaml
scenario_events:
  - type: GlobalArrivalRateChange
    multiplier: 2.0  # Double all arrival rates
    schedule:
      type: OneTime
      tick: 30
```

**Behavior**:
- Multiplies every agent's `arrival_rate_per_tick` by the factor
- Affects future arrivals (not retroactive)
- Persistent change (remains until another rate change event)
- Example: If BANK_A has rate 0.5, after multiplier 2.0, new rate = 1.0

---

### 5. AgentArrivalRateChange

**Purpose**: Adjust a specific agent's transaction arrival rate.

**Use Cases**:
- Bank-specific operational issues (system outage, reduced capacity)
- Client demand shocks (large customer places many transactions)
- Policy changes (bank prioritizes different business lines)
- Counterparty failure simulation (set rate to 0)

**Parameters**:
```yaml
type: AgentArrivalRateChange
agent: <string>           # Agent ID
multiplier: <float>       # Scaling factor for this agent only
schedule: <EventSchedule> # When to execute
```

**Example: Bank Outage (Halt Arrivals)**
```yaml
scenario_events:
  - type: AgentArrivalRateChange
    agent: BANK_C
    multiplier: 0.0  # Stop all new arrivals
    schedule:
      type: OneTime
      tick: 40

  # Resume operations 20 ticks later
  - type: AgentArrivalRateChange
    agent: BANK_C
    multiplier: 1.0  # Resume normal rate
    schedule:
      type: OneTime
      tick: 60
```

**Behavior**:
- Changes only the specified agent's `arrival_rate_per_tick`
- Other agents unaffected
- Persistent change until another event modifies it

---

### 6. CounterpartyWeightChange

**Purpose**: Modify agent's preferred counterparty relationships.

**Use Cases**:
- Correspondent banking changes (shift payment flows)
- Credit limit adjustments (reduce exposure to specific counterparty)
- Strategic relationship changes (prefer new partners)
- Stress testing concentration risk

**Parameters**:
```yaml
type: CounterpartyWeightChange
agent: <string>             # Agent whose preferences change
counterparty: <string>      # Target counterparty
new_weight: <float>         # New probability weight (0.0 to 1.0)
schedule: <EventSchedule>   # When to execute
```

**Example: Reduce Exposure to BANK_B**
```yaml
scenario_events:
  - type: CounterpartyWeightChange
    agent: BANK_A
    counterparty: BANK_B
    new_weight: 0.1  # Reduce from default to 10%
    schedule:
      type: OneTime
      tick: 35
```

**Behavior**:
- Updates counterparty probability weights in arrival generator
- Affects future transaction destinations (not existing transactions)
- Weights renormalized to sum to 1.0 across all counterparties

---

### 7. DeadlineWindowChange

**Purpose**: Adjust agent's default deadline window for new transactions.

**Use Cases**:
- Policy urgency changes (shift to faster settlement targets)
- Regulatory deadline changes (tighter compliance windows)
- Operational mode shifts (urgent vs. relaxed operations)
- Stress testing deadline pressure

**Parameters**:
```yaml
type: DeadlineWindowChange
agent: <string>             # Agent ID
new_window: <int>           # New deadline window in ticks
schedule: <EventSchedule>   # When to execute
```

**Example: Tighten Deadlines (Increase Urgency)**
```yaml
scenario_events:
  - type: DeadlineWindowChange
    agent: BANK_A
    new_window: 10  # Reduce from default 20 to 10 ticks
    schedule:
      type: OneTime
      tick: 15
```

**Behavior**:
- Changes default deadline for future arrivals
- Does NOT affect existing transactions in queues
- Tighter windows increase urgency (higher deadline penalty risk)

---

## Scheduling

### OneTime Execution

Execute event exactly once at specified tick.

```yaml
schedule:
  type: OneTime
  tick: 50  # Execute at tick 50 (0-indexed)
```

**Use Cases**:
- One-off shocks (margin call, emergency liquidity)
- Policy changes (occurs once and persists)
- Specific stress test timing

---

### Repeating Execution

Execute event multiple times at regular intervals.

```yaml
schedule:
  type: Repeating
  start_tick: 10    # First execution
  interval: 5       # Repeat every 5 ticks
  end_tick: 50      # Optional: stop after this tick
```

**Use Cases**:
- Periodic liquidity injections
- Recurring operational changes
- Simulating regular patterns (end-of-hour activity)

**Example: Periodic Liquidity Boost**
```yaml
scenario_events:
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: BANK_A
    amount: 100000
    schedule:
      type: Repeating
      start_tick: 10
      interval: 10
      end_tick: 90
    # Executes at ticks: 10, 20, 30, 40, 50, 60, 70, 80, 90
```

---

## Complete Example Scenarios

### Example 1: Liquidity Crisis Cascade

**Scenario**: BANK_A experiences cascading liquidity shocks over the course of a day.

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 1000000  # $10,000
    credit_limit: 200000      # $2,000
    policy:
      type: LiquidityAware
      buffer_target: 100000   # Try to keep $1,000 buffer

  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 200000
    policy:
      type: Fifo

  - id: CLEARING_HOUSE
    opening_balance: 10000000  # $100,000
    credit_limit: 0
    policy:
      type: Fifo

scenario_events:
  # Morning (tick 10): Large client payment
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 300000       # $3,000
    priority: 5
    deadline: 20
    is_divisible: false
    schedule: {type: OneTime, tick: 10}

  # Midday (tick 50): Margin call
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: CLEARING_HOUSE
    amount: 500000       # $5,000 outflow
    schedule: {type: OneTime, tick: 50}

  # Afternoon (tick 60): Collateral haircut
  - type: CollateralAdjustment
    agent: BANK_A
    delta: -100000       # $1,000 reduction
    schedule: {type: OneTime, tick: 60}

  # Late day (tick 80): Client surge
  - type: AgentArrivalRateChange
    agent: BANK_A
    multiplier: 3.0      # Triple arrival rate
    schedule: {type: OneTime, tick: 80}
```

**Expected Behavior**:
1. **Tick 10**: CustomTransactionArrival tests BANK_A's normal policy response
2. **Tick 50**: DirectTransfer causes immediate liquidity drain (balance drops to $5,000)
3. **Tick 60**: Collateral reduction limits credit access (can only borrow $1,000 now)
4. **Tick 80**: Arrival surge increases pressure (more transactions to settle with tight liquidity)

**Research Questions**:
- Does LiquidityAware policy maintain buffer under stress?
- How many transactions queue vs. settle immediately?
- Does BANK_A go into overdraft? If so, for how long?
- What's the total cost (liquidity + delay + penalties)?

---

### Example 2: Market-Wide Activity Surge

**Scenario**: Global arrival rate doubles during peak hours, then returns to normal.

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 123

agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 500000
    policy: {type: Fifo}

  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 500000
    policy: {type: Deadline}

  - id: BANK_C
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: LiquidityAware
      buffer_target: 200000

scenario_events:
  # Morning rush (tick 20): Double activity
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule: {type: OneTime, tick: 20}

  # Midday (tick 50): Return to normal
  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule: {type: OneTime, tick: 50}

  # Afternoon surge (tick 70): Triple activity
  - type: GlobalArrivalRateChange
    multiplier: 3.0
    schedule: {type: OneTime, tick: 70}
```

**Expected Behavior**:
- Ticks 0-19: Normal arrival rates
- Ticks 20-49: 2× arrivals (30 ticks of surge)
- Ticks 50-69: Normal rates again (20 ticks)
- Ticks 70-99: 3× arrivals (30 ticks of high stress)

**Research Questions**:
- Which policy handles surges best (FIFO, Deadline, LiquidityAware)?
- Does LSM effectiveness change with higher volumes?
- Settlement rate degradation under stress?

---

### Example 3: Counterparty Failure Simulation

**Scenario**: BANK_B fails mid-day (stops sending payments), triggering systemic stress.

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 999

agents:
  - id: BANK_A
    opening_balance: 500000
    credit_limit: 100000
    policy: {type: Fifo}

  - id: BANK_B
    opening_balance: 500000
    credit_limit: 100000
    policy: {type: Fifo}

  - id: BANK_C
    opening_balance: 500000
    credit_limit: 100000
    policy: {type: Fifo}

scenario_events:
  # Tick 40: BANK_B fails (stops sending)
  - type: AgentArrivalRateChange
    agent: BANK_B
    multiplier: 0.0  # Halt all outgoing payments
    schedule: {type: OneTime, tick: 40}

  # Tick 45: Others reduce exposure to BANK_B
  - type: CounterpartyWeightChange
    agent: BANK_A
    counterparty: BANK_B
    new_weight: 0.0  # Stop sending to BANK_B
    schedule: {type: OneTime, tick: 45}

  - type: CounterpartyWeightChange
    agent: BANK_C
    counterparty: BANK_B
    new_weight: 0.0
    schedule: {type: OneTime, tick: 45}
```

**Expected Behavior**:
- Before tick 40: Normal three-way payment flows
- Tick 40: BANK_B stops sending (but still receives)
- Tick 45: BANK_A and BANK_C stop sending to BANK_B
- Result: BANK_B becomes net receiver (accumulates balance)
- BANK_A and BANK_C lose incoming liquidity recycling

**Research Questions**:
- How long until gridlock forms?
- Does LSM help when one participant is inactive?
- Settlement rate degradation for BANK_A and BANK_C?

---

### Example 4: Repeating Liquidity Support

**Scenario**: Central bank provides periodic liquidity injections to support market.

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 555

agents:
  - id: BANK_A
    opening_balance: 200000  # Low starting liquidity
    credit_limit: 50000
    policy:
      type: LiquidityAware
      buffer_target: 100000

  - id: BANK_B
    opening_balance: 200000
    credit_limit: 50000
    policy:
      type: LiquidityAware
      buffer_target: 100000

  - id: CENTRAL_BANK
    opening_balance: 10000000
    credit_limit: 0
    policy: {type: Fifo}

scenario_events:
  # Every 10 ticks: Central bank injects liquidity
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: BANK_A
    amount: 50000
    schedule:
      type: Repeating
      start_tick: 10
      interval: 10
      end_tick: 90

  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: BANK_B
    amount: 50000
    schedule:
      type: Repeating
      start_tick: 10
      interval: 10
      end_tick: 90
```

**Expected Behavior**:
- BANK_A and BANK_B each receive $500 every 10 ticks
- Injections at ticks: 10, 20, 30, 40, 50, 60, 70, 80, 90
- Total support: 9 injections × $500 = $4,500 per bank

**Research Questions**:
- Do periodic injections prevent liquidity crunches?
- Optimal injection frequency and amount?
- Compare with one-time large injection vs. repeated small ones

---

## CLI Usage

### Running Scenarios with Events

```bash
# Run scenario with verbose output (see events execute)
payment-sim run --config liquidity_crisis.yaml --verbose

# Run with persistence (enables replay)
payment-sim run \
  --config liquidity_crisis.yaml \
  --persist \
  --db-path crisis.db \
  --verbose

# Replay specific tick range
payment-sim replay \
  --simulation-id <id> \
  --config liquidity_crisis.yaml \
  --from-tick 45 \
  --to-tick 65 \
  --verbose
```

### Verbose Output

Scenario events appear in verbose mode with full details:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🕐 TICK 50 (Day 0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎬 Scenario Events (2):
   • DirectTransfer: BANK_A → CLEARING_HOUSE ($5,000.00)
   • CustomTransactionArrival: BANK_A → BANK_B ($2,500.00)
     Priority: 8, TX: tx_abc123

📥 Transaction Arrivals (1):
   • TX tx_abc123: BANK_A → BANK_B ($2,500.00)
     Priority: 8 | Deadline: tick 60 | Divisible: no

...
```

---

## Replay Identity

Scenario events are **fully deterministic** and persist to the database with complete execution details.

### Verification Process

```bash
# 1. Run with persistence and save output
payment-sim run \
  --config crisis.yaml \
  --persist \
  --db-path test.db \
  --verbose > run.log

# 2. Replay from database
payment-sim replay \
  --simulation-id <id> \
  --config crisis.yaml \
  --verbose > replay.log

# 3. Verify identical output (ignore timing info)
diff <(grep -v "Duration:" run.log) <(grep -v "Duration:" replay.log)

# Expected: No differences (replay is byte-for-byte identical)
```

### Database Storage

Events stored in `simulation_events` table:

```sql
SELECT
  tick,
  event_type,
  details
FROM simulation_events
WHERE event_type = 'ScenarioEventExecuted'
ORDER BY tick;
```

Example row:
```json
{
  "tick": 50,
  "event_type": "ScenarioEventExecuted",
  "scenario_event_type": "custom_transaction_arrival",
  "details": {
    "from_agent": "BANK_A",
    "to_agent": "BANK_B",
    "amount": 250000,
    "priority": 8,
    "deadline": 60,
    "is_divisible": false,
    "tx_id": "tx_abc123"
  }
}
```

---

## Best Practices

### 1. Start Simple

```yaml
# Good: Single event, easy to understand
scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 100000
    schedule: {type: OneTime, tick: 50}
```

### 2. Document Intent

```yaml
# Good: Comments explain the purpose
scenario_events:
  # Morning: Simulate large client payment
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 500000
    schedule: {type: OneTime, tick: 10}

  # Midday: Margin call stress
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: CLEARING_HOUSE
    amount: 600000
    schedule: {type: OneTime, tick: 50}
```

### 3. Use Meaningful Tick Numbers

```yaml
# Good: Round numbers, logical timing
scenario_events:
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule: {type: OneTime, tick: 25}  # Quarter through day

  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule: {type: OneTime, tick: 75}  # Three-quarters through
```

### 4. Test Incrementally

```bash
# 1. Run without events (baseline)
payment-sim run --config baseline.yaml

# 2. Add one event, compare
payment-sim run --config with_one_event.yaml

# 3. Add more events progressively
payment-sim run --config full_scenario.yaml
```

### 5. Validate with Replay

```bash
# Always verify replay identity for research scenarios
payment-sim run --config scenario.yaml --persist --verbose > run.log
payment-sim replay --simulation-id <id> --config scenario.yaml --verbose > replay.log
diff <(grep -v "Duration:" run.log) <(grep -v "Duration:" replay.log)
```

---

## Integration with Other Features

### Cost Model

Scenario events interact with costs:

```yaml
# DirectTransfer causes immediate overdraft
- type: DirectTransfer
  from_agent: BANK_A
  to_agent: BANK_B
  amount: 1500000  # Exceeds BANK_A's balance
  schedule: {type: OneTime, tick: 50}
  # Result: Liquidity costs accrue on negative balance

# CustomTransactionArrival may trigger deadline penalties
- type: CustomTransactionArrival
  from_agent: BANK_A
  to_agent: BANK_B
  amount: 500000
  deadline: 5  # Tight deadline
  schedule: {type: OneTime, tick: 90}
  # Result: Deadline penalty if can't settle by tick 95
```

### Persistence & Queries

Query scenarios by event types:

```python
import duckdb

conn = duckdb.connect("simulations.db")

# Find all simulations with CustomTransactionArrival events
results = conn.execute("""
    SELECT DISTINCT simulation_id
    FROM simulation_events
    WHERE event_type = 'ScenarioEventExecuted'
      AND JSON_EXTRACT(details, '$.scenario_event_type') = 'custom_transaction_arrival'
""").fetchall()

print(f"Found {len(results)} scenarios with custom arrivals")
```

### Policy Testing

Use scenario events to evaluate policies:

```yaml
# Test: How does LiquidityAware policy handle liquidity shock?
agents:
  - id: TEST_BANK
    opening_balance: 500000
    credit_limit: 100000
    policy:
      type: LiquidityAware
      buffer_target: 200000

scenario_events:
  # Shock: Large outflow
  - type: DirectTransfer
    from_agent: TEST_BANK
    to_agent: OTHER_BANK
    amount: 400000
    schedule: {type: OneTime, tick: 50}

  # Follow-up: Can policy recover?
  - type: CustomTransactionArrival
    from_agent: TEST_BANK
    to_agent: OTHER_BANK
    amount: 100000
    priority: 5
    deadline: 20
    schedule: {type: OneTime, tick: 60}
```

**Evaluation Metrics**:
- Did TEST_BANK maintain buffer?
- How long in overdraft?
- Total costs (liquidity + delay)?
- Settlement rate maintained?

---

## Troubleshooting

### Event Doesn't Execute

**Check:**
1. Tick number is within simulation range (0 to `ticks_per_day * num_days - 1`)
2. Agent IDs exist in config
3. YAML syntax is correct (proper indentation)
4. Event type spelled correctly (case-sensitive)

**Debug:**
```bash
# Run with verbose output to see event execution
payment-sim run --config problematic.yaml --verbose

# Check for validation errors
payment-sim run --config problematic.yaml  # Errors printed to stderr
```

### Replay Divergence

**If replay output differs from run:**

1. **Check event details persisted correctly:**
```sql
SELECT * FROM simulation_events
WHERE event_type = 'ScenarioEventExecuted'
  AND simulation_id = '<your_id>';
```

2. **Verify seed matches:**
```yaml
# Config must have same seed
simulation:
  rng_seed: 42  # Must match original run
```

3. **Compare tick ranges:**
```bash
# Replay exact same tick range
payment-sim replay --from-tick 0 --to-tick 99 ...
```

### Unexpected Costs

**If costs seem wrong after scenario events:**

1. **DirectTransfer causing overdraft:**
```yaml
# Check: Does transfer exceed balance + credit?
- type: DirectTransfer
  from_agent: BANK_A  # Balance: $5,000, Credit: $2,000
  to_agent: BANK_B
  amount: 800000      # Exceeds capacity → overdraft costs
```

2. **CustomTransactionArrival deadline penalties:**
```yaml
# Check: Is deadline too tight?
- type: CustomTransactionArrival
  from_agent: BANK_A
  to_agent: BANK_B
  amount: 500000
  deadline: 2  # Only 2 ticks to settle → high penalty risk
```

---

## Further Reading

- **[README.md](../README.md)**: Main project documentation
- **[Grand Plan](../docs/grand_plan.md)**: Architecture and roadmap
- **[CLAUDE.md](../CLAUDE.md)**: Development guidelines (replay identity principles)
- **[API Tests](../api/tests/integration/test_custom_transaction_arrival.py)**: Implementation examples

---

*For questions or issues, see [GitHub Issues](https://github.com/yourusername/payment-simulator/issues)*
