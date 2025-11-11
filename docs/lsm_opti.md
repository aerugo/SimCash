# Liquidity-Saving in RTGS: Why It’s Hard, What We Need, and How We’ll Fix It

This guide introduces the problem we’re solving in our **LSM (Liquidity-Saving Mechanisms)** module, why determinism and performance both matter, and how our redesigned approach addresses the pain points while preserving **T2/RTGS semantics**.

---

## The Setting: RTGS, Queues, and Gridlock

In a real-time gross settlement (RTGS) system, each payment settles **at full value** or waits in a queue. When participants’ outgoing payments are blocked by limited liquidity—but those same participants are waiting to **receive** funds from others—the system can enter **gridlock**: plenty of value is “in flight,” but nothing moves.

**LSM** solves this by restructuring queued items to settle a **feasible subset** that keeps every participant within their available **balance + credit limit**, often using:

* **Bilateral offsetting**: netting A↔B obligations.
* **Multilateral cycles**: A→B→C→…→A, where unequal amounts are allowed.
* **Two-phase atomicity**: “check feasibility” then “settle all or nothing.”

### Non-negotiable constraints (T2 semantics)

* **Full value** (no splitting): a transaction either settles entirely or not at all.
* **Unequal cycles** are allowed; **net positions** must be covered.
* **Two-phase commit**: read-only feasibility, then atomic execution.
* **Determinism**: same inputs ⇒ same outputs, byte-for-byte (events, order, results).

---

## The Problem Today

1. **Performance bottlenecks**

* We rebuild bilateral maps by scanning the entire queue each tick.
* We remove transactions from the queue with repeated `.retain()`, doing work proportional to queue length **per transaction**.
* We detect cycles with an exponential DFS that re-visits a lot of state.

2. **Determinism fragility**

* Hash iteration order and capacity growth can vary, breaking reproducibility.
* Candidate selection (which pair or cycle to settle first) wasn’t fully tied to an explicit, total ordering.

The net effect: slow passes, unpredictable runtimes at scale, and outputs that could vary across runs.

---

## Our Goals

* **Deterministic by construction**
  Every selection uses an **explicit total order** with clear tie-breakers. All data structures we iterate are order-preserving.

* **Faster common case**
  Make bilateral and small cycles near-linear in practice; do one queue compaction per phase; avoid exhaustive graph rescans.

* **No behavioral change**
  Keep T2 semantics: full-value settlement, unequal amounts, and two-phase all-or-nothing execution.

---

## The Proposed Solution (At a Glance)

```
┌─────────────────────────────────────────────────────────────────┐
│  Queue                                                         │
│    (ordered list of queued txs)                                │
└───────────────┬───────────────────────────┬─────────────────────┘
                │                           │
        (1) Incremental                (3) Aggregated Graph Snapshot
            PairIndex                       per pass (BTreeMap)
                │                           │
         Ready pairs by                (4) SCC filter → only
         deterministic priority             strongly connected parts
                │                           │
      Settle bilateral nets            (5) Triangle finder (fast)
      (two-phase, full-value)               │
                │                      (6) Bounded Johnson (len 4–5)
      (2) Single compaction                 │
         of queue per phase            Settle feasible cycles
                │                           │
          process_queue()               process_queue()
                └──────────► Repeat small fixed # iterations ◄──────────┘
```

### 1) Incremental **PairIndex** for bilateral offsetting

* Maintain `(sender → receiver)` buckets with totals and the list of tx IDs in **enqueue order** using `BTreeMap`.
* Track **ready** bilateral pairs in a deterministic **`BTreeSet`** keyed by a priority tuple:

  * primary: larger liquidity release first (e.g., `min(sum A→B, sum B→A)`),
  * tie-break: lexicographic `(min(agent A,B), max(agent A,B))`.
* Process pairs until the ready set is empty; check **only the net payer’s** credit once; settle all full txs in both directions.

### 2) **One queue compaction** per phase

