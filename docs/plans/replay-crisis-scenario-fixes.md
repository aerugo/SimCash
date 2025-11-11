# Replay Crisis Scenario Fixes - Implementation Plan

**Status**: Draft
**Created**: 2025-11-11
**Epic**: Replay Identity & Display Correctness
**Context**: Comprehensive audit of `replay --from-tick=250 --to-tick=260` on `three_day_realistic_crisis.yaml` revealed critical correctness bugs and instrumentation gaps

---

## Executive Summary

A detailed audit of replay output (ticks 250-260) against the RTGS-First specification uncovered **10 categories of issues**, grouped into:

- **4 high-severity correctness bugs** (cost mis-scaling, missing events, data loss)
- **4 medium-severity realism gaps** (collateral churn, LSM visibility, deadline handling)
- **2 output consistency issues** (summary mismatches, missing invariant checks)

This plan provides a **surgical, test-driven approach** to fix each issue while preserving the existing replay identity architecture.

---

## Critical Context

### What's Working ✅
- **Replay identity architecture**: StateProvider pattern is sound
- **Balance conservation**: Sum of balances holds constant ($460,000)
- **Two-queue model**: Queue-1/Queue-2 separation is correct
- **Event persistence**: `simulation_events` table stores enriched events

### What's Broken 🚨
- **Cost calculations**: Orders of magnitude wrong (bps → % conversion bug)
- **Event gaps**: Queue-2 items disappear without settlement/drop events
- **Display bugs**: Queue-1 amounts shown as $0.00; credit percentages doubled
- **Operational realism**: Collateral oscillates every tick; deadlines exceed episode end

### Impact
- **Policy learning impossible**: Warped costs break incentives
- **Audit trail broken**: Missing events prevent traceability
- **User confusion**: Misleading displays undermine trust

---

## Prioritized Issue Breakdown

### 🔴 P0: High-Severity Correctness Bugs

#### Issue #1: Cost-Rate Mis-Scaling (bps interpreted as %)

**Symptom**
```
Tick 250, CORRESPONDENT_HUB:
  Balance: -$117,679.26 (overdraft)
  Liquidity cost: $94,143.41  ❌ WRONG

Expected (0.8 bps per tick):
  Cost = 117,679.26 × 0.8 × 1e-4 = $9.41  ✅ CORRECT
```

**Root Cause**
- Config defines `overdraft_bps_per_tick: 0.8` (basis points)
- Code multiplies by `0.8` as a raw fraction (80%), not `0.8 × 1e-4` (0.008%)
- Same bug for `collateral_cost_per_tick_bps: 0.0005`

**Affected Files**
- `backend/src/settlement/costs.rs` (or wherever cost accrual happens in Rust)
- `api/payment_simulator/cli/display/verbose_output.py` (display only; root is in Rust)

**Fix Strategy**
1. **Define canonical conversion** (Rust):
   ```rust
   // backend/src/settlement/costs.rs or backend/src/models/cost.rs

   /// Convert basis points per tick to a per-tick rate fraction.
   /// 1 bps = 0.0001 (1e-4) as a fraction.
   pub fn bps_to_rate(bps: f64) -> f64 {
       bps * 1e-4
   }

   // Usage in cost accrual:
   let overdraft_rate = bps_to_rate(config.overdraft_bps_per_tick);
   let liquidity_cost = neg_balance.abs() as f64 * overdraft_rate;
   ```

2. **Update all cost accrual sites**:
   - Overdraft cost (liquidity cost on negative balances)
   - Collateral cost (cost per tick on posted collateral)
   - Delay cost per tick per transaction

3. **Add unit tests** (`backend/tests/costs_test.rs`):
   ```rust
   #[test]
   fn test_overdraft_cost_accrual() {
       let balance = -100_000_00; // -$100,000 in cents
       let bps_per_tick = 1.0;     // 1 bps
       let rate = bps_to_rate(bps_per_tick);
       let cost = (balance.abs() as f64 * rate) as i64;
       assert_eq!(cost, 1000, "1 bps on $100k = $10/tick");
   }

   #[test]
   fn test_collateral_cost_accrual() {
       let collateral = 50_000_00; // $50,000 in cents
       let bps_per_tick = 0.0005;  // 0.0005 bps
       let rate = bps_to_rate(bps_per_tick);
       let cost = (collateral as f64 * rate) as i64;
       assert_eq!(cost, 0, "0.0005 bps on $50k ≈ $0.0025 (rounds to 0 cents)");
   }
   ```

