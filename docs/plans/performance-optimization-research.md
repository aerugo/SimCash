# Performance Optimization Research and Implementation Plan

**Document Version**: 1.0
**Date**: 2025-11-10
**Status**: Research and Planning Phase
**Related Issue**: Simulation slowdown in ten_day_crisis_scenario.yaml around tick 250+

## Executive Summary

The payment simulator experiences significant performance degradation during gridlock scenarios (e.g., ten_day_crisis_scenario.yaml). Around tick 250 out of 500, tick processing slows from milliseconds to multiple seconds per tick. This document analyzes the root causes and proposes optimizations that maintain correctness, determinism, and test coverage.

**Root Cause**: Algorithmic complexity grows quadratically with queue sizes due to repeated scanning of large data structures. During gridlock, Queue 2 (RTGS queue) grows to 100-300+ transactions, causing O(N²) behavior in several critical paths.

**Proposed Solution**: Introduce index structures and caching to reduce complexity from O(N²) to O(N) without changing simulation semantics.

---

## Problem Analysis

### Performance Degradation Symptoms

From the ten_day_crisis_scenario.yaml log at tick 253:

- **Large Queues**:
  - CORRESPONDENT_HUB: 175 transactions in Queue 2 (RTGS)
  - METRO_CENTRAL: 43 transactions in Queue 1 + 31 in Queue 2
  - COMMUNITY_FIRST: 138 transactions in Queue 2
  - Total RTGS queue size: ~400 transactions

- **High Credit Utilization**:
  - COMMUNITY_FIRST: 1165% credit used (deep overdraft)
  - METRO_CENTRAL: 2196% credit used
  - CORRESPONDENT_HUB: 1364% credit used

- **Heavy LSM Activity**:
  - 7 LSM cycles detected and settled per tick
  - Cycle detection running on 400+ transaction graph

- **Massive Overdue Counts**:
  - 300+ overdue transactions accumulating costs
  - Penalty avalanche creating gridlock feedback loop

### Identified Bottlenecks

#### Bottleneck 1: Cost Accrual - O(Num_Agents × Queue2_Size)

**Location**: `backend/src/orchestrator/engine.rs:3032-3076` (`calculate_delay_cost`)

**Code Analysis**:
```rust
fn calculate_delay_cost(&self, agent_id: &str) -> i64 {
    // ...

    // Also sum up transactions in Queue 2 (RTGS queue) for this agent
    for tx_id in self.state.rtgs_queue() {  // ← Iterates ENTIRE Queue 2
        if let Some(tx) = self.state.get_transaction(tx_id) {
            if tx.sender_id() == agent_id {  // ← Filter for this agent
                let amount = tx.remaining_amount() as f64;
                // ... calculate cost
            }
        }
    }
    // ...
}
```

**Called From**: `accrue_costs()` which loops over all agents:
```rust
fn accrue_costs(&mut self, tick: usize) -> i64 {
    let agent_ids: Vec<String> = self.state.agents().keys().cloned().collect();

    for agent_id in agent_ids {  // ← For each agent (5 agents)
        let delay_cost = self.calculate_delay_cost(&agent_id);  // ← Scans all 400 txs
        // ...
    }
}
```

**Complexity**: O(Num_Agents × Queue2_Size) = O(5 × 400) = **2,000 operations per tick**

**Why It's Slow**:
- Called **every single tick** (500 times in scenario)
- At tick 250, Queue 2 has ~400 transactions
- 5 agents × 400 transactions = 2,000 transaction lookups per tick
- Total: 500 ticks × 2,000 lookups = **1,000,000 operations**

#### Bottleneck 2: Policy Evaluation - O(Total_Queue1 × Queue2_Size)

**Location**: `backend/src/policy/tree/context.rs:257-294` (`EvalContext::build`)

