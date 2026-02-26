# SimCash: Comprehensive Analysis and Proposals for Realistic RTGS Scenarios and Policies

**Author:** Stefan, Research Director — Banking and Payments Department, Bank of Canada  
**Date:** February 2026  
**Version:** 1.0

---

## 1. Executive Summary

SimCash is a sophisticated payment system simulator modelling Real-Time Gross Settlement (RTGS) dynamics with Liquidity-Saving Mechanisms (LSM) inspired by TARGET2. It features a Rust simulation engine with Python orchestration, JSON-based decision tree policies, YAML scenario configuration, and LLM-driven policy optimization via bootstrap evaluation.

This document provides:

1. **Schema analysis** — what the YAML/JSON configuration can express
2. **Existing library critique** — cataloguing all scenarios and policies with realism assessment
3. **10 new scenario proposals** grounded in real RTGS operational experience (Lynx, CHAPS, Fedwire, TARGET2)
4. **10+ new policy proposals** reflecting actual bank treasury practices
5. **Implementation priorities** for the development roadmap

**Key finding:** SimCash has strong mechanical foundations (LSM algorithms, cost model, priority system) but its scenario library is heavily tilted toward academic game-theory demonstrations (Castro et al. 2025) and stylised crisis narratives. Real RTGS dynamics — intraday flow distributions, tiered participation structures, throughput guidelines, standing facility stigma, and heterogeneous payment types — are underrepresented. Similarly, the policy library lacks strategies reflecting actual bank treasury practices: time-of-day liquidity management, reciprocity-based release, throughput guideline compliance, and defensive crisis-mode behaviour.

---

## 2. Schema Analysis

### 2.1 Scenario YAML Schema

SimCash scenarios are YAML files consumed by `SimulationConfig`. The schema supports:

**Core Simulation Settings:**
```yaml
simulation:
  ticks_per_day: int      # Discrete time units per business day (2–100 typical)
  num_days: int            # Multi-day simulations supported
  rng_seed: int            # Deterministic reproducibility
```

**Agent Configuration:**
```yaml
agents:
  - id: str                          # Uppercase alphanumeric identifier
    opening_balance: int             # Cents, initial central bank reserves
    unsecured_cap: int               # Unsecured daylight overdraft limit
    liquidity_pool: int              # Castro-mode: direct balance allocation
    liquidity_allocation_fraction: float  # Fraction of pool to allocate
    posted_collateral: int           # Pre-posted collateral
    collateral_haircut: float        # Haircut on collateral value
    bilateral_limits: {str: int}     # Per-counterparty outflow caps
    multilateral_limit: int          # Total outflow cap
    policy:
      type: str                      # Fifo | Deadline | LiquidityAware | FromJson
      json_path: str                 # Path to policy JSON (if FromJson)
      params: {str: any}             # Policy parameter overrides
    arrival_config:                   # Stochastic payment generation
      rate_per_tick: float           # Poisson arrival rate (λ)
      amount_distribution:
        type: str                    # LogNormal | Normal | Uniform | Exponential
        mean/std_dev/min/max: num
      counterparty_weights: {str: float}
      deadline_range: [int, int]
      priority: int                  # Fixed, or use priority distribution
      divisible: bool
    arrival_bands: ...               # Alternative: time-varying arrival rates
```

**Cost Model:**
```yaml
cost_rates:
  delay_cost_per_tick_per_cent: float     # Queue 1 delay cost
  overdraft_bps_per_tick: float           # Overdraft interest rate
  collateral_cost_per_tick_bps: float     # Collateral opportunity cost
  liquidity_cost_per_tick_bps: int        # Castro-mode liquidity cost
  eod_penalty_per_transaction: int        # End-of-day unsettled penalty
  deadline_penalty: int                   # One-time overdue penalty
  split_friction_cost: int                # Per-split operational cost
  overdue_delay_multiplier: float         # Multiplier on delay cost post-deadline
  priority_delay_multipliers:             # Priority-differentiated delay costs
    urgent_multiplier: float
    normal_multiplier: float
    low_multiplier: float
```

**LSM Configuration:**
```yaml
lsm_config:
  enable_bilateral: bool
  enable_cycles: bool
  max_cycle_length: int
  max_cycles_per_tick: int
```

**Feature Toggles:**
```yaml
algorithm_sequencing: bool              # TARGET2-style FIFO→Bilateral→Multilateral
entry_disposition_offsetting: bool      # Offset check at Queue 2 entry
deferred_crediting: bool                # Credits apply at tick end only
deadline_cap_at_eod: bool               # Cap deadlines at end of day
priority_escalation:
  enabled: bool
  curve: str                            # linear | exponential
  threshold_ticks: int
  max_boost: int
```

**Scenario Events (deterministic interventions):**
```yaml
scenario_events:
  - type: str     # DirectTransfer | CustomTransactionArrival | CollateralAdjustment
                  # GlobalArrivalRateChange | AgentArrivalRateChange
                  # CounterpartyWeightChange | DeadlineWindowChange
    schedule:
      type: OneTime | Repeating
      tick: int
      start_tick: int       # For Repeating
      interval: int
      end_tick: int
```

### 2.2 Policy JSON Schema

Policies use a JSON decision tree DSL with four tree types:

| Tree | Evaluation Phase | Scope |
|------|-----------------|-------|
| `bank_tree` | Step 1.75 (once/tick) | Budget-setting, state registers |
| `payment_tree` | Step 2 (per transaction) | Release/Hold/Split decisions |
| `strategic_collateral_tree` | Step 1.5 (once/tick) | Proactive collateral posting |
| `end_of_tick_collateral_tree` | Step 5.5 (once/tick) | Reactive collateral cleanup |

**Node types:** Condition (boolean branching) and Action (terminal decisions).

**Payment actions:** Release, Hold, Split, StaggerSplit, ReleaseWithCredit, Reprioritize, WithdrawFromRtgs, ResubmitToRtgs, Drop.

**Bank actions:** SetReleaseBudget, SetState, AddState, NoAction.

**Collateral actions:** PostCollateral, WithdrawCollateral, HoldCollateral.

**Context fields (80+):** Balance/liquidity (balance, effective_liquidity, credit_headroom, liquidity_pressure), transaction (amount, ticks_to_deadline, priority, is_overdue), queue state (queue1_total_value, rtgs_queue_size), timing (day_progress_fraction, is_eod_rush, ticks_remaining_in_day), LSM-aware (my_bilateral_net_q2, tx_is_top_counterparty), throughput (my_throughput_fraction_today, throughput_gap), state registers (bank_state_*).

**Expression system:** Comparison operators (==, !=, <, <=, >, >=), logical operators (and, or, not), arithmetic computations (+, -, *, /, max, min, clamp, div0, ceil, floor, abs).

**Parameters:** Named floating-point values defined in the policy, referenced via `{"param": "name"}`.

### 2.3 Schema Capabilities & Limitations

**Strengths:**
- Rich cost model with 7+ cost types and priority multipliers
- TARGET2-aligned LSM with algorithm sequencing and entry disposition
- Deterministic events enable precise crisis narratives
- State registers allow cross-tick memory within a day
- 80+ context fields provide comprehensive decision-making information
- Throughput tracking fields (throughput_gap) support guideline compliance

**Limitations:**
- No conditional events (events are tick-based, not state-contingent)
- No agent communication or information sharing
- State registers reset at end of day (no multi-day memory)
- No heterogeneous payment types with different cost profiles within a single agent
- No standing facility/central bank lending with stigma effects
- No agent failure/removal mid-simulation
- No tiered participation (all agents are direct members)
- arrival_config counterparty_weights are static (can only be changed via events)
- No explicit throughput guideline enforcement mechanism (only tracking fields)

---

## 3. Existing Library Critique

### 3.1 Scenarios (18 total)

#### Example Config Scenarios (11 files)

| # | Scenario | Agents | Ticks/Day × Days | Key Features | Realism Assessment |
|---|----------|--------|------------------|--------------|-------------------|
| 1 | `bis_liquidity_delay_tradeoff` | 2 | 3×1 | Liquidity pool, priority delay multipliers | **Academic** — Replicates BIS Box 3 experiment. Useful pedagogically but too abstract for operational research. |
| 2 | `crisis_resolution_10day` | 4 | 100×10 | LSM, DirectTransfers, CollateralAdjustments, rate changes | **Moderate** — Good multi-phase crisis narrative with intervention. But uses simplistic rate multipliers rather than realistic flow shifts. Banks named metaphorically (METRO_CENTRAL, MOMENTUM_CAPITAL). |
| 3 | `target2_crisis_25day` | 4 | 100×25 | Algorithm sequencing, entry disposition, priority escalation, bilateral/multilateral limits | **Best existing** — Most sophisticated scenario. Tests limit cascades through a bottleneck bank. Good network topology. Lacks realistic flow timing patterns. |
| 4 | `target2_crisis_25day_bad_policy` | 4 | 100×25 | Same as above with different policy assignment | Variant of #3 |
| 5 | `advanced_policy_crisis` | 4 | 100×? | Multi-phase crisis | Crisis development scenario |
| 6 | `suboptimal_policies_10day` | ? | ?×10 | Tests impact of poor policies | Policy comparison |
| 7 | `suboptimal_policies_25day` | ? | ?×25 | Extended version of above | Extended policy comparison |
| 8 | `target2_lsm_features_test` | ? | ? | LSM feature testing | Feature validation |
| 9 | `test_minimal_eod` | ? | ? | Minimal EOD test | Unit test scenario |
| 10 | `test_near_deadline` | ? | ? | Deadline behaviour | Unit test scenario |
| 11 | `test_priority_escalation` | ? | ? | Priority escalation | Feature test |

#### Scenario Pack (Web UI Presets, 7 scenarios)

