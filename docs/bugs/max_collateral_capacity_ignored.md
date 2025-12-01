# Bug Report: `max_collateral_capacity` Config Field Ignored

**Date**: 2025-12-01
**Reporter**: Claude (AI Assistant)
**Severity**: High
**Component**: Agent Model / FFI Configuration Parsing
**Status**: ✅ RESOLVED (2025-12-01)

---

## Summary

The `max_collateral_capacity` field in agent YAML configuration is silently ignored. Instead, the value is hardcoded as `10 × unsecured_cap` in Rust, causing policies that reference `max_collateral_capacity` to use incorrect values.

---

## Steps to Reproduce

1. Create a config with explicit `max_collateral_capacity`:
```yaml
agents:
  - id: BANK_A
    unsecured_cap: 10000000000      # $100M
    max_collateral_capacity: 50000000  # Intended: $500k
```

2. Create a policy that posts a fraction of `max_collateral_capacity`:
```json
{
  "action": "PostCollateral",
  "parameters": {
    "amount": {
      "compute": {
        "op": "*",
        "left": { "field": "max_collateral_capacity" },
        "right": { "value": 0.5 }
      }
    }
  }
}
```

3. Run simulation and observe posted collateral amount.

**Expected**: $250,000 (50% of $500k)
**Actual**: $500,000,000 (50% of $1B)

---

## Root Cause

In `backend/src/models/agent.rs:1262-1266`:

```rust
pub fn max_collateral_capacity(&self) -> i64 {
    // Heuristic: 10x unsecured overdraft capacity
    self.unsecured_cap * 10
}
```

The `max_collateral_capacity` is computed from `unsecured_cap` rather than stored as a configurable field. The config value is never parsed or used.

### FFI Gap

Checking `backend/src/ffi/types.rs`, the agent parsing extracts:
- `unsecured_cap` ✓
- `posted_collateral` ✓
- `collateral_haircut` ✓
- `max_collateral_capacity` ✗ **NOT PARSED**

---

## Impact

### Cost Calculation Errors

With `unsecured_cap: $100M` (needed for unlimited credit):
- Computed `max_collateral_capacity` = $1B
- If policy posts 50% = $500M collateral
- Collateral cost at 83 bps/tick × 12 ticks = **$49.8M/day**

vs intended:
- Config `max_collateral_capacity` = $500k
- Policy posts 50% = $250k collateral
- Collateral cost = **$24,900/day**

**Error factor: 2000x**

### Research Impact

This bug caused our Castro et al. (2025) replication experiment to show $40M costs instead of expected $50k, making results appear non-comparable to the paper.

---

## Suggested Fix

### Option 1: Add Explicit Field (Recommended)

Add `max_collateral_capacity` as a configurable field on Agent:

**In `backend/src/models/agent.rs`:**
```rust
pub struct Agent {
    // ... existing fields ...
    max_collateral_capacity: Option<i64>,  // NEW
}

impl Agent {
    pub fn max_collateral_capacity(&self) -> i64 {
        // Use explicit value if set, otherwise fall back to heuristic
        self.max_collateral_capacity.unwrap_or(self.unsecured_cap * 10)
    }

    pub fn set_max_collateral_capacity(&mut self, cap: i64) {
        self.max_collateral_capacity = Some(cap);
    }
}
```

**In `backend/src/ffi/types.rs`:**
```rust
// Add to agent parsing
let max_collateral_capacity: Option<i64> = extract_optional(py_agent, "max_collateral_capacity")?;
```

### Option 2: Document the Limitation

If the 10x heuristic is intentional, update documentation to clearly state:
- `max_collateral_capacity` in YAML is ignored
- Actual capacity = `10 × unsecured_cap`
- Users must adjust `unsecured_cap` to control collateral capacity

---

## Workaround

Until fixed, users can work around by:

1. Calculating the desired fraction based on actual capacity:
   ```
   actual_capacity = unsecured_cap × 10
   adjusted_fraction = desired_collateral / actual_capacity
   ```

2. Example: To post $250k with $100M unsecured_cap:
   ```
   fraction = $250,000 / $1,000,000,000 = 0.00025
   ```

---

## Files Affected

- `backend/src/models/agent.rs` - `max_collateral_capacity()` method
- `backend/src/ffi/types.rs` - Agent parsing (missing field)
- `api/payment_simulator/config/schemas.py` - Schema allows field but it's unused

---

## Test Case

```rust
#[test]
fn test_explicit_max_collateral_capacity() {
    let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
    agent.set_unsecured_cap(100_000_000);  // $1M unsecured

    // Without explicit setting, should use heuristic
    assert_eq!(agent.max_collateral_capacity(), 1_000_000_000);  // 10x

    // With explicit setting, should use that value
    agent.set_max_collateral_capacity(500_000);  // $5k
    assert_eq!(agent.max_collateral_capacity(), 500_000);
}
```

---

## Related

- Experiment 2d investigation in `experiments/castro/LAB_NOTES.md`
- Workaround config: `experiments/castro/configs/castro_12period_castro_equiv_fixed.yaml`

---

## Resolution

**Fixed in commit**: [See branch `claude/fix-collateral-capacity-bug-*`]

The fix was implemented by:

1. **Added `max_collateral_capacity: Option<i64>` field to `Agent` struct** (`backend/src/models/agent.rs`)
   - New field stores the explicit configuration value
   - `max_collateral_capacity()` method uses stored value or falls back to heuristic (10 × unsecured_cap)
   - New `set_max_collateral_capacity()` setter method
   - New `max_collateral_capacity_setting()` getter for checkpoint serialization

2. **Added field to `AgentConfig` struct** (`backend/src/orchestrator/engine.rs`)
   - `max_collateral_capacity: Option<i64>` with serde default
   - Wired through to agent initialization in `Orchestrator::new()`

3. **Added FFI parsing** (`backend/src/ffi/types.rs`)
   - `extract_optional(py_agent, "max_collateral_capacity")?` to parse from Python config

4. **Added FFI export** (`backend/src/ffi/orchestrator.rs`)
   - `get_agent_state()` now returns `max_collateral_capacity` and `remaining_collateral_capacity`

5. **Updated Python schema** (`api/payment_simulator/config/schemas.py`)
   - Added `max_collateral_capacity: int | None` field to `AgentConfig`

6. **Updated checkpoint serialization** (`backend/src/orchestrator/checkpoint.rs`)
   - `AgentSnapshot` now includes `max_collateral_capacity` for proper state save/restore

7. **Added tests** (`backend/src/models/agent.rs`)
   - `test_explicit_max_collateral_capacity` verifies the fix works correctly

### Verification

```python
from payment_simulator_core_rs import Orchestrator

config = {
    'agent_configs': [{
        'id': 'BANK_A',
        'unsecured_cap': 100_000_000_00,  # $100M
        'max_collateral_capacity': 50_000_000,  # $500k explicit
        # ...
    }],
    # ...
}

orch = Orchestrator.new(config)
state = orch.get_agent_state('BANK_A')

# Previously (broken): 10 × $100M = $1B
# Now (fixed): $500k as configured
assert state['max_collateral_capacity'] == 50_000_000
```