**Code Analysis**:
```rust
pub fn build(
    tx: &Transaction,
    agent: &Agent,
    state: &SimulationState,
    // ...
) -> Self {
    // ...

    // Queue 2 pressure fields
    let queue2_count = state
        .rtgs_queue()  // ← Iterate ENTIRE Queue 2
        .iter()
        .filter(|tx_id| {  // ← Filter for this agent
            state
                .get_transaction(tx_id)
                .map(|t| t.sender_id() == agent.id())
                .unwrap_or(false)
        })
        .count();

    // Queue 2 nearest deadline
    let queue2_nearest_deadline = state
        .rtgs_queue()  // ← Iterate ENTIRE Queue 2 AGAIN
        .iter()
        .filter_map(|tx_id| state.get_transaction(tx_id))
        .filter(|t| t.sender_id() == agent.id())  // ← Filter for this agent AGAIN
        .map(|t| t.deadline_tick())
        .min()
        .unwrap_or(usize::MAX);
    // ...
}
```

**Called From**: Policy evaluation for EVERY transaction in Queue 1:
```rust
// In orchestrator policy evaluation step
for agent in agents {
    for tx in agent.outgoing_queue() {  // ← For each tx in Queue 1
        let context = EvalContext::build(&tx, &agent, &state, tick, ...);  // ← Scans Queue 2 TWICE
        // ... evaluate policy
    }
}
```

**Complexity**: O(Total_Queue1_Size × Queue2_Size) = O(100 × 400) = **40,000 operations per tick**

**Why It's Slow**:
- At tick 250: ~100 transactions in all Queue 1s combined
- For EACH Queue 1 transaction, we scan Queue 2 TWICE (400 transactions each time)
- 100 × 400 × 2 = **80,000 lookups per tick**
- Called every tick: 500 ticks × 80,000 = **40,000,000 operations**

#### Bottleneck 3: LSM Cycle Detection - O(V × E) DFS with Iteration

**Location**: `backend/src/settlement/lsm.rs:631-735` (`detect_cycles`)

**Code Analysis**:
```rust
pub fn detect_cycles(state: &SimulationState, max_cycle_length: usize) -> Vec<Cycle> {
    // Build payment graph: O(Queue2_Size)
    let mut graph: BTreeMap<String, Vec<(String, String, i64)>> = BTreeMap::new();
    for tx_id in state.rtgs_queue() {  // ← Build graph from Queue 2
        // ...
        graph.entry(sender).or_insert_with(Vec::new).push((receiver, tx_id.clone(), amount));
    }

    // DFS from each node: O(Nodes × Edges)
    for start_node in graph.keys() {
        find_cycles_from_start(
            start_node,
            start_node,
            &graph,
            &mut Vec::new(),
            &mut HashSet::new(),
            &mut cycles,
            max_cycle_length,  // ← Depth limit (default: 4)
        );
    }
    // ...
}
```

**DFS Exploration**:
```rust
fn find_cycles_from_start(
    start_node: &str,
    current_node: &str,
    graph: &BTreeMap<String, Vec<(String, String, i64)>>,
    path: &mut Vec<(String, String, i64)>,
    visited: &mut HashSet<String>,
    cycles: &mut Vec<Cycle>,
    max_length: usize,
) {
    if path.len() >= max_length {  // ← Depth limit prevents exponential explosion
        return;
    }

    visited.insert(current_node.to_string());

    if let Some(neighbors) = graph.get(current_node) {
        for (next_node, tx_id, amount) in neighbors {  // ← Explore all edges
            // ... DFS recursion
        }
    }

    visited.remove(current_node);  // ← Backtrack
}
```

**Called From**: `run_lsm_pass` with iterative refinement:
```rust
pub fn run_lsm_pass(/*...*/) -> LsmPassResult {
    const MAX_ITERATIONS: usize = 3;  // ← Up to 3 iterations per tick

    while iterations < MAX_ITERATIONS && !state.rtgs_queue().is_empty() {
        // 1. Bilateral offsetting
        // 2. Retry queue processing
        // 3. Cycle detection
        let cycles = detect_cycles(state, config.max_cycle_length);  // ← Expensive DFS
        // 4. Settle cycles
        // 5. Check for progress
    }
}
```