4. **Verify config comments align**:
   - `overdraft_bps_per_tick: 0.8` with comment "~145% annualized"
   - Verify: `0.8 bps/tick × 100 ticks/day × 250 business days/year = 20,000 bps/year = 200%/year`
   - Comment should say "~200% annualized", not 145% (or adjust config)

**Acceptance Criteria**
- [ ] All cost accruals use `bps_to_rate()` helper
- [ ] Unit tests pass for 1 bps, 0.8 bps, 0.0005 bps edge cases
- [ ] Replay output shows liquidity cost ~$9.41 (not $94k) for -$117k balance at 0.8 bps
- [ ] Config comments match actual annualized rates

---

#### Issue #2: Queue-2 "Teleportation" (Missing Events)

**Symptom**
```
Tick 250-251: Queue-2 contains TX bd441d74 → REGIONAL_TRUST $3,658.44
Tick 253:      Queue-2 only shows TX c8870bec $4,383.04
               bd441d74 disappeared with NO event ❌
```

**Root Cause**
- Queue-2 items are settling or being dropped, but events are not being:
  1. **Generated** in Rust (`Event::RtgsQueue2Settle`, `Event::RtgsQueue2Drop`), OR
  2. **Persisted** to `simulation_events` table, OR
  3. **Displayed** in replay verbose output

**Affected Files**
- `backend/src/settlement/rtgs.rs` (Queue-2 settlement logic)
- `backend/src/models/event.rs` (`Event` enum)
- `backend/src/ffi/orchestrator.rs` (`get_tick_events()` serialization)
- `api/payment_simulator/cli/display/verbose_output.py` (`display_tick_verbose_output()`)

**Fix Strategy**

1. **Define missing events** (`backend/src/models/event.rs`):
   ```rust
   pub enum Event {
       // ... existing variants ...

       /// Queue-2 item settled via RTGS (liquidity became available)
       RtgsQueue2Settle {
           tick: i64,
           tx_id: String,
           sender: String,
           receiver: String,
           amount: i64,
           reason: String, // "liquidity_restored", "lsm_freed_funds", etc.
       },

       /// Queue-2 item dropped at deadline (no liquidity + deadline passed)
       RtgsQueue2DropDeadline {
           tick: i64,
           tx_id: String,
           sender: String,
           receiver: String,
           amount: i64,
           deadline: i64,
       },

       /// Queue-2 item force-settled at EoD backstop
       EodBackstopSettle {
           tick: i64,
           tx_id: String,
           sender: String,
           receiver: String,
           amount: i64,
           backstop_method: String, // "central_bank_liquidity", "netting", etc.
       },
   }
   ```

2. **Generate events in Rust** (`backend/src/settlement/rtgs.rs`):
   ```rust
   // In process_queue2():
   for tx in queue2_ready_to_settle {
       // Attempt settlement
       if sender.balance >= tx.amount {
           // Settle
           sender.balance -= tx.amount;
           receiver.balance += tx.amount;

           // ✅ EMIT EVENT
           events.push(Event::RtgsQueue2Settle {
               tick: current_tick,
               tx_id: tx.id.clone(),
               sender: tx.from_agent.clone(),
               receiver: tx.to_agent.clone(),
               amount: tx.amount,
               reason: "liquidity_restored".to_string(),
           });
       } else if current_tick >= tx.deadline {
           // Drop
           events.push(Event::RtgsQueue2DropDeadline {
               tick: current_tick,
               tx_id: tx.id.clone(),
               sender: tx.from_agent.clone(),
               receiver: tx.to_agent.clone(),
               amount: tx.amount,
               deadline: tx.deadline,
           });
       }
   }
   ```