* During settlement, collect tx IDs to remove.
* After the bilateral phase (and again after the cycle phase), run **one** `retain` on the central queue—preserving the queue’s original order for survivors.

### 3) Aggregated **agent-level graph** snapshot

* Build a read-only snapshot mapping agent→agent with the **sum** of remaining amounts and the list of tx IDs—using `BTreeMap` so iteration is sorted and deterministic.

### 4) **SCC prefilter** (linear and deterministic)

* Compute strongly connected components. Only SCCs with size ≥ 3 can admit multilateral cycles.
* Process SCCs in sorted order (by their member AgentIds).

### 5) **Fast triangles** first

* Inside each SCC, assign a **stable vertex index** (sorted agents).
* Build `in/out` bitsets and enumerate **3-cycles** using set intersections.
* Rank triangle candidates by a single, explicit comparator (see below), then run **two-phase** settlement.

### 6) **Bounded Johnson** for length 4–5 cycles

* If needed after triangles, enumerate simple cycles up to a small max length (e.g., 5), in sorted neighbor order; sort candidates, then run two-phase settlement.

---

## Determinism: One Comparator to Rule Them All

All candidate selections (pairs and cycles) use a **total order**:

* **Bilateral pairs**:

  1. higher liquidity release first,
  2. then `(agent_a, agent_b)` lexicographically (with `a < b` canonicalized).

* **Cycles (triangles and 4–5)**: choose a mode and stick to it:

  * **ThroughputFirst** (default): higher **total settled value** first; tie-break by lower **max net outflow**; then by `(agents tuple, tx_ids tuple)` lexicographically.
  * **LiquidityFirst**: lower **max net outflow** first; tie-break by higher **total value**; then by `(agents tuple, tx_ids tuple)`.

**Events and replay outputs** are sorted before return with a stable comparator:

```
(tick, cycle_type, settled_value DESC, total_value DESC,
 agents_lex_tuple, tx_ids_lex_tuple)
```

---

## What Doesn’t Change (Semantics)

* **Two-phase protocol remains intact**:

  * **Phase 1** (read-only): compute net positions; verify conservation; check each net payer’s `balance + credit ≥ required`.
  * **Phase 2** (atomic): settle **each** involved transaction at **full value**; update balances; mark txs for removal; compact once.

* **Unequal values in cycles** supported; only **net payers** must fund outflow.

---

## Why This Will Be Faster (Even With Tree Maps)

* We stop rescanning everything every tick: **PairIndex** updates incrementally.
* We remove **O(N·K)** queue churn: **single compaction** replaces per-tx `retain`.
* We cut search space:

  * **SCCs** eliminate nodes/edges that cannot be in cycles.
  * **Bitset triangles** find the most common cycles quickly.
  * **Bounded Johnson** only runs on small SCCs and short lengths.
* We remove string churn by **interning IDs** to integers once.

---

## Rollout in Four Safe Phases

1. **Phase 0 (no behavior change)**

   * Intern agent/tx IDs; replace scattered clones.
   * Batch queue removals (single compaction).
   * Final-sort events for reproducibility.

2. **Phase 1 (bilateral speed)**

   * Implement `PairIndex` and deterministic ready set.
   * Drive bilateral netting from the index; keep two-phase checks.

3. **Phase 2 (multilateral speed)**

   * Aggregated graph snapshot + SCC prefilter + triangle enumeration.
   * Only if needed, keep the old DFS behind a flag for parity tests.

4. **Phase 3 (bounded Johnson, optional MILP)**

   * Add short-cycle enumeration (length 4–5).
   * Optional MILP fallback (max feasible batch), behind a feature flag.

Each phase is measurable and reversible.

---

## How We’ll Know It Worked

**Determinism**

* Same seed/run produces **byte-identical** `cycle_events`, `replay_events`, and final queue.
* No data structure iteration without an explicit, total order.

**Correctness**

* All existing unit tests pass.
* New tests for conservation, “all-or-nothing,” and liquidity edge cases pass.

**Performance**