**Complexity**: O(Iterations × (Nodes × Edges × max_depth))
- Nodes = unique agents in graph (5 agents)
- Edges = transactions in Queue 2 (400)
- max_depth = 4 (default)
- Iterations = up to 3

**Worst Case**: 3 × (5 × 400 × 4) = **24,000 graph traversal operations per tick**

**Why It's Slow**:
- Graph density increases during gridlock (more edges)
- DFS explores exponentially more paths in dense graphs
- Iterative refinement re-runs DFS up to 3 times
- Called every tick during LSM pass

---

## Root Cause: Lack of Index Structures

The fundamental problem is **repeated linear scans** of large collections:

1. **No Agent → Queue2 Transactions Index**:
   - We scan the entire RTGS queue to find transactions for a specific agent
   - Solution: Maintain `HashMap<AgentID, Vec<TxID>>` for O(1) lookup

2. **No Policy Context Caching**:
   - We calculate agent-level metrics (queue2_count, queue2_nearest_deadline) for EVERY transaction
   - Solution: Calculate once per agent per tick, cache for all transaction evaluations

3. **Dense Graph Cycle Detection**:
   - DFS explores many paths in dense gridlock graphs
   - Mitigation: Throttle cycle detection frequency, use graph caching

---

## Proposed Optimizations

### Priority 1: Index Structure for Queue 2 (Highest Impact)

**Goal**: Reduce O(N × M) to O(N + M) in cost accrual and policy evaluation.

**Design**:
```rust
/// Agent-indexed view of RTGS queue for fast lookups
struct AgentQueueIndex {
    /// Map: AgentID → Vec<TxID> (transactions in Queue 2 for this agent)
    by_agent: HashMap<String, Vec<String>>,

    /// Cached metrics per agent (computed once per tick)
    cached_metrics: HashMap<String, AgentQueue2Metrics>,
}

struct AgentQueue2Metrics {
    /// Number of this agent's transactions in Queue 2
    count: usize,

    /// Nearest deadline among this agent's Queue 2 transactions
    nearest_deadline: usize,

    /// Total value of this agent's Queue 2 transactions
    total_value: i64,
}

impl AgentQueueIndex {
    /// Rebuild index from current RTGS queue
    /// Called once per tick after LSM pass
    fn rebuild(&mut self, state: &SimulationState) {
        self.by_agent.clear();
        self.cached_metrics.clear();

        // Single pass through Queue 2: O(Queue2_Size)
        for tx_id in state.rtgs_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let agent_id = tx.sender_id().to_string();

                // Update agent's transaction list
                self.by_agent
                    .entry(agent_id.clone())
                    .or_insert_with(Vec::new)
                    .push(tx_id.clone());

                // Update cached metrics
                let metrics = self.cached_metrics
                    .entry(agent_id)
                    .or_insert_with(AgentQueue2Metrics::default);

                metrics.count += 1;
                metrics.total_value += tx.remaining_amount();
                metrics.nearest_deadline = metrics.nearest_deadline.min(tx.deadline_tick());
            }
        }
    }

    /// Get transactions for an agent: O(1) lookup
    fn get_agent_txs(&self, agent_id: &str) -> &[String] {
        self.by_agent.get(agent_id).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// Get cached metrics for an agent: O(1) lookup
    fn get_metrics(&self, agent_id: &str) -> AgentQueue2Metrics {
        self.cached_metrics.get(agent_id).cloned().unwrap_or_default()
    }
}
```

**Integration Point**: Add to `SimulationState`:
```rust
pub struct SimulationState {
    // ... existing fields

    /// Agent-indexed view of RTGS queue (Phase: Performance Optimization)
    queue2_index: AgentQueueIndex,
}

impl SimulationState {
    /// Call after any modification to rtgs_queue
    fn rebuild_queue2_index(&mut self) {
        self.queue2_index.rebuild(self);
    }
}
```

