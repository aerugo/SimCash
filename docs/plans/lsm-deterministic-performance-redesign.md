# LSM Deterministic Performance Redesign

**Status**: In Progress
**Created**: 2025-11-11
**Owner**: Claude Code
**Priority**: High

---

## Executive Summary

This plan implements the comprehensive LSM optimization strategy outlined in `/docs/lsm_opti.md`. The current implementation has **determinism fragility** (hash iteration order) and **performance bottlenecks** (O(N·K) queue mutations, exponential cycle detection). This redesign achieves **deterministic-by-construction** behavior while making bilateral and multilateral settlement **near-linear** in practice.

**Key Goals**:
1. **Determinism**: Total ordering on all selections, no hash iteration
2. **Performance**: Eliminate O(N·K) patterns, make common case near-linear
3. **Correctness**: Preserve T2 semantics (full-value, two-phase, unequal amounts)

---

## Current Performance Baseline

From benchmark run of `five_day_crisis_scenario.yaml`:

```
⏱️  Tick 70: 0.46ms (LSM:0.19ms, Policy:0.13ms)
⏱️  Tick 105: 0.46ms (Policy:0.26ms, LSM:0.08ms)
⏱️  Tick 120: 0.79ms (Policy:0.57ms, LSM:0.12ms)
```

**Observations**:
- LSM time ranges: 0.04ms - 0.19ms per tick
- Highest during stress periods (ticks 70, 120)
- Queue sizes grow during crisis events
- Current implementation functional but has known bottlenecks

---

## Problem Analysis

### Current Bottlenecks (from `backend/src/settlement/lsm.rs`)

1. **Bilateral Offsetting (lines 268-361)**
   ```rust
   // PROBLEM: Rebuilds bilateral_map from scratch every tick
   let mut bilateral_map: BTreeMap<(String, String), Vec<String>> = BTreeMap::new();
   for tx_id in state.rtgs_queue() {  // O(N) scan
       // Build map...
   }

   // PROBLEM: Per-transaction queue mutation
   state.rtgs_queue_mut().retain(|id| id != tx_id);  // O(N) per tx
   ```

2. **Cycle Detection (lines 631-735)**
   ```rust
   // PROBLEM: Exponential DFS on full graph
   fn find_cycles_from_start(...) {
       // Explores all paths up to max_length
       // Can revisit same states multiple times
   }
   ```

3. **Determinism Risks**
   - Uses `HashSet` for `processed_pairs` (line 294) - iteration order undefined
   - Uses `HashSet` for `visited` in DFS (line 650) - affects traversal order
   - String cloning everywhere (IDs not interned)

### Why This Matters

From the guide's "Non-negotiable constraints":
> **Determinism**: same inputs ⇒ same outputs, byte-for-byte (events, order, results)

Current code works but is **fragile**:
- Hash capacity changes across Rust versions could break determinism
- Performance degrades non-linearly with queue size

---

## Solution Architecture

### Phase 0: Foundation (No Behavior Change)

**Goal**: Make determinism explicit, batch queue operations

**Changes**:
1. **ID Interning** (stable mapping)
   - `AgentId(u32)` from sorted agent list
   - `TxId(u64)` from transaction creation order
   - Eliminates string cloning in hot paths

2. **Batch Queue Removals**
   - Replace per-tx `retain()` with single compaction per phase
   - Collect `to_remove: BTreeSet<TxId>` during settlement
   - One `queue.retain()` after bilateral phase, one after cycle phase

3. **Event Sorting**
   - Sort `cycle_events` and `replay_events` before return
   - Deterministic comparator: `(tick, cycle_type, settled_value DESC, ...)`

**Acceptance Criteria**:
- All existing tests pass
- Same outputs as before (byte-for-byte)
- Reduced string allocations (visible in profiling)

---

### Phase 1: Fast Bilateral Offsetting

**Goal**: Make bilateral offsetting incremental and deterministic

**New Structure**: `PairIndex`