* Instrumentation shows:

  * ≤ 1 compaction per phase,
  * Bilateral work proportional to #affected pairs/txs, not full queue size,
  * Triangle pass satisfies most multilateral settlements,
  * Minimal (or no) DFS usage on hot paths.

---

## FAQ

**Does using `BTreeMap` slow us down too much?**
No. The main wins are from **algorithmic** changes (incremental indexing, single compaction, SCC+triangles). Tree maps ensure ordering; the overall pass gets much faster despite slightly higher per-lookup cost.

**Why not parallelize?**
We can parallelize **read-only** building (e.g., adjacency), but any phase that affects selection order must remain serial—or must **sort results** before they influence outcomes. Determinism first.

**Will cycle choices change?**
We now make the selection criteria explicit and deterministic. If you need different trade-offs, switch the comparator mode (`ThroughputFirst` vs `LiquidityFirst`)—results remain deterministic.

---

## TL;DR

* Keep T2 semantics and determinism.
* Stop rescanning and stop per-tx queue mutation.
* Use **PairIndex** + **single compaction** + **SCC → triangles → short cycles**.
* Make all selections come from **total orders** with explicit tie-breakers.

This yields a reproducible, much faster LSM that behaves exactly like an RTGS should—just without the gridlock in our CPU.

-----------------------

Below is a **single, consolidated, implementation‑ready plan** that delivers **deterministic** behavior while addressing the major performance bottlenecks you identified in `backend/src/settlement/lsm.rs`.

---

## 0) Goals & non‑negotiable invariants

**Functional**

* Preserve **T2 semantics**:

  * Each payment settles **at full value** or not at all.
  * **Two‑phase**: feasibility check (read‑only) then atomic execution.
  * **Unequal values** in cycles allowed; settlement is **all‑or‑nothing**.

**Determinism**

* **Total order** governs **every** selection that affects outcomes:

  * No reliance on hash iteration order.
  * No nondeterministic tie‑breakers.
* Same inputs ⇒ **byte‑identical** `cycle_events`, `replay_events`, and queue state.

**Performance**

* Remove O(N·K) queue mutation patterns.
* Avoid exponential cycle search; make the common case (bilateral & triangles) **near linear**.

---

## 1) Data model & deterministic containers

1. **Agent/Tx IDs (stable interning)**

   * Build a **stable mapping** from agent string → `AgentId(u32)` by **sorting agent names lexicographically** once at init.
   * Build a **stable mapping** from tx string → `TxId(u64)` by assigning IDs **in queue order** (or by lexicographic order if you want identical IDs across runs independent of enqueue order).
   * Keep reverse maps for reporting.

2. **Core containers**

   * Use `BTreeMap`/`BTreeSet` wherever iteration order impacts logic:

     * Aggregated adjacency: `BTreeMap<AgentId, BTreeMap<AgentId, PairBucket>>`
     * Ready pair queue: `BTreeSet<ReadyKey>`
     * Remove sets: `BTreeSet<TxId>`
   * For small, append‑heavy per‑pair tx storage: `Vec<TxId>` or `SmallVec<[TxId; 8]>` (order = enqueue order).

3. **Event ordering**

   * Before returning from `run_lsm_pass`, **sort** `cycle_events` & `replay_events` by a deterministic comparator (see §6).

---

## 2) Incremental **PairIndex** (deterministic & fast bilateral)

**Purpose**
Avoid rebuilding (sender,receiver) buckets every tick and avoid per‑tx queue mutation.

**Types**