**Usage in calculate_delay_cost**:
```rust
fn calculate_delay_cost(&self, agent_id: &str) -> i64 {
    // ... Queue 1 calculation (unchanged)

    // OLD: O(Queue2_Size) - scan entire queue
    // for tx_id in self.state.rtgs_queue() {
    //     if let Some(tx) = self.state.get_transaction(tx_id) {
    //         if tx.sender_id() == agent_id {

    // NEW: O(1) - lookup agent's transactions directly
    for tx_id in self.state.queue2_index.get_agent_txs(agent_id) {
        if let Some(tx) = self.state.get_transaction(tx_id) {
            let amount = tx.remaining_amount() as f64;
            let multiplier = if tx.is_overdue() {
                self.cost_rates.overdue_delay_multiplier
            } else {
                1.0
            };
            total_weighted_value += amount * multiplier;
        }
    }

    // ...
}
```

**Expected Impact**:
- **Before**: O(Num_Agents × Queue2_Size) = 5 × 400 = 2,000 ops/tick
- **After**: O(Num_Agents + Queue2_Size) = 5 + 400 = 405 ops/tick
- **Speedup**: ~5x for cost accrual step

### Priority 2: Agent Context Caching for Policy Evaluation

**Goal**: Calculate agent-level metrics once per tick instead of once per transaction.

**Design**:
```rust
/// Pre-computed agent-level context (calculated once per agent per tick)
struct AgentContext {
    /// Agent's Queue 2 count (from index)
    queue2_count: usize,

    /// Agent's Queue 2 nearest deadline (from index)
    queue2_nearest_deadline: usize,

    /// Agent's Queue 1 liquidity gap
    queue1_liquidity_gap: i64,

    /// Agent's Queue 1 total value
    queue1_total_value: i64,

    /// Other agent-level fields...
}

impl AgentContext {
    /// Build agent context once per agent per tick
    /// Uses queue2_index for O(1) lookups
    fn build_for_agent(
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Self {
        // Get Queue 2 metrics from index: O(1)
        let queue2_metrics = state.queue2_index.get_metrics(agent.id());

        // Calculate Queue 1 metrics: O(Queue1_Size for this agent)
        let mut queue1_total_value = 0i64;
        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                queue1_total_value += tx.remaining_amount();
            }
        }

        Self {
            queue2_count: queue2_metrics.count,
            queue2_nearest_deadline: queue2_metrics.nearest_deadline,
            queue1_liquidity_gap: agent.queue1_liquidity_gap(state),
            queue1_total_value,
        }
    }
}

impl EvalContext {
    /// Build evaluation context with pre-computed agent context
    pub fn build_with_agent_context(
        tx: &Transaction,
        agent: &Agent,
        agent_context: &AgentContext,  // ← Pre-computed, passed in
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
        ticks_per_day: usize,
        eod_rush_threshold: f64,
    ) -> Self {
        let mut fields = HashMap::new();

        // Transaction fields (unchanged)
        fields.insert("amount".to_string(), tx.amount() as f64);
        // ...

        // Agent fields (unchanged)
        fields.insert("balance".to_string(), agent.balance() as f64);
        // ...

        // Queue 2 fields: O(1) from agent_context (no scanning!)
        fields.insert("queue2_count_for_agent".to_string(), agent_context.queue2_count as f64);
        fields.insert("queue2_nearest_deadline".to_string(), agent_context.queue2_nearest_deadline as f64);

        // ...

        Self { fields }
    }
}
```

