# Scenario System Analysis

> Exhaustive catalog of SimCash scenario configuration, example scenarios, and parameter reference.

---

## Table of Contents

1. [Example Scenario Catalog](#example-scenario-catalog)
2. [Full Parameter Reference](#full-parameter-reference)
3. [Payment Generation System](#payment-generation-system)
4. [Settlement System Configuration](#settlement-system-configuration)
5. [Custom Events System](#custom-events-system)
6. [Config-to-Engine Pipeline](#config-to-engine-pipeline)

---

## Example Scenario Catalog

### 1. `advanced_policy_crisis.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Advanced Policy Crisis |
| **Agents** | 4 (METRO_CENTRAL, REGIONAL_TRUST, MOMENTUM_CAPITAL, CORRESPONDENT_HUB) |
| **Ticks/Day** | 100 |
| **Days** | 3 (300 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Stochastic (Poisson arrivals per agent, rates 0.18–0.24/tick) plus ~20 custom scenario events (transactions, collateral adjustments, rate changes).

**Amount Distributions**: Mix of LogNormal (mean 10.5/9.8, std 0.9/1.3) and Uniform ($500–$4,500).

**Cost Parameters**:
- `delay_cost_per_tick_per_cent`: 0.0002
- `overdraft_bps_per_tick`: 0.8
- `collateral_cost_per_tick_bps`: 0.0005
- `eod_penalty_per_transaction`: 500,000 ($5,000)
- `deadline_penalty`: 250,000 ($2,500)
- `overdue_delay_multiplier`: 5.0
- `split_friction_cost`: 7,500

**LSM**: Bilateral + cycles enabled, max cycle length 4, max 10 cycles/tick.

**Agent Configs**: All use `cautious_liquidity_preserver.json` with params (buffer_multiplier: 2.5, urgency_threshold: 3.0, eod_threshold: 0.5). Opening balances $45K–$55K, unsecured caps $18K–$22K.

**What Makes It Interesting**: Designed to showcase advanced policy features—bank-level budgets, collateral auto-withdraw timers, state registers, and adaptive mode switching. Three-day arc: baseline → crisis → recovery. Demonstrates 4-agent payment cycles for LSM multilateral offsetting.

---

### 2. `bis_liquidity_delay_tradeoff.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | BIS Box 3: Liquidity-Delay Trade-off |
| **Agents** | 2 (FOCAL_BANK, COUNTERPARTY) |
| **Ticks/Day** | 3 |
| **Days** | 1 (3 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Fully deterministic via `CustomTransactionArrival` events only. No stochastic arrivals.

**Cost Parameters** (BIS-specific):
- `delay_cost_per_tick_per_cent`: 0.01 (1% per period)
- `priority_delay_multipliers`: urgent 1.5×, normal 1.0×, low 0.5×
- `liquidity_cost_per_tick_bps`: 150 (1.5% opportunity cost)
- All other costs zeroed out (overdraft, collateral, EOD, deadline, split, overdue multiplier=1.0)

**LSM**: Bilateral only (no cycles), max 1 cycle/tick.

**Agent Configs**: FOCAL_BANK starts at $0 balance with `liquidity_pool: 1,000,000` ($10K) and `liquidity_allocation_fraction: 0.5` (allocates $5K). COUNTERPARTY has $100K. Both use FIFO policy.

**What Makes It Interesting**: Direct replication of BIS Working Paper 1310 Box 3. Tests optimal liquidity allocation with 3-period model. Demonstrates `liquidity_pool` and `liquidity_allocation_fraction` features. Minimal configuration—only 4 deterministic transactions.

---

### 3. `crisis_resolution_10day.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Crisis Resolution – 10 Day |
| **Agents** | 4 (same as advanced_policy_crisis) |
| **Ticks/Day** | 100 |
| **Days** | 10 (1,000 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Same stochastic rates as advanced_policy_crisis (0.18–0.24/tick) plus extensive scenario events spanning 10 days.

**Cost Parameters**: Identical to advanced_policy_crisis.

**LSM**: Same as advanced_policy_crisis.

**Agent Configs**: Identical to advanced_policy_crisis.

**What Makes It Interesting**: Extends the 3-day crisis with a Day 4 "central bank intervention"—massive $500K `DirectTransfer` injections and $100K–$200K `CollateralAdjustment` boosts. Days 5–10 show gradual recovery via stepped `GlobalArrivalRateChange` (0.5→0.7→0.8→0.85→0.9→1.0). Tests intervention policy effectiveness over extended timeline.

---

### 4. `suboptimal_policies_10day.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Suboptimal Policies – 10 Day |
| **Agents** | 4 (METRO_CENTRAL, REGIONAL_TRUST, CONSERVATIVE_BANK, REACTIVE_BANK) |
| **Ticks/Day** | 100 |
| **Days** | 10 (1,000 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Stochastic (0.11–0.13/tick, lower than crisis scenarios) plus ~20 custom transaction events and arrival rate changes.

**Cost Parameters**: Lower penalties—`eod_penalty: 0`, `deadline_penalty: 0`, `overdue_delay_multiplier: 3.0`. Otherwise similar.

**LSM**: Same (bilateral + cycles, max 4, max 10/tick).

**Agent Configs**: Two "optimal" agents (buffer_multiplier 2.0, urgency 2.5) vs two "suboptimal" agents—CONSERVATIVE_BANK (buffer 3.5, urgency 1.8, eod 0.85) and REACTIVE_BANK (buffer 1.7, urgency 2.8, eod 0.7). Higher opening balances ($120K–$130K) and caps ($40K–$45K).

**What Makes It Interesting**: A/B comparison of policy quality in non-crisis conditions. No EOD or deadline penalties—costs come purely from delay and overdraft. Shows how subtle parameter differences compound over 10 days.

---

### 5. `suboptimal_policies_25day.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Suboptimal Policies – 25 Day Resilient |
| **Agents** | 4 (BIG_BANK_A, BIG_BANK_B, SMALL_BANK_A, SMALL_BANK_B) |
| **Ticks/Day** | 100 |
| **Days** | 25 (2,500 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: High stochastic rates (0.66–0.78/tick, ~66–78 tx/day) plus ~40 custom events including large payments ($65K–$80K) and collateral adjustments.

**Cost Parameters**:
- `delay_cost_per_tick_per_cent`: 0.00022
- `overdraft_bps_per_tick`: 0.5
- `deadline_penalty`: 5,000
- `overdue_delay_multiplier`: 2.5

**LSM**: max_cycles_per_tick: 20 (increased for gridlock resolution).

**Agent Configs**: Three agents use `cautious_liquidity_preserver.json`, one (SMALL_BANK_B) uses `efficient_proactive.json`. All start with $120K–$130K balances and $40K–$45K caps.

**What Makes It Interesting**: Longest non-crisis scenario. Compares conservative vs. efficient policy over 25 days with multiple recovery mechanisms (collateral injections at days 12, 15, 17, 18, 20, 21, 24). Demonstrates how high delay costs punish the "hoarding" strategy.

---

### 6. `target2_crisis_25day.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | TARGET2 Crisis – 25 Day (Good Policy Variant) |
| **Agents** | 4 (BIG_BANK_A, BIG_BANK_B, SMALL_BANK_A, SMALL_BANK_B) |
| **Ticks/Day** | 100 |
| **Days** | 25 (2,500 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Stochastic (0.55–0.65/tick) plus ~50 custom events across 4 phases.

**Cost Parameters**:
- `delay_cost_per_tick_per_cent`: 0.00035 (highest of all scenarios)
- `overdraft_bps_per_tick`: 0.50
- `collateral_cost_per_tick_bps`: 0.0003
- `eod_penalty_per_transaction`: 25,000
- `deadline_penalty`: 12,000
- `overdue_delay_multiplier`: 5.0
- `split_friction_cost`: 8,000

**LSM**: max_cycles_per_tick: 20.

**Advanced Settings**:
- `algorithm_sequencing: true` (FIFO→Bilateral→Multilateral)
- `entry_disposition_offsetting: true`
- `priority_escalation`: enabled, exponential curve, threshold 25 ticks, max_boost 4

**Agent Configs**: Each agent has **bilateral_limits** (per-counterparty, $25K–$60K) and **multilateral_limit** ($75K–$120K). Policies: `target2_priority_aware.json`, `target2_limit_aware.json`, `target2_crisis_proactive_manager.json` (SMALL_BANK_A), `target2_crisis_risk_denier.json` (SMALL_BANK_B—bad policy).

**What Makes It Interesting**: The "flagship" TARGET2 scenario. Tests all T2 features: dual priority system, bilateral/multilateral limits, algorithm sequencing, entry disposition offsetting, priority escalation. SMALL_BANK_B is the critical bottleneck—designed to cascade into gridlock with bad policy. Four phases: Normal→Pressure→Crisis→Resolution/Collapse.

---

### 7. `target2_crisis_25day_bad_policy.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | TARGET2 Crisis – 25 Day (Bad Policy Variant) |
| **Agents** | 4 (identical to target2_crisis_25day) |
| **Configuration** | Nearly identical to target2_crisis_25day |

**Differences from target2_crisis_25day**: SMALL_BANK_A uses `target2_limit_aware.json` instead of `target2_crisis_proactive_manager.json`. Both small banks now run suboptimal policies—a "both bad" variant for comparison.

**What Makes It Interesting**: Control experiment—same scenario events, but no agent has the proactive crisis management policy. Shows how universal bad policy leads to system-wide failure.

---

### 8. `target2_lsm_features_test.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | TARGET2 LSM Features Test |
| **Agents** | 4 (ALPHA_BANK, BETA_BANK, GAMMA_BANK, DELTA_BANK) |
| **Ticks/Day** | 100 |
| **Days** | 5 (500 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Stochastic (0.35–0.50/tick) plus ~20 custom events designed to trigger specific LSM features.

**Cost Parameters**: Moderate (delay 0.00015, overdraft 0.4, EOD 10K, deadline 5K).

**Advanced Settings**: Same T2 alignment (algorithm_sequencing, entry_disposition_offsetting, priority_escalation with linear curve).

**Agent Configs**: Each agent has bilateral_limits ($12K–$30K) and multilateral_limits ($40K–$80K). Four different policies: `target2_priority_aware`, `target2_aggressive_settler`, `target2_conservative_offsetter`, `target2_limit_aware`. Decreasing balances ($50K→$40K→$35K→$30K) to force queueing.

**What Makes It Interesting**: Comprehensive feature validation scenario. Events carefully designed to trigger: bilateral limit exceeded, multilateral limit exceeded, entry disposition offsets, algorithm sequencing (all 3 phases), priority escalation (low priority + tight deadline), 3-way and 4-way cycles.

---

### 9. `test_minimal_eod.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Minimal EOD Test |
| **Agents** | 2 (BANK_A, BANK_B) |
| **Ticks/Day** | 100 |
| **Days** | 3 (300 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Stochastic only (rate 1.0/tick each, ~100 tx/day), Uniform $100–$500.

**Cost Parameters**: Uses legacy agent-level fields (`overdraft_rate: 500`, `delay_cost_per_tick: 100`), plus LSM settings (`lsm_enabled: true`, `lsm_frequency_ticks: 10`).

**LSM**: No explicit `lsm_config` block—uses inline `lsm_enabled/lsm_frequency_ticks`.

**Agent Configs**: Both use FIFO, $10K balance, $5K unsecured cap. Symmetric.

**What Makes It Interesting**: Simplest "real" scenario. Two symmetric banks with identical policies and arrival rates. Baseline for EOD testing.

---

### 10. `test_near_deadline.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Near Deadline Test |
| **Agents** | 2 (BANK_A, BANK_B) |
| **Ticks/Day** | 100 |
| **Days** | 1 (100 total ticks) |
| **RNG Seed** | 42 |

**Payment Generation**: Stochastic (rate 2.0/tick, high), Uniform $200–$300, very short deadlines (10–20 ticks).

**Cost Parameters**: Uses legacy `cost_model` block with `delay_cost_per_tick_bps: 50`, `overdraft_cost_per_day_bps: 100`, `deadline_penalty_cost: 1000`, `eod_unsettled_penalty: 10000`.

**Agent Configs**: Both FIFO, extremely low balance ($500), zero unsecured cap. Designed to create liquidity pressure and missed deadlines.

**What Makes It Interesting**: Stress test for deadline handling. Low liquidity + high rates + short deadlines = maximum queue pressure and penalty generation.

---

### 11. `test_priority_escalation.yaml`

| Property | Value |
|----------|-------|
| **Scenario Name** | Priority Escalation Test |
| **Agents** | 2 (BANK_A, BANK_B) |
| **Ticks/Day** | 100 |
| **Days** | 1 (100 total ticks) |
| **RNG Seed** | 12345 |

**Payment Generation**: Single deterministic `CustomTransactionArrival` at tick 5 ($1,200, priority 3, deadline 55).

**Cost Parameters**: Low (delay 0.0001, overdraft 0.3, EOD 5K, deadline 3K).

**Advanced Settings**: `algorithm_sequencing: true`, `entry_disposition_offsetting: false`.

**Agent Configs**: BANK_A uses `target2_priority_escalator.json` policy, $1K balance, no credit. BANK_B uses FIFO with $100K balance. No stochastic arrivals.

**What Makes It Interesting**: Isolated test for priority escalation via Queue 2 resubmission. Single transaction that can be released but not settled (amount > balance). Tests `ResubmitToRtgs` compound action and priority boosting from Normal→Urgent→HighlyUrgent as deadline approaches.

---

## Full Parameter Reference

### Top-Level Configuration Structure

```yaml
# REQUIRED
simulation:
  ticks_per_day: <int>          # > 0
  num_days: <int>               # > 0
  rng_seed: <int>               # Any integer

agents: [...]                   # At least 1 agent

# OPTIONAL
cost_rates: {...}               # Defaults provided
lsm_config: {...}               # Defaults provided
scenario_events: [...]          # Default: none
policy_feature_toggles: {...}   # Default: none

# OPTIONAL ADVANCED (top-level booleans/objects)
algorithm_sequencing: <bool>           # Default: false
entry_disposition_offsetting: <bool>   # Default: false
deferred_crediting: <bool>            # Default: false
eod_rush_threshold: <float>           # Default: 0.8 (0.0–1.0)
deadline_cap_at_eod: <bool>           # Default: false
queue1_ordering: <string>             # "Fifo" | "priority_deadline", default: "Fifo"
priority_mode: <bool>                 # Default: false

priority_escalation:
  enabled: <bool>                      # Default: false
  curve: <string>                      # "linear" | "exponential" | "step"
  threshold_ticks: <int>               # Default: 20 (alias: start_escalating_at_ticks)
  max_boost: <int>                     # Default: 3
```

### Agent Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | string | Yes | — | Unique agent identifier |
| `opening_balance` | int (cents) | Yes | — | Starting balance |
| `unsecured_cap` | int (cents) | No | 0 | Unsecured overdraft limit |
| `policy` | PolicyConfig | No | Fifo | Decision-making strategy |
| `arrival_config` | ArrivalConfig | No | None | Stochastic transaction generation |
| `arrival_bands` | ArrivalBandsConfig | No | None | Per-priority-band arrivals (mutually exclusive with arrival_config) |
| `posted_collateral` | int (cents) | No | None | Initial posted collateral |
| `collateral_haircut` | float | No | None | Collateral discount (0.0–1.0) |
| `bilateral_limits` | Dict[str, int] | No | None | Per-counterparty outflow limits |
| `multilateral_limit` | int (cents) | No | None | Total daily outflow limit |
| `liquidity_pool` | int (cents) | No | None | External liquidity source |
| `liquidity_allocation_fraction` | float | No | None | Fraction of pool to allocate (0.0–1.0) |

### Policy Types

| Type | Parameters | Description |
|------|-----------|-------------|
| `Fifo` | None | Release everything immediately |
| `Deadline` | `urgency_threshold: int` | Release when deadline ≤ threshold ticks away |
| `LiquidityAware` | `target_buffer: int`, `urgency_threshold: int` | Maintain buffer, override on urgency |
| `LiquiditySplitting` | `max_splits: int (2-10)`, `min_split_amount: int` | Split large divisible transactions |
| `MockSplitting` | `num_splits: int (2-10)` | Always split into N parts (testing) |
| `FromJson` | `json_path: str`, `params: dict (optional)` | JSON DSL decision tree from file |
| `Inline` | `decision_trees: dict` | Embedded JSON DSL (dict form) |
| `InlineJson` | `json_string: str` | JSON DSL as raw string |

### Arrival Config Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `rate_per_tick` | float | Yes | — | Poisson λ parameter |
| `amount_distribution` | AmountDist | Yes | — | How to sample amounts |
| `counterparty_weights` | Dict[str, float] | No | {} (uniform) | Routing probabilities |
| `deadline_range` | [int, int] | Yes | — | [min, max] ticks to deadline |
| `priority` | int (0-10) | No | 5 | Fixed priority |
| `priority_distribution` | PriorityDist | No | None | Variable priority (overrides `priority`) |
| `divisible` | bool | No | false | Can be split by policies |

### Amount Distribution Types

| Type | Parameters | Output |
|------|-----------|--------|
| `Normal` | `mean: int`, `std_dev: int` | Symmetric bell curve (cents) |
| `LogNormal` | `mean: float`, `std_dev: float` | Right-skewed, log-scale params |
| `Uniform` | `min: int`, `max: int` | Equal probability in range (cents) |
| `Exponential` | `lambda: float` | Many small, few large |

### Priority Distribution Types

| Type | Parameters |
|------|-----------|
| `Fixed` | `value: int (0-10)` |
| `Categorical` | `values: [int...]`, `weights: [float...]` |
| `Uniform` | `min: int`, `max: int` |

### Arrival Bands Config

```yaml
arrival_bands:
  urgent:    # Priority 8-10
    rate_per_tick: <float>
    amount_distribution: <AmountDist>
    deadline_offset_min: <int>
    deadline_offset_max: <int>
    counterparty_weights: <Dict>    # Optional
    divisible: <bool>               # Optional
  normal:    # Priority 4-7
    ...
  low:       # Priority 0-3
    ...
```

At least one band required. Priority auto-assigned from band range.

### Cost Rate Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `overdraft_bps_per_tick` | float | 0.001 | Per-tick cost of negative balance |
| `delay_cost_per_tick_per_cent` | float | 0.0001 | Per-tick per-cent cost of queued transactions |
| `collateral_cost_per_tick_bps` | float | 0.0002 | Opportunity cost of posted collateral |
| `liquidity_cost_per_tick_bps` | float | 0.0 | Opportunity cost of allocated liquidity pool |
| `eod_penalty_per_transaction` | int | 10,000 | One-time penalty per unsettled tx at day end |
| `deadline_penalty` | int | 50,000 | One-time penalty when tx becomes overdue |
| `split_friction_cost` | int | 1,000 | Cost per split operation |
| `overdue_delay_multiplier` | float | 5.0 | Delay cost multiplier for overdue transactions |
| `priority_delay_multipliers` | object | None | Per-band delay cost multipliers |

**Priority Delay Multipliers sub-fields**:
- `urgent_multiplier`: float (default 1.0, for priority 8-10)
- `normal_multiplier`: float (default 1.0, for priority 4-7)
- `low_multiplier`: float (default 1.0, for priority 0-3)

### LSM Config Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `enable_bilateral` | bool | true | — | Enable A↔B offset detection |
| `enable_cycles` | bool | true | — | Enable multilateral cycle detection |
| `max_cycle_length` | int | 4 | 3–10 | Max participants in settlement cycle |
| `max_cycles_per_tick` | int | 10 | 1–100 | Max cycles settled per tick |

### Policy Feature Toggles

```yaml
policy_feature_toggles:
  include: [<category>...]    # Allowlist (mutually exclusive with exclude)
  # OR
  exclude: [<category>...]    # Blocklist
```

**Categories**: ComparisonOperator, LogicalOperator, BinaryArithmetic, NaryArithmetic, UnaryMath, TernaryMath, ValueType, PaymentAction, BankAction, CollateralAction, RtgsAction, TransactionField, AgentField, QueueField, CollateralField, CostField, TimeField, LsmField, ThroughputField, StateRegisterField, SystemField, DerivedField, NodeType, TreeType.

---

## Payment Generation System

### Stochastic Generation (arrival_config / arrival_bands)

Each tick, per agent:
1. Sample count from `Poisson(rate_per_tick × global_multiplier × agent_multiplier)`
2. For each transaction:
   - Sample amount from `amount_distribution`
   - Select counterparty via weighted random from `counterparty_weights`
   - Sample deadline as `current_tick + Uniform(deadline_range[0], deadline_range[1])`
   - Optionally cap deadline at EOD if `deadline_cap_at_eod: true`
   - Assign priority (fixed, distribution, or band range)
   - Set divisibility flag

### Deterministic Generation (scenario_events)

`CustomTransactionArrival` events create transactions at exact ticks:
- Go through normal Queue 1 → policy → Queue 2 → settlement flow
- Deadline is relative (ticks from arrival), also subject to `deadline_cap_at_eod`
- Optional fields: priority (default 5), deadline, is_divisible (default false)

### Rate Modification

- `GlobalArrivalRateChange`: multiplies all agents' rates (persists until next change)
- `AgentArrivalRateChange`: multiplies one agent's rate (stacks with global)
- `CounterpartyWeightChange`: changes routing probabilities
- `DeadlineWindowChange`: scales deadline ranges via multipliers

---

## Settlement System Configuration

### RTGS Modes

**Queue 1 Ordering** (`queue1_ordering`):
- `"Fifo"` (default): Process in arrival order
- `"priority_deadline"`: Sort by priority (desc), deadline (asc), arrival (asc)

**Priority Mode** (`priority_mode`):
- `false` (default): Pure FIFO in Queue 2
- `true`: Process all Urgent before Normal before Low in Queue 2

### LSM Modes

1. **Bilateral Only**: `enable_bilateral: true, enable_cycles: false`
2. **Full LSM**: `enable_bilateral: true, enable_cycles: true`
3. **Disabled**: Both false—pure RTGS settlement

### Algorithm Sequencing

When `algorithm_sequencing: true`:
```
Each tick: FIFO Settlement → Bilateral Offsets → Multilateral Cycles
```

When false: LSM integrated with RTGS processing.

### Entry Disposition Offsetting

When `entry_disposition_offsetting: true`: Each payment entering Queue 2 immediately checks for bilateral offset against existing queue contents.

### Deferred Crediting

When `deferred_crediting: true`: Credits from settlements accumulated during tick, applied at end. Prevents within-tick liquidity recycling.

### Priority Escalation

Auto-boosts priority as deadlines approach:
- Linear: `boost = max_boost × (1 - ticks_remaining / threshold)`
- Exponential/Step: Also available
- Generates `PriorityEscalated` events

---

## Custom Events System

### Event Types

| Type | Effect | Key Fields |
|------|--------|------------|
| `DirectTransfer` | Instant balance move, bypasses queues | from_agent, to_agent, amount |
| `CustomTransactionArrival` | Normal settlement-path transaction | from_agent, to_agent, amount, priority, deadline, is_divisible |
| `CollateralAdjustment` | Add/remove collateral | agent, delta (positive or negative) |
| `GlobalArrivalRateChange` | Scale all rates | multiplier (persists) |
| `AgentArrivalRateChange` | Scale one agent's rate | agent, multiplier (persists) |
| `CounterpartyWeightChange` | Adjust routing weights | agent, counterparty, new_weight, auto_balance_others |
| `DeadlineWindowChange` | Scale deadline ranges | min_ticks_multiplier, max_ticks_multiplier |

### Scheduling

| Schedule Type | Fields | Behavior |
|---------------|--------|----------|
| `OneTime` | `tick: int` | Execute once at specified tick |
| `Repeating` | `start_tick: int`, `interval: int`, `end_tick: int (optional)` | Execute periodically |

### Event Patterns Used Across Scenarios

1. **Payment Cycles**: Simultaneous `CustomTransactionArrival` events forming A→B→C→A cycles to test LSM multilateral offsetting
2. **Bilateral Offset Pairs**: Two opposing payments at consecutive ticks to test entry disposition offsetting
3. **Activity Spikes**: `GlobalArrivalRateChange` with multiplier > 1.0, followed by restoration to 1.0
4. **Crisis-Recovery Arcs**: Collateral removal → pressure → collateral restoration
5. **Intervention**: `DirectTransfer` for emergency liquidity + `CollateralAdjustment` + rate reduction

---

## Config-to-Engine Pipeline

### `SimulationConfig.from_dict()`

```python
SimulationConfig.from_dict(config_dict) → SimulationConfig
```

Delegates to `cls.model_validate(config_dict)` (Pydantic v2 validation). The config dict can come from:
- YAML file loading (`yaml.safe_load()`)
- Direct Python dict construction
- API request payloads

### YAML → Rust Flow

1. **YAML parsed** → Python dict
2. **Pydantic validation** → `SimulationConfig` object (validates types, constraints, cross-references)
3. **FFI conversion** → Config serialized to Rust-compatible structures via PyO3
4. **Policy loading**: `FromJson` policies loaded from disk; `Inline`/`InlineJson` serialized to JSON strings
5. **Policy validation**: If `policy_feature_toggles` present, all JSON policies validated against allowed categories
6. **Engine initialization**: Rust `Orchestrator` receives config, creates agents, queues, cost model
7. **Simulation loop**: Tick-by-tick execution with deterministic RNG

### Key Validation Rules

- Agent IDs must be unique
- Counterparty references must exist in agents list
- Cannot have both `arrival_config` and `arrival_bands`
- `ticks_per_day` and `num_days` must be > 0
- All monetary values are integer cents (i64)
- Same `rng_seed` guarantees byte-for-byte identical results

---

## Scenario Design Patterns

### Pattern 1: Symmetric Baseline
Two identical agents with FIFO policy. Tests infrastructure. (test_minimal_eod)

### Pattern 2: BIS Replication
Minimal ticks/day, deterministic events only, specialized cost model, liquidity pool. (bis_liquidity_delay_tradeoff)

### Pattern 3: Policy Comparison
Same scenario events, different policies per agent. Compare costs. (suboptimal_policies_*)

### Pattern 4: Crisis Arc
Multi-day with escalating stress events, intervention, and recovery phases. (crisis_resolution_10day, advanced_policy_crisis)

### Pattern 5: TARGET2 Feature Test
All T2 features enabled (algorithm_sequencing, entry_disposition_offsetting, priority_escalation, bilateral/multilateral limits). Events designed to trigger specific features. (target2_*)

### Pattern 6: Isolated Feature Test
Single transaction, minimal agents, tests one specific mechanism. (test_priority_escalation, test_near_deadline)

---

## Summary Statistics Across All Scenarios

| Scenario | Agents | Ticks | Events | Stochastic | T2 Features |
|----------|--------|-------|--------|------------|-------------|
| advanced_policy_crisis | 4 | 300 | ~25 | Yes | No |
| bis_liquidity_delay_tradeoff | 2 | 3 | 4 | No | No |
| crisis_resolution_10day | 4 | 1,000 | ~35 | Yes | No |
| suboptimal_policies_10day | 4 | 1,000 | ~20 | Yes | No |
| suboptimal_policies_25day | 4 | 2,500 | ~40 | Yes | No |
| target2_crisis_25day | 4 | 2,500 | ~50 | Yes | Full |
| target2_crisis_25day_bad_policy | 4 | 2,500 | ~50 | Yes | Full |
| target2_lsm_features_test | 4 | 500 | ~20 | Yes | Full |
| test_minimal_eod | 2 | 300 | 0 | Yes | No |
| test_near_deadline | 2 | 100 | 0 | Yes | No |
| test_priority_escalation | 2 | 100 | 1 | No | Partial |

---

*Generated: 2026-02-17*
