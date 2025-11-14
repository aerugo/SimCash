# Collateral & Headroom Invariants - TDD Implementation Plan

## Executive Summary

Transform the collateral/headroom system from time-based "free-floating credit" to a realistic T2/CLM-style collateralized intraday credit line, where **posted collateral directly determines allowed overdraft capacity**.

**Core Problem**: Currently, agents can withdraw collateral while deeply overdrawn (e.g., REGIONAL_TRUST at tick 282: -$164,897 balance with $80k credit limit, yet withdraws $17,934 collateral).

**Solution**: Enforce invariants that tie headroom to pledged collateral with haircuts, prevent unsafe withdrawals, and make auto-withdraw state-safe.

---

## Critical Invariants

### I1: Credit Usage Cannot Exceed Allowed Limit
```
credit_used ≤ allowed_overdraft_limit

where:
  credit_used = max(0, -balance)
  allowed_overdraft_limit = floor(posted_collateral × (1 - haircut)) + unsecured_cap
```

### I2: Withdrawals Must Preserve Headroom
```
Cannot withdraw collateral if:
  credit_used > (allowed_overdraft_limit - withdrawal_amount_effect)

where:
  withdrawal_amount_effect = floor(withdrawn × (1 - haircut))
```

### I3: Buffer Cushion (Optional)
```
headroom ≥ safety_buffer after any withdrawal

where:
  headroom = allowed_overdraft_limit - credit_used
```

---

## Phase 1: Baseline & Test Infrastructure

### Task 1.1: Capture Baseline Behavior

**Test**: `test_baseline_tick_282_broken_behavior`

```python
def test_baseline_tick_282_broken_behavior():
    """
    Documents current (broken) behavior at tick 282 where REGIONAL_TRUST
    withdraws collateral while deeply overdrawn.

    This test CAPTURES the bug - it will pass initially, then fail after fix.
    """
    # Load simulation up to tick 281
    orch = load_advanced_crisis_to_tick(281)

    # Get REGIONAL_TRUST state before tick 282
    rt_before = orch.get_agent_state("REGIONAL_TRUST")
    assert rt_before["balance"] < -160_000_00  # Deep overdraft
    assert rt_before["posted_collateral"] > 0

    # Execute tick 282
    orch.tick()

    # Get state after
    rt_after = orch.get_agent_state("REGIONAL_TRUST")

    # CURRENT BROKEN BEHAVIOR: Collateral was withdrawn despite overdraft
    # This assertion will PASS before fix, FAIL after fix
    assert rt_after["posted_collateral"] < rt_before["posted_collateral"], \
        "Bug: Currently allows withdrawal while overdrawn"

    # Document the violation
    credit_used = max(0, -rt_after["balance"])
    credit_limit = rt_after["credit_limit"]
    assert credit_used > credit_limit, \
        f"Overdraft ({credit_used}) exceeds limit ({credit_limit})"
```

**Expected Output**:
- Initial run: PASS (captures broken behavior)
- After fix: FAIL (withdrawal should be blocked)

### Task 1.2: Create Baseline Replay Output

```bash
# Generate baseline (before changes)
cd api
uv run payment-sim replay --simulation-id sim-1b96f561 --verbose \
  --from-tick=282 --to-tick=282 > /tmp/baseline_tick_282.txt

# Save for comparison
cp /tmp/baseline_tick_282.txt docs/test-data/tick_282_baseline.txt
```

**What to verify in baseline**:
- "💰 Collateral Activity (1): REGIONAL_TRUST: AUTO-WITHDRAWN (timer): $17,934.08"
- "Balance: $-164,897.33 (overdraft)"
- "Credit Used: 206% over limit"

---

## Phase 2: Unit Tests for Agent Helpers

### Task 2.1: Test `credit_used()` Method

**File**: `backend/tests/test_agent_collateral_math.rs` (new)

```rust
#[cfg(test)]
mod test_credit_used {
    use super::*;

    #[test]
    fn test_credit_used_positive_balance() {
        let agent = create_test_agent("TEST", 100_000, 0);
        assert_eq!(agent.credit_used(), 0, "No credit used when balance positive");
    }

    #[test]
    fn test_credit_used_negative_balance() {
        let mut agent = create_test_agent("TEST", -50_000, 0);
        assert_eq!(agent.credit_used(), 50_000, "Credit used equals absolute overdraft");
    }

    #[test]
    fn test_credit_used_zero_balance() {
        let agent = create_test_agent("TEST", 0, 0);
        assert_eq!(agent.credit_used(), 0, "No credit used at zero balance");
    }
}
```