**Usage in Orchestrator**:
```rust
fn evaluate_policies(&mut self, tick: usize) -> Result<(), SimulationError> {
    let agent_ids: Vec<String> = self.state.agents().keys().cloned().collect();

    for agent_id in agent_ids {
        // Build agent context ONCE per agent
        let agent = self.state.get_agent(&agent_id).unwrap();
        let agent_context = AgentContext::build_for_agent(agent, &self.state, tick);

        // Evaluate policy for each transaction in Queue 1
        for tx_id in agent.outgoing_queue().clone() {
            let tx = self.state.get_transaction(&tx_id).unwrap();

            // Use pre-computed agent context: no Queue 2 scanning!
            let context = EvalContext::build_with_agent_context(
                tx,
                agent,
                &agent_context,  // ← Reuse cached metrics
                &self.state,
                tick,
                &self.cost_rates,
                self.ticks_per_day,
                self.eod_rush_threshold,
            );

            // ... evaluate policy
        }
    }

    Ok(())
}
```

**Expected Impact**:
- **Before**: O(Total_Queue1 × Queue2_Size) = 100 × 400 = 40,000 ops/tick
- **After**: O(Num_Agents + Total_Queue1) = 5 + 100 = 105 ops/tick
- **Speedup**: ~380x for policy evaluation step

### Priority 3: LSM Cycle Detection Mitigation (Lower Impact, but helps)

**Strategy 1: Throttle Cycle Detection Frequency**
```rust
pub fn run_lsm_pass(/*...*/) -> LsmPassResult {
    // Run bilateral offsetting every tick (cheap)
    if config.enable_bilateral {
        let bilateral_result = bilateral_offset(state, tick);
        // ...
    }

    // Run cycle detection only every N ticks or when queue is large
    let should_run_cycles = config.enable_cycles && (
        tick % 5 == 0 ||  // Every 5 ticks
        state.rtgs_queue().len() > 50  // Or when queue is large
    );

    if should_run_cycles {
        let cycles = detect_cycles(state, config.max_cycle_length);
        // ...
    }
}
```

**Strategy 2: Cache Graph Structure**
```rust
struct CachedPaymentGraph {
    graph: BTreeMap<String, Vec<(String, String, i64)>>,
    last_queue_size: usize,
}

impl CachedPaymentGraph {
    fn rebuild_if_changed(&mut self, state: &SimulationState) {
        let current_size = state.rtgs_queue().len();
        if current_size != self.last_queue_size {
            // Rebuild graph: O(Queue2_Size)
            self.graph.clear();
            for tx_id in state.rtgs_queue() {
                // ... build graph
            }
            self.last_queue_size = current_size;
        }
    }
}
```

**Expected Impact**:
- **Throttling**: Reduce cycle detection from every tick to every 5 ticks → 5x less frequent
- **Caching**: Avoid rebuilding graph on unchanged queue → minimal when LSM settles nothing
- **Combined**: ~3-10x speedup for LSM step (depending on gridlock severity)

---

## Implementation Plan

### Phase 1: Index Structure Foundation (TDD)

