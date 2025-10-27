# Phase 4b: Orchestrator Integration - Implementation Plan

**Status**: In Progress (2025-10-27)
**Goal**: Implement complete simulation tick loop integrating all Phase 1-4a components

---

## Overview

Phase 4b connects all previously built components into a working end-to-end simulation:
- **Phase 1-2**: Core models (Transaction, Agent, State, Time, RNG)
- **Phase 3**: Settlement engines (RTGS + LSM)
- **Phase 4a**: Cash manager policies (Queue 1 decision logic)
- **Phase 4b** ← YOU ARE HERE: Orchestrator (tick loop, arrivals, costs, events)

---

## Architecture

### Core Components

```rust
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator (Phase 4b)                                         │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Configuration                                              │ │
│  │ - ticks_per_day                                            │ │
│  │ - num_days                                                 │ │
│  │ - agent_configs (balances, policies, arrival configs)     │ │
│  │ - cost_rates (overdraft, delay, penalty)                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ State Management                                           │ │
│  │ - SimulationState (agents, transactions, queues)          │ │
│  │ - TimeManager (current_tick, current_day)                 │ │
│  │ - RngManager (deterministic randomness)                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Per-Agent Policy Executors                                 │ │
│  │ - Map<AgentId, Box<dyn CashManagerPolicy>>               │ │
│  │ - Evaluate Queue 1 decisions each tick                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Event Log                                                  │ │
│  │ - Arrival events                                           │ │
│  │ - Policy decision events                                   │ │
│  │ - Settlement events                                        │ │
│  │ - LSM release events                                       │ │
│  │ - Cost accrual events                                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Tick Loop (main simulation function)                      │ │
│  │ fn tick(&mut self) -> TickResult                          │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tick Loop Specification

Based on `/docs/grand_plan.md` lines 637-670:

```rust
impl Orchestrator {
    pub fn tick(&mut self) -> Result<TickResult, SimulationError> {
        let current_tick = self.time_manager.current_tick();

        // 1. ARRIVALS: Generate new transactions
        let arrivals = self.generate_arrivals()?;
        for tx in arrivals {
            self.state.add_transaction(tx.clone());
            // Add to sender's Queue 1 (internal queue)
            self.state
                .get_agent_mut(tx.sender_id())
                .unwrap()
                .queue_outgoing(tx.id().to_string());

            self.log_event(Event::Arrival { tick: current_tick, tx_id: tx.id() });
        }

        // 2. POLICY EVALUATION: Evaluate Queue 1 for each agent
        for agent_id in self.state.agents_with_queued_transactions() {
            let agent = self.state.get_agent(&agent_id).unwrap();
            let policy = self.policies.get_mut(&agent_id).unwrap();

            let decisions = policy.evaluate_queue(agent, &self.state, current_tick);

            for decision in decisions {
                match decision {
                    ReleaseDecision::SubmitFull { tx_id } => {
                        // Move from Queue 1 to settlement attempt
                        self.state.get_agent_mut(&agent_id).unwrap()
                            .dequeue_outgoing(&tx_id);
                        self.pending_settlements.push(tx_id);
                    }
                    ReleaseDecision::SubmitPartial { .. } => {
                        // Phase 5: Transaction splitting
                        unimplemented!("Transaction splitting deferred to Phase 5");
                    }
                    ReleaseDecision::Hold { .. } => {
                        // Transaction stays in Queue 1
                        self.log_event(Event::PolicyHold { tick, tx_id, reason });
                    }
                    ReleaseDecision::Drop { .. } => {
                        // Remove from Queue 1, mark as dropped
                        self.state.get_agent_mut(&agent_id).unwrap()
                            .dequeue_outgoing(&tx_id);
                        self.state.get_transaction_mut(&tx_id).unwrap()
                            .mark_dropped(reason);
                        self.log_event(Event::Drop { tick, tx_id, reason });
                    }
                }
            }
        }

        // 3. RTGS SETTLEMENT: Process pending settlements
        for tx_id in self.pending_settlements.drain(..) {
            match rtgs::settle(&mut self.state, &tx_id)? {
                SettlementResult::Settled => {
                    self.log_event(Event::Settlement { tick, tx_id });
                }
                SettlementResult::Queued => {
                    // Insufficient liquidity, added to Queue 2 (RTGS queue)
                    self.log_event(Event::QueuedRtgs { tick, tx_id });
                }
            }
        }

        // 4. PROCESS RTGS QUEUE (Queue 2): Retry queued transactions
        rtgs::process_queue(&mut self.state, current_tick)?;

        // 5. LSM COORDINATOR: Find offsetting opportunities
        let lsm_releases = lsm::run_lsm(&mut self.state)?;
        for release in lsm_releases {
            self.log_event(Event::LsmRelease { tick, mechanism: release.mechanism, tx_ids: release.tx_ids });
        }

        // 6. COST ACCRUAL: Calculate costs for this tick
        for (agent_id, agent) in self.state.agents() {
            let costs = self.calculate_costs(agent, current_tick);
            self.accumulated_costs.entry(agent_id.clone())
                .or_insert(CostAccumulator::new())
                .add(costs);
            self.log_event(Event::CostAccrual { tick, agent_id, costs });
        }

        // 7. DEADLINE ENFORCEMENT: Drop expired transactions
        self.drop_expired_transactions(current_tick)?;

        // 8. ADVANCE TIME
        self.time_manager.advance_tick();

        // 9. END-OF-DAY HANDLING
        if self.time_manager.is_end_of_day() {
            self.handle_end_of_day()?;
        }

        Ok(TickResult {
            tick: current_tick,
            num_arrivals: arrivals.len(),
            num_settlements: settlements_count,
            num_lsm_releases: lsm_releases.len(),
        })
    }
}
```

---

## Module Structure

### 1. `/backend/src/orchestrator/engine.rs` (NEW)

Core orchestrator implementation with tick loop.

**Key Types**:
```rust
pub struct Orchestrator {
    state: SimulationState,
    time_manager: TimeManager,
    rng_manager: RngManager,
    policies: HashMap<String, Box<dyn CashManagerPolicy>>,
    arrival_configs: HashMap<String, ArrivalConfig>,
    cost_rates: CostRates,
    event_log: Vec<Event>,
    accumulated_costs: HashMap<String, CostAccumulator>,
    pending_settlements: Vec<String>,  // Transaction IDs to settle this tick
}

