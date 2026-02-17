# Scenario Events System Analysis

## 1. What Are Custom Scenario Events?

Scenario events are **deterministic interventions** injected into a SimCash simulation at specific ticks. They allow researchers to precisely control simulation state — transferring funds, injecting transactions, adjusting arrival rates, modifying collateral, and changing counterparty relationships — all with exact timing and full reproducibility.

Key properties:
- **Deterministic**: Execute at exact ticks, not probabilistically
- **Reproducible**: Same config + same seed = identical results
- **Composable**: Multiple events combine to create complex scenarios
- **Persistent**: Events are stored in the database and survive replay verification

Events are declared in YAML config under `scenario_events:` and each requires a `schedule` field specifying when to execute.

---

## 2. Event Types

SimCash provides **7 event types**, covering the full range of interventions needed for payment system research:

### 2.1 DirectTransfer
**Instant balance movement** between agents, bypassing all queues and settlement. Used for central bank liquidity injections, margin calls, interbank loans. The transfer is immediate — no policy evaluation, no RTGS processing.

### 2.2 CustomTransactionArrival
**Inject a specific transaction** that flows through the normal settlement path (Queue 1 → policy decision → Queue 2 → RTGS → LSM). Supports `priority` (0-10), `deadline` (relative ticks), and `is_divisible` flags. This is the primary tool for controlled stress testing since it exercises the full engine.

### 2.3 CollateralAdjustment
**Add or remove collateral** from an agent, affecting their credit capacity. Positive delta increases borrowing power; negative delta simulates margin calls or haircuts. Subject to collateral opportunity costs.

### 2.4 GlobalArrivalRateChange
**Multiply all agents' arrival rates** by a factor. Persists until the next change (use `1.0` to restore). Models market-wide surges (end-of-quarter), holiday slowdowns, or capacity stress tests.

### 2.5 AgentArrivalRateChange
**Multiply a single agent's rate**. Stacks with global multiplier. Setting to `0.0` simulates operational failure or counterparty default. Setting to `1.0` restores normal operations.

### 2.6 CounterpartyWeightChange
**Redirect payment flows** by adjusting routing probabilities. With `auto_balance_others: true`, remaining weights are automatically rescaled. Setting weight to `0.0` cuts off a counterparty — useful for contagion and network topology experiments.

### 2.7 DeadlineWindowChange
**Tighten or loosen deadline pressure** globally via multipliers on min/max deadline ticks. Affects only future transactions. A `0.5` multiplier halves all deadlines, creating urgency; `2.0` relaxes them.

---

## 3. Scheduling Mechanisms

### OneTime
Execute once at exact tick:
```yaml
schedule:
  type: OneTime
  tick: 50
```

### Repeating
Execute periodically:
```yaml
schedule:
  type: Repeating
  start_tick: 10
  interval: 10
  end_tick: 90  # Optional (in examples guide; reference shows unbounded)
```
Fires at: `start_tick`, `start_tick + interval`, `start_tick + 2×interval`, ...

**Notable limitation**: No conditional or random scheduling. All events are deterministic and tick-based. This is by design — reproducibility is paramount.

---

## 4. Engine Interaction

Events execute at the **start of each tick**, before normal simulation phases:

| Event Type | Queue 1 | Policy | Queue 2 | RTGS | LSM | Balance |
|:-----------|:--------|:-------|:--------|:-----|:----|:--------|
| DirectTransfer | Skip | Skip | Skip | Skip | Skip | **Immediate** |
| CustomTransactionArrival | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | Via settlement |
| CollateralAdjustment | — | — | — | — | — | Credit capacity |
| GlobalArrivalRateChange | — | — | — | — | — | Future arrivals |
| AgentArrivalRateChange | — | — | — | — | — | Future arrivals |
| CounterpartyWeightChange | — | — | — | — | — | Future routing |
| DeadlineWindowChange | — | — | — | — | — | Future deadlines |

Key interactions:
- **DirectTransfer** maintains balance conservation (zero-sum across agents)
- **CustomTransactionArrival** generates real costs (delay, deadline penalties, liquidity)
- Rate/weight changes affect the stochastic arrival generator going forward
- Events persist to the `simulation_events` table for replay verification

---

## 5. Example Configurations from YAML Files

### target2_crisis_25day.yaml — Multi-Phase Crisis
A 25-day scenario with three phases:
1. **Days 1-8 (Normal)**: Bilateral offset opportunities — pairs of opposing payments between agents to test LSM entry disposition offsetting
2. **Day 5**: First liquidity pressure via large `CustomTransactionArrival` ($22,000)
3. **Day 6**: `CollateralAdjustment` boost (+$20,000)
4. **Day 10**: `GlobalArrivalRateChange` surge (2.0×)

### advanced_policy_crisis.yaml — Advanced Policy Stress Test
Tests sophisticated policy features under crisis:
- **Day 1**: Baseline (no events)
- **Day 2 (tick 105)**: `GlobalArrivalRateChange` 1.5× + coordinated 4-agent gridlock cycle via four simultaneous `CustomTransactionArrival` events ($18,000 each, priority 9, tight deadlines)
- Tests how adaptive budgets, mode switching, and momentum policies respond

