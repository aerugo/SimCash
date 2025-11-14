# TDD Plan: Fix Collateral Timer Bypass (Invariant I2)

**Issue**: Auto-withdraw timer bypasses headroom protection, allowing collateral withdrawal while overdrawn.

**Date**: 2025-11-14
**Status**: Planning
**Priority**: HIGH - Invariant violation, unrealistic simulation behavior

---

## Problem Summary

### Current Behavior (Bug)

At **tick 288** in `sim-1b96f561`:
```
💰 Collateral Activity (1):
   CORRESPONDENT_HUB:
   • AUTO-WITHDRAWN (timer): $5,298.12 - Originally posted at tick 273

CORRESPONDENT_HUB
  Balance:            $-338,120.13 (overdraft)
  Credit Used:        $338,120.13
  Posted Collateral:  $393,458.97
```

The timer **allowed withdrawal** even though:
- Agent is deeply overdrawn (`credit_used` = $338k)
- Withdrawal reduces available headroom
- This violates real-world RTGS/CLM practice

### Root Cause

**Two code paths for collateral withdrawal:**

1. **Manual/Policy Path** (✅ Enforces Invariant I2)
   - Location: `backend/src/ffi/orchestrator.rs:554-638`
   - Checks: `agent.max_withdrawable_collateral(SAFETY_BUFFER)`
   - Rejects if: `requested > max_withdrawable`
   - Emits: `CollateralWithdraw` event

2. **Timer Path** (❌ Bypasses Invariant I2)
   - Location: `backend/src/orchestrator/engine.rs:2626-2642`
   - **Directly** modifies: `agent.set_posted_collateral(new_collateral)`
   - **No check** for headroom
   - Emits: `CollateralTimerWithdrawn` event

```rust
// CURRENT BUG (lines 2626-2642):
for (amount, original_reason, posted_at_tick) in timers {
    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();
    let current_collateral = agent_mut.posted_collateral();
    let withdrawal_amount = amount.min(current_collateral); // ❌ Only caps at posted amount
    let new_collateral = current_collateral - withdrawal_amount;
    agent_mut.set_posted_collateral(new_collateral); // ❌ BYPASS!

    self.log_event(Event::CollateralTimerWithdrawn { ... });
}
```

### Invariant I2: Withdrawal Headroom Protection

**Specification** (from `docs/collateral-headroom-invariants.md`):

After withdrawal:
```
floor((posted_collateral - amount) × (1 - haircut)) + unsecured_cap ≥ credit_used
```

**Meaning**: The allowed overdraft limit after withdrawal must **still cover** the current overdraft usage.

**Implementation** (from `backend/src/models/agent.rs:464-486`):

```rust
pub fn max_withdrawable_collateral(&self, buffer: i64) -> i64 {
    let one_minus_haircut = (1.0 - self.collateral_haircut).max(0.0);
    if one_minus_haircut <= 0.0 {
        return self.posted_collateral;
    }

    let credit_used = self.credit_used();
    let target_limit = credit_used + buffer;
    let unsecured_contribution = self.unsecured_cap.min(target_limit);

    let required_from_collateral = target_limit.saturating_sub(unsecured_contribution);
    let required_collateral_f = required_from_collateral as f64 / one_minus_haircut;
    let required_collateral = required_collateral_f.ceil() as i64;

    // Max withdrawable is the excess
    (self.posted_collateral - required_collateral).max(0)
}
```

---

## TDD Plan: Strict Red-Green-Refactor

### Phase 1: Write Failing Tests (Red)

**Objective**: Capture the bug in tests **before** fixing.

#### Test 1.1: Timer Bypasses Headroom Guard (Integration Test)

**File**: `backend/tests/test_collateral_timer_invariants.rs` (new file)

**Test Name**: `test_timer_withdrawal_respects_headroom_when_overdrawn`