3. **Serialize via FFI** (`backend/src/ffi/orchestrator.rs`):
   ```rust
   Event::RtgsQueue2Settle { tick, tx_id, sender, receiver, amount, reason } => {
       let mut dict = HashMap::new();
       dict.insert("event_type".to_string(), "rtgs_queue2_settle".into());
       dict.insert("tick".to_string(), tick.into());
       dict.insert("tx_id".to_string(), tx_id.into());
       dict.insert("sender".to_string(), sender.into());
       dict.insert("receiver".to_string(), receiver.into());
       dict.insert("amount".to_string(), amount.into());
       dict.insert("reason".to_string(), reason.into());
       dict
   }
   // Similar for RtgsQueue2DropDeadline, EodBackstopSettle
   ```

4. **Display in verbose output** (`api/payment_simulator/cli/display/verbose_output.py`):
   ```python
   def display_tick_verbose_output(provider, tick, events):
       # ... existing sections ...

       # NEW: Queue-2 Activity section
       q2_settles = [e for e in events if e['event_type'] == 'rtgs_queue2_settle']
       q2_drops = [e for e in events if e['event_type'] == 'rtgs_queue2_drop_deadline']

       if q2_settles or q2_drops:
           console.print("\n💳 Queue-2 Activity:")
           for e in q2_settles:
               console.print(f"   ✅ SETTLED: TX {e['tx_id'][:8]}... | "
                            f"{e['sender']} → {e['receiver']} | "
                            f"${e['amount']/100:.2f} | Reason: {e['reason']}")
           for e in q2_drops:
               console.print(f"   ❌ DROPPED: TX {e['tx_id'][:8]}... | "
                            f"{e['sender']} → {e['receiver']} | "
                            f"${e['amount']/100:.2f} | Deadline: Tick {e['deadline']}")
   ```

5. **Add invariant check** (new: `api/payment_simulator/cli/display/invariant_checks.py`):
   ```python
   def check_queue2_continuity(prev_q2, curr_q2, events, tick):
       """
       Verify Queue-2 continuity: any item missing from curr_q2 must have
       a corresponding settle/drop event.
       """
       prev_ids = {tx['id'] for tx in prev_q2}
       curr_ids = {tx['id'] for tx in curr_q2}
       missing = prev_ids - curr_ids

       event_ids = {e['tx_id'] for e in events if e['event_type'] in
                    ['rtgs_queue2_settle', 'rtgs_queue2_drop_deadline', 'eod_backstop_settle']}

       unaccounted = missing - event_ids
       if unaccounted:
           raise InvariantViolation(
               f"Tick {tick}: Queue-2 items disappeared without events: {unaccounted}"
           )
   ```

**Acceptance Criteria**
- [ ] Every Queue-2 removal has a corresponding event (settle/drop/backstop)
- [ ] `replay trace --tx-id bd441d74` shows all state transitions with timestamps
- [ ] Re-run replay ticks 250-260; bd441d74 shows explicit event at tick where it leaves Queue-2
- [ ] Invariant check passes: `check_queue2_continuity()` reports no violations

---

#### Issue #3: Queue-1 Amounts Displayed as $0.00

**Symptom**
```
Queue 1 (35 transactions, $0.00 total):  ❌
  • TX 5cc97e72 → REGIONAL_TRUST: $0.00 | P:6 | ⏰ Tick 280
  • TX 4361da2e → MOMENTUM_CAPITAL: $0.00 | P:6 | ⏰ Tick 280
  ...
```

**Root Cause**
- Display code is fetching Queue-1 items from a source that doesn't include amounts, OR
- Amount field is being zeroed out during serialization/deserialization

**Affected Files**
- `backend/src/ffi/orchestrator.rs` (`get_tick_agent_states()` or similar)
- `api/payment_simulator/cli/display/verbose_output.py` (queue rendering)
- `api/payment_simulator/cli/execution/state_provider.py` (StateProvider interface)

**Fix Strategy**

1. **Trace data flow**:
   - Add debug logging in `get_tick_agent_states()` to print raw queue data
   - Verify that Rust is returning full transaction objects with amounts
   - Check Python deserialization (FFI boundary)