### crisis_resolution_10day.yaml — Crisis & Recovery
Similar structure to advanced_policy_crisis but compressed to 10 days. Tests whether policies can recover after a stress period.

### bis_liquidity_delay_tradeoff.yaml
BIS-style deterministic injection sequence: precise transactions at ticks 0, 1, 2 to create controlled liquidity-delay tradeoff scenarios matching academic paper setups.

---

## 6. Creating Realistic Market Stress Scenarios

The event system enables several classes of realistic stress scenarios:

### Liquidity Crisis Cascade
Chain events temporally: large client payment → margin call → collateral haircut → arrival surge. Each event compounds pressure, testing whether policies degrade gracefully.

### Counterparty Failure
Set agent arrival rate to 0.0, then redirect all other agents' counterparty weights away from the failed bank. Measures contagion: how quickly does gridlock spread? Does LSM help?

### Coordinated Gridlock Construction
Inject multiple `CustomTransactionArrival` events at the same tick forming a payment cycle (A→B, B→C, C→D, D→A). This creates gridlock that only LSM cycle detection can resolve.

### Central Bank Intervention
Use `Repeating` `DirectTransfer` events to model periodic liquidity facilities. Compare injection strategies: frequency vs. amount, targeted vs. uniform.

### Regulatory Regime Change
Combine `DeadlineWindowChange` (tighter deadlines) with `CollateralAdjustment` (higher requirements) to simulate new regulatory environments.

---

## 7. Full Expressiveness — What Can You Simulate?

### What's Possible

| Scenario Class | Events Used | Complexity |
|:---------------|:------------|:-----------|
| Single bank stress test | DirectTransfer + CustomTransactionArrival | Low |
| Market-wide volume spike | GlobalArrivalRateChange | Low |
| Bank operational failure | AgentArrivalRateChange (0.0) | Low |
| Counterparty contagion | ArrivalRateChange + CounterpartyWeightChange | Medium |
| Liquidity crisis cascade | DirectTransfer + CollateralAdjustment + ArrivalRateChange | Medium |
| Gridlock construction | Multiple synchronized CustomTransactionArrival | Medium |
| Central bank facility design | Repeating DirectTransfer | Medium |
| Multi-phase crisis narrative | All event types, phased over days | High |
| Regulatory regime change | DeadlineWindowChange + CollateralAdjustment | Medium |
| Network topology evolution | Multiple CounterpartyWeightChange over time | Medium |

### What's NOT Possible (Current Limitations)

- **Conditional events**: No "if balance < X, then inject liquidity" — all scheduling is tick-based
- **Random/stochastic events**: No probabilistic event firing — deterministic only
- **Agent removal/addition**: Cannot add or remove agents mid-simulation
- **Policy changes mid-run**: Cannot switch an agent's policy tree during simulation
- **Fee/cost parameter changes**: Cannot adjust cost rates dynamically
- **LSM parameter changes**: Cannot modify LSM configuration mid-simulation

These limitations are deliberate: determinism enables replay identity verification, which is a core architectural guarantee.

---

## 8. Research Experiment Designs

### Experiment 1: Optimal Central Bank Intervention Strategy
**Question**: What's the most cost-effective liquidity support pattern?
**Design**: Hold crisis constant (same shocks), vary intervention: (a) one large injection, (b) frequent small injections, (c) no intervention. Compare total system cost, settlement rates, and overdraft duration.

### Experiment 2: Policy Robustness Under Stress
**Question**: Which policy degrades most gracefully under cascading shocks?
**Design**: Run identical crisis scenarios across FIFO, Deadline, LiquidityAware, and LLM-optimized policies. Measure settlement rate degradation curves.

### Experiment 3: Contagion Speed in Different Network Topologies
**Question**: How does network structure affect contagion propagation?
**Design**: Use `CounterpartyWeightChange` to create different topologies (hub-spoke, ring, complete graph) before triggering a bank failure. Measure time-to-gridlock.

### Experiment 4: LSM Effectiveness Under Constructed Gridlock
**Question**: When does cycle detection pay for itself?
**Design**: Inject known payment cycles of varying sizes (2-agent, 3-agent, 4-agent) and measure settlement with/without LSM. Calculate the breakeven point.

### Experiment 5: Deadline Pressure and Strategic Behavior
**Question**: Do tighter deadlines improve or harm system-wide settlement?
**Design**: Use `DeadlineWindowChange` with multipliers from 0.25 to 2.0. With tight deadlines, LiquidityAware agents may rush payments (good for settlement) but drain liquidity faster (bad for costs).

### Experiment 6: Asymmetric Shock Response
**Question**: How do different-sized banks respond to the same absolute shock?
**Design**: Apply identical `DirectTransfer` outflows to banks with different opening balances. Measure relative impact on settlement rates and costs.

---

## Summary

The scenario events system is SimCash's primary tool for **controlled experimentation**. Its 7 event types cover balance manipulation, transaction injection, arrival rate control, collateral management, routing changes, and deadline pressure. The deterministic, tick-based scheduling ensures perfect reproducibility at the cost of conditional/stochastic flexibility. Combined with the policy system and LSM, events enable researchers to construct arbitrarily complex crisis narratives and measure exactly how different strategies respond.