### Task 2.2: Test `allowed_overdraft_limit()` Method

```rust
#[test]
fn test_allowed_overdraft_no_collateral() {
    let agent = create_test_agent_with_collateral("TEST", 100_000, 0, 0.0, 0);
    assert_eq!(agent.allowed_overdraft_limit(), 0,
        "No overdraft allowed without collateral or unsecured cap");
}

#[test]
fn test_allowed_overdraft_with_collateral_no_haircut() {
    let mut agent = create_test_agent_with_collateral("TEST", 100_000, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00); // $100k
    agent.set_collateral_haircut(0.0); // 0% haircut

    assert_eq!(agent.allowed_overdraft_limit(), 100_000_00,
        "Full collateral value available with 0% haircut");
}

#[test]
fn test_allowed_overdraft_with_haircut() {
    let mut agent = create_test_agent_with_collateral("TEST", 0, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00); // $100k
    agent.set_collateral_haircut(0.10); // 10% haircut

    let expected = (100_000_00.0 * 0.9).floor() as i64; // $90k
    assert_eq!(agent.allowed_overdraft_limit(), expected,
        "Overdraft limit = floor(collateral × (1 - haircut))");
}

#[test]
fn test_allowed_overdraft_with_unsecured_cap() {
    let mut agent = create_test_agent_with_collateral("TEST", 0, 0, 0.0, 20_000_00);
    agent.set_posted_collateral(100_000_00); // $100k collateral
    agent.set_collateral_haircut(0.05); // 5% haircut

    let collat_portion = (100_000_00.0 * 0.95).floor() as i64; // $95k
    let expected = collat_portion + 20_000_00; // $95k + $20k = $115k

    assert_eq!(agent.allowed_overdraft_limit(), expected,
        "Overdraft limit = collateralized + unsecured cap");
}
```

### Task 2.3: Test `headroom()` Method

```rust
#[test]
fn test_headroom_no_usage() {
    let mut agent = create_test_agent_with_collateral("TEST", 50_000, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // No overdraft, so credit_used = 0
    // allowed_limit = 90k
    assert_eq!(agent.headroom(), 90_000_00, "Full headroom available");
}

#[test]
fn test_headroom_partial_usage() {
    let mut agent = create_test_agent_with_collateral("TEST", -30_000_00, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // credit_used = 30k
    // allowed_limit = 90k
    // headroom = 60k
    assert_eq!(agent.headroom(), 60_000_00,
        "Headroom = allowed_limit - credit_used");
}

#[test]
fn test_headroom_fully_utilized() {
    let mut agent = create_test_agent_with_collateral("TEST", -90_000_00, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // credit_used = 90k
    // allowed_limit = 90k
    assert_eq!(agent.headroom(), 0, "Zero headroom at full utilization");
}

#[test]
fn test_headroom_over_limit_should_not_occur() {
    // This represents a VIOLATION state (should never happen after fix)
    let mut agent = create_test_agent_with_collateral("TEST", -100_000_00, 0, 0.0, 0);
    agent.set_posted_collateral(80_000_00);
    agent.set_collateral_haircut(0.10);

    // credit_used = 100k
    // allowed_limit = 72k
    // headroom = -28k (NEGATIVE!)
    assert!(agent.headroom() < 0,
        "Negative headroom indicates invariant violation (should be prevented)");
}
```

### Task 2.4: Test `max_withdrawable_collateral()` Method