2. **Ensure StateProvider returns amounts**:
   ```python
   # api/payment_simulator/cli/execution/state_provider.py

   class OrchestratorStateProvider(StateProvider):
       def get_agent_queue1(self, agent_id: str) -> List[Dict]:
           raw = self.orchestrator.get_agent_queue1(agent_id)  # FFI call
           # Verify 'amount' field is present and non-zero
           for tx in raw:
               assert 'amount' in tx, f"Missing amount in Queue-1 tx {tx.get('id')}"
               assert tx['amount'] > 0, f"Zero amount in Queue-1 tx {tx['id']}"
           return raw
   ```

3. **Fix display logic**:
   ```python
   # api/payment_simulator/cli/display/verbose_output.py

   def render_queue1(queue: List[Dict]):
       total = sum(tx['amount'] for tx in queue)
       console.print(f"Queue 1 ({len(queue)} transactions, ${total/100:.2f} total):")
       for tx in queue:
           console.print(f"  • TX {tx['id'][:8]}... → {tx['receiver']}: "
                        f"${tx['amount']/100:.2f} | P:{tx['priority']} | "
                        f"⏰ Tick {tx['deadline']}")
   ```

4. **Add smoke test**:
   ```python
   # api/tests/integration/test_replay_display.py

   def test_queue1_amounts_nonzero():
       """Queue-1 items must have positive amounts and sum must match header."""
       output = run_replay(from_tick=250, to_tick=260, capture_stdout=True)

       # Parse Queue-1 sections
       for agent_section in parse_queue1_sections(output):
           header_total = extract_total_from_header(agent_section)
           detail_lines = extract_detail_lines(agent_section)

           detail_amounts = [extract_amount(line) for line in detail_lines]
           assert all(amt > 0 for amt in detail_amounts), "Found $0.00 amounts"

           detail_sum = sum(detail_amounts)
           assert abs(detail_sum - header_total) < 0.01, \
               f"Sum mismatch: header={header_total}, detail={detail_sum}"
   ```

**Acceptance Criteria**
- [ ] All Queue-1 items show non-zero amounts (or explicit "amount_tbd" marker for split children)
- [ ] Sum of detail amounts matches "Queue 1 (N transactions, $T total)"
- [ ] Smoke test passes for all banks in ticks 250-260 replay

---

#### Issue #4: "Credit: 198% Used" Formatting Bug

**Symptom**
```
CORRESPONDENT_HUB:
  Credit Limit: $120,000.00
  Credit Used:  $117,679.26
  Summary:      Credit: 198% used  ❌ (should be ~98%)
```

**Root Cause**
- Likely formula: `percent = 100 + (used / limit) * 100` instead of `(used / limit) * 100`

**Affected Files**
- `api/payment_simulator/cli/display/verbose_output.py` (agent stats section)

**Fix Strategy**

1. **Find calculation**:
   ```python
   # Likely in display/verbose_output.py or display/agent_stats.py

   # BAD (current):
   credit_pct = 100 + (credit_used / credit_limit) * 100  ❌

   # GOOD:
   credit_pct = (credit_used / credit_limit) * 100  ✅
   ```

2. **Add display test**:
   ```python
   # api/tests/unit/test_display_formatting.py

   @pytest.mark.parametrize("used,limit,expected", [
       (0, 100_000, 0),        # No credit used
       (50_000, 100_000, 50),  # 50% used
       (100_000, 100_000, 100),# Fully used
       (117_679, 120_000, 98), # Real example from log
   ])
   def test_credit_usage_percent(used, limit, expected):
       pct = calculate_credit_usage_percent(used, limit)
       assert abs(pct - expected) < 1, f"Expected ~{expected}%, got {pct}%"
   ```

**Acceptance Criteria**
- [ ] Formula corrected
- [ ] Unit tests pass
- [ ] Replay shows "Credit: 98% used" for $117,679/$120,000

---

### ⚠️ P1: Medium-Severity Realism & Instrumentation Gaps

#### Issue #5: Collateral "Chattering"