pub struct OrchestratorConfig {
    pub ticks_per_day: usize,
    pub num_days: usize,
    pub rng_seed: u64,
    pub agent_configs: Vec<AgentConfig>,
    pub cost_rates: CostRates,
}

pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub credit_limit: i64,
    pub policy: PolicyConfig,
    pub arrival_config: Option<ArrivalConfig>,
}

pub enum PolicyConfig {
    Fifo,
    Deadline { urgency_threshold: usize },
    LiquidityAware { target_buffer: i64, urgency_threshold: usize },
}

pub struct TickResult {
    pub tick: usize,
    pub num_arrivals: usize,
    pub num_settlements: usize,
    pub num_lsm_releases: usize,
}
```

**Key Methods**:
- `new(config: OrchestratorConfig) -> Self`
- `tick(&mut self) -> Result<TickResult, SimulationError>`
- `run_to_completion(&mut self) -> Result<SimulationSummary, SimulationError>`
- `generate_arrivals(&mut self) -> Vec<Transaction>`
- `calculate_costs(&self, agent: &Agent, tick: usize) -> CostBreakdown`
- `drop_expired_transactions(&mut self, current_tick: usize)`
- `handle_end_of_day(&mut self)`

---

### 2. `/backend/src/arrivals/mod.rs` (NEW)

Deterministic transaction arrival generation.

**Key Types**:
```rust
pub struct ArrivalConfig {
    /// Rate parameter for Poisson distribution (expected arrivals per tick)
    pub rate_per_tick: f64,

    /// Amount distribution
    pub amount_distribution: AmountDistribution,

    /// Counterparty selection weights
    pub counterparty_weights: HashMap<String, f64>,