```rust
#[test]
fn test_max_withdrawable_no_usage_no_buffer() {
    let mut agent = create_test_agent_with_collateral("TEST", 50_000, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // No usage, no buffer: can withdraw all
    assert_eq!(agent.max_withdrawable_collateral(0), 100_000_00,
        "Can withdraw all collateral when no credit used");
}

#[test]
fn test_max_withdrawable_no_usage_with_buffer() {
    let mut agent = create_test_agent_with_collateral("TEST", 50_000, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // Buffer = $20k
    // Need: allowed_limit ≥ 0 + 20k after withdrawal
    // Need: C_new × 0.9 ≥ 20k → C_new ≥ 22,223 (ceil)
    // Can withdraw: 100k - 22,223 = 77,777

    let max_w = agent.max_withdrawable_collateral(20_000_00);
    assert!(max_w >= 77_777_00 && max_w <= 77_778_00,
        "Max withdrawable accounts for safety buffer");
}

#[test]
fn test_max_withdrawable_with_active_overdraft() {
    let mut agent = create_test_agent_with_collateral("TEST", -60_000_00, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // credit_used = 60k
    // Need: C_new × 0.9 ≥ 60k → C_new ≥ 66,667
    // Can withdraw: 100k - 66,667 = 33,333

    let max_w = agent.max_withdrawable_collateral(0);
    assert!(max_w >= 33_333_00 && max_w <= 33_334_00,
        "Can withdraw excess beyond required collateral");
}

#[test]
fn test_max_withdrawable_at_limit() {
    let mut agent = create_test_agent_with_collateral("TEST", -90_000_00, 0, 0.0, 0);
    agent.set_posted_collateral(100_000_00);
    agent.set_collateral_haircut(0.10);

    // credit_used = 90k
    // allowed_limit = 90k (fully utilized)
    // Cannot withdraw anything

    assert_eq!(agent.max_withdrawable_collateral(0), 0,
        "Cannot withdraw when at utilization limit");
}

#[test]
fn test_max_withdrawable_over_limit_violation() {
    // Represents the tick 282 bug scenario
    let mut agent = create_test_agent_with_collateral("TEST", -164_897_33, 0, 0.0, 0);
    agent.set_posted_collateral(120_000_00); // Hypothetical posted amount
    agent.set_collateral_haircut(0.02);

    // credit_used = 164,897
    // allowed_limit = 117,600 (120k × 0.98)
    // Already over limit! Max withdrawable = 0

    assert_eq!(agent.max_withdrawable_collateral(0), 0,
        "Cannot withdraw any collateral when over limit");
}

#[test]
fn test_max_withdrawable_with_unsecured_cap() {
    let mut agent = create_test_agent_with_collateral("TEST", -50_000_00, 0, 0.0, 20_000_00);
    agent.set_posted_collateral(80_000_00);
    agent.set_collateral_haircut(0.10);

    // credit_used = 50k
    // Need: C_new × 0.9 + 20k ≥ 50k
    // Need: C_new ≥ (50k - 20k) / 0.9 = 33,334
    // Can withdraw: 80k - 33,334 = 46,666

    let max_w = agent.max_withdrawable_collateral(0);
    assert!(max_w >= 46_666_00 && max_w <= 46_667_00,
        "Unsecured cap reduces required collateral");
}
```

---

## Phase 3: Integration Tests for Withdrawal Invariants

### Task 3.1: Test Withdrawal Rejection When Overdrawn

**File**: `api/tests/integration/test_collateral_withdrawal_invariants.py` (new)

```python
def test_cannot_withdraw_while_overdrawn():
    """
    Invariant I2: Cannot withdraw collateral if credit_used > 0
    and withdrawal would breach allowed_overdraft_limit.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -100_000_00,  # Overdrawn
                "credit_limit": 120_000_00,  # Legacy field (to be deprecated)
                "collateral_haircut": 0.10,
                "unsecured_cap": 0,
                "posted_collateral": 120_000_00,  # Posted to cover overdraft
                "policy": "simple_queue_flush",
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Verify initial state
    state = orch.get_agent_state("BANK_A")
    assert state["balance"] == -100_000_00
    assert state["posted_collateral"] == 120_000_00

    # Try to withdraw $50k (should fail)
    with pytest.raises(Exception) as exc_info:
        orch.withdraw_collateral("BANK_A", 50_000_00)

    assert "breach" in str(exc_info.value).lower() or \
           "headroom" in str(exc_info.value).lower(), \
           "Should reject withdrawal that would breach headroom"

    # Verify collateral unchanged
    state_after = orch.get_agent_state("BANK_A")
    assert state_after["posted_collateral"] == 120_000_00, \
        "Collateral should remain unchanged after rejected withdrawal"
```

### Task 3.2: Test Allowed Withdrawal of Excess Collateral

```python
def test_can_withdraw_excess_collateral():
    """
    Should allow withdrawal of collateral that exceeds requirement.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 0,  # No overdraft
                "collateral_haircut": 0.05,
                "posted_collateral": 200_000_00,  # Excess posted
                "policy": "simple_queue_flush",
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Should allow withdrawal since no credit is being used
    result = orch.withdraw_collateral("BANK_A", 150_000_00)

    assert result["success"] is True
    assert result["new_total"] == 50_000_00, \
        "Should successfully withdraw excess collateral"
```

### Task 3.3: Test Withdrawal with Safety Buffer