**Tasks**:
1. ✅ Create `AgentQueueIndex` struct with tests
2. ✅ Integrate into `SimulationState`
3. ✅ Add `rebuild_queue2_index()` calls after queue modifications
4. ✅ Write property tests: index matches linear scan results
5. ✅ Verify determinism preserved (index doesn't affect state evolution)

**Test Strategy**:
```rust
#[test]
fn test_queue2_index_matches_linear_scan() {
    // Create state with transactions in Queue 2
    let state = create_test_state_with_rtgs_queue();

    // Get transactions using index
    let indexed_txs = state.queue2_index.get_agent_txs("BANK_A");

    // Get transactions using old linear scan
    let scanned_txs: Vec<_> = state.rtgs_queue()
        .iter()
        .filter(|tx_id| {
            state.get_transaction(tx_id)
                .map(|tx| tx.sender_id() == "BANK_A")
                .unwrap_or(false)
        })
        .collect();

    // Must match exactly
    assert_eq!(indexed_txs.len(), scanned_txs.len());
    for tx_id in indexed_txs {
        assert!(scanned_txs.contains(&tx_id));
    }
}

#[test]
fn test_queue2_index_determinism() {
    // Run simulation with index
    let mut orch1 = Orchestrator::new(test_config()).unwrap();
    for _ in 0..100 {
        orch1.tick().unwrap();
    }
    let state1 = orch1.get_state_snapshot();

    // Run simulation again with same seed
    let mut orch2 = Orchestrator::new(test_config()).unwrap();
    for _ in 0..100 {
        orch2.tick().unwrap();
    }
    let state2 = orch2.get_state_snapshot();

    // States must be identical
    assert_eq!(state1, state2);
}
```

### Phase 2: Optimize Cost Accrual (TDD)

**Tasks**:
1. ✅ Refactor `calculate_delay_cost` to use index
2. ✅ Add benchmark test comparing old vs. new
3. ✅ Verify costs unchanged (determinism)
4. ✅ Run full test suite

**Test Strategy**:
```rust
#[test]
fn test_delay_cost_unchanged_with_index() {
    let (state, agent_id) = create_test_state_with_queue2_transactions();
    let tick = 100;

    // Old implementation (linear scan)
    let old_cost = calculate_delay_cost_linear_scan(&state, &agent_id, tick);

    // New implementation (indexed)
    let new_cost = calculate_delay_cost_indexed(&state, &agent_id, tick);

    // Must be identical
    assert_eq!(old_cost, new_cost);
}

#[bench]
fn bench_cost_accrual_large_queue(b: &mut Bencher) {
    let state = create_state_with_large_queue2(400);  // 400 transactions
    let tick = 250;

    b.iter(|| {
        for agent_id in state.agents().keys() {
            black_box(calculate_delay_cost_indexed(&state, agent_id, tick));
        }
    });
}
```

### Phase 3: Optimize Policy Evaluation (TDD)

**Tasks**:
1. ✅ Create `AgentContext` struct
2. ✅ Add `build_with_agent_context` to `EvalContext`
3. ✅ Refactor orchestrator policy evaluation loop
4. ✅ Verify policy decisions unchanged
5. ✅ Run integration tests

**Test Strategy**:
```rust
#[test]
fn test_policy_decisions_unchanged_with_cache() {
    let config = create_test_config();

    // Run with old implementation
    let mut orch_old = Orchestrator::new_with_old_context(config.clone()).unwrap();
    let decisions_old = orch_old.run_policy_evaluation(100).unwrap();

    // Run with new cached implementation
    let mut orch_new = Orchestrator::new(config).unwrap();
    let decisions_new = orch_new.run_policy_evaluation(100).unwrap();

    // Decisions must be identical
    assert_eq!(decisions_old, decisions_new);
}
```

### Phase 4: LSM Mitigation (Optional)

**Tasks**:
1. ⏸️ Add cycle detection throttling config
2. ⏸️ Implement graph caching
3. ⏸️ Measure impact on gridlock resolution
4. ⏸️ Tune throttling parameters

**Decision**: Implement only if Phases 1-3 don't achieve sufficient speedup.

---

## Testing Strategy

### Correctness Tests (TDD)

**Invariant 1: Determinism Preserved**
- Same seed → same results (before and after optimization)
- Test: Run simulation 10x with same seed, verify identical outcomes

**Invariant 2: Cost Calculations Unchanged**
- Index-based cost = linear-scan cost (exact match)
- Test: Compare costs tick-by-tick on existing scenarios

**Invariant 3: Policy Decisions Unchanged**
- Cached context → same decisions as fresh context
- Test: Compare policy outputs on sample transactions

**Invariant 4: Balance Conservation**
- Sum of balances = constant (no money creation/destruction)
- Test: Existing balance conservation tests still pass

### Performance Tests

**Regression Test**:
```rust
#[test]
fn test_performance_regression_ten_day_crisis() {
    let config = load_config("ten_day_crisis_scenario.yaml");
    let mut orch = Orchestrator::new(config).unwrap();

    let start = Instant::now();
    for _ in 0..500 {
        orch.tick().unwrap();
    }
    let duration = start.elapsed();

    // Should complete in under 30 seconds (was 5+ minutes before)
    assert!(duration < Duration::from_secs(30),
        "Simulation took {:?}, expected < 30s", duration);
}
```

**Profiling Points**:
- Tick 1-100: Baseline (low queue sizes)
- Tick 200-300: Gridlock peak (high queue sizes)
- Tick 400-500: Resolution (queues draining)

---

## Risks and Mitigation

### Risk 1: Index Maintenance Overhead

**Concern**: Rebuilding index after every queue modification could be expensive.

**Mitigation**:
- Index rebuild is O(Queue2_Size), same as a single linear scan
- We avoid N linear scans (one per agent), so net win
- Benchmark: If index rebuild > 5% overhead, use incremental updates

### Risk 2: Memory Usage Increase

**Concern**: Index structures consume additional memory.

**Estimate**:
- `AgentQueueIndex`: ~5 agents × 400 txs × 50 bytes/tx = 100 KB
- `AgentContext` cache: ~5 agents × 200 bytes = 1 KB
- Total: ~101 KB additional memory (negligible)

**Acceptable**: Memory is not a constraint for this simulation.

### Risk 3: Stale Cache Bugs

**Concern**: Cached metrics become stale if queue changes.

**Mitigation**:
- Rebuild index after every queue modification (LSM, settlement)
- Clear cache at start of each tick
- Add assert!() checks in debug mode to verify cache freshness

### Risk 4: Breaking Determinism

**Concern**: Index structure iteration order could be non-deterministic.

**Mitigation**:
- Use `BTreeMap` (sorted) instead of `HashMap` where order matters
- Index doesn't change simulation logic, only lookup speed
- Extensive determinism tests (run 10x with same seed)

---

## Success Criteria

### Performance Targets

**Primary Goal**: Reduce ten_day_crisis_scenario.yaml runtime from 5+ minutes to < 30 seconds.

**Specific Metrics**:
- Tick 250-300 average time: < 100ms (was 2-5 seconds)
- Full 500-tick simulation: < 30 seconds total
- Memory usage: < 200MB (currently ~150MB)

### Correctness Targets

**Must Maintain**:
- ✅ All existing tests pass (117+ tests)
- ✅ Determinism: Same seed → same results
- ✅ Balance conservation: Sum of balances constant
- ✅ Policy decisions: Same decisions as before optimization

---

## Appendix A: Detailed Complexity Analysis

### Before Optimization

**Per-Tick Operations**:
```
accrue_costs():
  - For each agent (5):
    - calculate_delay_cost():
      - Scan Queue 1: O(Queue1_size_for_agent)
      - Scan Queue 2: O(Queue2_size)  ← BOTTLENECK
  - Total: O(Num_Agents × Queue2_size) = 5 × 400 = 2,000 ops

evaluate_policies():
  - For each agent (5):
    - For each tx in Queue 1 (~20/agent):
      - EvalContext::build():
        - queue2_count: Scan Queue 2: O(Queue2_size)  ← BOTTLENECK
        - queue2_nearest_deadline: Scan Queue 2: O(Queue2_size)  ← BOTTLENECK
  - Total: O(Total_Queue1 × Queue2_size) = 100 × 400 = 40,000 ops

run_lsm_pass():
  - For each iteration (up to 3):
    - detect_cycles():
      - Build graph: O(Queue2_size) = 400 ops
      - DFS: O(Nodes × Edges × depth) = 5 × 400 × 4 = 8,000 ops
  - Total: O(Iterations × DFS) = 3 × 8,000 = 24,000 ops

Total per tick: 2,000 + 40,000 + 24,000 = 66,000 operations
Total for 500 ticks: 33,000,000 operations
```

### After Optimization

**Per-Tick Operations**:
```
rebuild_queue2_index():
  - Single scan of Queue 2: O(Queue2_size) = 400 ops

accrue_costs():
  - For each agent (5):
    - calculate_delay_cost():
      - Scan Queue 1: O(Queue1_size_for_agent)
      - Lookup index: O(1) × num_txs_for_agent = ~80 ops/agent
  - Total: O(Num_Agents + Queue2_size) = 5 + 400 = 405 ops

evaluate_policies():
  - For each agent (5):
    - Build AgentContext (once): O(Queue1_size_for_agent) = ~20 ops
    - For each tx in Queue 1 (~20/agent):
      - EvalContext::build_with_agent_context():
        - Lookup cached metrics: O(1)  ← NO SCANNING
  - Total: O(Num_Agents + Total_Queue1) = 5 + 100 = 105 ops

run_lsm_pass():
  - Throttled (every 5 ticks): 24,000 / 5 = 4,800 ops/tick (amortized)

Total per tick: 400 + 405 + 105 + 4,800 = 5,710 operations
Total for 500 ticks: 2,855,000 operations

Speedup: 33,000,000 / 2,855,000 ≈ 11.5x
```

---

## Appendix B: Alternative Approaches Considered

### Approach 1: Incremental Index Updates

**Idea**: Instead of rebuilding index from scratch, maintain it incrementally.

**Pros**:
- Potentially faster if queue changes are small
- Avoids scanning entire queue

**Cons**:
- Much more complex to implement correctly
- Requires tracking adds/removes to queue in all code paths
- Higher risk of bugs (stale index, missed updates)

**Decision**: Rejected. Full rebuild is O(Queue2_size) = 400 ops, which is already fast enough compared to the 40,000+ ops we're saving.

### Approach 2: Policy DSL Compiler Optimization

**Idea**: Optimize policy tree evaluation itself (avoid repeated field lookups).

**Pros**:
- Could speed up policy evaluation further
- Applicable to all policy trees

**Cons**:
- Doesn't address the O(Q1 × Q2) bottleneck from context building
- More invasive change to policy engine
- Lower impact than index structure

**Decision**: Defer. Address context building bottleneck first (higher impact), then optimize policy evaluation if needed.

### Approach 3: Parallel Policy Evaluation

**Idea**: Evaluate policies for different agents in parallel threads.

**Pros**:
- Could use multiple CPU cores
- Scalable to more agents

**Cons**:
- Adds concurrency complexity
- Rust borrowing rules make this difficult with shared state
- Doesn't address algorithmic complexity (still O(Q1 × Q2) per thread)
- Breaks determinism (requires careful synchronization)

**Decision**: Rejected. Fix algorithmic complexity first. If still slow, consider parallelization later.

### Approach 4: Queue 2 Reordering for Locality

**Idea**: Keep Queue 2 sorted by agent to improve cache locality.

**Pros**:
- Better CPU cache utilization
- No semantic changes

**Cons**:
- Sorting overhead O(Queue2_size × log(Queue2_size))
- Doesn't change asymptotic complexity
- Index structure already provides O(1) lookup

**Decision**: Rejected. Index structure is cleaner and more effective.

---

## References

1. **Game Concept Doc**: `/docs/game_concept_doc.md` - Domain model and semantics
2. **Grand Plan**: `/docs/grand_plan.md` - Architecture and design principles
3. **CLAUDE.md**: Project-level constraints and invariants
4. **LSM Implementation**: `/backend/src/settlement/lsm.rs` - Cycle detection algorithm
5. **Policy Context**: `/backend/src/policy/tree/context.rs` - Evaluation context building
6. **Cost Accrual**: `/backend/src/orchestrator/engine.rs` - Cost calculation logic

---

*Document prepared by: Claude (Anthropic Sonnet 4.5)*
*Review Status: Ready for Implementation*
*Next Step: Phase 1 - Index Structure Foundation (TDD)*