    /// Deadline configuration (ticks from arrival)
    pub deadline_range: (usize, usize),  // (min, max)
}

pub enum AmountDistribution {
    Uniform { min: i64, max: i64 },
    Normal { mean: i64, std_dev: i64 },
    LogNormal { mean: f64, std_dev: f64 },
    Exponential { rate: f64 },
}

pub struct ArrivalGenerator {
    configs: HashMap<String, ArrivalConfig>,
    all_agent_ids: Vec<String>,
}
```

**Key Methods**:
- `generate_for_agent(&self, agent_id: &str, tick: usize, rng: &mut RngManager) -> Vec<Transaction>`
- `sample_amount(&self, distribution: &AmountDistribution, rng: &mut RngManager) -> i64`
- `select_counterparty(&self, weights: &HashMap<String, f64>, rng: &mut RngManager) -> String`
- `generate_deadline(&self, arrival_tick: usize, range: (usize, usize), rng: &mut RngManager) -> usize`

---

### 3. `/backend/src/costs/mod.rs` (NEW)

Cost accrual for liquidity, delay, and penalties.

**Key Types**:
```rust
pub struct CostRates {
    /// Overdraft cost in basis points per tick
    pub overdraft_bps_per_tick: f64,

    /// Delay cost per tick per unit of value
    pub delay_cost_per_tick_per_unit: f64,

    /// End-of-day penalty for unsettled transactions
    pub eod_penalty_per_transaction: i64,

    /// Missed deadline penalty (per transaction)
    pub deadline_penalty: i64,
}

pub struct CostBreakdown {
    pub liquidity_cost: i64,   // Overdraft cost this tick
    pub delay_cost: i64,        // Queue delay cost this tick
    pub penalty_cost: i64,      // Penalties incurred this tick
}

pub struct CostAccumulator {
    pub total_liquidity_cost: i64,
    pub total_delay_cost: i64,
    pub total_penalty_cost: i64,
    pub peak_net_debit: i64,
}
```

**Key Methods**:
- `calculate_overdraft_cost(balance: i64, rates: &CostRates) -> i64`
- `calculate_delay_cost(queued_transactions: &[Transaction], tick: usize, rates: &CostRates) -> i64`
- `calculate_eod_penalty(unsettled_count: usize, rates: &CostRates) -> i64`

---

### 4. `/backend/src/models/event.rs` (NEW)

Event logging for simulation replay and analysis.

**Key Types**:
```rust
pub enum Event {
    Arrival {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,
        deadline: usize,
    },

    PolicyDecision {
        tick: usize,
        agent_id: String,
        tx_id: String,
        decision: ReleaseDecision,
    },

    Settlement {
        tick: usize,
        tx_id: String,
        amount: i64,
        sender_balance_after: i64,
        receiver_balance_after: i64,
    },

    QueuedRtgs {
        tick: usize,
        tx_id: String,
        reason: String,
    },

    LsmRelease {
        tick: usize,
        mechanism: LsmMechanism,
        tx_ids: Vec<String>,
        total_value: i64,
    },

    CostAccrual {
        tick: usize,
        agent_id: String,
        costs: CostBreakdown,
    },

    Drop {
        tick: usize,
        tx_id: String,
        reason: DropReason,
    },

    EndOfDay {
        day: usize,
        total_settlements: usize,
        total_value_settled: i64,
    },
}