```python
def test_withdrawal_respects_safety_buffer():
    """
    Invariant I3: Withdrawal should maintain headroom ≥ buffer.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "safety_buffer": 20_000_00,  # $20k buffer
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -30_000_00,  # Using $30k credit
                "collateral_haircut": 0.10,
                "posted_collateral": 100_000_00,
                "policy": "simple_queue_flush",
            }
        ],
    }

    orch = Orchestrator.new(config)

    # credit_used = 30k
    # allowed_limit = 90k (100k × 0.9)
    # headroom = 60k
    #
    # With buffer = 20k, need headroom ≥ 20k after withdrawal
    # Max withdrawable ≈ amount that keeps C_new × 0.9 ≥ 50k (30k + 20k)
    # C_new ≥ 55,556 → max withdraw = 100k - 55,556 = 44,444

    # Try to withdraw $50k (should fail due to buffer)
    with pytest.raises(Exception):
        orch.withdraw_collateral("BANK_A", 50_000_00)

    # Try to withdraw $44k (should succeed)
    result = orch.withdraw_collateral("BANK_A", 44_000_00)
    assert result["success"] is True
```

### Task 3.4: Test Withdrawal Rejection Reproduces Tick 282 Bug

```python
def test_tick_282_scenario_withdrawal_blocked():
    """
    Reproduces tick 282 REGIONAL_TRUST scenario where withdrawal
    should have been blocked but wasn't.

    This test will FAIL initially, PASS after fix.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {
                "id": "REGIONAL_TRUST",
                "opening_balance": -164_897_33,  # Deep overdraft
                "credit_limit": 80_000_00,
                "collateral_haircut": 0.02,
                "posted_collateral": 50_000_00,  # Hypothetical
                "policy": "simple_queue_flush",
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Attempt the withdrawal that occurred at tick 282
    with pytest.raises(Exception) as exc_info:
        orch.withdraw_collateral("REGIONAL_TRUST", 17_934_08)

    assert "breach" in str(exc_info.value).lower() or \
           "headroom" in str(exc_info.value).lower(), \
           "Should block withdrawal when deeply overdrawn"
```

---

## Phase 4: Scenario Tests with Advanced Crisis Config

### Task 4.1: Test Full Simulation with Invariants

**File**: `api/tests/integration/test_collateral_crisis_scenario.py` (new)

```python
def test_advanced_crisis_maintains_invariants():
    """
    Run advanced_policy_crisis.yaml and verify invariants hold throughout.
    """
    config_path = "../examples/configs/advanced_policy_crisis.yaml"
    config = load_yaml_config(config_path)

    orch = Orchestrator.new(config)

    # Run simulation
    max_ticks = 300
    violations = []

    for tick in range(max_ticks):
        orch.tick()

        # Check invariants for all agents
        for agent_id in config["agent_configs"]:
            state = orch.get_agent_state(agent_id["id"])

            credit_used = max(0, -state["balance"])
            allowed_limit = state.get("allowed_overdraft_limit", state["credit_limit"])

            # Invariant I1: credit_used ≤ allowed_limit
            if credit_used > allowed_limit:
                violations.append({
                    "tick": tick,
                    "agent": agent_id["id"],
                    "credit_used": credit_used,
                    "allowed_limit": allowed_limit,
                    "violation": "I1: credit_used > allowed_limit"
                })

    assert len(violations) == 0, \
        f"Invariant violations detected:\n{json.dumps(violations, indent=2)}"
```

### Task 4.2: Test Tick 282 Specific Behavior

```python
def test_tick_282_no_unsafe_withdrawal():
    """
    Load advanced_crisis to tick 281, execute tick 282,
    verify REGIONAL_TRUST does NOT withdraw collateral unsafely.
    """
    config = load_yaml_config("../examples/configs/advanced_policy_crisis.yaml")
    orch = Orchestrator.new(config)

    # Fast-forward to tick 281
    for _ in range(281):
        orch.tick()

    # Capture REGIONAL_TRUST state before tick 282
    rt_before = orch.get_agent_state("REGIONAL_TRUST")
    collateral_before = rt_before["posted_collateral"]
    balance_before = rt_before["balance"]

    # Execute tick 282
    orch.tick()

    # Capture state after
    rt_after = orch.get_agent_state("REGIONAL_TRUST")
    collateral_after = rt_after["posted_collateral"]
    balance_after = rt_after["balance"]

    # If still overdrawn, collateral should NOT decrease
    if balance_after < 0:
        credit_used = -balance_after
        # Calculate what allowed_limit would be after withdrawal
        haircut = rt_after.get("collateral_haircut", 0.0)

        if collateral_after < collateral_before:
            # Withdrawal occurred - verify it was safe
            allowed_limit_after = int(collateral_after * (1 - haircut))

            assert credit_used <= allowed_limit_after, \
                f"UNSAFE WITHDRAWAL: credit_used ({credit_used}) > " \
                f"allowed_limit ({allowed_limit_after}) after withdrawal"

    # Better: if overdrawn beyond allowed limit, should NOT have withdrawn
    if balance_after < -rt_after.get("allowed_overdraft_limit", rt_after["credit_limit"]):
        assert collateral_after >= collateral_before, \
            "Should NOT withdraw collateral when over allowed limit"
```