```rust
struct PairBucket {
    sum: i64,                   // sum of amounts s->r
    tx_ids: Vec<TxId>,          // in enqueue order
}

type Adj = BTreeMap<AgentId, BTreeMap<AgentId, PairBucket>>;

#[derive(Clone, Eq, PartialEq, Ord, PartialOrd)]
struct ReadyKey {
    neg_priority: i64,          // -min(sum_ab, sum_ba) for max-heap
    a: AgentId,                 // canonicalized: a < b
    b: AgentId,
}

struct PairIndex {
    out: Adj,                   // sender -> receiver -> bucket
    ready: BTreeSet<ReadyKey>,  // deterministic priority queue
}
```

**Algorithm**:
1. Build `PairIndex` once per pass from current queue
2. While `!ready.is_empty()`:
   - Pop highest priority pair from `ready`
   - Check net sender can cover net flow (single credit check)
   - Settle ALL txs in both directions
   - Update buckets, recompute ready keys
3. Single `queue.retain()` at end

**Determinism**:
- `BTreeMap` iteration is sorted by `AgentId`
- `BTreeSet<ReadyKey>` pops deterministically (highest priority first)
- Tie-breaks: `(liquidity_release DESC, agent_a, agent_b)`

**Performance Gains**:
- No full queue rescan per tick
- O(pairs × txs_per_pair) instead of O(N²)
- One compaction instead of per-tx `retain`

---

### Phase 2: Fast Multilateral Cycles

**Goal**: Make cycle detection near-linear for common cases

**New Pipeline**:

```
1. Build aggregated graph snapshot (agent-level, BTreeMap)
   ↓
2. SCC prefilter (Tarjan, O(V+E))
   ↓ (only SCCs with size ≥ 3)
3. Fast triangle enumeration (bitset intersections)
   ↓ (sort candidates, two-phase settle)
4. Bounded Johnson for length 4-5 (if needed)
   ↓
5. Single queue compaction
```

**Key Optimizations**:

1. **Aggregated Graph**
   ```rust
   struct AggEdge {
       sum: i64,          // sum i->j (all queued txs)
       tx_ids: Vec<TxId>, // map back to concrete txs
   }
   type Graph = BTreeMap<AgentId, BTreeMap<AgentId, AggEdge>>;
   ```

