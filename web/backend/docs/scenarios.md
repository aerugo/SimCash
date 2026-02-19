# Scenario System

*Configuring simulated payment environments*

A **scenario** defines everything about a simulated payment environment:
how many banks exist, when payments arrive, what they cost, and what events shake up the
system. Scenarios are written in YAML and fully control the Rust simulation engine.

## What a Scenario Configures

Every scenario specifies these core elements:

- **Simulation timing** — ticks per day, number of days, RNG seed
- **Agents** — bank identities, opening balances, credit limits, policies
- **Payment generation** — how transactions arrive (stochastic or deterministic)
- **Cost rates** — delay costs, overdraft rates, penalties
- **LSM settings** — bilateral/multilateral offsetting configuration
- **Custom events** — scheduled interventions (transfers, rate changes, collateral shocks)

```yaml
# Minimal scenario example
simulation:
  ticks_per_day: 12
  num_days: 5
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 5000000  # $50,000 in cents
    unsecured_cap: 2000000
    policy:
      type: Fifo
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10.0
        std_dev: 1.0
      deadline_range: [5, 20]

  - id: BANK_B
    opening_balance: 5000000
    unsecured_cap: 2000000
    policy:
      type: Deadline
      urgency_threshold: 3
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: Uniform
        min: 5000
        max: 50000
      deadline_range: [5, 20]

cost_rates:
  delay_cost_per_tick_per_cent: 0.0001
  overdraft_bps_per_tick: 0.001
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
```

## Configuration Hierarchy

```
SimulationConfig (root)
├── simulation: SimulationSettings
│   ├── ticks_per_day: int
│   ├── num_days: int
│   └── rng_seed: int
├── agents: List[AgentConfig]
│   └── AgentConfig
│       ├── id: str
│       ├── opening_balance: int (cents)
│       ├── unsecured_cap: int (cents)
│       ├── policy: PolicyConfig
│       ├── arrival_config: Optional[ArrivalConfig]
│       ├── arrival_bands: Optional[ArrivalBandsConfig]
│       ├── posted_collateral: Optional[int]
│       ├── collateral_haircut: Optional[float]
│       ├── limits: Optional[Dict]
│       ├── liquidity_pool: Optional[int]
│       └── liquidity_allocation_fraction: Optional[float]
├── cost_rates: CostRates
├── lsm_config: LsmConfig
├── policy_feature_toggles: Optional[PolicyFeatureToggles]
└── scenario_events: Optional[List[ScenarioEvent]]
```

## Payment Generation Modes

SimCash supports three modes for generating payment arrivals, which can be combined
within a single scenario:

### Deterministic (Custom Events Only)

No stochastic arrivals — every transaction is a `CustomTransactionArrival` event
placed at a specific tick. Used for BIS paper replication and isolated feature tests where
you need exact control over every payment.

### Poisson Arrivals

Each tick, the number of new payments is drawn from a Poisson distribution with
rate `λ = rate_per_tick`. This models realistic payment flow where arrivals
are random but have a known average rate. Rates can be modified mid-simulation
via `GlobalArrivalRateChange` or `AgentArrivalRateChange` events.

### Amount Distributions

Payment amounts are sampled independently from one of four distributions:

| Type | Parameters | Use Case |
|------|------------|----------|
| `LogNormal` | mean, std_dev (log-scale) | Realistic: many small, few large payments |
| `Normal` | mean, std_dev (cents) | Symmetric distribution around mean |
| `Uniform` | min, max (cents) | Equal probability in range |
| `Exponential` | lambda | Many small, exponentially fewer large |

### Priority Distributions

Payment priorities can be assigned via three distribution types:

| Type | Parameters | Description |
|------|------------|-------------|
| `Fixed` | value | All transactions get the same priority |
| `Categorical` | values, weights | Weighted random selection from discrete values |
| `Uniform` | min, max | Uniform random in range |

## Cost Rates

Cost rates control how the engine scores settlement outcomes. All monetary values are integer cents.

| Setting | Default | Description |
|---------|---------|-------------|
| `overdraft_bps_per_tick` | `0.001` | Overdraft cost in basis points per tick |
| `delay_cost_per_tick_per_cent` | `0.0001` | Delay cost per tick per cent held |
| `collateral_cost_per_tick_bps` | `0.0002` | Collateral opportunity cost |
| `eod_penalty_per_transaction` | `10000` | Penalty per unsettled transaction at end of day |
| `deadline_penalty` | `50000` | One-time penalty when deadline is missed |
| `split_friction_cost` | `1000` | Cost per payment split |
| `overdue_delay_multiplier` | `5.0` | Multiplier on delay cost after deadline |

## LSM Configuration

The Liquidity-Saving Mechanism (LSM) enables bilateral and multilateral offsetting
to reduce liquidity requirements.

| Setting | Default | Description |
|---------|---------|-------------|
| `enable_bilateral` | `true` | Enable bilateral offsetting |
| `enable_cycles` | `true` | Enable cycle detection (multilateral) |
| `max_cycle_length` | `4` | Maximum cycle length |
| `max_cycles_per_tick` | `10` | Max cycles resolved per tick |

## Custom Events

Scenario events are deterministic interventions injected at specific ticks. They let you
create crisis narratives, central bank interventions, and controlled stress tests.

| Event Type | Effect |
|------------|--------|
| `DirectTransfer` | Instant balance move between agents, bypasses all queues |
| `CustomTransactionArrival` | Inject a transaction that flows through normal settlement |
| `CollateralAdjustment` | Add or remove collateral from an agent |
| `GlobalArrivalRateChange` | Multiply all agents' arrival rates (persists until next change) |
| `AgentArrivalRateChange` | Multiply one agent's arrival rate |
| `CounterpartyWeightChange` | Redirect payment flows by adjusting routing probabilities |
| `DeadlineWindowChange` | Tighten or loosen deadline pressure globally |

Events use two scheduling modes:

```yaml
# One-time event at tick 150 (day 2 of a 100-tick-per-day scenario)
scenario_events:
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: STRESSED_BANK
    amount: 50000000  # $500K emergency injection
    schedule:
      type: OneTime
      tick: 150

  # Repeating event: collateral adjustments every 50 ticks
  - type: CollateralAdjustment
    agent: BANK_A
    delta: 1000000  # +$10K collateral
    schedule:
      type: Repeating
      start_tick: 100
      interval: 50
      end_tick: 400
```

## Validation Rules

| Rule | Description |
|------|-------------|
| Unique agent IDs | All agent `id` values must be unique (uppercase alphanumeric) |
| Counterparty references | Referenced agents in weights/limits must exist |
| Arrival exclusivity | Cannot have both `arrival_config` and `arrival_bands` on one agent |
| Positive timing | `ticks_per_day` and `num_days` must be > 0 |
| Integer money | All monetary values are `i64` cents — no floats |
| Priority range | Priority values must be 0–10 |

## Scenario Design: Building a Stress Test

A realistic multi-phase crisis scenario follows this pattern:

1. **Baseline phase** (days 1–3) — Normal operations, establish cost baseline
2. **Pressure phase** (days 4–6) — Increase arrival rates (1.5–2×), inject large payments
3. **Crisis phase** (days 7–8) — Remove collateral, cut counterparty weights, spike rates
4. **Intervention** (day 9) — DirectTransfer liquidity injection, restore collateral
5. **Recovery phase** (days 10+) — Gradually restore rates to 1.0×, measure recovery speed

> ℹ️ All events are deterministic and tick-based — there's no conditional logic
> ("if balance drops below X, inject liquidity"). This is by design: determinism ensures
> perfect reproducibility. The same config + same seed always produces byte-identical results.