| # | Scenario | Agents | Ticks/Day | Description | Realism Assessment |
|---|----------|--------|-----------|-------------|-------------------|
| 12 | `2bank_2tick` | 2 | 2 | Minimal Nash equilibrium | **Toy** — Pure game theory |
| 13 | `2bank_12tick` | 2 | 12 | Castro Exp 2 replication | **Academic** — LVTS-inspired but homogeneous agents |
| 14 | `2bank_3tick` | 2 | 3 | Split-or-concentrate | **Toy** — Minimal decision space |
| 15 | `3bank_6tick` | 3 | 6 | Trilateral coordination | **Academic** — Tests free-riding |
| 16 | `4bank_8tick` | 4 | 8 | Network cascade | **Academic** — Tests cascade effects |
| 17 | `2bank_stress` | 2 | 12 | High penalties (5× normal) | **Stress variant** — Useful parameter sensitivity |
| 18 | `5bank_12tick` | 5 | 12 | Maximum complexity | **Academic** — Largest network but still homogeneous |

#### Castro Experiment Configs (3 configs)

| # | Config | Description |
|---|--------|-------------|
| 19 | `exp1_2period` | 2-period deterministic, validates Nash equilibrium |
| 20 | `exp2_12period` | 12-period stochastic, LVTS-style with Poisson arrivals |
| 21 | `exp3_joint` | 3-period joint liquidity & timing optimization |

### 3.2 Critique of Existing Scenarios