```rust
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Debug)]
struct AgentId(u32);
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Debug)]
struct TxId(u64);

struct PairBucket {
    sum: i64,                   // sum of remaining amounts s->r
    tx_ids: Vec<TxId>,          // in enqueue order
}

/// sender -> (receiver -> bucket), deterministic by key order
type Adj = BTreeMap<AgentId, BTreeMap<AgentId, PairBucket>>;

#[derive(Clone, Eq, PartialEq, Debug)]
struct ReadyKey {
    // smallest tuple wins: negative to get "max priority first"
    neg_priority: i64,          // e.g., -min(sum_ab, sum_ba)
    a: AgentId,                 // a < b (canonicalized)
    b: AgentId,
}
impl Ord for ReadyKey { /* lex on (neg_priority, a, b) */ }
impl PartialOrd for ReadyKey { /* delegate to Ord */ }

struct PairIndex {
    out: Adj,
    ready: BTreeSet<ReadyKey>,  // deterministic priority queue
}
```

**Updates**

* **On enqueue** of tx `s→r, amt`:

  * `out[s][r].sum += amt; out[s][r].tx_ids.push(tx_id);`
  * If both `out[s][r].sum > 0` and `out[r][s].sum > 0`, insert/update
    `ReadyKey{ neg_priority: -min(sum_ab,sum_ba), a=min(s,r), b=max(s,r) }` into `ready`.
* **On full settlement** of a pair: remove used txs from both buckets (pop or drain), reduce sums, update `ready` accordingly.

**Processing**

* While `!ready.is_empty()`:

  * `let key = ready.first().cloned().unwrap(); ready.remove(&key);`
  * Resolve pair `(a,b)` by settling **all** transactions in both directions (see §4), subject to the **single net‑paying agent** credit check (as you already do).
* Collect tx ids into `to_remove: BTreeSet<TxId>`; perform **one** queue compaction at the end of the bilateral phase:

  ```rust
  queue.retain(|id| !to_remove.contains(&intern_tx(id)));
  ```

**Determinism**

* All structures are `BTree*`; priorities are numeric + lexicographic tie‑breakers; pop order is unique.

---

## 3) Graph snapshot for multilateral search (agent‑level, aggregated)

Build a **read‑only**, per‑pass snapshot (this keeps PairIndex simple and avoids cross‑concerns):

```rust
struct AggEdge {
    sum: i64,          // sum of remaining amounts i->j
    tx_ids: Vec<TxId>, // map back to concrete txs for settlement
}

type Graph = BTreeMap<AgentId, BTreeMap<AgentId, AggEdge>>;
```

* Build from the **current queue minus** the `to_remove` set from the bilateral phase.
* This graph is **deterministic** because it derives from ordered inputs and uses `BTreeMap`.

---

## 4) Multilateral cycles: SCC → triangles → bounded Johnson

### 4.1 Strongly Connected Components (SCC) prefilter

* Run **Tarjan** on the aggregated `Graph`, iterating vertices and neighbors in sorted order.
* Only SCCs with **size ≥ 3** can contain true multilateral cycles.
* Process SCCs in **ascending** canonical tuple order (the sorted list of member AgentIds).

### 4.2 Fast triangles (length 3) first

* For each SCC:

  1. Build a **stable vertex index**: `Vec<AgentId>` sorted ascending; map `AgentId -> idx`.
  2. Build `out_bits[idx]` and `in_bits[idx]` bitsets (`Vec<u64>` or a fixed‑bitset) from the SCC subgraph.
  3. Deterministically generate candidates:

     * For `u` ascending, for each neighbor `v` ascending:

       * `cand = out_bits[v] & in_bits[u]` → iterate `w` ascending.
       * Candidate triangle: `u→v, v→w, w→u`.
  4. For each triangle, compute:

     * `total_value = sum(agg(u→v), agg(v→w), agg(w→u))`
     * `net_positions` (your existing function on real txs or using aggregated sums)
     * `max_net_outflow = max(|negatives|)`
     * **priority tuple** (see §6).
  5. **Sort** the triangle candidates by the priority tuple (descending value of the primary score; lex tie‑breakers).
  6. Iterate candidates in that order:

     * Phase 1 feasibility (existing `check_cycle_feasibility` but fed with the concrete tx lists of the three edges).
     * If feasible, **phase 2**: settle **all full txs** on the three edges; update **only the snapshot** (and collect `to_remove`), then continue (no re‑scan).
     * Stop if per‑tick budget hit (`max_cycles_per_tick`).