**Setup**:
```rust
let mut agent = Agent::new("BANK_A", -60_000_00, 0); // $60k overdraft
agent.set_posted_collateral(100_000_00); // $100k posted
agent.set_collateral_haircut(0.10); // 10% haircut
agent.set_unsecured_cap(0);

// credit_used = 60k
// allowed_limit = floor(100k × 0.9) = 90k
// headroom = 90k - 60k = 30k

// Max withdrawable:
// Need: C × 0.9 ≥ 60k → C ≥ 66,667
// Can withdraw: 100k - 66,667 = 33,333

let max_safe = agent.max_withdrawable_collateral(0);
assert_eq!(max_safe, 33_333_00); // ~$33k

// Schedule timer to withdraw $80k (UNSAFE!)
agent.schedule_collateral_withdrawal_with_posted_tick(
    10, // withdrawal_tick
    80_000_00, // amount (exceeds max_safe!)
    "TemporaryBoost".to_string(),
    5, // posted_at_tick
);
```

**Expected Behavior (After Fix)**:
```rust
// Process timer at tick 10
process_collateral_timers(&mut agent, 10);

// Should withdraw ONLY max_safe amount, not the full 80k
assert_eq!(agent.posted_collateral(), 66_667_00); // 100k - 33,333
// OR block entirely with event:
// Event::CollateralTimerBlocked { reason: "InsufficientHeadroom" }
```

**Current Behavior (Bug)**:
```rust
// Currently withdraws the FULL 80k (capped by posted amount)
// This leaves: 100k - 80k = 20k posted
// New limit: floor(20k × 0.9) = 18k
// But credit_used = 60k → VIOLATES I2! ❌
```

**Status**: EXPECTED TO FAIL ❌ (captures the bug)

---

#### Test 1.2: Timer Clamps to Safe Amount

**File**: `backend/tests/test_collateral_timer_invariants.rs`

**Test Name**: `test_timer_clamps_withdrawal_to_safe_amount`

**Setup**:
```rust
let mut agent = Agent::new("BANK_A", -30_000_00, 0);
agent.set_posted_collateral(100_000_00);
agent.set_collateral_haircut(0.10);

// Max safe = 100k - ceil(30k / 0.9) = 100k - 33,334 = 66,666
agent.schedule_collateral_withdrawal_with_posted_tick(
    10,
    80_000_00, // Request more than safe
    "TemporaryBoost".to_string(),
    5,
);
```

**Expected** (after fix):
```rust
process_collateral_timers(&mut agent, 10);
assert_eq!(agent.posted_collateral(), 33_334_00); // Withdrew only 66,666
```

**Status**: EXPECTED TO FAIL ❌

---

#### Test 1.3: Timer Blocked When No Headroom

**File**: `backend/tests/test_collateral_timer_invariants.rs`

**Test Name**: `test_timer_blocked_when_no_headroom_available`

**Setup**:
```rust
let mut agent = Agent::new("BANK_A", -90_000_00, 0); // Deep overdraft
agent.set_posted_collateral(100_000_00);
agent.set_collateral_haircut(0.10);

// Max safe = 100k - ceil(90k / 0.9) = 100k - 100k = 0 (NONE!)
let max_safe = agent.max_withdrawable_collateral(0);
assert_eq!(max_safe, 0);

agent.schedule_collateral_withdrawal_with_posted_tick(10, 10_000_00, "Test".to_string(), 5);
```

**Expected** (after fix):
```rust
process_collateral_timers(&mut agent, 10);
// NO withdrawal occurred
assert_eq!(agent.posted_collateral(), 100_000_00); // Unchanged
// Event logged:
// CollateralTimerBlocked { reason: "InsufficientHeadroom", requested: 10k, max_safe: 0 }
```

**Status**: EXPECTED TO FAIL ❌

---

#### Test 1.4: Timer Respects Minimum Holding Period

**File**: `backend/tests/test_collateral_timer_invariants.rs`

**Test Name**: `test_timer_respects_minimum_holding_period`

**Setup**:
```rust
let mut agent = Agent::new("BANK_A", 100_000_00, 0); // Positive balance
agent.set_posted_collateral(50_000_00);
agent.set_collateral_posted_at_tick(5); // Posted at tick 5

// Schedule for tick 8 (only 3 ticks later, MIN=5)
agent.schedule_collateral_withdrawal_with_posted_tick(8, 10_000_00, "Test".to_string(), 5);
```