**What's good:**
- Solid Castro et al. (2025) replication with proper game-theoretic foundations
- TARGET2 crisis scenario (#3) demonstrates sophisticated LSM feature interactions
- Crisis resolution scenario (#2) has genuine multi-phase narrative structure
- Deterministic event system enables precise experimental control

**What's missing (critical gaps from an RTGS research perspective):**

1. **No realistic intraday flow patterns.** Real RTGS systems show characteristic flow distributions: slow morning (banks conserving liquidity), midday pickup, afternoon rush, end-of-day urgency. All existing scenarios use either constant Poisson rates or crude multiplier adjustments. Actual Lynx/CHAPS data shows payment value distributions that are heavily right-skewed with distinct temporal clustering.

2. **Homogeneous agents.** Almost all scenarios use identical or near-identical agents. Real systems have enormous heterogeneity: large clearing banks process 40%+ of volume, small banks may process <1%. Tiered participation (direct vs. correspondent) creates fundamentally different strategic dynamics.

3. **No throughput guideline modelling.** Bank of Canada's Lynx requires ~50% by value settled by noon. Bank of England's CHAPS has similar throughput targets. These are critical coordination mechanisms absent from all scenarios.

4. **No payment type heterogeneity.** Real RTGS systems settle CLS (urgent, time-critical), regular interbank, securities settlement, and government payments — each with different urgency profiles and cost structures within the same day.

5. **Crisis scenarios are too mechanical.** Real crises involve information asymmetry, rumour, gradual counterparty withdrawal, and stigma — not just balance/collateral shocks applied at predetermined ticks.

6. **No seasonal/calendar effects.** Quarter-end, tax dates, and government bond settlement days create predictable but challenging flow patterns absent from the library.

7. **No operational disruption scenarios.** 9/11 showed what happens when a major participant goes offline. The BoE's "operational resilience" framework specifically requires such modelling.

### 3.3 Policies (26 production policies + 17 test policies)

#### Production Policies Catalogue

| # | Policy | Trees Used | Complexity | Strategy Summary | Realism |
|---|--------|-----------|-----------|-----------------|---------|
| 1 | `fifo` | payment_tree | Simple | Release in order when affordable | **Baseline** — Useful reference but no bank operates this way |
| 2 | `deadline` | payment_tree | Simple | Prioritise by deadline proximity | **Partial** — Captures urgency but ignores liquidity |
| 3 | `liquidity_aware` | payment_tree | Moderate | Consider balance before releasing | **Partial** — Missing time-of-day awareness |
| 4 | `cautious_liquidity_preserver` | payment_tree, bank_tree | Moderate | Buffer-based, conservative releases | **Moderate** — Closest to real conservative bank |
| 5 | `aggressive_market_maker` | payment_tree | Simple | Release almost everything immediately | **Partial** — Some banks do operate aggressively |
| 6 | `balanced_cost_optimizer` | payment_tree | Moderate | Balance delay vs. liquidity costs | **Moderate** — Cost-aware but static |
| 7 | `adaptive_liquidity_manager` | payment_tree, bank_tree | Moderate | Adjusts based on state registers | **Good** — Shows adaptive potential |
| 8 | `deadline_driven_trader` | payment_tree | Moderate | Deadline-focused with liquidity checks | **Moderate** |
| 9 | `efficient_memory_adaptive` | payment_tree, bank_tree | Complex | Uses state registers for cross-tick memory | **Good concept** — But doesn't model real treasury patterns |
| 10 | `efficient_proactive` | payment_tree, bank_tree | Moderate | Proactive release with budget limits | **Moderate** |
| 11 | `efficient_splitting` | payment_tree | Moderate | Split large payments | **Moderate** — Splitting is used in practice |
| 12 | `liquidity_splitting` | payment_tree | Moderate | Liquidity-aware splitting | **Moderate** |
| 13 | `smart_splitter` | payment_tree | Moderate | Intelligent split decisions | **Moderate** |
| 14 | `smart_budget_manager` | payment_tree, bank_tree | Complex | Budget-based release control | **Good** — Closest to real budget management |
| 15 | `memory_driven_strategist` | payment_tree, bank_tree | Complex | Memory-based adaptive strategy | **Good concept** |
| 16 | `agile_regional_bank` | multiple | Complex | Regional bank persona | **Moderate** — Named for role but doesn't fully model it |
| 17 | `goliath_national_bank` | multiple | Complex | Large bank persona | **Moderate** — Similar issue |
| 18 | `momentum_investment_bank` | multiple | Complex | Investment bank persona | **Moderate** |
| 19 | `sophisticated_adaptive_bank` | multiple | Complex | Multi-tree adaptive | **Good** |
| 20 | `target2_aggressive_settler` | payment_tree | Simple | Aggressive in TARGET2 context | **Moderate** |
| 21 | `target2_conservative_offsetter` | payment_tree | Moderate | Offset-aware conservative | **Good** — LSM awareness |
| 22 | `target2_crisis_proactive_manager` | multiple | Complex | Crisis-aware proactive | **Good** — Best crisis policy |
| 23 | `target2_crisis_risk_denier` | multiple | Complex | Deliberately poor crisis response | **Pedagogical** — Counter-example |
| 24 | `target2_limit_aware` | payment_tree | Moderate | Bilateral limit awareness | **Good** — Limit management |
| 25 | `target2_priority_aware` | payment_tree | Moderate | Priority system awareness | **Good** — T2 feature awareness |
| 26 | `target2_priority_escalator` | payment_tree | Moderate | Priority escalation strategy | **Good** |

### 3.4 Critique of Existing Policies

**What's good:**
- Good range from simple (FIFO) to complex (multi-tree adaptive)
- TARGET2-specific policies show LSM awareness
- State register usage demonstrates cross-tick memory
- Crisis policies show defensive/proactive patterns
- Budget management policies (SetReleaseBudget) model real controls

**What's missing:**

1. **No time-of-day liquidity management.** Real bank treasurers manage liquidity through the day: conserve in the morning (wait for incoming), release gradually, then accelerate in the afternoon. No policy uses `day_progress_fraction` or `system_tick_in_day` to implement this pattern.

2. **No reciprocity-based strategies.** Banks track whether counterparties are "doing their share" — if Bank B isn't sending payments, Bank A restricts outflows to B. The `my_bilateral_net_q2` field exists but no policy implements reciprocity logic.

3. **No throughput guideline compliance.** The `throughput_gap` and `my_throughput_fraction_today` fields exist but no policy uses them. This is a critical gap since throughput guidelines are the primary coordination mechanism in modern RTGS.

4. **No defensive crisis-mode switching.** Real treasurers switch to "defensive mode" during crises — reducing release budgets, tightening bilateral limits, and hoarding liquidity. Existing crisis policies are static rather than responsive.

5. **No morning funding strategy.** Many banks fund their settlement account via repo or money market before the day starts, then manage the declining balance. No policy models initial funding decisions beyond the Castro `liquidity_allocation_fraction`.

6. **No collateral optimization through the day.** Real banks post collateral in the morning when they need credit headroom, then withdraw it progressively. The collateral trees exist but no policy implements this temporal pattern.

---

## 4. New Scenario Proposals

### 4.1 Scenario: Realistic Intraday Flow Patterns ("Lynx Day")

**Motivation:** Real RTGS systems exhibit characteristic intraday patterns. Bank of Canada's Lynx data shows: 5% of value by 9am, 20% by 11am, 50% by 1pm (throughput guideline), 85% by 3pm, 100% by 5pm. This creates genuine strategic tension around morning conservation vs. early release.

```yaml
# Scenario: Realistic Intraday Flow Patterns
# Models a typical Lynx business day with time-varying payment arrivals
# matching observed Canadian LVTS/Lynx flow distributions.

simulation:
  ticks_per_day: 60    # 60 ticks = 8-hour day, each tick ≈ 8 minutes
  num_days: 5          # 5 business days for statistical stability
  rng_seed: 42

agents:
  # Large clearing bank (TD/RBC-scale) — 40% of system volume
  - id: CLEARING_MAJOR
    opening_balance: 25000000      # $250K starting reserves
    unsecured_cap: 15000000        # $150K intraday credit
    posted_collateral: 10000000
    collateral_haircut: 0.02
    policy:
      type: FromJson
      json_path: "policies/intraday_treasury.json"
    arrival_config:
      rate_per_tick: 3.5           # ~210 payments/day
      amount_distribution:
        type: LogNormal
        mean: 11.5                 # Median ~$1,000, mean ~$3,000
        std_dev: 1.2
      counterparty_weights:
        CLEARING_SECOND: 0.30
        REGIONAL_A: 0.25
        REGIONAL_B: 0.25
        SMALL_BANK: 0.20
      deadline_range: [15, 50]
      priority:
        type: Categorical
        values: [2, 5, 8, 10]
        weights: [0.20, 0.50, 0.20, 0.10]  # 10% urgent, 20% high, 50% normal, 20% low

  # Second large clearer — 30% of volume
  - id: CLEARING_SECOND
    opening_balance: 20000000
    unsecured_cap: 12000000
    posted_collateral: 8000000
    collateral_haircut: 0.02
    policy:
      type: FromJson
      json_path: "policies/intraday_treasury.json"
    arrival_config:
      rate_per_tick: 2.8
      amount_distribution:
        type: LogNormal
        mean: 11.2
        std_dev: 1.1
      counterparty_weights:
        CLEARING_MAJOR: 0.35
        REGIONAL_A: 0.25
        REGIONAL_B: 0.20
        SMALL_BANK: 0.20
      deadline_range: [15, 50]
      priority:
        type: Categorical
        values: [2, 5, 8]
        weights: [0.25, 0.55, 0.20]

  # Mid-size regional bank A — 15% of volume
  - id: REGIONAL_A
    opening_balance: 8000000
    unsecured_cap: 5000000
    posted_collateral: 3000000
    collateral_haircut: 0.03
    policy:
      type: FromJson
      json_path: "policies/regional_cautious.json"
    arrival_config:
      rate_per_tick: 1.5
      amount_distribution:
        type: LogNormal
        mean: 10.5
        std_dev: 0.9
      counterparty_weights:
        CLEARING_MAJOR: 0.40
        CLEARING_SECOND: 0.35
        REGIONAL_B: 0.15
        SMALL_BANK: 0.10
      deadline_range: [20, 55]
      priority:
        type: Fixed
        value: 5

  # Mid-size regional bank B — 10% of volume
  - id: REGIONAL_B
    opening_balance: 6000000
    unsecured_cap: 3500000
    posted_collateral: 2000000
    collateral_haircut: 0.03
    policy:
      type: FromJson
      json_path: "policies/regional_cautious.json"
    arrival_config:
      rate_per_tick: 1.0
      amount_distribution:
        type: Uniform
        min: 50000
        max: 300000
      counterparty_weights:
        CLEARING_MAJOR: 0.40
        CLEARING_SECOND: 0.30
        REGIONAL_A: 0.20
        SMALL_BANK: 0.10
      deadline_range: [20, 55]
      priority:
        type: Fixed
        value: 5

  # Small participant — 5% of volume
  - id: SMALL_BANK
    opening_balance: 3000000
    unsecured_cap: 1500000
    policy:
      type: FromJson
      json_path: "policies/small_bank_conservative.json"
    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: Uniform
        min: 20000
        max: 200000
      counterparty_weights:
        CLEARING_MAJOR: 0.45
        CLEARING_SECOND: 0.35
        REGIONAL_A: 0.10
        REGIONAL_B: 0.10
      deadline_range: [25, 58]
      priority:
        type: Fixed
        value: 5

# Model intraday flow variation via arrival rate changes
# Pattern: slow morning → midday pickup → afternoon rush → EOD urgency
scenario_events:
  # Morning slow start (ticks 0-14, ~7:30-9:30am)
  - type: GlobalArrivalRateChange
    multiplier: 0.4
    schedule:
      type: OneTime
      tick: 0

  # Mid-morning pickup (ticks 15-24, ~9:30-11:00am)
  - type: GlobalArrivalRateChange
    multiplier: 0.8
    schedule:
      type: OneTime
      tick: 15

  # Noon activity (ticks 25-34, ~11:00am-1:00pm)
  - type: GlobalArrivalRateChange
    multiplier: 1.2
    schedule:
      type: OneTime
      tick: 25

  # Afternoon rush (ticks 35-49, ~1:00-3:30pm)
  - type: GlobalArrivalRateChange
    multiplier: 1.6
    schedule:
      type: OneTime
      tick: 35

  # EOD wind-down (ticks 50-59, ~3:30-5:30pm)
  - type: GlobalArrivalRateChange
    multiplier: 0.6
    schedule:
      type: OneTime
      tick: 50

  # Deadline tightening in afternoon (reflects real EOD pressure)
  - type: DeadlineWindowChange
    min_deadline: 5
    max_deadline: 15
    schedule:
      type: OneTime
      tick: 45

cost_rates:
  delay_cost_per_tick_per_cent: 0.0002
  overdraft_bps_per_tick: 0.5
  collateral_cost_per_tick_bps: 0.0003
  eod_penalty_per_transaction: 500000
  deadline_penalty: 200000
  split_friction_cost: 5000
  overdue_delay_multiplier: 5.0
  priority_delay_multipliers:
    urgent_multiplier: 2.0
    normal_multiplier: 1.0
    low_multiplier: 0.3

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 5
  max_cycles_per_tick: 15

algorithm_sequencing: true
entry_disposition_offsetting: true
```

**Research questions:** Do agents learn morning conservation? Does the afternoon rush create gridlock? How do heterogeneous banks coordinate under asymmetric flow patterns?

---

### 4.2 Scenario: Tiered Participation ("Hub and Spoke")

**Motivation:** In real RTGS, direct participants (clearing banks) process payments on behalf of their correspondent banking clients. Correspondent banks do not directly access the RTGS; their payments are netted and batched by the direct participant. This creates hub-and-spoke dynamics with very different strategic considerations for hubs vs. spokes.

```yaml
# Scenario: Tiered Participation
# Models direct members processing on behalf of correspondents.
# The correspondent banks' flows are modelled as additional payment
# obligations on the direct members, with different priority profiles.

simulation:
  ticks_per_day: 48    # 48 ticks ≈ 10-minute intervals over 8 hours
  num_days: 5
  rng_seed: 42

agents:
  # Direct participant: Large clearer acting as correspondent hub
  # Processes own payments PLUS those of 3 correspondent clients
  - id: HUB_BANK_A
    opening_balance: 40000000      # $400K — needs more because of correspondent flows
    unsecured_cap: 25000000
    posted_collateral: 15000000
    collateral_haircut: 0.02
    bilateral_limits:
      HUB_BANK_B: 20000000
      DIRECT_SMALL: 10000000
    multilateral_limit: 35000000
    policy:
      type: FromJson
      json_path: "policies/hub_bank_treasury.json"
    arrival_config:
      rate_per_tick: 5.0           # Very high: own + correspondent flows
      amount_distribution:
        type: LogNormal
        mean: 11.0
        std_dev: 1.5               # High variance: small correspondent payments + large own
      counterparty_weights:
        HUB_BANK_B: 0.50
        DIRECT_SMALL: 0.50
      deadline_range: [10, 40]
      priority:
        type: Categorical
        values: [3, 5, 8, 10]
        weights: [0.30, 0.40, 0.20, 0.10]  # Many low-priority correspondent payments

  # Direct participant: Second large clearer
  - id: HUB_BANK_B
    opening_balance: 35000000
    unsecured_cap: 20000000
    posted_collateral: 12000000
    collateral_haircut: 0.02
    bilateral_limits:
      HUB_BANK_A: 18000000
      DIRECT_SMALL: 8000000
    multilateral_limit: 30000000
    policy:
      type: FromJson
      json_path: "policies/hub_bank_treasury.json"
    arrival_config:
      rate_per_tick: 4.5
      amount_distribution:
        type: LogNormal
        mean: 11.0
        std_dev: 1.4
      counterparty_weights:
        HUB_BANK_A: 0.55
        DIRECT_SMALL: 0.45
      deadline_range: [10, 40]
      priority:
        type: Categorical
        values: [3, 5, 8]
        weights: [0.25, 0.50, 0.25]

  # Small direct participant (no correspondent clients)
  - id: DIRECT_SMALL
    opening_balance: 5000000
    unsecured_cap: 3000000
    bilateral_limits:
      HUB_BANK_A: 4000000
      HUB_BANK_B: 4000000
    multilateral_limit: 7000000
    policy:
      type: FromJson
      json_path: "policies/small_bank_conservative.json"
    arrival_config:
      rate_per_tick: 0.8
      amount_distribution:
        type: Uniform
        min: 30000
        max: 250000
      counterparty_weights:
        HUB_BANK_A: 0.55
        HUB_BANK_B: 0.45
      deadline_range: [15, 45]
      priority:
        type: Fixed
        value: 5

# Inject "correspondent payment batches" at regular intervals
# Simulates the hub bank's internal netting cycle releasing batched payments
scenario_events:
  # Morning correspondent batch (tick 6, ~9:00am)
  - type: CustomTransactionArrival
    from_agent: HUB_BANK_A
    to_agent: HUB_BANK_B
    amount: 5000000     # Large netted correspondent batch
    priority: 3         # Low priority — can be deferred
    deadline: 35
    is_divisible: true
    schedule:
      type: Repeating
      start_tick: 6
      interval: 48       # Once per day
      end_tick: 240

  # Midday CLS settlement obligation (urgent, every day at tick 20)
  - type: CustomTransactionArrival
    from_agent: HUB_BANK_A
    to_agent: HUB_BANK_B
    amount: 8000000
    priority: 10         # CLS: maximally urgent
    deadline: 5          # Very tight deadline
    schedule:
      type: Repeating
      start_tick: 20
      interval: 48
      end_tick: 240

  - type: CustomTransactionArrival
    from_agent: HUB_BANK_B
    to_agent: HUB_BANK_A
    amount: 7500000
    priority: 10
    deadline: 5
    schedule:
      type: Repeating
      start_tick: 20
      interval: 48
      end_tick: 240

cost_rates:
  delay_cost_per_tick_per_cent: 0.0002
  overdraft_bps_per_tick: 0.6
  collateral_cost_per_tick_bps: 0.0004
  eod_penalty_per_transaction: 500000
  deadline_penalty: 250000
  split_friction_cost: 5000
  overdue_delay_multiplier: 5.0
  priority_delay_multipliers:
    urgent_multiplier: 3.0    # CLS payments have extreme urgency cost
    normal_multiplier: 1.0
    low_multiplier: 0.3       # Correspondent batches are flexible

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 3
  max_cycles_per_tick: 10

algorithm_sequencing: true
entry_disposition_offsetting: true
```

**Research questions:** How do hub banks manage the dual responsibility of own vs. correspondent payments? Does the CLS obligation create systemic liquidity pressure? Does the small direct participant free-ride on hub bank liquidity?

---

### 4.3 Scenario: Throughput Guideline Compliance

**Motivation:** BoC's Lynx and BoE's CHAPS both have throughput guidelines requiring banks to settle a target percentage of payments by specific times. These are "soft" requirements — no automatic penalty but regulatory attention for non-compliance.

```yaml
# Scenario: Throughput Guideline Compliance
# Tests whether agents can learn to meet throughput targets while minimising costs.
# Modelled on CHAPS throughput guidelines: 50% by noon, 75% by 2:30pm.

simulation:
  ticks_per_day: 48
  num_days: 10         # Enough days to observe compliance patterns
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 15000000
    unsecured_cap: 8000000
    posted_collateral: 5000000
    collateral_haircut: 0.02
    policy:
      type: FromJson
      json_path: "policies/throughput_compliant.json"
    arrival_config:
      rate_per_tick: 2.5
      amount_distribution:
        type: LogNormal
        mean: 10.8
        std_dev: 1.0
      counterparty_weights:
        BANK_B: 0.40
        BANK_C: 0.35
        BANK_D: 0.25
      deadline_range: [12, 40]
      priority:
        type: Categorical
        values: [3, 5, 8]
        weights: [0.20, 0.60, 0.20]

  - id: BANK_B
    opening_balance: 14000000
    unsecured_cap: 7500000
    posted_collateral: 4500000
    collateral_haircut: 0.02
    policy:
      type: FromJson
      json_path: "policies/throughput_compliant.json"
    arrival_config:
      rate_per_tick: 2.3
      amount_distribution:
        type: LogNormal
        mean: 10.7
        std_dev: 1.0
      counterparty_weights:
        BANK_A: 0.40
        BANK_C: 0.30
        BANK_D: 0.30
      deadline_range: [12, 40]
      priority:
        type: Categorical
        values: [3, 5, 8]
        weights: [0.20, 0.60, 0.20]

  - id: BANK_C
    opening_balance: 10000000
    unsecured_cap: 5000000
    posted_collateral: 3000000
    collateral_haircut: 0.03
    policy:
      type: FromJson
      json_path: "policies/throughput_compliant.json"
    arrival_config:
      rate_per_tick: 1.8
      amount_distribution:
        type: LogNormal
        mean: 10.5
        std_dev: 0.9
      counterparty_weights:
        BANK_A: 0.35
        BANK_B: 0.35
        BANK_D: 0.30
      deadline_range: [15, 42]
      priority:
        type: Fixed
        value: 5

  - id: BANK_D
    opening_balance: 8000000
    unsecured_cap: 4000000
    policy:
      type: FromJson
      json_path: "policies/throughput_laggard.json"  # Deliberately non-compliant
    arrival_config:
      rate_per_tick: 1.5
      amount_distribution:
        type: Uniform
        min: 40000
        max: 250000
      counterparty_weights:
        BANK_A: 0.35
        BANK_B: 0.35
        BANK_C: 0.30
      deadline_range: [15, 42]
      priority:
        type: Fixed
        value: 5

# Model throughput guideline pressure via intraday flow pattern
scenario_events:
  # Morning slow
  - type: GlobalArrivalRateChange
    multiplier: 0.5
    schedule: { type: OneTime, tick: 0 }

  # Mid-morning: guideline pressure begins
  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule: { type: OneTime, tick: 12 }

  # Post-noon: if behind guideline, pressure mounts
  - type: GlobalArrivalRateChange
    multiplier: 1.3
    schedule: { type: OneTime, tick: 24 }

  # Afternoon rush
  - type: GlobalArrivalRateChange
    multiplier: 1.5
    schedule: { type: OneTime, tick: 32 }

  # EOD wind-down
  - type: GlobalArrivalRateChange
    multiplier: 0.5
    schedule: { type: OneTime, tick: 44 }

cost_rates:
  delay_cost_per_tick_per_cent: 0.0003     # Slightly higher to encourage compliance
  overdraft_bps_per_tick: 0.5
  collateral_cost_per_tick_bps: 0.0003
  eod_penalty_per_transaction: 400000
  deadline_penalty: 200000
  split_friction_cost: 5000
  overdue_delay_multiplier: 5.0

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10

algorithm_sequencing: true
entry_disposition_offsetting: true
```

**Research questions:** Can agents learn throughput-compliant strategies? Does one non-compliant agent (BANK_D) create negative externalities for others? What's the cost of compliance vs. non-compliance?

---

### 4.4 Scenario: Information-Driven Crisis ("Rumour Mill")

**Motivation:** Real crises develop through information channels, not just balance shocks. When rumours circulate about a counterparty's creditworthiness, other banks gradually withdraw bilateral credit lines and slow payments — a dynamic that current crisis scenarios miss entirely.

```yaml
# Scenario: Information-Driven Crisis
# Models gradual counterparty confidence erosion.
# STRESSED_BANK faces progressive credit line withdrawal as rumours spread.

simulation:
  ticks_per_day: 60
  num_days: 10
  rng_seed: 42

agents:
  - id: STRESSED_BANK
    opening_balance: 12000000
    unsecured_cap: 8000000
    posted_collateral: 5000000
    collateral_haircut: 0.03
    bilateral_limits:
      CAUTIOUS_BANK: 6000000
      NEUTRAL_BANK: 6000000
      AGGRESSIVE_BANK: 6000000
    multilateral_limit: 15000000
    policy:
      type: FromJson
      json_path: "policies/defensive_treasury.json"
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10.8
        std_dev: 1.0
      counterparty_weights:
        CAUTIOUS_BANK: 0.35
        NEUTRAL_BANK: 0.35
        AGGRESSIVE_BANK: 0.30
      deadline_range: [15, 50]

  - id: CAUTIOUS_BANK
    opening_balance: 15000000
    unsecured_cap: 10000000
    bilateral_limits:
      STRESSED_BANK: 8000000     # Will be reduced via events
      NEUTRAL_BANK: 7000000
      AGGRESSIVE_BANK: 7000000
    multilateral_limit: 18000000
    policy:
      type: FromJson
      json_path: "policies/crisis_defensive.json"
    arrival_config:
      rate_per_tick: 2.2
      amount_distribution:
        type: LogNormal
        mean: 10.8
        std_dev: 1.0
      counterparty_weights:
        STRESSED_BANK: 0.35
        NEUTRAL_BANK: 0.35
        AGGRESSIVE_BANK: 0.30
      deadline_range: [15, 50]

  - id: NEUTRAL_BANK
    opening_balance: 14000000
    unsecured_cap: 9000000
    bilateral_limits:
      STRESSED_BANK: 7000000
      CAUTIOUS_BANK: 7000000
      AGGRESSIVE_BANK: 7000000
    multilateral_limit: 16000000
    policy:
      type: FromJson
      json_path: "policies/intraday_treasury.json"
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10.5
        std_dev: 0.9
      counterparty_weights:
        STRESSED_BANK: 0.35
        CAUTIOUS_BANK: 0.35
        AGGRESSIVE_BANK: 0.30
      deadline_range: [15, 50]

  - id: AGGRESSIVE_BANK
    opening_balance: 16000000
    unsecured_cap: 12000000
    policy:
      type: FromJson
      json_path: "policies/aggressive_market_maker.json"
    arrival_config:
      rate_per_tick: 2.5
      amount_distribution:
        type: LogNormal
        mean: 11.0
        std_dev: 1.2
      counterparty_weights:
        STRESSED_BANK: 0.35
        CAUTIOUS_BANK: 0.35
        NEUTRAL_BANK: 0.30
      deadline_range: [12, 45]

scenario_events:
  # Days 1-3: Normal operations
  # No events — establish baseline

  # Day 4 (tick 180): First rumour — CAUTIOUS_BANK starts reducing exposure
  # Model: reduce counterparty weights to STRESSED_BANK
  - type: CounterpartyWeightChange
    agent: CAUTIOUS_BANK
    new_weights:
      STRESSED_BANK: 0.20      # Reduced from 0.35
      NEUTRAL_BANK: 0.45
      AGGRESSIVE_BANK: 0.35
    schedule: { type: OneTime, tick: 180 }

  # Day 5 (tick 240): Rumour spreads — NEUTRAL_BANK joins
  - type: CounterpartyWeightChange
    agent: NEUTRAL_BANK
    new_weights:
      STRESSED_BANK: 0.20
      CAUTIOUS_BANK: 0.45
      AGGRESSIVE_BANK: 0.35
    schedule: { type: OneTime, tick: 300 }

  # Day 5 (tick 310): STRESSED_BANK loses some collateral (margin call)
  - type: CollateralAdjustment
    agent: STRESSED_BANK
    delta: -2000000
    schedule: { type: OneTime, tick: 310 }

  # Day 6 (tick 360): Crisis deepens — AGGRESSIVE_BANK also pulls back
  - type: CounterpartyWeightChange
    agent: AGGRESSIVE_BANK
    new_weights:
      STRESSED_BANK: 0.15
      CAUTIOUS_BANK: 0.45
      NEUTRAL_BANK: 0.40
    schedule: { type: OneTime, tick: 360 }

  # Day 7 (tick 420): STRESSED_BANK's arrival rate drops (clients leaving)
  - type: AgentArrivalRateChange
    agent: STRESSED_BANK
    multiplier: 0.6
    schedule: { type: OneTime, tick: 420 }

  # Day 7 (tick 440): Further collateral erosion
  - type: CollateralAdjustment
    agent: STRESSED_BANK
    delta: -2000000
    schedule: { type: OneTime, tick: 440 }

  # Day 8 (tick 480): Central bank intervenes with emergency lending
  - type: DirectTransfer
    from_agent: NEUTRAL_BANK      # Proxy for central bank
    to_agent: STRESSED_BANK
    amount: 20000000
    schedule: { type: OneTime, tick: 480 }

  - type: CollateralAdjustment
    agent: STRESSED_BANK
    delta: 10000000
    schedule: { type: OneTime, tick: 480 }

  # Day 9-10: Gradual normalisation
  - type: CounterpartyWeightChange
    agent: CAUTIOUS_BANK
    new_weights:
      STRESSED_BANK: 0.25
      NEUTRAL_BANK: 0.40
      AGGRESSIVE_BANK: 0.35
    schedule: { type: OneTime, tick: 540 }

  - type: AgentArrivalRateChange
    agent: STRESSED_BANK
    multiplier: 0.8
    schedule: { type: OneTime, tick: 540 }

cost_rates:
  delay_cost_per_tick_per_cent: 0.0002
  overdraft_bps_per_tick: 0.6
  collateral_cost_per_tick_bps: 0.0003
  eod_penalty_per_transaction: 500000
  deadline_penalty: 200000
  split_friction_cost: 5000
  overdue_delay_multiplier: 5.0

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10
```

**Research questions:** How does gradual counterparty withdrawal compare to sudden shocks? Can the stressed bank's defensive policy prevent liquidity death spiral? Does central bank intervention need to arrive before the tipping point?

---

### 4.5 Scenario: Lehman Monday

**Motivation:** Lehman Brothers' bankruptcy (15 September 2008) caused immediate cascading effects in RTGS systems globally. Banks that had pending payments to Lehman suddenly faced settlement uncertainty. The scenario models a major participant effectively ceasing to send payments while its counterparties must manage the fallout.

```yaml
# Scenario: Lehman Monday
# Models sudden counterparty failure. FAILED_BANK stops sending payments
# on Day 3. Other banks must adapt their strategies in real-time.

simulation:
  ticks_per_day: 60
  num_days: 7
  rng_seed: 42

agents:
  - id: FAILED_BANK
    opening_balance: 18000000
    unsecured_cap: 10000000
    policy:
      type: FromJson
      json_path: "policies/fifo.json"  # Continues with simple policy
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution:
        type: LogNormal
        mean: 11.2
        std_dev: 1.3
      counterparty_weights:
        BANK_B: 0.30
        BANK_C: 0.30
        BANK_D: 0.20
        BANK_E: 0.20
      deadline_range: [15, 50]

  - id: BANK_B
    opening_balance: 20000000
    unsecured_cap: 12000000
    posted_collateral: 8000000
    collateral_haircut: 0.02
    policy:
      type: FromJson
      json_path: "policies/crisis_adaptive.json"
    arrival_config:
      rate_per_tick: 2.5
      amount_distribution:
        type: LogNormal
        mean: 11.0
        std_dev: 1.1
      counterparty_weights:
        FAILED_BANK: 0.30
        BANK_C: 0.25
        BANK_D: 0.25
        BANK_E: 0.20
      deadline_range: [15, 50]

  - id: BANK_C
    opening_balance: 16000000
    unsecured_cap: 9000000
    posted_collateral: 6000000
    collateral_haircut: 0.02
    policy:
      type: FromJson
      json_path: "policies/crisis_adaptive.json"
    arrival_config:
      rate_per_tick: 2.2
      amount_distribution:
        type: LogNormal
        mean: 10.8
        std_dev: 1.0
      counterparty_weights:
        FAILED_BANK: 0.25
        BANK_B: 0.30
        BANK_D: 0.25
        BANK_E: 0.20
      deadline_range: [15, 50]

  - id: BANK_D
    opening_balance: 12000000
    unsecured_cap: 6000000
    policy:
      type: FromJson
      json_path: "policies/intraday_treasury.json"
    arrival_config:
      rate_per_tick: 1.8
      amount_distribution:
        type: Uniform
        min: 50000
        max: 350000
      counterparty_weights:
        FAILED_BANK: 0.20
        BANK_B: 0.30
        BANK_C: 0.30
        BANK_E: 0.20
      deadline_range: [15, 50]

  - id: BANK_E
    opening_balance: 10000000
    unsecured_cap: 5000000
    policy:
      type: FromJson
      json_path: "policies/small_bank_conservative.json"
    arrival_config:
      rate_per_tick: 1.5
      amount_distribution:
        type: Uniform
        min: 30000
        max: 250000
      counterparty_weights:
        FAILED_BANK: 0.20
        BANK_B: 0.30
        BANK_C: 0.30
        BANK_D: 0.20
      deadline_range: [15, 50]

scenario_events:
  # Days 1-2: Normal operations
  
  # Day 3, tick 120: FAILED_BANK stops sending payments
  - type: AgentArrivalRateChange
    agent: FAILED_BANK
    multiplier: 0.0     # Complete cessation
    schedule: { type: OneTime, tick: 120 }

  # Other banks stop sending TO failed bank (counterparty weight redirect)
  - type: CounterpartyWeightChange
    agent: BANK_B
    new_weights:
      FAILED_BANK: 0.0
      BANK_C: 0.35
      BANK_D: 0.35
      BANK_E: 0.30
    schedule: { type: OneTime, tick: 125 }

  - type: CounterpartyWeightChange
    agent: BANK_C
    new_weights:
      FAILED_BANK: 0.0
      BANK_B: 0.40
      BANK_D: 0.35
      BANK_E: 0.25
    schedule: { type: OneTime, tick: 125 }

  - type: CounterpartyWeightChange
    agent: BANK_D
    new_weights:
      FAILED_BANK: 0.0
      BANK_B: 0.40
      BANK_C: 0.35
      BANK_E: 0.25
    schedule: { type: OneTime, tick: 128 }

  - type: CounterpartyWeightChange
    agent: BANK_E
    new_weights:
      FAILED_BANK: 0.0
      BANK_B: 0.40
      BANK_C: 0.35
      BANK_D: 0.25
    schedule: { type: OneTime, tick: 130 }

  # Day 3: Global activity drops (market freeze)
  - type: GlobalArrivalRateChange
    multiplier: 0.6
    schedule: { type: OneTime, tick: 135 }

  # Day 4: Partial recovery
  - type: GlobalArrivalRateChange
    multiplier: 0.8
    schedule: { type: OneTime, tick: 180 }

  # Day 5: Near-normal operations (without FAILED_BANK)
  - type: GlobalArrivalRateChange
    multiplier: 0.95
    schedule: { type: OneTime, tick: 240 }

  # Day 6-7: Full normalisation
  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule: { type: OneTime, tick: 300 }

cost_rates:
  delay_cost_per_tick_per_cent: 0.0002
  overdraft_bps_per_tick: 0.6
  collateral_cost_per_tick_bps: 0.0003
  eod_penalty_per_transaction: 500000
  deadline_penalty: 250000
  split_friction_cost: 5000
  overdue_delay_multiplier: 5.0

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 5
  max_cycles_per_tick: 10
```

---

### 4.6 Scenario: Operational Disruption (9/11-style)

**Motivation:** On September 11, 2001, Bank of New York's inability to process payments for several hours caused massive liquidity dislocations in Fedwire. Remaining participants had to manage without a key counterparty's outflows.

*Schema approach:* Similar to Lehman Monday but the disrupted bank eventually comes back online. Use `AgentArrivalRateChange` to zero out, then restore. Add `DirectTransfer` to model Fed liquidity injection.

```yaml
# Key differentiation from Lehman: DISRUPTED_BANK returns at Day 2 tick 40
# Central bank provides massive emergency liquidity to prevent cascade
scenario_events:
  # Day 1 tick 20: Disruption begins
  - type: AgentArrivalRateChange
    agent: DISRUPTED_BANK
    multiplier: 0.0
    schedule: { type: OneTime, tick: 20 }

  # Day 1 tick 25: Central bank emergency liquidity (to all surviving banks)
  - type: DirectTransfer
    from_agent: DISRUPTED_BANK      # Proxy: central bank injects via balance
    to_agent: BANK_A
    amount: 30000000
    schedule: { type: OneTime, tick: 25 }

  # Day 2 tick 40: DISRUPTED_BANK comes back online
  - type: AgentArrivalRateChange
    agent: DISRUPTED_BANK
    multiplier: 1.5                  # Catch-up processing
    schedule: { type: OneTime, tick: 100 }

  # Day 2 tick 50: Back to normal
  - type: AgentArrivalRateChange
    agent: DISRUPTED_BANK
    multiplier: 1.0
    schedule: { type: OneTime, tick: 110 }
```

---

### 4.7 Scenario: Seasonal Patterns — Quarter-End

**Motivation:** Quarter-end days see 2-3× normal payment volumes in RTGS systems due to securities settlement, dividend payments, and corporate treasury activity.

```yaml
# Scenario: Quarter-End Day
# 5-day simulation where Day 3 is quarter-end with 2.5× volume

simulation:
  ticks_per_day: 60
  num_days: 5
  rng_seed: 42

# Standard 4-bank setup (same as Lynx Day agents)...

scenario_events:
  # Days 1-2: Normal
  
  # Day 3 (quarter-end): Volume surge
  - type: GlobalArrivalRateChange
    multiplier: 2.5
    schedule: { type: OneTime, tick: 120 }

  # Day 3: Large corporate dividend payments (time-critical)
  - type: CustomTransactionArrival
    from_agent: CLEARING_MAJOR
    to_agent: CLEARING_SECOND
    amount: 15000000
    priority: 9
    deadline: 10          # Very tight — must settle by noon
    schedule: { type: OneTime, tick: 125 }

  - type: CustomTransactionArrival
    from_agent: CLEARING_MAJOR
    to_agent: REGIONAL_A
    amount: 8000000
    priority: 9
    deadline: 10
    schedule: { type: OneTime, tick: 125 }

  # Day 3: Securities settlement batch
  - type: CustomTransactionArrival
    from_agent: CLEARING_SECOND
    to_agent: CLEARING_MAJOR
    amount: 12000000
    priority: 8
    deadline: 15
    schedule: { type: OneTime, tick: 130 }

  # Day 3 afternoon: Government bond settlement
  - type: CustomTransactionArrival
    from_agent: REGIONAL_A
    to_agent: CLEARING_MAJOR
    amount: 10000000
    priority: 10
    deadline: 8
    schedule: { type: OneTime, tick: 155 }

  # Day 4: Back to normal
  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule: { type: OneTime, tick: 180 }

  # Day 4: Below-normal post-quarter activity
  - type: GlobalArrivalRateChange
    multiplier: 0.7
    schedule: { type: OneTime, tick: 180 }

  # Day 5: Normal
  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule: { type: OneTime, tick: 240 }
```

---

### 4.8 Scenario: Heterogeneous Payment Types

**Motivation:** Real RTGS days involve multiple payment types with fundamentally different urgency and cost profiles. CLS settlements must occur within a narrow window; regular interbank payments have moderate deadlines; government tax receipts are deferrable.

*Implementation approach:* Use `CustomTransactionArrival` events with different priority levels and deadline ranges to create mixed payment streams alongside stochastic arrivals:

```yaml
# Mix of payment types injected deterministically alongside stochastic base flow
scenario_events:
  # CLS settlements: priority 10, deadline 3 ticks, every day at tick 15
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 10000000
    priority: 10
    deadline: 3
    is_divisible: false    # CLS: all-or-nothing
    schedule:
      type: Repeating
      start_tick: 15
      interval: 60         # Every day
      end_tick: 300

  # Securities DVP settlement: priority 8, deadline 10, every day at tick 25
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_C
    amount: 5000000
    priority: 8
    deadline: 10
    is_divisible: true
    schedule:
      type: Repeating
      start_tick: 25
      interval: 60
      end_tick: 300

  # Government tax transfers: priority 3, deadline 50, deferrable
  - type: CustomTransactionArrival
    from_agent: BANK_C
    to_agent: BANK_A
    amount: 3000000
    priority: 3
    deadline: 50           # Very flexible timing
    is_divisible: true
    schedule:
      type: Repeating
      start_tick: 5
      interval: 60
      end_tick: 300
```

---

### 4.9 Scenario: Standing Facility Stigma

**Motivation:** Central bank standing lending facilities are available as a liquidity backstop, but banks are reluctant to use them due to reputational "stigma" — the market may interpret usage as a sign of financial weakness. This creates a strategic tension where banks prefer expensive market borrowing over cheaper central bank facilities.

*Schema limitation:* SimCash doesn't have an explicit standing facility mechanism. We can approximate it using high-cost collateral posting as a proxy: collateral is cheap to post (representing facility availability) but we set high `collateral_cost_per_tick_bps` to represent stigma costs. Banks with low opening balances and high `unsecured_cap` face the choice of using the facility (posting collateral to access credit) or managing without.

```yaml
# Scenario: Standing Facility Stigma
# High collateral costs represent reputational stigma of central bank borrowing

cost_rates:
  delay_cost_per_tick_per_cent: 0.0002
  overdraft_bps_per_tick: 0.3          # Moderate overdraft cost
  collateral_cost_per_tick_bps: 0.005  # VERY HIGH — stigma premium
  eod_penalty_per_transaction: 500000
  deadline_penalty: 200000

agents:
  - id: WELL_FUNDED_BANK
    opening_balance: 20000000
    unsecured_cap: 5000000
    posted_collateral: 0               # Doesn't need facility
    # max_collateral_capacity implicit — can post but won't want to
    # ...

  - id: LIQUIDITY_CONSTRAINED_BANK
    opening_balance: 5000000           # Low starting balance
    unsecured_cap: 15000000            # Generous facility access
    posted_collateral: 0
    # Must choose: post collateral (stigma cost) or manage with limited funds
    # ...
```

---

### 4.10 Scenario: Herstatt-Style Settlement Risk

**Motivation:** Bankhaus Herstatt (1974) failed after receiving DEM payments in European hours but before making USD payments in US hours. This time-zone mismatch creates settlement risk in cross-currency transactions. CLS Bank was created to eliminate this via payment-versus-payment (PvP) settlement.

*Schema approach:* Model as a multi-day scenario where payments between "time zone A" and "time zone B" banks arrive at different ticks, creating asymmetric settlement windows. Use tight deadlines on one leg to simulate the PvP coordination challenge.

```yaml
# Scenario: Herstatt Settlement Risk
# Banks in different "time zones" with overlapping settlement windows

simulation:
  ticks_per_day: 48
  num_days: 5
  rng_seed: 42

agents:
  # European bank: active ticks 0-30, settles early
  - id: EUR_BANK
    opening_balance: 15000000
    unsecured_cap: 8000000
    arrival_config:
      rate_per_tick: 2.0
      # ... standard config
      deadline_range: [8, 25]    # Tight deadlines — European hours

  # US bank: active ticks 15-48, settles late
  - id: USD_BANK
    opening_balance: 15000000
    unsecured_cap: 8000000
    arrival_config:
      rate_per_tick: 2.0
      deadline_range: [20, 45]   # Longer deadlines — US hours

  # CLS-like intermediary: bridges time zones
  - id: CLS_BRIDGE
    opening_balance: 25000000    # Large reserves for bridging
    unsecured_cap: 15000000
    arrival_config:
      rate_per_tick: 0.5         # Mostly processes cross-border
      deadline_range: [5, 15]    # Very tight PvP deadlines

scenario_events:
  # European opening: EUR_BANK active, USD_BANK dormant
  - type: AgentArrivalRateChange
    agent: EUR_BANK
    multiplier: 1.5
    schedule: { type: OneTime, tick: 0 }

  - type: AgentArrivalRateChange
    agent: USD_BANK
    multiplier: 0.2              # Minimal overnight activity
    schedule: { type: OneTime, tick: 0 }

  # Overlap window (ticks 15-30): Both active
  - type: AgentArrivalRateChange
    agent: USD_BANK
    multiplier: 1.5
    schedule: { type: OneTime, tick: 15 }

  # European close (tick 30): EUR_BANK winds down
  - type: AgentArrivalRateChange
    agent: EUR_BANK
    multiplier: 0.2
    schedule: { type: OneTime, tick: 30 }

  # CLS settlement window: Paired PvP payments at tick 20 (overlap)
  - type: CustomTransactionArrival
    from_agent: EUR_BANK
    to_agent: CLS_BRIDGE
    amount: 8000000
    priority: 10
    deadline: 5                  # Must settle within PvP window
    schedule:
      type: Repeating
      start_tick: 20
      interval: 48
      end_tick: 240

  - type: CustomTransactionArrival
    from_agent: CLS_BRIDGE
    to_agent: USD_BANK
    amount: 8000000
    priority: 10
    deadline: 5
    schedule:
      type: Repeating
      start_tick: 21             # Slight delay — CLS processes then releases
      interval: 48
      end_tick: 240
```

---

## 5. New Policy Proposals

### 5.1 Policy: Intraday Treasury Manager

**Concept:** Implements realistic bank treasury practice with time-of-day liquidity management.

**Decision logic:**

```
BANK_TREE:
  Morning phase (day_progress < 0.3):
    SetReleaseBudget(max_value = 30% of queue1_total_value)
    SetState(bank_state_phase = 1, "morning conservation")
  
  Midday phase (0.3 ≤ day_progress < 0.6):
    SetReleaseBudget(max_value = 70% of queue1_total_value)
    SetState(bank_state_phase = 2, "midday release")
  
  Afternoon phase (0.6 ≤ day_progress < 0.85):
    SetReleaseBudget(max_value = 100% of queue1_total_value)
    SetState(bank_state_phase = 3, "afternoon flush")
  
  EOD rush (day_progress ≥ 0.85):
    SetReleaseBudget(max_value = queue1_total_value)  // Unlimited
    SetState(bank_state_phase = 4, "EOD rush")

PAYMENT_TREE:
  If priority >= 8 (urgent): Release always
  If ticks_to_deadline <= 5: Release always
  If bank_state_phase == 1 (morning):
    If effective_liquidity >= amount * 3.0: Release
    Else: Hold (reason: "morning conservation")
  If bank_state_phase == 2 (midday):
    If effective_liquidity >= amount * 1.5: Release
    Else: Hold (reason: "awaiting inflows")
  If bank_state_phase >= 3 (afternoon/EOD):
    If effective_liquidity >= amount: Release
    Else if is_eod_rush: ReleaseWithCredit
    Else: Hold

STRATEGIC_COLLATERAL_TREE:
  If day_progress < 0.2 AND queue1_liquidity_gap > 0:
    PostCollateral(amount = queue1_liquidity_gap, auto_withdraw = 20 ticks)
  Else: HoldCollateral

END_OF_TICK_COLLATERAL_TREE:
  If day_progress > 0.8 AND excess_collateral > 0:
    WithdrawCollateral(amount = excess_collateral, reason: "EndOfDayCleanup")
  Else: HoldCollateral
```

**Parameters:**
- `morning_budget_fraction`: 0.3
- `midday_budget_fraction`: 0.7
- `morning_buffer_multiplier`: 3.0
- `midday_buffer_multiplier`: 1.5
- `urgency_threshold`: 5

---

### 5.2 Policy: Reciprocity-Based Strategist

**Concept:** Banks track bilateral net positions and release payments preferentially to counterparties who are also releasing. Uses `my_bilateral_net_q2` to detect imbalances.

```
BANK_TREE:
  // Track release volume this day via state register
  AddState(bank_state_released_today, queue1_total_value * released_fraction)

PAYMENT_TREE:
  If priority >= 9: Release (always send urgent)
  If ticks_to_deadline <= 3: Release (deadline imminent)
  
  // Reciprocity check: Is counterparty "doing their share"?
  If my_bilateral_net_q2 > 0:
    // We've sent more than received from this counterparty in Q2
    // They owe us — be cautious
    If my_bilateral_net_q2 > amount * 2:
      Hold(reason: "awaiting reciprocity")
    Else:
      If effective_liquidity >= amount * 1.5: Release
      Else: Hold
  Else:
    // Counterparty has sent more (negative net = they're ahead)
    // Reciprocate by releasing
    If effective_liquidity >= amount: Release
    Else: Hold

  // Override: Always release to top counterparties regardless
  If tx_is_top_counterparty AND effective_liquidity >= amount: Release
```

**Parameters:**
- `reciprocity_patience`: 2.0 (how much net imbalance to tolerate)
- `top_counterparty_bypass`: true

---

### 5.3 Policy: Throughput Guideline Compliant

**Concept:** Uses `my_throughput_fraction_today` and `expected_throughput_fraction_by_now` to adjust release aggressiveness.

```
BANK_TREE:
  If throughput_gap < -0.1:
    // Behind guideline — must accelerate
    SetReleaseBudget(max_value = queue1_total_value)  // Release everything possible
    SetState(bank_state_behind_guideline = 1)
  Elif throughput_gap < 0:
    // Slightly behind — moderate acceleration
    SetReleaseBudget(max_value = queue1_total_value * 0.8)
    SetState(bank_state_behind_guideline = 0.5)
  Else:
    // On track or ahead — normal release pace
    SetReleaseBudget(max_value = queue1_total_value * 0.5)
    SetState(bank_state_behind_guideline = 0)

PAYMENT_TREE:
  If bank_state_behind_guideline >= 1:
    // Guideline crisis — release aggressively
    If effective_liquidity >= amount: Release
    Elif effective_liquidity >= amount * 0.7: ReleaseWithCredit
    Else: Hold
  If bank_state_behind_guideline >= 0.5:
    // Slightly behind — prioritise large payments for throughput impact
    If amount >= queue1_total_value * 0.1 AND effective_liquidity >= amount:
      Release  // Large payment moves the throughput needle
    Elif ticks_to_deadline <= 5: Release
    Else: Hold
  Else:
    // On track — standard cost-optimising behaviour
    If ticks_to_deadline <= urgency_threshold: Release
    If effective_liquidity >= amount * 1.5: Release
    Else: Hold
```

**Parameters:**
- `urgency_threshold`: 5
- `guideline_acceleration_threshold`: -0.1
- `large_payment_threshold_fraction`: 0.1

---

### 5.4 Policy: Crisis-Mode Defensive

**Concept:** Automatically switches to defensive mode when system stress indicators rise. Uses liquidity_pressure and system_queue2_pressure_index to detect emerging crises.

```
BANK_TREE:
  If liquidity_pressure > 0.7 OR system_queue2_pressure_index > 0.6:
    // Crisis mode: severely restrict releases
    SetReleaseBudget(max_value = min(queue1_total_value * 0.2, balance * 0.3))
    SetState(bank_state_crisis_mode = 1)
  Elif liquidity_pressure > 0.5:
    // Caution mode: moderate restriction
    SetReleaseBudget(max_value = queue1_total_value * 0.5)
    SetState(bank_state_crisis_mode = 0.5)
  Else:
    // Normal mode
    SetReleaseBudget(max_value = queue1_total_value)
    SetState(bank_state_crisis_mode = 0)

PAYMENT_TREE:
  If bank_state_crisis_mode >= 1:
    // Only release truly urgent payments
    If priority >= 9 AND ticks_to_deadline <= 3: Release
    Elif is_past_deadline: Release  // Overdue must go
    Else: Hold(reason: "crisis liquidity conservation")
  Elif bank_state_crisis_mode >= 0.5:
    If priority >= 7 AND effective_liquidity >= amount * 2: Release
    If ticks_to_deadline <= 3: Release
    Else: Hold
  Else:
    // Normal operation
    If ticks_to_deadline <= 5: Release
    If effective_liquidity >= amount * 1.5: Release
    Else: Hold

STRATEGIC_COLLATERAL_TREE:
  If bank_state_crisis_mode >= 1:
    // Crisis: post maximum collateral for credit headroom
    If remaining_collateral_capacity > 0:
      PostCollateral(amount = remaining_collateral_capacity, reason: "DeadlineEmergency")
    Else: HoldCollateral
  Else: HoldCollateral
```

---

### 5.5 Policy: Hub Bank Treasury (Correspondent Banking)

**Concept:** Hub banks must balance own-account payments against correspondent obligations. Prioritise own urgent payments, then correspondent batches, managing bilateral limits carefully.

```
BANK_TREE:
  // Reserve capacity for expected CLS settlements
  If system_tick_in_day < 20:
    // Before CLS window: reserve 40% of balance for CLS
    SetReleaseBudget(max_value = balance * 0.6)
    SetState(bank_state_cls_reserve = balance * 0.4)
  Elif system_tick_in_day >= 20 AND system_tick_in_day < 25:
    // CLS window: release everything
    SetReleaseBudget(max_value = queue1_total_value)
    SetState(bank_state_cls_reserve = 0)
  Else:
    // Post-CLS: normal treasury management
    SetReleaseBudget(max_value = queue1_total_value * 0.7)

PAYMENT_TREE:
  // CLS payments: always release (priority 10, tight deadline)
  If priority >= 10: Release
  
  // Own-account urgent payments
  If priority >= 8 AND ticks_to_deadline <= 5: Release
  
  // Correspondent batches (low priority): defer to afternoon
  If priority <= 3:
    If day_progress_fraction >= 0.6 AND effective_liquidity >= amount: Release
    Else: Hold(reason: "correspondent batch deferred")
  
  // Standard payments: liquidity-aware release
  If effective_liquidity >= amount * 1.3: Release
  Else: Hold
```

---

### 5.6 Policy: Small Bank Conservative

**Concept:** Small banks with limited liquidity must be extremely cautious. They rely heavily on incoming payments from larger counterparties before releasing outgoing.

```
PAYMENT_TREE:
  If is_past_deadline: Release  // Must clear overdue
  If ticks_to_deadline <= 2: Release  // Deadline imminent
  
  // Very conservative: require 3× coverage
  If effective_liquidity >= amount * 3.0: Release
  
  // If low on liquidity but have Q2 inflows expected, wait
  If effective_liquidity < amount AND my_q2_in_value_from_counterparty > 0:
    Hold(reason: "awaiting Q2 inflows")
  
  // Near EOD: become more aggressive
  If is_eod_rush AND effective_liquidity >= amount: Release
  
  Else: Hold(reason: "insufficient buffer")
```

---

### 5.7 Policy: LSM-Aware Offset Seeker

**Concept:** Deliberately times payment releases to create bilateral or multilateral offset opportunities. Checks whether counterparty has payments queued in the opposite direction.

```
PAYMENT_TREE:
  // Always release urgent
  If priority >= 9: Release
  If ticks_to_deadline <= 3: Release
  
  // Check for offset opportunity: counterparty has Q2 payments to us
  If my_q2_in_value_from_counterparty > 0:
    // Good offset potential — release to enable bilateral netting
    If my_bilateral_net_q2 <= 0:  // They're ahead — reciprocate
      Release
    Elif my_bilateral_net_q2 < amount:
      Release  // Offset will cover the cost
    Else:
      Hold  // Already overexposed
  
  // No offset available: standard liquidity check
  If effective_liquidity >= amount * 1.5: Release
  Else: Hold
```

---

### 5.8 Policy: Throughput Laggard (Counter-Example)

**Concept:** A deliberately non-compliant policy that maximises morning conservation, creating negative externalities for other banks. Useful as a benchmark for measuring throughput guideline effectiveness.

```
BANK_TREE:
  // Always restrict to minimum
  If day_progress_fraction < 0.7:
    SetReleaseBudget(max_value = queue1_total_value * 0.15)
  Else:
    SetReleaseBudget(max_value = queue1_total_value)  // Dump everything at EOD

PAYMENT_TREE:
  If is_past_deadline: Release
  If day_progress_fraction >= 0.7 AND effective_liquidity >= amount: Release
  If priority >= 10 AND ticks_to_deadline <= 2: Release
  Else: Hold(reason: "maximising morning conservation")
```

---

### 5.9 Policy: Adaptive Crisis Detector

**Concept:** Uses state registers to track rolling indicators and auto-detect regime shifts. Switches between normal, cautious, and crisis modes based on accumulated evidence.

```
BANK_TREE:
  // Track incoming flow trend
  If balance < bank_state_prev_balance:
    // Balance declining — increment stress counter
    AddState(bank_state_stress_count, 1)
  Else:
    // Balance stable/rising — decrement (floor at 0)
    AddState(bank_state_stress_count, -0.5)
  
  SetState(bank_state_prev_balance = balance)
  
  // Mode switching based on stress accumulation
  If bank_state_stress_count >= 5:
    SetState(bank_state_mode = 2)  // Crisis
    SetReleaseBudget(max_value = balance * 0.2)
  Elif bank_state_stress_count >= 3:
    SetState(bank_state_mode = 1)  // Cautious
    SetReleaseBudget(max_value = queue1_total_value * 0.5)
  Else:
    SetState(bank_state_mode = 0)  // Normal
    SetReleaseBudget(max_value = queue1_total_value)

PAYMENT_TREE:
  // Mode-dependent behaviour
  If bank_state_mode >= 2:
    If priority >= 9 AND ticks_to_deadline <= 3: Release
    Else: Hold
  Elif bank_state_mode >= 1:
    If ticks_to_deadline <= 5 OR (effective_liquidity >= amount * 2): Release
    Else: Hold
  Else:
    If ticks_to_deadline <= 8 OR (effective_liquidity >= amount * 1.3): Release
    Else: Hold
```

---

### 5.10 Policy: Morning Funding + Afternoon Release

**Concept:** Models the common treasury pattern of posting collateral first thing in the morning to secure credit headroom, releasing payments gradually through the day, then withdrawing collateral in the evening.

```
STRATEGIC_COLLATERAL_TREE:
  // Morning: post collateral proactively
  If system_tick_in_day <= 5 AND remaining_collateral_capacity > 0:
    PostCollateral(
      amount = min(remaining_collateral_capacity, queue1_total_value * 0.5),
      reason: "PreemptivePosting",
      auto_withdraw_after_ticks: 40
    )
  Else: HoldCollateral

BANK_TREE:
  // Phase-based budget
  If system_tick_in_day <= 15:
    SetReleaseBudget(max_value = credit_headroom * 0.4)  // Use credit facility
  Elif system_tick_in_day <= 35:
    SetReleaseBudget(max_value = effective_liquidity * 0.7)
  Else:
    SetReleaseBudget(max_value = queue1_total_value)  // End of day: clear queue

PAYMENT_TREE:
  If ticks_to_deadline <= 3: Release
  If effective_liquidity >= amount: Release
  If credit_headroom >= amount AND priority >= 7: ReleaseWithCredit
  Else: Hold

END_OF_TICK_COLLATERAL_TREE:
  If ticks_remaining_in_day <= 10 AND excess_collateral > 0:
    WithdrawCollateral(amount: excess_collateral, reason: "EndOfDayCleanup")
  Else: HoldCollateral
```

---

## 6. Implementation Notes and Priorities

### 6.1 Priority 1: Quick Wins (Implementable Now)

These proposals work entirely within the existing schema:

1. **Intraday Treasury Manager policy** — Use existing fields (`day_progress_fraction`, `system_tick_in_day`, `bank_state_*`). Implement as JSON decision tree immediately.

2. **Throughput Compliant policy** — Uses existing `throughput_gap` and `my_throughput_fraction_today` fields. Critical gap to fill.

3. **Lynx Day scenario** — Combine heterogeneous agents with `GlobalArrivalRateChange` events for intraday flow patterns. No engine changes needed.

4. **Reciprocity policy** — Uses existing `my_bilateral_net_q2` field. Straightforward decision tree.

5. **Quarter-End scenario** — Standard event-driven scenario with volume surges.

### 6.2 Priority 2: Moderate Effort (Minor Engine Extensions)

6. **Throughput guideline enforcement** — Add a cost penalty for throughput non-compliance. Could be modelled as a periodic `deadline_penalty`-like charge triggered when `throughput_gap < 0` at specified ticks. Requires either a new event type or a new cost mechanism.

7. **Arrival bands** — The schema mentions `arrival_bands` as an alternative to `arrival_config`. If implemented, this would enable time-varying arrival rates without `GlobalArrivalRateChange` events — more elegant for the Lynx Day scenario.

8. **Agent failure** — Add a `AgentFailure` event type that freezes an agent's ability to send (arrival rate → 0, all queued payments held). This would enable Lehman Monday and 9/11 scenarios more cleanly than the current workaround of setting arrival rate to 0.

### 6.3 Priority 3: Significant Engine Work

9. **Tiered participation** — True correspondent banking requires modelling indirect participants whose payments are batched and netted by direct members. This would require either a new agent type or a "correspondent flow" configuration that adds batched payment obligations.

10. **Standing facility with stigma** — Requires a new lending facility mechanism distinct from collateral/overdraft. The facility should have low explicit cost but high implicit cost (stigma), potentially modelled as a separate cost type that increases non-linearly with usage.

11. **Conditional events** — Currently events are purely tick-based. State-contingent events ("if balance drops below X, inject liquidity") would enable more realistic central bank intervention modelling. This is a significant architectural change.

12. **Multi-day state registers** — Currently reset at EOD. Persistent registers would enable learning across days (e.g., tracking counterparty reliability over a week).

13. **Heterogeneous payment type costs** — Currently all payments from an agent share the same cost structure. Per-payment-type cost multipliers (e.g., CLS payments have 3× delay cost) would improve realism.

### 6.4 Research Agenda

The proposed scenarios and policies enable several research directions aligned with Bank of Canada's interests:

1. **Throughput guideline effectiveness** — Using the Throughput Guideline scenario with compliant vs. laggard policies to quantify welfare gains from compliance.

2. **Crisis propagation channels** — Comparing Information-Driven Crisis (gradual) vs. Lehman Monday (sudden) to understand whether RTGS system design can mitigate different crisis types differently.

3. **Optimal intraday liquidity management** — Using the Lynx Day scenario with LLM-optimised policies to discover whether AI agents independently discover the morning-conservation/afternoon-release pattern observed empirically.

4. **LSM effectiveness under stress** — Comparing offset-seeking policies against standard policies across crisis scenarios to quantify the value of LSM awareness in bank treasury operations.

5. **Tiered participation risks** — Using the Hub and Spoke scenario to study whether correspondent banking concentration creates systemic liquidity risks.

---

## Appendix A: Existing Scenario File Reference

| File | Location |
|------|----------|
| `bis_liquidity_delay_tradeoff.yaml` | `examples/configs/` |
| `crisis_resolution_10day.yaml` | `examples/configs/` |
| `target2_crisis_25day.yaml` | `examples/configs/` |
| `target2_crisis_25day_bad_policy.yaml` | `examples/configs/` |
| `advanced_policy_crisis.yaml` | `examples/configs/` |
| `suboptimal_policies_10day.yaml` | `examples/configs/` |
| `suboptimal_policies_25day.yaml` | `examples/configs/` |
| `target2_lsm_features_test.yaml` | `examples/configs/` |
| `test_minimal_eod.yaml` | `examples/configs/` |
| `test_near_deadline.yaml` | `examples/configs/` |
| `test_priority_escalation.yaml` | `examples/configs/` |
| `exp1_2period.yaml` | `experiments/castro/configs/` |
| `exp2_12period.yaml` | `experiments/castro/configs/` |
| `exp3_joint.yaml` | `experiments/castro/configs/` |
| Scenario Pack (7 presets) | `web/backend/app/scenario_pack.py` |

## Appendix B: Existing Policy File Reference

| Policy | Location | Complexity |
|--------|----------|-----------|
| `fifo.json` | `simulator/policies/` | Simple |
| `deadline.json` | `simulator/policies/` | Simple |
| `liquidity_aware.json` | `simulator/policies/` | Moderate |
| `cautious_liquidity_preserver.json` | `simulator/policies/` | Moderate |
| `aggressive_market_maker.json` | `simulator/policies/` | Simple |
| `balanced_cost_optimizer.json` | `simulator/policies/` | Moderate |
| `adaptive_liquidity_manager.json` | `simulator/policies/` | Moderate |
| `deadline_driven_trader.json` | `simulator/policies/` | Moderate |
| `efficient_memory_adaptive.json` | `simulator/policies/` | Complex |
| `efficient_proactive.json` | `simulator/policies/` | Moderate |
| `efficient_splitting.json` | `simulator/policies/` | Moderate |
| `liquidity_splitting.json` | `simulator/policies/` | Moderate |
| `smart_splitter.json` | `simulator/policies/` | Moderate |
| `smart_budget_manager.json` | `simulator/policies/` | Complex |
| `memory_driven_strategist.json` | `simulator/policies/` | Complex |
| `agile_regional_bank.json` | `simulator/policies/` | Complex |
| `goliath_national_bank.json` | `simulator/policies/` | Complex |
| `momentum_investment_bank.json` | `simulator/policies/` | Complex |
| `sophisticated_adaptive_bank.json` | `simulator/policies/` | Complex |
| `target2_aggressive_settler.json` | `simulator/policies/` | Simple |
| `target2_conservative_offsetter.json` | `simulator/policies/` | Moderate |
| `target2_crisis_proactive_manager.json` | `simulator/policies/` | Complex |
| `target2_crisis_risk_denier.json` | `simulator/policies/` | Complex |
| `target2_limit_aware.json` | `simulator/policies/` | Moderate |
| `target2_priority_aware.json` | `simulator/policies/` | Moderate |
| `target2_priority_escalator.json` | `simulator/policies/` | Moderate |
| 17 test policies | `simulator/policies/test_policies/` | Simple |

---

*End of document. For questions or collaboration, contact the Banking and Payments Department research team.*