### 4.3 Bounded Johnson for cycles of length 4–5

* On SCCs still rich after triangles:

  * Run **Johnson’s elementary cycles** with:

    * neighbor iteration in ascending order,
    * **length cap** `k = min(config.max_cycle_length, 5)`,
    * accumulate each cycle as a candidate record with the same priority fields as triangles,
    * **sort** the candidate list with the same comparator before feasibility.
  * Apply feasibility & settlement as above; update snapshot and `to_remove`.

**Why this is fast**

* SCC filtering is O(V+E).
* Triangles via bitset intersections are extremely fast and capture most practical cases.
* Johnson runs only in small SCCs and stops at small lengths.

---

## 5) Settlement mechanics (unchanged semantics; faster execution)

* **Phase 1 (check)**
  Use your existing:

  * Validate txs exist & unsatisfied.
  * Compute `net_positions` over **actual** txs (not only sums).
  * Check conservation and each net payer’s liquidity (`balance + credit ≥ required`).

* **Phase 2 (execute atomically)**

  * For **each tx** in the candidate cycle, settle **full amount**:

    * `adjust_balance(sender, -amount)`; `adjust_balance(receiver, +amount)`.
    * `settle(amount, tick)`.
    * Add tx to `to_remove`.
  * Do **not** mutate the central queue inside the inner loop; defer to the single compaction at the end of the multilateral phase.

* **Replay & events**

  * Create `Event::LsmCycleSettlement`/`LsmCycleEvent` records for each settled cycle.
  * De‑duplicate via a cycle key if needed; otherwise, your SCC+candidate process avoids duplicates naturally.

---

## 6) Deterministic priority & tie‑breakers (single source of truth)

Define these **once**; use them everywhere:

* **Pairs (bilateral)**

  1. **Primary**: `liquidity_release = min(sum_ab, sum_ba)` (**higher first**).
  2. **Secondary**: `(a_id, b_id)` ascending, where `a_id < b_id` canonicalizes the pair.

  Store as `ReadyKey{ neg_priority = -liquidity_release, a, b }` in a `BTreeSet`.

* **Cycles (triangles & length 4–5)**

  1. Choose **one** primary objective. Two sensible options:

     * `LiquidityFirst`: **lower** `max_net_outflow` first (uses less liquidity), then higher `total_value`.
     * `ThroughputFirst` (default): **higher** `total_value` first, then lower `max_net_outflow`.
  2. **Ties**: break by `agents_lex_tuple` (sorted list of unique agents in cycle) then by `tx_ids_lex_tuple` (sorted ids).

  Implement as a tuple comparator and reuse for both triangle and Johnson candidates.

* **Event/replay sorting**

  * Sort before returning by:

    ```
    (tick, cycle_type, settled_value DESC, total_value DESC,
     agents_lex_tuple, tx_ids_lex_tuple)
    ```

---

## 7) `run_lsm_pass` orchestration (new shape)

1. **Initialize per‑pass accumulators**

   * `to_remove: BTreeSet<TxId>`
   * `cycle_events: Vec<LsmCycleEvent>`
   * `replay_events: Vec<Event>`
   * `iterations = 0;`

2. **Loop up to MAX_ITERATIONS** (small number like current 3)

   * **Bilateral phase**

     * Drive `PairIndex.ready` to settle pairs.
     * Accumulate `to_remove`.
   * **Queue compaction #1** (if any removals)

     * Single `retain` pass on the central queue using `to_remove`.
     * Clear `to_remove` or carry it into multilateral if you want a single compaction later; both are deterministic.
   * **Process queue normally** (`process_queue`) once; accumulate its result.
   * **Build aggregated Graph snapshot** from current queue.
   * **SCC → triangles → bounded Johnson**; settle cycles; accumulate `to_remove`, `cycle_events`, `replay_events`.
   * **Queue compaction #2** (if any).
   * **Process queue again** (`process_queue`) once.
   * If no progress vs. previous iteration, **break**.

