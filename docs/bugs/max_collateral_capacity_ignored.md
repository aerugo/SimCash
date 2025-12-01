# Bug Report: `max_collateral_capacity` Config Field Ignored

**Date**: 2025-12-01
**Reporter**: Claude (AI Assistant)
**Severity**: High
**Component**: Agent Model / FFI Configuration Parsing

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