2. **SCC Prefilter** (Tarjan's algorithm)
   - Only nodes in SCCs can be in cycles
   - Skip isolated nodes and trees
   - Process SCCs in sorted order (deterministic)

3. **Triangle Finder** (length 3 cycles)
   ```rust
   // For each edge u->v:
   //   candidates = out_neighbors[v] ∩ in_neighbors[u]
   //   For each w in candidates: found triangle u->v->w->u
   ```
   - Uses bitset intersections (extremely fast)
   - Captures 80%+ of real-world cycles

4. **Bounded Johnson** (length 4-5)
   - Only run on small SCCs after triangles
   - Strict length cap (5)
   - Neighbor iteration in sorted order (deterministic)

**Cycle Priority Comparator**:
```rust
enum CyclePriority {
    ThroughputFirst,  // max total_value, then min liquidity
    LiquidityFirst,   // min max_net_outflow, then max value
}

// Total order: (primary_score, agents_tuple, tx_ids_tuple)
```

**Determinism**:
- All graph structures use `BTreeMap` (sorted iteration)
- Tarjan visits vertices in sorted order
- Triangle enumeration: sorted u, sorted neighbors
- Candidate cycles sorted before feasibility check

**Performance Gains**:
- SCC: O(V+E) instead of exponential DFS
- Triangles: O(V·E) with bitset speedup
- Johnson: only on small SCCs, short lengths

---

### Phase 3: Extended Cycle Search (Optional)

**Goal**: Handle rare cases with longer cycles

**When**: Enabled by config flag `max_cycle_length > 5`

**Options**:
1. **Bounded Johnson** (lengths 6-8)
   - Exponential but controlled
   - Deterministic neighbor ordering

2. **MILP Fallback** (feature-gated)
   - Binary variable per tx: `x_t ∈ {0,1}`
   - Constraints: `balance_i + credit_i + Σ_recv - Σ_send ≥ 0`
   - Objective: `max Σ x_t · amount_t`
   - Settle selected batch atomically

**Default**: Disabled for performance

---

## Implementation Phases

### Phase 0: Foundation (Week 1)

**Tasks**:
1. Add `AgentId`, `TxId` interning infrastructure
2. Replace `HashSet` with `BTreeSet` in LSM
3. Implement batch queue removal pattern
4. Add event sorting before return
5. Add metrics (feature-gated): `lsm_metrics`

**Tests**:
- `test_id_interning_stability`
- `test_batch_removal_determinism`
- `test_event_sorting`
- All existing LSM tests pass

**Deliverable**: Same behavior, deterministic by construction

---

### Phase 1: Bilateral Speed (Week 2)

**Tasks**:
1. Implement `PairIndex` struct
2. Implement `ReadyKey` with total ordering
3. Replace `bilateral_offset()` body to use `PairIndex`
4. Add bilateral-specific metrics
5. Benchmark vs baseline

**Tests**:
- `test_pair_index_incremental_updates`
- `test_ready_key_ordering_deterministic`
- `test_bilateral_phase_single_compaction`
- `test_bilateral_credit_check_correctness`
- All existing bilateral tests pass

**Acceptance**:
- ≤ 1 queue compaction per bilateral phase
- Work proportional to #pairs, not #queue_items
- 2-10× speedup on bilateral-heavy scenarios

---

### Phase 2: Multilateral Speed (Week 3)

**Tasks**:
1. Implement aggregated graph builder
2. Implement Tarjan SCC (deterministic)
3. Implement triangle finder (bitset version)
4. Replace `detect_cycles()` with new pipeline
5. Add cycle-specific metrics
6. Benchmark vs baseline

**Tests**:
- `test_scc_prefilter_correctness`
- `test_triangle_enumeration_deterministic`
- `test_aggregated_graph_consistency`
- `test_cycle_priority_ordering`
- All existing cycle tests pass

**Acceptance**:
- Triangle pass satisfies 80%+ of multilateral settlements
- No exponential DFS on hot path
- 5-20× speedup on gridlock scenarios

---

### Phase 3: Extended Cycles (Week 4, Optional)

**Tasks**:
1. Implement bounded Johnson (length 4-8)
2. Add MILP fallback (feature-gated)
3. Config flag: `enable_extended_cycles`
4. Benchmark tradeoffs

**Tests**:
- `test_johnson_bounded_correctness`
- `test_milp_max_feasible_batch` (if implemented)
- Performance benchmarks on large SCCs

**Acceptance**:
- Handles rare long cycles without timeout
- Optional, disabled by default

---

## Testing Strategy

### Unit Tests (Rust)

1. **Determinism Suite**
   ```rust
   #[test]
   fn test_lsm_pass_determinism_1000_runs() {
       // Run same config 1000 times, assert byte-identical outputs
   }
   ```

2. **Correctness Suite**
   - Conservation: sum(net_positions) = 0
   - All-or-nothing: feasibility failures leave state unchanged
   - T2-compliant: full-value settlement, not partial

3. **Performance Suite** (feature-gated)
   ```rust
   #[bench]
   fn bench_bilateral_phase_vs_baseline(b: &mut Bencher) {
       // Compare old vs new with controlled queue sizes
   }
   ```

### Integration Tests (Python)

From `api/tests/integration/test_lsm_*.py`:
- `test_lsm_cycle_persistence.py` - events logged correctly
- `test_lsm_activation.py` - LSM triggers in expected scenarios
- `test_lsm_event_completeness.py` - all fields present

### Stress Tests

**Scenario**: `12_bank_lsm_gridlock_scenario.yaml`
- 12 banks, high arrival rates, tight liquidity
- Expected: heavy LSM usage, large cycles

**Metrics**:
- LSM time per tick (before vs after)
- Cycles settled per tick
- Queue compactions per phase
- SCC sizes, triangle vs Johnson usage

---

## Rollout Plan

### Week 1: Phase 0 (Foundation)
- **Merge criteria**: All tests pass, no behavior change
- **Risk**: Low (refactoring only)
- **Rollback**: Simple (revert commits)

### Week 2: Phase 1 (Bilateral)
- **Merge criteria**: 2× speedup on bilateral scenarios, determinism verified
- **Risk**: Medium (changed logic, but isolated)
- **Rollback**: Keep old `bilateral_offset` behind feature flag for 1 sprint

### Week 3: Phase 2 (Multilateral)
- **Merge criteria**: 5× speedup on gridlock scenarios, correctness tests pass
- **Risk**: High (complex algorithm change)
- **Rollback**: Keep old `detect_cycles` behind feature flag for 1 sprint

### Week 4: Phase 3 (Optional)
- **Merge criteria**: Config-gated, no default behavior change
- **Risk**: Low (opt-in feature)

---

## Success Metrics

### Determinism
- ✅ Same seed produces byte-identical `cycle_events`
- ✅ Same seed produces byte-identical `replay_events`
- ✅ No `HashSet` iteration in hot paths
- ✅ 1000 consecutive runs: all outputs identical

### Correctness
- ✅ All existing unit tests pass
- ✅ All existing integration tests pass
- ✅ New T2-compliant tests pass
- ✅ Conservation invariant never violated

### Performance
- ✅ Bilateral: 2-10× faster (depending on queue size)
- ✅ Multilateral: 5-20× faster (depending on gridlock severity)
- ✅ Queue compactions: ≤ 2 per pass (bilateral + multilateral)
- ✅ No O(N²) or worse patterns on hot path

### Instrumentation
- ✅ Per-phase timings available (feature-gated)
- ✅ SCC size distribution logged
- ✅ Triangle vs Johnson split logged
- ✅ Liquidity release metrics

---

## Risks & Mitigations

### Risk 1: Behavioral Changes
**Impact**: High (could break existing simulations)
**Mitigation**:
- Phased rollout with extensive testing
- Keep old implementations behind feature flags (1 sprint)
- Differential testing: compare old vs new on 100 scenarios

### Risk 2: Performance Regression
**Impact**: Medium (new code might be slower in some cases)
**Mitigation**:
- Benchmark suite with various queue sizes
- Abort if any scenario >10% slower
- Profile before/after on real configs

### Risk 3: Determinism Breaks
**Impact**: Critical (violates core invariant)
**Mitigation**:
- Determinism test runs 1000× before merge
- CI runs determinism suite on every commit
- Manual review of all `HashMap` → `BTreeMap` changes

### Risk 4: Cycle Selection Changes
**Impact**: Medium (could affect research results)
**Mitigation**:
- Make priority mode explicit (config: `ThroughputFirst` vs `LiquidityFirst`)
- Document changes in CHANGELOG
- Provide migration guide for existing studies

---

## Open Questions

1. **ID Interning Lifetime**
   - Option A: Per-pass (rebuild every tick)
   - Option B: Per-simulation (maintain throughout)
   - **Decision**: Per-simulation (simpler, faster)

2. **Metrics Feature Flag**
   - Should metrics be always-on or feature-gated?
   - **Decision**: Feature-gated `lsm_metrics` (avoid overhead in production)

3. **Backward Compatibility**
   - Keep old implementations for 1 sprint or remove immediately?
   - **Decision**: Keep behind `legacy_lsm` feature for 1 sprint

4. **MILP Solver**
   - Which library? (good_lp, coin_cbc, grb_rs)
   - **Decision**: Defer to Phase 3, use `good_lp` (pure Rust)

---

## References

- **Primary Guide**: `/docs/lsm_opti.md`
- **Current Implementation**: `backend/src/settlement/lsm.rs`
- **T2 Tests**: `backend/tests/test_lsm_t2_compliant.rs`
- **Cycle Detection Tests**: `backend/tests/test_lsm_cycle_detection.rs`
- **CLAUDE.md**: Project invariants and FFI guidelines

---

## Appendix: Detailed Algorithms

### A.1: PairIndex Update Algorithm

```rust
fn on_enqueue(tx: &Transaction) {
    let s = tx.sender_id();
    let r = tx.receiver_id();
    let amt = tx.amount();

    // Update forward bucket
    let bucket_sr = self.out.entry(s).or_default().entry(r).or_default();
    bucket_sr.sum += amt;
    bucket_sr.tx_ids.push(tx.id());

    // Check if reverse bucket exists
    if let Some(bucket_rs) = self.out.get(r).and_then(|m| m.get(s)) {
        if bucket_rs.sum > 0 && bucket_sr.sum > 0 {
            // Both directions have flow → ready pair
            let key = ReadyKey {
                neg_priority: -(bucket_sr.sum.min(bucket_rs.sum)),
                a: s.min(r),
                b: s.max(r),
            };
            self.ready.insert(key);
        }
    }
}

fn settle_pair(&mut self, a: AgentId, b: AgentId) -> BTreeSet<TxId> {
    // Get both buckets
    let bucket_ab = self.out.get_mut(a).unwrap().get_mut(b).unwrap();
    let bucket_ba = self.out.get_mut(b).unwrap().get_mut(a).unwrap();

    // Collect all tx_ids
    let mut to_remove = BTreeSet::new();
    to_remove.extend(bucket_ab.tx_ids.drain(..));
    to_remove.extend(bucket_ba.tx_ids.drain(..));

    // Zero out sums
    bucket_ab.sum = 0;
    bucket_ba.sum = 0;

    // Remove from ready (both directions)
    self.ready.remove(&ReadyKey { neg_priority: -(bucket_ab.sum), a, b });

    to_remove
}
```

### A.2: Triangle Enumeration Algorithm

```rust
fn find_triangles(scc: &[AgentId], graph: &Graph) -> Vec<Triangle> {
    let n = scc.len();
    let mut id_to_idx: BTreeMap<AgentId, usize> = BTreeMap::new();
    for (idx, &agent) in scc.iter().enumerate() {
        id_to_idx.insert(agent, idx);
    }

    // Build bitsets for out/in neighbors
    let mut out_bits: Vec<Vec<bool>> = vec![vec![false; n]; n];
    let mut in_bits: Vec<Vec<bool>> = vec![vec![false; n]; n];

    for (&u, neighbors) in graph {
        if let Some(&u_idx) = id_to_idx.get(&u) {
            for (&v, _edge) in neighbors {
                if let Some(&v_idx) = id_to_idx.get(&v) {
                    out_bits[u_idx][v_idx] = true;
                    in_bits[v_idx][u_idx] = true;
                }
            }
        }
    }

    let mut triangles = Vec::new();

    // For each edge u->v
    for u_idx in 0..n {
        for v_idx in 0..n {
            if !out_bits[u_idx][v_idx] { continue; }

            // Find w such that v->w and w->u
            for w_idx in 0..n {
                if out_bits[v_idx][w_idx] && in_bits[u_idx][w_idx] {
                    // Found triangle: u->v->w->u
                    let u = scc[u_idx];
                    let v = scc[v_idx];
                    let w = scc[w_idx];
                    triangles.push(Triangle { agents: vec![u, v, w, u], ... });
                }
            }
        }
    }

    triangles
}
```

### A.3: Deterministic Cycle Comparator

```rust
fn cycle_priority(mode: CyclePriorityMode, cycle: &Cycle) -> impl Ord {
    let total_value = cycle.transactions.iter()
        .map(|tx_id| get_tx_amount(tx_id))
        .sum();

    let net_positions = calculate_net_positions(cycle);
    let max_net_outflow = net_positions.values()
        .filter(|&&v| v < 0)
        .map(|v| v.abs())
        .max()
        .unwrap_or(0);

    let agents_tuple: Vec<AgentId> = cycle.agents.iter()
        .unique()
        .sorted()
        .copied()
        .collect();

    let tx_ids_tuple: Vec<TxId> = cycle.transactions.iter()
        .sorted()
        .copied()
        .collect();

    match mode {
        CyclePriorityMode::ThroughputFirst => {
            // Higher total value first, then lower liquidity usage
            (-total_value, max_net_outflow, agents_tuple, tx_ids_tuple)
        }
        CyclePriorityMode::LiquidityFirst => {
            // Lower liquidity usage first, then higher value
            (max_net_outflow, -total_value, agents_tuple, tx_ids_tuple)
        }
    }
}
```

---

**End of Plan**

*This plan will be updated as implementation progresses.*