### Task 4.3: Test Auto-Withdraw Becomes Conditional

```python
def test_auto_withdraw_deferred_when_unsafe():
    """
    Verify that auto-withdraw timer does NOT execute when agent is overdrawn.
    """
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": -80_000_00,  # Overdrawn
                "collateral_haircut": 0.10,
                "posted_collateral": 100_000_00,
                "policy": "advanced_with_auto_withdraw",  # Has auto-withdraw logic
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Run past the auto-withdraw timer threshold
    for _ in range(10):  # Assuming MIN_HOLDING_TICKS = 5
        orch.tick()

    # Verify collateral was NOT auto-withdrawn
    state = orch.get_agent_state("BANK_A")
    assert state["posted_collateral"] == 100_000_00, \
        "Auto-withdraw should be deferred when agent is overdrawn"

    # Check for deferred event in logs
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e.get("event_type") == "collateral_release_deferred"]

    assert len(collateral_events) > 0, \
        "Should log a 'deferred' event when auto-withdraw is unsafe"
```

---

## Phase 5: Implementation Checklist

### 5.1 Rust Backend Changes

**File**: `backend/src/models/agent.rs`

- [ ] Add field: `collateral_haircut: Option<f64>` (0.0-1.0, default 0.02 for 2%)
- [ ] Add field: `unsecured_cap: Option<i64>` (cents, default 0)
- [ ] Add method: `pub fn credit_used(&self) -> i64`
- [ ] Add method: `pub fn allowed_overdraft_limit(&self) -> i64`
- [ ] Add method: `pub fn headroom(&self) -> i64`
- [ ] Add method: `pub fn max_withdrawable_collateral(&self, buffer: i64) -> i64`
- [ ] Add getters/setters for new fields

**File**: `backend/src/ffi/orchestrator.rs`

- [ ] Update `withdraw_collateral` to call `max_withdrawable_collateral`
- [ ] Replace "sufficient posted collateral" check with headroom check
- [ ] Add parameter: `safety_buffer: i64` (from config or default 0)
- [ ] Update error message to mention headroom breach
- [ ] Ensure MIN_HOLDING_TICKS check remains

**File**: `backend/src/ffi/orchestrator.rs` (get_agent_state)

- [ ] Export `credit_used` field
- [ ] Export `allowed_overdraft_limit` field
- [ ] Export `overdraft_headroom` field
- [ ] Export `max_withdrawable_collateral` field
- [ ] Export `collateral_haircut` field
- [ ] Export `unsecured_cap` field

### 5.2 Policy Tree Context Changes

**File**: `backend/src/policy/tree/context.rs`

- [ ] Add to `EvalContext`: `credit_used`
- [ ] Add to `EvalContext`: `allowed_overdraft_limit`
- [ ] Add to `EvalContext`: `overdraft_headroom`
- [ ] Add to `EvalContext`: `required_collateral_for_usage`
- [ ] Add to `EvalContext`: `excess_collateral`
- [ ] Add to `EvalContext`: `collateral_utilization` (posted / capacity)
- [ ] Add to `EvalContext`: `overdraft_utilization` (credit_used / allowed_limit)

### 5.3 Python API Changes

**File**: `api/payment_simulator/config/schema.py`

- [ ] Add `collateral_haircut` to `AgentConfig` (Optional[float], default 0.02)
- [ ] Add `unsecured_cap` to `AgentConfig` (Optional[int], default 0)
- [ ] Add `safety_buffer` to `SimulationConfig` (Optional[int], default 0)
- [ ] Update validation to ensure 0.0 ≤ haircut ≤ 1.0

**File**: `api/payment_simulator/cli/display/verbose_output.py`