**Symptom**
```
Tick 250: WITHDRAWN: $62,713.27 - LiquidityRestored
Tick 251: POSTED:    $64,944.24 - DeadlineEmergency
Tick 252: WITHDRAWN: $64,944.24 - LiquidityRestored
Tick 253: POSTED:    $82,524.99 - DeadlineEmergency
```

**Root Cause**
- No hysteresis or minimum dwell time
- Policy posts collateral as soon as liquidity drops below threshold
- Immediately withdraws when liquidity restored (even if margin is tiny)

**Affected Files**
- `backend/policies/*.json` (policy definitions)
- `backend/src/policies/mod.rs` (policy execution)
- `backend/src/models/agent.rs` (collateral state tracking)

**Fix Strategy**

1. **Add hysteresis parameters** to agent config:
   ```yaml
   agents:
     - id: REGIONAL_TRUST
       collateral_posting_threshold: 10000  # Post when liquidity < $100
       collateral_withdrawal_threshold: 50000  # Withdraw when liquidity > $500
       collateral_min_dwell_ticks: 5  # Keep posted for at least 5 ticks
   ```

2. **Track collateral post time** in agent state:
   ```rust
   // backend/src/models/agent.rs

   pub struct Agent {
       pub id: String,
       pub balance: i64,
       pub collateral_posted: i64,
       pub collateral_posted_at_tick: Option<i64>,  // NEW
       // ...
   }
   ```

3. **Update collateral logic**:
   ```rust
   // In policy execution:

   fn should_post_collateral(agent: &Agent, current_tick: i64) -> bool {
       let liquidity = agent.balance + agent.credit_limit - agent.collateral_posted;
       liquidity < agent.collateral_posting_threshold
   }

   fn should_withdraw_collateral(agent: &Agent, current_tick: i64) -> bool {
       let liquidity = agent.balance + agent.credit_limit - agent.collateral_posted;
       let ticks_posted = agent.collateral_posted_at_tick
           .map(|t| current_tick - t)
           .unwrap_or(0);

       liquidity > agent.collateral_withdrawal_threshold
           && ticks_posted >= agent.collateral_min_dwell_ticks
   }
   ```

4. **Add churn friction cost** (optional):
   ```rust
   // In cost accrual:

   if event.event_type == "collateral_posted" || event.event_type == "collateral_withdrawn" {
       let churn_cost = 5000; // $50 per collateral operation
       agent.costs.collateral_churn += churn_cost;
   }
   ```

**Acceptance Criteria**
- [ ] Collateral posts only when liquidity < posting threshold
- [ ] Collateral withdraws only when liquidity > withdrawal threshold AND min dwell time met
- [ ] Replay shows stable collateral (no oscillations within 5-tick windows)

---

#### Issue #6: Deadlines Beyond Episode End

**Symptom**
```
Tick 250 arrivals have deadlines at Tick 309-328
Episode ends at Tick 299 (Day 3 end)
```

**Root Cause**
- Arrival generator doesn't cap deadlines at `episode_end_tick`

**Affected Files**
- `backend/src/core/arrival.rs` (deadline generation)
- `api/payment_simulator/cli/display/verbose_output.py` (deadline rendering)

**Fix Strategy**

1. **Cap deadlines during generation**:
   ```rust
   // backend/src/core/arrival.rs

   let raw_deadline = arrival_tick + deadline_offset;
   let deadline = raw_deadline.min(episode_end_tick);
   ```

2. **Update display to show capped deadlines**:
   ```python
   # In verbose_output.py:

   def render_deadline(tx, episode_end_tick):
       if tx['deadline'] >= episode_end_tick:
           return f"⏰ EoD (Tick {episode_end_tick})"
       else:
           return f"⏰ Tick {tx['deadline']}"
   ```

**Acceptance Criteria**
- [ ] All generated deadlines ≤ `episode_end_tick`
- [ ] Display shows "⏰ EoD" for deadlines at episode end

---

#### Issue #7: Missing LSM Visibility

**Symptom**
- "total_lsm_releases: 0" for ticks 250-260
- No `lsm_bilateral_offset` or `lsm_cycle_settlement` events printed
- Hard to verify LSM engine behavior