**Expected** (after fix):
```rust
const MIN_HOLDING_TICKS: usize = 5;

process_collateral_timers(&mut agent, 8, MIN_HOLDING_TICKS);
// Blocked because 8 < 5 + 5 = 10
assert_eq!(agent.posted_collateral(), 50_000_00); // Unchanged

// Try again at tick 10
process_collateral_timers(&mut agent, 10, MIN_HOLDING_TICKS);
// Now allowed (10 ≥ 5 + 5)
assert_eq!(agent.posted_collateral(), 40_000_00); // Withdrawn
```

**Status**: EXPECTED TO FAIL ❌ (current code doesn't check min holding)

---

#### Test 1.5: Simulation Test with `advanced_policy_crisis.yaml`

**File**: `api/tests/integration/test_collateral_timer_replay.py`

**Test Name**: `test_tick_288_no_unsafe_timer_withdrawal`

**Purpose**: Use the EXACT scenario from the user's log.

**Setup**:
```python
def test_tick_288_no_unsafe_timer_withdrawal():
    """
    Regression test for timer bypass at tick 288 in sim-1b96f561.

    BEFORE FIX: Timer withdraws $5,298.12 despite deep overdraft.
    AFTER FIX: Timer withdrawal should be blocked or clamped.
    """
    config_path = Path(__file__).parent.parent.parent / "examples" / "configs" / "advanced_policy_crisis.yaml"
    config = yaml.safe_load(config_path.read_text())

    # Use same seed as original sim
    config["rng_seed"] = ... # Extract from sim-1b96f561 if known

    orch = Orchestrator.new(config)

    # Run up to tick 288
    for _ in range(288):
        orch.tick()

    # Get CORRESPONDENT_HUB state before timer processing
    agent_metrics = orch.get_agent_metrics("CORRESPONDENT_HUB")
    credit_used = agent_metrics["credit_used"]
    posted_collateral = agent_metrics["posted_collateral"]
    headroom = agent_metrics["headroom"]

    # Verify agent is deeply overdrawn (as in original log)
    assert credit_used > 300_000_00, "Agent should be overdrawn"
    assert headroom < credit_used, "Headroom should be limited"

    # Get max safe withdrawal
    # TODO: Add FFI method `get_max_withdrawable_collateral(agent_id, buffer)`
    # For now, compute manually:
    haircut = agent_metrics["collateral_haircut"]
    unsecured = agent_metrics["unsecured_cap"]

    one_minus_haircut = 1.0 - haircut
    required_collateral = math.ceil((credit_used - unsecured) / one_minus_haircut)
    max_safe = max(0, posted_collateral - required_collateral)

    # Check events at tick 288
    events = orch.get_tick_events(288)
    timer_withdrawals = [e for e in events if e["event_type"] == "CollateralTimerWithdrawn"]

    if len(timer_withdrawals) > 0:
        # If withdrawal occurred, it MUST be ≤ max_safe
        for event in timer_withdrawals:
            assert event["amount"] <= max_safe, \
                f"Timer withdrew {event['amount']} but max safe is {max_safe}"

    # ALTERNATIVE: Assert NO withdrawal occurred
    # assert len(timer_withdrawals) == 0, "Timer should be blocked when no headroom"
```

**Status**: EXPECTED TO FAIL ❌ (before fix)

---

### Phase 2: Implement Unified Guard (Green)

**Objective**: Make tests pass with **minimal, correct implementation**.

#### Step 2.1: Add Helper Method to Agent

**File**: `backend/src/models/agent.rs`

**Method**: `try_withdraw_collateral_guarded`

```rust
/// Attempt to withdraw collateral with full guard checks
///
/// Enforces:
/// 1. Minimum holding period (if posted_at_tick is set)
/// 2. Invariant I2: Headroom protection
/// 3. Non-negative collateral
///
/// # Arguments
/// * `requested` - Requested withdrawal amount (cents)
/// * `current_tick` - Current simulation tick
/// * `min_holding_ticks` - Minimum ticks to hold (default 5)
/// * `safety_buffer` - Additional headroom buffer (cents, default 100)
///
/// # Returns
/// * `Ok(actual)` - Actual amount withdrawn (may be less than requested if clamped)
/// * `Err(WithdrawError)` - Withdrawal blocked with reason
///
/// # Invariant Guarantee
/// After successful withdrawal:
/// ```text
/// floor((posted_collateral - actual) × (1 - haircut)) + unsecured_cap ≥ credit_used + buffer
/// ```
pub fn try_withdraw_collateral_guarded(
    &mut self,
    requested: i64,
    current_tick: usize,
    min_holding_ticks: usize,
    safety_buffer: i64,
) -> Result<i64, WithdrawError> {
    // Validation 1: Positive amount
    if requested <= 0 {
        return Err(WithdrawError::NonPositive);
    }

    // Validation 2: Minimum holding period
    if !self.can_withdraw_collateral(current_tick, min_holding_ticks) {
        let posted_at = self.collateral_posted_at_tick.unwrap_or(0);
        let ticks_held = current_tick.saturating_sub(posted_at);
        let ticks_remaining = min_holding_ticks.saturating_sub(ticks_held);
        return Err(WithdrawError::MinHoldingPeriodNotMet {
            ticks_remaining,
            posted_at_tick: posted_at,
        });
    }

    // Validation 3: Headroom protection (Invariant I2)
    let max_safe = self.max_withdrawable_collateral(safety_buffer);
    if max_safe <= 0 {
        return Err(WithdrawError::NoHeadroom {
            credit_used: self.credit_used(),
            allowed_limit: self.allowed_overdraft_limit(),
            headroom: self.headroom(),
        });
    }

    // Clamp to safe amount
    let actual = requested.min(max_safe).min(self.posted_collateral);

    // Apply withdrawal
    let new_total = self.posted_collateral - actual;
    self.set_posted_collateral(new_total);

    // Clear posted_at_tick if all collateral withdrawn
    if new_total == 0 {
        self.collateral_posted_at_tick = None;
    }

    Ok(actual)
}
```

**Error Type** (add to `backend/src/models/agent.rs`):

```rust
#[derive(Debug, Error, PartialEq)]
pub enum WithdrawError {
    #[error("Withdrawal amount must be positive")]
    NonPositive,

    #[error("Minimum holding period not met: {ticks_remaining} tick(s) remaining (posted at tick {posted_at_tick})")]
    MinHoldingPeriodNotMet {
        ticks_remaining: usize,
        posted_at_tick: usize,
    },

    #[error("No headroom available for withdrawal: credit_used={credit_used}, allowed_limit={allowed_limit}, headroom={headroom}")]
    NoHeadroom {
        credit_used: i64,
        allowed_limit: i64,
        headroom: i64,
    },
}
```

---

#### Step 2.2: Update Timer Processing to Use Guard

**File**: `backend/src/orchestrator/engine.rs` (lines 2626-2642)

**Replace**:
```rust
// OLD CODE (lines 2626-2642):
for (amount, original_reason, posted_at_tick) in timers {
    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();
    let current_collateral = agent_mut.posted_collateral();
    let withdrawal_amount = amount.min(current_collateral);
    let new_collateral = current_collateral - withdrawal_amount;
    agent_mut.set_posted_collateral(new_collateral);

    self.log_event(Event::CollateralTimerWithdrawn {
        tick: current_tick,
        agent_id: agent_id.clone(),
        amount: withdrawal_amount,
        original_reason: original_reason.clone(),
        posted_at_tick,
    });
}
```

**With**:
```rust
// NEW CODE:
const MIN_HOLDING_TICKS: usize = 5; // Same as FFI withdrawal
const SAFETY_BUFFER: i64 = 100; // Small buffer to avoid edge cases

for (requested_amount, original_reason, posted_at_tick) in timers {
    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();

    match agent_mut.try_withdraw_collateral_guarded(
        requested_amount,
        current_tick,
        MIN_HOLDING_TICKS,
        SAFETY_BUFFER,
    ) {
        Ok(actual_withdrawn) if actual_withdrawn > 0 => {
            // Withdrawal succeeded (full or partial)
            self.log_event(Event::CollateralTimerWithdrawn {
                tick: current_tick,
                agent_id: agent_id.clone(),
                amount: actual_withdrawn,
                original_reason: original_reason.clone(),
                posted_at_tick,
                new_total: agent_mut.posted_collateral(), // ADD THIS FIELD
            });

            // If partial, reschedule remainder (optional behavior)
            let remainder = requested_amount - actual_withdrawn;
            if remainder > 0 {
                // Option A: Reschedule for next tick
                agent_mut.schedule_collateral_withdrawal_with_posted_tick(
                    current_tick + 1,
                    remainder,
                    original_reason.clone(),
                    posted_at_tick,
                );

                // Option B: Log and drop remainder
                // (Current design: drop, document as "best-effort")
            }
        }
        Ok(0) => {
            // Zero withdrawal (max_safe = 0, all collateral needed)
            self.log_event(Event::CollateralTimerBlocked {
                tick: current_tick,
                agent_id: agent_id.clone(),
                requested_amount,
                reason: "NoHeadroom".to_string(),
                original_reason: original_reason.clone(),
                posted_at_tick,
            });
        }
        Err(err) => {
            // Blocked by guard (min holding period, etc.)
            self.log_event(Event::CollateralTimerBlocked {
                tick: current_tick,
                agent_id: agent_id.clone(),
                requested_amount,
                reason: err.to_string(),
                original_reason: original_reason.clone(),
                posted_at_tick,
            });
        }
    }
}
```

---

#### Step 2.3: Add New Event Variant

**File**: `backend/src/models/event.rs`

**Add**:
```rust
/// Collateral timer withdrawal was blocked (Phase 3.4+)
///
/// Emitted when automatic withdrawal timer triggers but guard prevents withdrawal.
/// Reasons: NoHeadroom, MinHoldingPeriodNotMet, etc.
CollateralTimerBlocked {
    tick: usize,
    agent_id: String,
    requested_amount: i64,
    reason: String, // "NoHeadroom", "MinHoldingPeriodNotMet", etc.
    original_reason: String, // Reason from when collateral was posted
    posted_at_tick: usize,
},
```

**Update**: `CollateralTimerWithdrawn` to include `new_total`:
```rust
CollateralTimerWithdrawn {
    tick: usize,
    agent_id: String,
    amount: i64,
    original_reason: String,
    posted_at_tick: usize,
    new_total: i64, // ADD: Posted collateral after withdrawal
},
```

---

#### Step 2.4: Update FFI to Use Shared Helper

**File**: `backend/src/ffi/orchestrator.rs` (lines 554-638)

**Replace** validation logic with:
```rust
fn withdraw_collateral(&mut self, py: Python, agent_id: &str, amount: i64) -> PyResult<Py<PyDict>> {
    const MIN_HOLDING_TICKS: usize = 5;
    const SAFETY_BUFFER: i64 = 100;

    let dict = PyDict::new(py);

    let current_tick = self.inner.current_tick();
    let state = self.inner.state_mut();

    let result = match state.get_agent_mut(agent_id) {
        Some(agent) => {
            agent.try_withdraw_collateral_guarded(
                amount,
                current_tick,
                MIN_HOLDING_TICKS,
                SAFETY_BUFFER,
            )
        }
        None => {
            dict.set_item("success", false)?;
            dict.set_item("message", format!("Agent '{}' not found", agent_id))?;
            return Ok(dict.into());
        }
    };

    match result {
        Ok(actual) => {
            let new_total = state.get_agent(agent_id).unwrap().posted_collateral();

            self.inner.log_event(Event::CollateralWithdraw {
                tick: current_tick,
                agent_id: agent_id.to_string(),
                amount: actual,
                reason: "ManualWithdraw".to_string(),
                new_total,
            });

            dict.set_item("success", true)?;
            dict.set_item("message", format!("Withdrew {} cents collateral", actual))?;
            Ok(dict.into())
        }
        Err(err) => {
            dict.set_item("success", false)?;
            dict.set_item("message", err.to_string())?;
            Ok(dict.into())
        }
    }
}
```

---

#### Step 2.5: Update Event Serialization for FFI

**File**: `backend/src/ffi/orchestrator.rs` (in `event_to_py_dict`)

**Add**:
```rust
Event::CollateralTimerWithdrawn { tick, agent_id, amount, original_reason, posted_at_tick, new_total } => {
    dict.set_item("tick", tick)?;
    dict.set_item("event_type", "CollateralTimerWithdrawn")?;
    dict.set_item("agent_id", agent_id)?;
    dict.set_item("amount", amount)?;
    dict.set_item("original_reason", original_reason)?;
    dict.set_item("posted_at_tick", posted_at_tick)?;
    dict.set_item("new_total", new_total)?; // NEW
}

Event::CollateralTimerBlocked { tick, agent_id, requested_amount, reason, original_reason, posted_at_tick } => {
    dict.set_item("tick", tick)?;
    dict.set_item("event_type", "CollateralTimerBlocked")?;
    dict.set_item("agent_id", agent_id)?;
    dict.set_item("requested_amount", requested_amount)?;
    dict.set_item("reason", reason)?;
    dict.set_item("original_reason", original_reason)?;
    dict.set_item("posted_at_tick", posted_at_tick)?;
}
```

---

### Phase 3: Verify Tests Pass (Green)

**Objective**: All tests must pass.

#### Checklist:
- [ ] `cargo test --no-default-features test_timer_withdrawal_respects_headroom_when_overdrawn`
- [ ] `cargo test --no-default-features test_timer_clamps_withdrawal_to_safe_amount`
- [ ] `cargo test --no-default-features test_timer_blocked_when_no_headroom_available`
- [ ] `cargo test --no-default-features test_timer_respects_minimum_holding_period`
- [ ] `pytest api/tests/integration/test_collateral_timer_replay.py::test_tick_288_no_unsafe_timer_withdrawal`

**Success Criteria**: All tests GREEN ✅

---

### Phase 4: Replay Validation (Gold Standard)

**Objective**: Verify behavior changed correctly in real simulation.

#### Step 4.1: Baseline (Before Fix)

```bash
cd api
uv run payment-sim replay --simulation-id sim-1b96f561 --verbose --from-tick=288 --to-tick=288 > /tmp/before_fix.txt
```

**Expected Output** (before fix):
```
💰 Collateral Activity (1):
   CORRESPONDENT_HUB:
   • AUTO-WITHDRAWN (timer): $5,298.12 - Originally posted at tick 273 (UrgentLiquidityNeed)
```

#### Step 4.2: Apply Fix and Rebuild

```bash
cd api
uv sync --extra dev --reinstall-package payment-simulator
```

#### Step 4.3: Compare (After Fix)

**Option A**: Re-run with same seed (if deterministic)
```bash
uv run payment-sim run --config ../examples/configs/advanced_policy_crisis.yaml --persist --verbose > /tmp/after_fix_run.txt
uv run payment-sim replay --simulation-id <new_sim_id> --verbose --from-tick=288 --to-tick=288 > /tmp/after_fix_replay.txt
```

**Expected Output** (after fix):
```
💰 Collateral Activity (1):
   CORRESPONDENT_HUB:
   ⚠️ AUTO-WITHDRAW BLOCKED (timer): $5,298.12 - NoHeadroom (credit_used=$338,120, max_safe=$0)
      Originally posted at tick 273 (UrgentLiquidityNeed)
```

**OR**:
```
💰 Collateral Activity (1):
   CORRESPONDENT_HUB:
   • AUTO-WITHDRAWN (timer): $0.00 - CLAMPED from requested $5,298.12 (max safe: $0)
      Originally posted at tick 273 (UrgentLiquidityNeed)
```

#### Step 4.4: Validation Criteria

✅ **Pass if**:
- Withdrawn amount ≤ `max_withdrawable_collateral(100)`
- Invariant I2 holds: `allowed_limit ≥ credit_used` after withdrawal
- Headroom remains ≥ safety buffer (100 cents)

❌ **Fail if**:
- Withdrawn amount > `max_safe`
- Headroom goes negative
- Credit used > allowed limit

---

### Phase 5: Refactor (Optional)

**Objective**: Improve code quality without changing behavior.

#### Refactor 5.1: Extract Constants

**File**: `backend/src/models/agent.rs`

```rust
/// Minimum ticks collateral must be held before withdrawal (T2/CLM standard)
pub const DEFAULT_MIN_HOLDING_TICKS: usize = 5;

/// Safety buffer for collateral calculations (cents)
/// Prevents edge cases where floor/ceil rounding causes violations
pub const DEFAULT_SAFETY_BUFFER_CENTS: i64 = 100;
```

#### Refactor 5.2: Add FFI Method for Max Withdrawable

**File**: `backend/src/ffi/orchestrator.rs`

```rust
/// Get maximum withdrawable collateral for agent
///
/// Returns the safe amount that can be withdrawn while maintaining headroom.
///
/// # Arguments
/// * `agent_id` - Agent identifier
/// * `buffer` - Safety buffer (cents, default 100)
///
/// # Returns
/// Max withdrawable amount (cents), or None if agent not found
fn get_max_withdrawable_collateral(&self, agent_id: &str, buffer: Option<i64>) -> Option<i64> {
    let buffer = buffer.unwrap_or(DEFAULT_SAFETY_BUFFER_CENTS);
    self.inner.state().get_agent(agent_id).map(|a| a.max_withdrawable_collateral(buffer))
}
```

**Use in Python tests**:
```python
max_safe = orch.get_max_withdrawable_collateral("BANK_A", buffer=100)
```

#### Refactor 5.3: Update Display Code

**File**: `api/payment_simulator/cli/display/verbose_output.py`

```python
def log_collateral_timer_blocked_event(event: Dict):
    """Display CollateralTimerBlocked in verbose output."""
    console.print(f"[yellow]⚠️  AUTO-WITHDRAW BLOCKED (timer):[/yellow]")
    console.print(f"   Agent: {event['agent_id']}")
    console.print(f"   Requested: ${event['requested_amount']/100:.2f}")
    console.print(f"   Reason: {event['reason']}")
    console.print(f"   Originally posted: Tick {event['posted_at_tick']} ({event['original_reason']})")
```

---

## Testing Matrix

| Test | Type | File | Purpose | Status |
|------|------|------|---------|--------|
| 1.1 | Unit | `test_collateral_timer_invariants.rs` | Timer respects headroom when overdrawn | ❌ Red |
| 1.2 | Unit | `test_collateral_timer_invariants.rs` | Timer clamps to safe amount | ❌ Red |
| 1.3 | Unit | `test_collateral_timer_invariants.rs` | Timer blocked when no headroom | ❌ Red |
| 1.4 | Unit | `test_collateral_timer_invariants.rs` | Timer respects min holding period | ❌ Red |
| 1.5 | Integration | `test_collateral_timer_replay.py` | Tick 288 regression test | ❌ Red |
| 2.1 | Unit | `test_agent_collateral_math.rs` | `try_withdraw_collateral_guarded` works | ⏳ Pending |
| 3.1 | Replay | Manual | Tick 288 output changed correctly | ⏳ Pending |

---

## Design Decisions

### Decision 1: Clamp vs. Block

**Options**:
1. **Clamp**: Withdraw up to `max_safe`, reschedule remainder
2. **Block**: Reject entire withdrawal if any part unsafe

**Choice**: **Clamp** (partial withdrawal allowed)

**Rationale**:
- More realistic: Real CLM allows partial releases
- Avoids "all or nothing" logic
- Timer intent: "return excess when safe", not "return exact amount"
- Logged as separate event for transparency

### Decision 2: Minimum Holding Period

**Question**: Should timer check `posted_at_tick` for min holding?

**Answer**: **YES**

**Rationale**:
- Same guard as manual withdrawal (consistency)
- Prevents oscillation (post → immediate timer withdraw)
- Real RTGS practice: Collateral pledges have settlement periods

### Decision 3: Safety Buffer

**Question**: What buffer value?

**Answer**: **100 cents** ($1.00)

**Rationale**:
- Small enough to not block legitimate withdrawals
- Large enough to handle floor/ceil rounding edge cases
- Matches existing FFI `SAFETY_BUFFER`

### Decision 4: Event Telemetry

**Required Fields** for `CollateralTimerWithdrawn`:
- `tick` - When withdrawal occurred
- `agent_id` - Who withdrew
- `amount` - Actual withdrawn (may be < requested)
- `original_reason` - Why collateral was posted
- `posted_at_tick` - When collateral was posted
- `new_total` - **NEW**: Posted collateral after withdrawal

**Required Fields** for `CollateralTimerBlocked`:
- `tick` - When block occurred
- `agent_id` - Who was blocked
- `requested_amount` - What was requested
- `reason` - Why blocked ("NoHeadroom", "MinHoldingPeriodNotMet")
- `original_reason` - Why collateral was posted
- `posted_at_tick` - When collateral was posted

**Rationale**: Full observability for replay identity and debugging

---

## Success Criteria

### Must Have (MVP)
- [ ] All unit tests pass (Rust)
- [ ] All integration tests pass (Python)
- [ ] Invariant I2 **never** violated (enforced in timer path)
- [ ] Tick 288 behavior changes as expected
- [ ] Replay identity preserved (events sufficient for display)

### Should Have
- [ ] FFI method `get_max_withdrawable_collateral`
- [ ] Display code handles `CollateralTimerBlocked` events
- [ ] Documentation updated

### Could Have
- [ ] Configurable `MIN_HOLDING_TICKS` per agent
- [ ] Configurable `SAFETY_BUFFER` per agent
- [ ] Timer "retry" logic (reschedule remainder)

---

## Rollout Plan

### Step 1: Write Tests (This PR)
- Add all failing tests
- Document expected behavior
- Commit: `test: Add failing tests for collateral timer invariant I2`

### Step 2: Implement Fix (This PR)
- Add `try_withdraw_collateral_guarded` to Agent
- Update timer processing
- Add new events
- Commit: `fix: Enforce invariant I2 in collateral timer withdrawals`

### Step 3: Verify (This PR)
- Run all tests
- Manual replay comparison
- Commit: `test: Verify collateral timer fix with replay`

### Step 4: Documentation (This PR)
- Update `CLAUDE.md` with new invariant enforcement
- Update collateral docs
- Commit: `docs: Document collateral timer safety guarantees`

---

## Risks and Mitigations

### Risk 1: Breaking Change

**Risk**: Existing simulations may behave differently.

**Mitigation**:
- This is a **bug fix**, not a feature change
- Old behavior violates documented invariants
- New behavior matches manual withdrawal (consistency)
- Document in changelog as "correctness fix"

### Risk 2: Performance Impact

**Risk**: Additional calculations in timer loop.

**Mitigation**:
- `max_withdrawable_collateral` is O(1) (simple arithmetic)
- Only computed when timer fires (rare)
- Negligible impact (<1% overhead)

### Risk 3: Edge Cases

**Risk**: Rounding errors cause violations.

**Mitigation**:
- `SAFETY_BUFFER = 100` cents handles rounding
- Ceiling used in `max_withdrawable_collateral`
- Tests include boundary conditions (exactly at limit)

---

## Appendix: Code Locations

| Component | File | Lines |
|-----------|------|-------|
| **BUG** Timer bypass | `backend/src/orchestrator/engine.rs` | 2626-2642 |
| **GUARD** Manual withdrawal | `backend/src/ffi/orchestrator.rs` | 554-638 |
| **HELPER** `max_withdrawable_collateral` | `backend/src/models/agent.rs` | 464-486 |
| **HELPER** `can_withdraw_collateral` | `backend/src/models/agent.rs` | 869-874 |
| **EVENT** `CollateralTimerWithdrawn` | `backend/src/models/event.rs` | 125-131 |
| **TESTS** Existing timer tests | `backend/tests/test_collateral_timers.rs` | All |

---

## Next Steps

1. **Review this plan** with team/user
2. **Create test file**: `backend/tests/test_collateral_timer_invariants.rs`
3. **Write failing tests** (Phase 1)
4. **Verify tests fail** ❌
5. **Implement fix** (Phase 2)
6. **Verify tests pass** ✅
7. **Manual validation** (Phase 4)
8. **Commit and PR**

---

**Author**: Claude (AI Assistant)
**Reviewer**: TBD
**Status**: DRAFT - Awaiting approval to proceed