3. **Final sorting of events** using the deterministic comparator (see §6).

4. **Return `LsmPassResult`** (unchanged API), with events sorted and queue size recomputed.

---

## 8) Metrics & instrumentation (to validate wins)

Add counters/timers (feature‑gated) captured per pass:

* Queue sizes: before/after bilateral, before/after cycles.
* `pairs_examined`, `pairs_settled`, `pair_liquidity_release_total`.
* `scc_count`, distribution of SCC sizes.
* `triangles_found`, `triangles_attempted`, `triangles_settled`.
* `cycles_k_found/attempted/settled` for k=4..5.
* `total_settled_value`, `max_net_outflow_peak`.
* Wall‑clock timings for: building PairIndex, SCC, triangles, Johnson, compactions.

Keep metric names stable so before/after comparisons are apples‑to‑apples.

---

## 9) Testing & verification plan

**Determinism**

* Run the same input seed **N times**:

  * Assert byte‑identical `cycle_events` and `replay_events` (serialize to bytes and diff).
  * Assert final queue content/order identical.
* Property: any iteration budget or detection budget change **cannot** alter results if they’re not hit (use oversized budgets to compare with small).

**Correctness**

* Unit tests for:

  * Bilateral netting examples (your doc examples).
  * Triangles with unequal values and known net positions.
  * Cycles that **fail** feasibility (just under liquidity) and then **pass** when liquidity is raised.
  * Conservation invariant in `calculate_cycle_net_positions` (sum == 0).
* Property tests (QuickCheck/proptest):

  * Random graphs where you compare net balances pre‑ vs post‑settlement; conservation holds globally.
  * “All or nothing”: in a selected cycle, either **all** txs moved to settled or **none**.
* Differential tests:

  * For small graphs (≤ 8 agents, ≤ 30 txs) compare **new** engine vs **old DFS** engine; assert equal (or better) settled sets with the same tie‑break objective.

**Performance**

* Stress tests with growing M (tx count) and density; record metrics in §8 and watch slope.

---

## 10) Risks & mitigations

* **Risk:** Different objective ordering could change which cycles are chosen.
  **Mitigation:** Make objective explicit (`LiquidityFirst` vs `ThroughputFirst`) with default; document; add tests that exercise both; expose in `LsmConfig`.

* **Risk:** Snapshot drift if we mutate queue during inner loops.
  **Mitigation:** Enforce the **single compaction** rule; forbid per‑tx queue mutation in code review (lint comment); add an internal flag that panics if queue is mutated inside cycle settlement loops (debug builds).

* **Risk:** Event duplication across iterations.
  **Mitigation:** Deterministic processing + removal after settlement removes inputs; additionally, keep a `BTreeSet<(agents_lex_tuple, tx_ids_lex_tuple)>` seen‑set per pass if needed.

---

## 11) Rollout strategy (safe & incremental)

* **Phase 0 (no logic change):**

  * Batch queue removals (single compaction).
  * Replace `BTreeMap`/`Vec<String>` hot clones with ID interning (stable mapping).
  * Add final sorting of events.

* **Phase 1 (bilateral speed):**

  * Introduce `PairIndex` + deterministic `ready` queue.
  * Remove full rescans from `bilateral_offset`.

* **Phase 2 (multilateral speed):**

  * Aggregated Graph + SCC + triangles pipeline.
  * Keep old DFS behind a flag for parity tests.

* **Phase 3 (optional):**

  * Bounded Johnson for k=4..5.
  * Optional MILP fallback behind a feature flag (see §12).

Each phase is independently measurable and reversible.

---

## 12) Optional: MILP “max feasible batch” fallback

When heuristics stall:

* Binary `x_t ∈ {0,1}` per tx.
* For each agent `i`: `balance_i + credit_i + Σ_recv(i) x_t·amt_t − Σ_send(i) x_t·amt_t ≥ 0`.
* Objective: maximize `Σ x_t·amt_t` (or priority‑weighted).
* If enabled, run **rarely** (e.g., no progress for X passes), settle selected txs in one batch.
* Keep behind `#[cfg(feature = "lsm_milp")]` to avoid solver deps by default.