**Affected Files**
- `backend/src/settlement/lsm.rs` (LSM execution)
- `backend/src/models/event.rs` (LSM events)
- `api/payment_simulator/cli/display/verbose_output.py` (LSM display)

**Fix Strategy**

1. **Add LSM attempt event** (even when no releases):
   ```rust
   // backend/src/models/event.rs

   pub enum Event {
       // ...
       LsmAttempt {
           tick: i64,
           queue2_size: usize,
           bilaterals_found: usize,
           cycles_found: usize,
           total_released: i64,
       },
   }
   ```

2. **Emit on every LSM run**:
   ```rust
   // backend/src/settlement/lsm.rs

   pub fn run_lsm(queue2: &mut Queue, config: &LsmConfig, tick: i64) -> Vec<Event> {
       let initial_size = queue2.len();

       let bilaterals = find_bilateral_offsets(queue2);
       let cycles = find_cycles(queue2, config.max_cycle_length);

       let total_released = apply_lsm_releases(queue2, bilaterals, cycles);

       // ✅ ALWAYS emit attempt event
       vec![Event::LsmAttempt {
           tick,
           queue2_size: initial_size,
           bilaterals_found: bilaterals.len(),
           cycles_found: cycles.len(),
           total_released,
       }]
   }
   ```

3. **Display in verbose output**:
   ```python
   # In verbose_output.py:

   lsm_attempts = [e for e in events if e['event_type'] == 'lsm_attempt']
   if lsm_attempts:
       for attempt in lsm_attempts:
           console.print(f"\n🔄 LSM Attempt:")
           console.print(f"   Queue-2 size: {attempt['queue2_size']}")
           console.print(f"   Bilaterals found: {attempt['bilaterals_found']}")
           console.print(f"   Cycles found: {attempt['cycles_found']}")
           console.print(f"   Total released: ${attempt['total_released']/100:.2f}")
   ```

**Acceptance Criteria**
- [ ] LSM attempt logged every tick when Queue-2 is non-empty
- [ ] Replay shows "LSM Attempt: 0 cycles, 0 releases" even when nothing found
- [ ] Summary includes `lsm_attempts` and `lsm_successes` (successes = attempts with releases > 0)

---

#### Issue #8: Public Signals Not Surfaced

**Symptom**
- Spec mentions "public signals" (throughput, Queue-2 pressure)
- No logs showing these values

**Affected Files**
- `backend/src/core/orchestrator.rs` (signal calculation)
- `backend/src/models/event.rs` (public signal event)
- `api/payment_simulator/cli/display/verbose_output.py` (signal display)

**Fix Strategy**

1. **Define public signal event**:
   ```rust
   pub enum Event {
       // ...
       PublicSignalBroadcast {
           tick: i64,
           throughput_rate: f64,        // settlements / arrivals over last N ticks
           queue2_pressure: String,     // "low", "medium", "high"
           avg_settlement_delay: f64,   // ticks
       },
   }
   ```

2. **Calculate and emit each tick**:
   ```rust
   // In orchestrator.rs tick():

   let throughput = calculate_throughput(last_10_ticks);
   let q2_pressure = classify_queue2_pressure(queue2.len(), thresholds);

   events.push(Event::PublicSignalBroadcast {
       tick: current_tick,
       throughput_rate: throughput,
       queue2_pressure,
       avg_settlement_delay: calculate_avg_delay(settlements),
   });
   ```

3. **Display in verbose output**:
   ```python
   signals = [e for e in events if e['event_type'] == 'public_signal_broadcast']
   if signals:
       s = signals[0]  # One per tick
       console.print(f"\n📡 Public Signals:")
       console.print(f"   Throughput: {s['throughput_rate']:.1%}")
       console.print(f"   Queue-2 Pressure: {s['queue2_pressure']}")
       console.print(f"   Avg Delay: {s['avg_settlement_delay']:.1f} ticks")
   ```

**Acceptance Criteria**
- [ ] Public signal event emitted every tick
- [ ] Display shows throughput, pressure, avg delay
- [ ] Can audit how policies respond to signals

---

### 🧹 P2: Output and Analytics Inconsistencies

#### Issue #9: Replay Summary Contradicts In-Tick State