pub enum LsmMechanism {
    Bilateral,
    Cycle3,
    Cycle4,
}
```

---

## Implementation Phases

### Phase 4b.1: Core Orchestrator Structure ✅ Next
- [ ] Create `orchestrator/engine.rs` with Orchestrator struct
- [ ] Define OrchestratorConfig, AgentConfig, PolicyConfig
- [ ] Implement `new()` constructor
- [ ] Add basic field accessors
- [ ] Write unit tests for initialization

### Phase 4b.2: Arrival Generation
- [ ] Create `arrivals/mod.rs` module
- [ ] Implement ArrivalConfig, AmountDistribution
- [ ] Implement ArrivalGenerator
- [ ] Add Poisson sampling for arrival count
- [ ] Add amount distribution sampling
- [ ] Add counterparty selection
- [ ] Write comprehensive tests for determinism

### Phase 4b.3: Cost Accrual
- [ ] Create `costs/mod.rs` module
- [ ] Implement CostRates, CostBreakdown, CostAccumulator
- [ ] Implement overdraft cost calculation
- [ ] Implement delay cost calculation
- [ ] Implement penalty calculations
- [ ] Write tests for cost calculations

### Phase 4b.4: Event Logging
- [ ] Create `models/event.rs` module
- [ ] Define Event enum with all variants
- [ ] Implement event serialization (for future replay)
- [ ] Add event log to Orchestrator
- [ ] Write tests for event logging

### Phase 4b.5: Tick Loop Implementation
- [ ] Implement arrival generation in tick loop
- [ ] Implement policy evaluation integration
- [ ] Integrate RTGS settlement calls
- [ ] Integrate LSM coordinator calls
- [ ] Add cost accrual at end of tick
- [ ] Add deadline enforcement
- [ ] Add end-of-day handling
- [ ] Write integration tests for complete tick cycle

### Phase 4b.6: Integration Tests
- [ ] Test single-tick simulation
- [ ] Test multi-tick simulation
- [ ] Test end-of-day rollover
- [ ] Test multi-day simulation
- [ ] Test determinism (same seed → same results)
- [ ] Test with different policies
- [ ] Test with different arrival configurations

### Phase 4b.7: Documentation
- [ ] Update backend/CLAUDE.md with orchestrator patterns
- [ ] Update foundational_plan.md with Phase 4b completion
- [ ] Create examples in docs/examples/
- [ ] Write integration test documentation

---

## Testing Strategy

### Unit Tests
- Orchestrator initialization
- Arrival generation (deterministic)
- Cost calculations (exact arithmetic)
- Event logging (completeness)

### Integration Tests
- Complete tick loop execution
- Multi-agent scenarios
- Policy interaction scenarios
- Cost accrual over time
- Determinism verification

### Property Tests
- Balance conservation (sum of balances unchanged)
- Determinism (replaying with same seed)
- Event log completeness (every action logged)
- Cost monotonicity (costs never decrease)

---

## Success Criteria

✅ Phase 4b Complete when:
1. Orchestrator can run multi-day simulations end-to-end
2. All 3 policies (FIFO, Deadline, LiquidityAware) work in orchestrator
3. Arrivals generate deterministically
4. Costs accrue correctly
5. Events log completely
6. **All tests passing** (target: 80+ tests total)
7. Determinism verified (replay produces identical results)
8. Documentation complete

---

## Open Questions / Decisions Needed

1. **Transaction ID generation**: Use UUID or sequential counter? (Sequential for determinism)
2. **Event log storage**: In-memory only or optional file output? (In-memory for Phase 4b)
3. **Policy hot-swap**: Support changing policies mid-simulation? (No, deferred to Phase 6)
4. **Partial settlement**: Implement in Phase 4b or defer to Phase 5? (Defer to Phase 5)
5. **Multi-rail support**: Single rail for Phase 4b? (Yes, single rail initially)

---

## Dependencies

**Requires (Already Complete)**:
- ✅ Transaction model (Phase 1)
- ✅ Agent model (Phase 2)
- ✅ SimulationState (Phase 2, extended in Phase 4a)
- ✅ TimeManager (Phase 1)
- ✅ RngManager (Phase 1)
- ✅ RTGS settlement (Phase 3a)
- ✅ LSM coordinator (Phase 3b)
- ✅ CashManagerPolicy trait (Phase 4a)
- ✅ Three baseline policies (Phase 4a)

**Deferred to Later Phases**:
- ❌ Transaction splitting (Phase 5)
- ❌ Advanced arrival patterns (time windows, intraday rate changes) (Phase 5)
- ❌ Policy DSL interpreter (Phase 6)
- ❌ FFI/Python API (Phase 7)

---

*Created: 2025-10-27*
*Next Action: Begin Phase 4b.1 (Core Orchestrator Structure)*