---

## 13) Concrete code hooks to add/change (in this repo)

* **`backend/src/settlement/lsm.rs`**

  * Add modules (can be inline first, split later):

    * `mod pair_index;` — PairIndex, ReadyKey, bilateral driver.
    * `mod graph;` — aggregated snapshot builder, SCC (Tarjan), triangle finder, bounded Johnson.
    * `mod order;` — all comparators & `sort_*` helpers (single source of truth for tie‑break).
    * `mod metrics;` — counters/timers behind `#[cfg(feature="lsm_metrics")]`.
  * Replace `bilateral_offset` body to **consume** `PairIndex` instead of scanning queue.
  * Replace `detect_cycles` with `find_and_settle_cycles(state, &config, tick, ticks_per_day, &mut to_remove, &mut events, &mut replay_events)`, which implements §4 and §5.
  * Ensure **single queue compaction** per phase (bilateral & multilateral).
  * At end of `run_lsm_pass`, **sort** events via `order::sort_events(&mut cycle_events, &mut replay_events)`.

---

## 14) Acceptance criteria (what “done” looks like)

1. **Determinism**

   * Running the same scenario twice emits **byte‑identical** `cycle_events` + `replay_events`.
   * Final queue contents (ids and order) are identical across runs.

2. **Correctness**

   * All current unit tests pass; new tests in §9 pass.
   * All doc examples in `lsm.rs` continue to hold.

3. **Performance**

   * In synthetic benchmarks with ≥ 10k queued txs, the new engine shows:

     * A single or near‑single `retain` per phase (verified by counters).
     * Triangle pass dominates multilateral settlements (DFS either removed or not on the hot path).
     * No iteration or settlement path scales worse than O(V+E) except bounded Johnson when enabled.

---

## 15) Pseudocode snippets (drop‑in skeletons)

**Bilateral loop (driver)**

```rust
fn run_bilateral_phase(state: &mut SimulationState,
                       pidx: &mut PairIndex,
                       tick: usize,
                       to_remove: &mut BTreeSet<TxId>) -> BilateralOffsetResult
{
    let mut result = BilateralOffsetResult { /* ... */ };

    while let Some(key) = pidx.ready.first().cloned() {
        pidx.ready.remove(&key);
        let (a, b) = (key.a, key.b);

        // sums from pidx.out[a][b], pidx.out[b][a]
        // decide net sender; check credit limit once (deterministic).
        if !net_sender_can_cover(/* ... */) { continue; }

        // settle all txs in both directions in enqueue order
        // adjust balances; mark tx_ids in to_remove; update pidx buckets & ready keys
        // increment counters in `result`
    }

    result
}
```

**Cycle candidate priority (single definition)**

```rust
enum CyclePriorityMode { LiquidityFirst, ThroughputFirst }

fn cycle_priority(mode: CyclePriorityMode,
                  total_value: i64,
                  max_net_outflow: i64,
                  agents_tuple: &[AgentId],
                  tx_ids_tuple: &[TxId]) -> impl Ord {
    match mode {
        CyclePriorityMode::LiquidityFirst =>
            (max_net_outflow, -total_value, agents_tuple.to_vec(), tx_ids_tuple.to_vec()),
        CyclePriorityMode::ThroughputFirst =>
            (-total_value, max_net_outflow, agents_tuple.to_vec(), tx_ids_tuple.to_vec()),
    }
}
```

**Single compaction**

```rust
fn compact_queue(state: &mut SimulationState, to_remove: &BTreeSet<TxId>) {
    if to_remove.is_empty() { return; }
    state.rtgs_queue_mut().retain(|tx_str_id| {
        let tid = intern_tx(tx_str_id); // stable mapping
        !to_remove.contains(&tid)
    });
}
```

---