**Symptom**
```
Tick 260 in-tick: Queue-1 has 61 items (CORRESPONDENT_HUB)
End-of-replay JSON: "queue1_size": 0
```

**Root Cause**
- Summary is computed from end-of-episode state, not last-replayed-tick state

**Affected Files**
- `api/payment_simulator/cli/commands/replay.py` (summary generation)

**Fix Strategy**

1. **Compute summary from last replayed tick**:
   ```python
   # In replay.py:

   def generate_replay_summary(db, sim_id, from_tick, to_tick):
       last_tick = to_tick  # Use last replayed tick, not episode end

       agent_states = get_tick_agent_states(db, sim_id, last_tick)

       return {
           "simulation": {
               "simulation_id": sim_id,
               "tick_range": [from_tick, to_tick],  # NEW
               "last_tick_replayed": last_tick,     # NEW
           },
           "agents": [
               {
                   "id": a['id'],
                   "final_balance": a['balance'],
                   "queue1_size": len(a['queue1']),  # From last_tick, not episode end
               }
               for a in agent_states
           ],
       }
   ```

**Acceptance Criteria**
- [ ] Summary reflects state at `to_tick`, not episode end
- [ ] JSON includes `"tick_range": [250, 260]` and `"last_tick_replayed": 260`

---

#### Issue #10: Totals Sanity Checks Missing

**Symptom**
- No automated invariant checks in replay output

**Affected Files**
- `api/payment_simulator/cli/display/verbose_output.py` (new section)
- `api/payment_simulator/cli/display/invariant_checks.py` (new module)

**Fix Strategy**

1. **Create invariant check module**:
   ```python
   # api/payment_simulator/cli/display/invariant_checks.py

   class InvariantViolation(Exception):
       pass

   def check_balance_conservation(agents, expected_total=46_000_000):
       """Sum of balances must equal total system liquidity."""
       actual = sum(a['balance'] for a in agents)
       if actual != expected_total:
           raise InvariantViolation(
               f"Balance sum mismatch: expected={expected_total}, actual={actual}"
           )

   def check_queue_accounting(prev_state, curr_state, events):
       """prev_Q1 + arrivals - submissions = curr_Q1"""
       for agent_id in prev_state.keys():
           prev_q1 = len(prev_state[agent_id]['queue1'])
           curr_q1 = len(curr_state[agent_id]['queue1'])

           arrivals = count_arrivals_for_agent(events, agent_id)
           submissions = count_submissions_for_agent(events, agent_id)

           expected_q1 = prev_q1 + arrivals - submissions
           if curr_q1 != expected_q1:
               raise InvariantViolation(
                   f"{agent_id}: Queue-1 mismatch: expected={expected_q1}, actual={curr_q1}"
               )
   ```

2. **Run checks in verbose output**:
   ```python
   # In display_tick_verbose_output():

   # After displaying all sections, check invariants:
   try:
       check_balance_conservation(agent_states)
       check_queue_accounting(prev_tick_state, curr_tick_state, events)
       console.print("\n✅ Invariants: All checks passed")
   except InvariantViolation as e:
       console.print(f"\n❌ Invariant Violation: {e}", style="bold red")
       raise
   ```

**Acceptance Criteria**
- [ ] Balance sum checked every tick
- [ ] Queue accounting checked every tick
- [ ] Replay fails loudly if invariant violated

---

## Implementation Phases

### Phase 1: Critical Fixes (Week 1)
**Goal**: Restore correctness and auditability