- [ ] Update "💰 Agent Financial Stats" section
- [ ] Replace "Credit Limit" with "Allowed Overdraft (collateralized)"
- [ ] Show "Posted Collateral", "Haircut (%)", "Headroom"
- [ ] Show "Credit Used / Allowed: X / Y (Z%)"
- [ ] Add visual indicator when headroom is low (< 10%)

### 5.4 Event System Changes (Optional)

**File**: `backend/src/models/collateral_event.rs`

- [ ] Add field: `executed: bool`
- [ ] Add field: `defer_reason: Option<String>`
- [ ] Update serialization to include new fields

**File**: `api/payment_simulator/cli/display/verbose_output.py`

- [ ] Update collateral event display to show deferred withdrawals
- [ ] Format: "DEFERRED: $X (reason: insufficient_headroom)"

---

## Phase 6: Validation & Comparison

### Task 6.1: Run Regression Tests

```bash
# Run all new unit tests
cd backend
cargo test test_credit_used --no-default-features
cargo test test_allowed_overdraft --no-default-features
cargo test test_headroom --no-default-features
cargo test test_max_withdrawable --no-default-features

# Run integration tests
cd ../api
uv run python -m pytest tests/integration/test_collateral_withdrawal_invariants.py -v
uv run python -m pytest tests/integration/test_collateral_crisis_scenario.py -v
```

### Task 6.2: Compare Replay Output

```bash
# Generate new replay output after changes
cd api
uv run payment-sim replay --simulation-id sim-1b96f561 --verbose \
  --from-tick=282 --to-tick=282 > /tmp/fixed_tick_282.txt

# Compare with baseline
diff docs/test-data/tick_282_baseline.txt /tmp/fixed_tick_282.txt
```

**Expected differences**:
- ❌ REMOVED: "AUTO-WITHDRAWN (timer): $17,934.08"
- ✅ ADDED: "Collateral Activity: DEFERRED: $17,934.08 (insufficient_headroom)"
- ✅ CHANGED: Display now shows "Headroom: -$52,897.33" (negative = violation prevented)

### Task 6.3: Full Simulation Replay

```bash
# Run full simulation with new invariants
uv run payment-sim run --config ../examples/configs/advanced_policy_crisis.yaml \
  --persist output_fixed.db --verbose > /tmp/run_with_invariants.txt

# Replay to verify
uv run payment-sim replay --simulation-id <new-sim-id> --verbose \
  --from-tick=280 --to-tick=290 > /tmp/replay_with_invariants.txt

# Compare (should be identical)
diff <(grep -v "Duration:" /tmp/run_with_invariants.txt) \
     <(grep -v "Duration:" /tmp/replay_with_invariants.txt)
```

---

## Success Criteria

### Tests
- [x] All unit tests for Agent helper methods pass
- [x] All integration tests for withdrawal invariants pass
- [x] Scenario test with advanced_policy_crisis.yaml passes
- [x] No invariant violations detected during full simulation

### Behavior
- [x] Cannot withdraw collateral while overdrawn beyond allowed limit
- [x] Auto-withdraw is deferred when unsafe
- [x] Tick 282 no longer shows unsafe withdrawal
- [x] Headroom calculation is accurate and real-time

### Display
- [x] Verbose output shows new collateral/headroom metrics
- [x] Clear indication when headroom is negative or low
- [x] Deferred withdrawal events are logged appropriately

### Determinism
- [x] Replay output matches run output (byte-for-byte, minus timing)
- [x] All collateral events are persisted and replayed correctly

---

## Rollout Checklist

1. [ ] Baseline captured (tick 282 before fix)
2. [ ] All unit tests written and initially FAILING
3. [ ] All integration tests written and initially FAILING
4. [ ] Rust implementation complete
5. [ ] FFI boundary updated
6. [ ] Python display updated
7. [ ] All tests now PASSING
8. [ ] Replay comparison shows expected differences
9. [ ] Full simulation runs without invariant violations
10. [ ] Documentation updated (CLAUDE.md)
11. [ ] Commit and push changes

---

## Future Enhancements (Out of Scope for This Plan)

- [ ] Settlement-lagged releases (1-2 tick delay for withdrawals)
- [ ] Tiered haircuts by asset class
- [ ] End-of-day forced settlement (U must = 0 at close)
- [ ] Collateral capacity inventory management
- [ ] Scenario events for haircut changes mid-day

---

*Last Updated: 2025-11-14*
*Target Implementation Time: 4-6 hours*