- [ ] **Day 1-2**: Fix cost-rate mis-scaling (#1)
  - Define `bps_to_rate()` helper
  - Update all cost accrual sites
  - Add unit tests
  - Verify replay output

- [ ] **Day 3-4**: Fix Queue-2 teleportation (#2)
  - Define new event types
  - Emit events in RTGS logic
  - Add display section
  - Add invariant check

- [ ] **Day 5**: Fix Queue-1 amounts (#3) and credit percentage (#4)
  - Trace data flow for Queue-1 amounts
  - Fix display logic
  - Add smoke tests

### Phase 2: Realism Improvements (Week 2)
**Goal**: Improve operational realism

- [ ] **Day 1-2**: Add collateral hysteresis (#5)
  - Add config parameters
  - Update collateral logic
  - Test with crisis scenario

- [ ] **Day 3**: Cap deadlines at episode end (#6)
  - Update arrival generator
  - Update display

- [ ] **Day 4-5**: Add LSM visibility (#7) and public signals (#8)
  - Add LSM attempt events
  - Add public signal events
  - Update display

### Phase 3: Instrumentation & Polish (Week 3)
**Goal**: Complete observability

- [ ] **Day 1**: Fix replay summary (#9)
  - Update summary generation
  - Add tick range to JSON

- [ ] **Day 2**: Add invariant checks (#10)
  - Create invariant check module
  - Integrate into display

- [ ] **Day 3**: Add transaction trace tool
  - Implement `replay trace --tx-id`
  - Test with bd441d74

- [ ] **Day 4-5**: Integration testing
  - Run full crisis scenario
  - Verify all fixes
  - Update documentation

---

## Testing Strategy

### Unit Tests
- Cost calculation helpers (1 bps, 0.8 bps, edge cases)
- Display formatting (credit %, amounts, deadlines)
- Collateral hysteresis logic

### Integration Tests
- Queue-2 continuity (all removals have events)
- Queue-1 amount consistency (sum matches header)
- Invariant checks (balance conservation, queue accounting)
- Replay identity (run vs replay still identical after fixes)

### Regression Tests
- Re-run `three_day_realistic_crisis.yaml` full episode
- Verify LSM demonstrations still occur
- Verify settlement rates in expected ranges (92-96%)

---

## Success Criteria

### Correctness ✅
- [ ] All cost accruals use correct bps → rate conversion
- [ ] Every Queue-2 removal has a logged event
- [ ] All Queue-1 amounts are non-zero and sum correctly
- [ ] Credit usage percentages are accurate

### Auditability ✅
- [ ] Can trace any transaction through all state transitions
- [ ] Invariant checks pass on every tick
- [ ] LSM attempts logged even when no releases

### Realism ✅
- [ ] Collateral posts/withdraws follow hysteresis rules
- [ ] Deadlines never exceed episode end
- [ ] Public signals visible and policy-usable

### User Experience ✅
- [ ] Replay output is clear and unambiguous
- [ ] Summary JSON reflects actual replayed ticks
- [ ] Documentation updated with new event types

---

## Rollout Plan

1. **Branch**: `fix/replay-crisis-audit-fixes`
2. **PR Strategy**:
   - **PR #1** (Phase 1): Critical correctness fixes (#1-4)
   - **PR #2** (Phase 2): Realism improvements (#5-8)
   - **PR #3** (Phase 3): Instrumentation & polish (#9-10)
3. **Deployment**: Merge to `main` after all integration tests pass

---

## Documentation Updates

- [ ] Update `CLAUDE.md` with new event types
- [ ] Update `docs/replay-unified-architecture-implementation.md` with invariant checks
- [ ] Add `docs/cost-calculations.md` explaining bps → rate conversions
- [ ] Update `docs/game-design.md` with collateral hysteresis rules

---

## Open Questions

1. **Collateral churn friction**: Should we add a small cost per post/withdraw operation? (Recommendation: Yes, $50-100)
2. **EoD backstop mechanics**: Current spec mentions "central bank liquidity" but doesn't detail the mechanism. Should we implement a specific backstop rule? (Recommendation: Yes, in separate ticket)
3. **LSM search frequency**: Should LSM run every tick or only when Queue-2 changes? (Current: every tick; seems fine)

---

## References

- Original audit: User message (2025-11-11)
- RTGS-First spec: `CLAUDE.md` sections on cost model, two-queue RTGS, LSM
- Replay identity architecture: `docs/replay-unified-architecture-implementation.md`
- StateProvider pattern: `api/payment_simulator/cli/execution/state_provider.py`

---

**Estimated Effort**: 3 weeks (1 engineer)
**Risk**: Low (surgical fixes with comprehensive tests)
**Impact**: High (restores correctness, enables policy learning, improves UX)
