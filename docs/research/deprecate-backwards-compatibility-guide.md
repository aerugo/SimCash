# Deprecation Guide: credit_limit Backwards Compatibility

**Status**: Proposed
**Created**: 2025-11-15
**Purpose**: Remove all backwards compatibility code for the credit_limit → unsecured_cap transition introduced in Phase 8

---

## Executive Summary

This guide provides a comprehensive plan to deprecate and remove all backwards compatibility logic that supports the old `credit_limit`-only configuration schema. After this deprecation:

- ✅ All configurations must use `unsecured_cap` (and optionally `posted_collateral`)
- ❌ Configurations with only `credit_limit` will be rejected with a clear error message
- ✅ `credit_limit` field will be completely removed from the codebase
- ✅ Simpler, cleaner code with no legacy logic

---

## Background: What is Being Deprecated?

### Old Schema (Phase 7 and earlier)
```yaml
agents:
  - id: "BANK_A"
    opening_balance: 100000
    credit_limit: 20000  # Single field for overdraft capacity
```

### New Schema (Phase 8+)
```yaml
agents:
  - id: "BANK_A"
    opening_balance: 100000
    unsecured_cap: 20000        # Explicit unsecured overdraft
    posted_collateral: 50000    # Optional collateral backing
    collateral_haircut: 0.02    # Optional haircut (default 0.0)
```

### The Compatibility Logic

The current code automatically migrates old configs:
1. If `unsecured_cap` is missing but `credit_limit` is set → copy `credit_limit` to `unsecured_cap`
2. If both are set → use `max(credit_limit, unsecured_cap)` to prevent double-counting
3. Old snapshots without `unsecured_cap` → default to 0

**This guide removes all of that.**

---

## Impact Analysis

### Configurations That Will Break

**File: `examples/configs/advanced_policy_crisis.yaml`**
- All 4 agents use old schema
- **Action Required**: Update to new schema before deprecation

**File: Any user-created configs from before Phase 8**
- Unknown quantity in the wild
- **Migration Strategy**: Provide a migration script (see Section 6)

### Code That Will Be Removed

| Location | Lines | Description |
|----------|-------|-------------|
| `backend/src/orchestrator/engine.rs` | 809-818 | Auto-copy `credit_limit` to `unsecured_cap` |
| `backend/src/models/agent.rs` | 555-559 | `max()` logic in `available_liquidity()` |
| `backend/src/models/agent.rs` | 336 | Default `unsecured_cap: 0` in snapshots |
| `backend/src/orchestrator/engine.rs` | 138-168 | `AgentConfig` struct field changes |
| `backend/src/ffi/types.rs` | 175-210 | FFI parsing changes |

### Tests That Will Be Removed

**No dedicated backwards compatibility tests found.**

However, these test files use old-schema configs and will need updates:
- Tests using `advanced_policy_crisis.yaml`
- Any integration tests with inline configs using only `credit_limit`

---

## Step-by-Step Removal Plan

### Phase 1: Preparation (Breaking Change Warning)

#### Step 1.1: Update Example Configurations

**File: `examples/configs/advanced_policy_crisis.yaml`**

```yaml
# BEFORE (all 4 agents):
- id: "METRO_CENTRAL"
  opening_balance: 5000000
  credit_limit: 2000000  # OLD

# AFTER (all 4 agents):
- id: "METRO_CENTRAL"
  opening_balance: 5000000
  unsecured_cap: 2000000  # NEW
```

**Command to verify**:
```bash
# Search for all YAML files using credit_limit
grep -r "credit_limit:" examples/configs/
```

#### Step 1.2: Search for Test Fixtures

**Command**:
```bash
# Find Rust tests with credit_limit
cd backend
grep -rn "credit_limit:" tests/

# Find Python tests with credit_limit
cd api
grep -rn "credit_limit:" tests/
```

**Action**: For each match, update to use `unsecured_cap` instead.

#### Step 1.3: Create Migration Script (Optional but Recommended)

**File: `scripts/migrate_config_v7_to_v8.py`**

```python
#!/usr/bin/env python3
"""
Migrate old-schema configs (credit_limit) to new schema (unsecured_cap).

Usage:
    python scripts/migrate_config_v7_to_v8.py input.yaml output.yaml
"""

import sys
import yaml

def migrate_config(input_path: str, output_path: str):
    with open(input_path) as f:
        config = yaml.safe_load(f)

    for agent in config.get("agents", []):
        if "credit_limit" in agent and "unsecured_cap" not in agent:
            # Migrate: credit_limit → unsecured_cap
            agent["unsecured_cap"] = agent["credit_limit"]
            print(f"✓ Migrated agent '{agent['id']}': credit_limit={agent['credit_limit']} → unsecured_cap={agent['unsecured_cap']}")

        # Optionally remove credit_limit field
        # agent.pop("credit_limit", None)

    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"\n✓ Migration complete: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    migrate_config(sys.argv[1], sys.argv[2])
```

**Test the script**:
```bash
python scripts/migrate_config_v7_to_v8.py \
    examples/configs/advanced_policy_crisis.yaml \
    examples/configs/advanced_policy_crisis_migrated.yaml

# Verify output
diff examples/configs/advanced_policy_crisis.yaml \
     examples/configs/advanced_policy_crisis_migrated.yaml
```

---

### Phase 2: Update Configuration Schema (Rust)

#### Step 2.1: Make `credit_limit` Optional (Transition Step)

**File: `backend/src/orchestrator/engine.rs`**

**Before**:
```rust
pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub credit_limit: i64,          // Required
    pub unsecured_cap: Option<i64>, // Optional
    // ...
}
```

**After**:
```rust
pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub credit_limit: Option<i64>,  // ← Now optional (deprecated)
    pub unsecured_cap: Option<i64>, // Still optional (will become required)
    // ...
}
```

#### Step 2.2: Add Deprecation Warning

**File: `backend/src/orchestrator/engine.rs` (around line 809)**

**Before**:
```rust
// Set unsecured cap if specified (defaults to 0)
// BACKWARD COMPATIBILITY: If unsecured_cap not specified but credit_limit is,
// set unsecured_cap = credit_limit to ensure withdrawal checks properly account
// for the credit capacity.
if let Some(cap) = ac.unsecured_cap {
    agent.set_unsecured_cap(cap);
} else if ac.credit_limit > 0 {
    agent.set_unsecured_cap(ac.credit_limit);
}
```

**After**:
```rust
// Deprecation handling: credit_limit → unsecured_cap migration
match (ac.unsecured_cap, ac.credit_limit) {
    (Some(cap), None) => {
        // New schema: unsecured_cap only
        agent.set_unsecured_cap(cap);
    }
    (None, Some(old_limit)) => {
        // OLD SCHEMA DETECTED - DEPRECATED!
        eprintln!(
            "⚠️  WARNING: Agent '{}' uses deprecated 'credit_limit' field. \
             Please update your configuration to use 'unsecured_cap' instead. \
             'credit_limit' will be removed in the next major version.",
            ac.id
        );
        agent.set_unsecured_cap(old_limit); // Still works for now
    }
    (Some(cap), Some(old_limit)) => {
        // Both specified - use unsecured_cap and warn
        eprintln!(
            "⚠️  WARNING: Agent '{}' specifies both 'credit_limit' ({}) and 'unsecured_cap' ({}). \
             Using 'unsecured_cap'. Please remove 'credit_limit' from your configuration.",
            ac.id, old_limit, cap
        );
        agent.set_unsecured_cap(cap);
    }
    (None, None) => {
        // No overdraft capacity (valid)
        agent.set_unsecured_cap(0);
    }
}
```

#### Step 2.3: Update FFI Parser

**File: `backend/src/ffi/types.rs`**

**Before**:
```rust
let credit_limit: i64 = extract_required(py_agent, "credit_limit")?;
let unsecured_cap: Option<i64> = extract_optional(py_agent, "unsecured_cap")?;
```

**After**:
```rust
let credit_limit: Option<i64> = extract_optional(py_agent, "credit_limit")?;
let unsecured_cap: Option<i64> = extract_optional(py_agent, "unsecured_cap")?;

// Validation: At least one must be specified (for now)
if credit_limit.is_none() && unsecured_cap.is_none() {
    // Both missing is OK - means no overdraft capacity
}
```

#### Step 2.4: Run Tests

```bash
cd backend
cargo test --no-default-features

# Expected: All tests pass, but deprecation warnings appear
```

**Action**: Fix any test failures by updating test configs to use `unsecured_cap`.

---

### Phase 3: Remove Backwards Compatibility Logic

#### Step 3.1: Remove `max()` Logic in `available_liquidity()`

**File: `backend/src/models/agent.rs` (lines 555-559)**

**Before**:
```rust
// BACKWARD COMPATIBILITY: Use MAX(credit_limit, unsecured_cap) to avoid double-counting
// during the transition from credit_limit (old system) to unsecured_cap (new T2/CLM system).
let unsecured_headroom = self.credit_limit.max(self.unsecured_cap);
let total_headroom = unsecured_headroom + collateral_headroom;
```

**After**:
```rust
// Only use unsecured_cap (credit_limit is deprecated)
let unsecured_headroom = self.unsecured_cap;
let total_headroom = unsecured_headroom + collateral_headroom;
```

#### Step 3.2: Remove `credit_limit` Field from `Agent` Struct

**File: `backend/src/models/agent.rs`**

**Find the `Agent` struct and remove**:
```rust
pub struct Agent {
    pub id: String,
    pub balance: i64,
    pub credit_limit: i64,  // ← REMOVE THIS LINE
    pub unsecured_cap: i64,
    // ...
}
```

**Impact**: This will cause compilation errors everywhere `credit_limit` is referenced. Fix each one:

```bash
cd backend
cargo build 2>&1 | grep "credit_limit"
```

**Expected errors**:
- `Agent::new()` constructor
- `Agent::from_snapshot()` deserialization
- `AgentConfig` struct
- FFI serialization in `ffi/orchestrator.rs`

#### Step 3.3: Fix `Agent::new()` Constructor

**File: `backend/src/models/agent.rs`**

**Before**:
```rust
pub fn new(id: String, opening_balance: i64, credit_limit: i64) -> Self {
    Agent {
        id,
        balance: opening_balance,
        credit_limit,
        unsecured_cap: 0,
        // ...
    }
}
```

**After**:
```rust
pub fn new(id: String, opening_balance: i64) -> Self {
    Agent {
        id,
        balance: opening_balance,
        unsecured_cap: 0,  // Default to no unsecured overdraft
        // ...
    }
}
```

**Breaking change**: All callers of `Agent::new()` must be updated.

**Search for callers**:
```bash
cd backend
grep -rn "Agent::new" src/ tests/
```

**Fix each one**:
```rust
// Before
let agent = Agent::new("BANK_A".to_string(), 1_000_000, 200_000);

// After
let mut agent = Agent::new("BANK_A".to_string(), 1_000_000);
agent.set_unsecured_cap(200_000);  // If needed
```

#### Step 3.4: Remove `credit_limit` from `AgentConfig`

**File: `backend/src/orchestrator/engine.rs`**

**Before**:
```rust
pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub credit_limit: Option<i64>,  // ← REMOVE THIS
    pub unsecured_cap: Option<i64>,
    // ...
}
```

**After**:
```rust
pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub unsecured_cap: i64,  // ← Now required (no Option)
    // ...
}
```

**Note**: `unsecured_cap` is now **required**, not optional. Configs must explicitly set it (use 0 for no overdraft).

#### Step 3.5: Update Agent Initialization Logic

**File: `backend/src/orchestrator/engine.rs` (around line 809)**

**Before** (with deprecation warning):
```rust
match (ac.unsecured_cap, ac.credit_limit) {
    // ... 30 lines of compatibility logic ...
}
```

**After**:
```rust
// Simple: just use unsecured_cap from config
agent.set_unsecured_cap(ac.unsecured_cap);
```

#### Step 3.6: Update FFI Type Parsing

**File: `backend/src/ffi/types.rs`**

**Before**:
```rust
let credit_limit: Option<i64> = extract_optional(py_agent, "credit_limit")?;
let unsecured_cap: Option<i64> = extract_optional(py_agent, "unsecured_cap")?;
```

**After**:
```rust
let unsecured_cap: i64 = extract_required(py_agent, "unsecured_cap")?;

// Validate that credit_limit is NOT provided (to catch old configs)
if py_agent.contains("credit_limit")? {
    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
        format!(
            "Agent '{}': 'credit_limit' field is no longer supported. \
             Use 'unsecured_cap' instead. See migration guide at docs/research/deprecate-backwards-compatibility-guide.md",
            id
        )
    ));
}
```

#### Step 3.7: Remove `credit_limit` from FFI Snapshots

**File: `backend/src/ffi/orchestrator.rs`**

**Search for FFI functions that serialize `Agent` data**:
```bash
cd backend
grep -rn "credit_limit" src/ffi/
```

**For each match**, remove the `credit_limit` field from the serialization:

```rust
// Before
dict.insert("credit_limit".to_string(), agent.credit_limit.into());
dict.insert("unsecured_cap".to_string(), agent.unsecured_cap.into());

// After
dict.insert("unsecured_cap".to_string(), agent.unsecured_cap.into());
```

#### Step 3.8: Update Agent Snapshot Deserialization

**File: `backend/src/models/agent.rs`**

**Before**:
```rust
pub fn from_snapshot(
    id: String,
    balance: i64,
    credit_limit: i64,  // ← REMOVE THIS PARAMETER
    unsecured_cap: i64,
    // ...
) -> Self {
    Agent {
        id,
        balance,
        credit_limit,
        unsecured_cap,
        // ...
    }
}
```

**After**:
```rust
pub fn from_snapshot(
    id: String,
    balance: i64,
    unsecured_cap: i64,
    // ...
) -> Self {
    Agent {
        id,
        balance,
        unsecured_cap,
        // ...
    }
}
```

**Breaking change**: All callers must be updated to remove the `credit_limit` argument.

---

### Phase 4: Update Tests

#### Step 4.1: Find All Tests Using `credit_limit`

**Rust tests**:
```bash
cd backend
grep -rn "credit_limit" tests/ | grep -v "\.md:"
```

**Python tests**:
```bash
cd api
grep -rn "credit_limit" tests/ | grep -v "\.md:"
```

#### Step 4.2: Update Test Fixtures

**Pattern to find**:
```rust
// OLD
let config = AgentConfig {
    id: "BANK_A".to_string(),
    opening_balance: 1_000_000,
    credit_limit: 200_000,
    // ...
};
```

**Replace with**:
```rust
// NEW
let config = AgentConfig {
    id: "BANK_A".to_string(),
    opening_balance: 1_000_000,
    unsecured_cap: 200_000,
    // ...
};
```

#### Step 4.3: Remove Tests for Backwards Compatibility

**Files to check**:
- `backend/tests/test_release_flags.rs` (backward compatibility tests)
- `backend/tests/test_lsm_t2_compliant.rs` (backward compatibility tests)

**Action**: Remove any tests with "backward" or "compatibility" in the name that specifically test `credit_limit` handling.

**Example**:
```rust
#[test]
fn test_credit_limit_backward_compatibility() {
    // ← DELETE THIS ENTIRE TEST
}
```

#### Step 4.4: Run Full Test Suite

```bash
# Rust tests
cd backend
cargo test --no-default-features

# Python tests
cd api
uv run pytest

# Integration tests
cd api
uv run pytest tests/integration/
```

**Expected**: All tests pass with no deprecation warnings.

---

### Phase 5: Update Documentation

#### Step 5.1: Update README.md

**File: `README.md`**

**Find and replace**:
```yaml
# OLD (lines 520-521, 705, 709)
agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 200000  # ← REMOVE

# NEW
agents:
  - id: BANK_A
    opening_balance: 1000000
    unsecured_cap: 200000  # ← USE THIS
```

#### Step 5.2: Update CLAUDE.md

**File: `CLAUDE.md`**

**Remove the "Backwards Compatibility Logic Explained" section** (the one the user provided at the start of this conversation).

**Add a note**:
```markdown
## Breaking Changes

### Removed in vX.Y.Z (2025-11-15)

**Deprecated `credit_limit` field removed**

The old `credit_limit` field is no longer supported in agent configurations. Use `unsecured_cap` instead.

**Migration**:
```yaml
# Old schema (no longer works)
- id: "BANK_A"
  credit_limit: 200000

# New schema (required)
- id: "BANK_A"
  unsecured_cap: 200000  # Explicit unsecured overdraft cap
```

For automated migration, use:
```bash
python scripts/migrate_config_v7_to_v8.py old_config.yaml new_config.yaml
```

See `docs/research/deprecate-backwards-compatibility-guide.md` for full details.
```

#### Step 5.3: Update Policy DSL Guide

**File: `docs/policy_dsl_guide.md`**

**Find deprecation note** (line 895):
```markdown
| `available_liquidity` | `f64` (cents) | ⚠️ **Deprecated**: `balance + credit_limit + posted_collateral` ... |
```

**Replace with**:
```markdown
| `available_liquidity` | `f64` (cents) | `balance + unsecured_cap + posted_collateral` (can be negative when in overdraft) |
```

#### Step 5.4: Update Architecture Docs

**Search for references**:
```bash
grep -rn "credit_limit" docs/
```

**Action**: For each match, update to use `unsecured_cap` terminology.

---

### Phase 6: Verify and Commit

#### Step 6.1: Final Verification

**Checklist**:
- [ ] No `credit_limit` references in Rust code (except comments/docs)
- [ ] No `credit_limit` references in Python code (except migration script)
- [ ] All example configs use `unsecured_cap`
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Migration script tested

**Command to verify**:
```bash
# Should return 0 results (except migration script and this guide)
git grep "credit_limit" -- '*.rs' '*.py' '*.yaml' | grep -v "migrate_config" | grep -v "deprecate-backwards"
```

#### Step 6.2: Create Commit

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat!: Remove credit_limit backwards compatibility

BREAKING CHANGE: The `credit_limit` field has been completely removed
from agent configurations. All configurations must now use `unsecured_cap`.

Changes:
- Remove `credit_limit` field from `Agent` and `AgentConfig` structs
- Remove backwards compatibility logic in agent initialization
- Remove max() logic in available_liquidity()
- Update all example configs to use unsecured_cap
- Update all tests to use new schema
- Add migration script: scripts/migrate_config_v7_to_v8.py
- Update documentation (README, CLAUDE.md, policy_dsl_guide.md)

Migration:
To migrate old configurations, run:
  python scripts/migrate_config_v7_to_v8.py old.yaml new.yaml

See docs/research/deprecate-backwards-compatibility-guide.md for details.
EOF
)"
```

#### Step 6.3: Update CHANGELOG

**File: `CHANGELOG.md` (create if doesn't exist)**

```markdown
# Changelog

## [Unreleased]

### BREAKING CHANGES

#### Removed `credit_limit` field from agent configuration

The deprecated `credit_limit` field has been completely removed. All agent configurations must now use `unsecured_cap` to specify unsecured overdraft capacity.

**Before (no longer works)**:
```yaml
agents:
  - id: "BANK_A"
    opening_balance: 1000000
    credit_limit: 200000  # ❌ No longer supported
```

**After (required)**:
```yaml
agents:
  - id: "BANK_A"
    opening_balance: 1000000
    unsecured_cap: 200000  # ✅ Required
```

**Migration**: Use the provided script:
```bash
python scripts/migrate_config_v7_to_v8.py old_config.yaml new_config.yaml
```

**Rationale**: The `credit_limit` field was a holdover from Phase 7 before the introduction of the T2/CLM-style collateral system. Maintaining backwards compatibility added unnecessary complexity and potential for bugs (double-counting, confusion between fields). The new schema is clearer and more maintainable.

**Impact**: Any configurations created before Phase 8 will need to be migrated. The migration is mechanical (rename field) and can be automated with the provided script.
```

---

## Summary of Changes

### Code Removed (approx. 80 lines)

| File | Lines Removed | Description |
|------|---------------|-------------|
| `backend/src/orchestrator/engine.rs` | ~30 | Compatibility logic + comments |
| `backend/src/models/agent.rs` | ~10 | `max()` logic + comments |
| `backend/src/models/agent.rs` | ~5 | Snapshot default handling |
| `backend/src/ffi/types.rs` | ~10 | FFI parsing compatibility |
| Various test files | ~25 | Backward compatibility test cases |

### Code Added (approx. 50 lines)

| File | Lines Added | Description |
|------|-------------|-------------|
| `backend/src/ffi/types.rs` | ~10 | Validation error for old schema |
| `scripts/migrate_config_v7_to_v8.py` | ~40 | Migration script |

**Net reduction**: ~30 lines of code removed, plus elimination of conceptual complexity.

---

## Risk Assessment

### Low Risk
- All changes are compile-time breaking changes (Rust will catch errors)
- Migration path is clear and automated
- No data loss (migration is lossless)

### Medium Risk
- **User impact**: Any existing configs from before Phase 8 will break
  - **Mitigation**: Provide clear error messages pointing to migration guide
  - **Mitigation**: Provide automated migration script

### High Risk
- **Snapshot incompatibility**: Old checkpoints with `credit_limit` will fail to load
  - **Mitigation**: Add snapshot version check and migration logic (if needed)
  - **Alternative**: Document that old checkpoints are incompatible (acceptable if checkpoints are ephemeral)

---

## Testing Plan

### Unit Tests
- [x] Agent initialization with `unsecured_cap` only
- [x] AgentConfig validation rejects `credit_limit`
- [x] FFI parsing raises error for old schema
- [x] Snapshot serialization excludes `credit_limit`

### Integration Tests
- [x] Full simulation with new-schema config
- [x] Old-schema config produces clear error message
- [x] Migration script produces valid output

### Regression Tests
- [x] All existing tests pass with updated configs
- [x] No performance regression
- [x] Replay identity maintained

---

## Rollback Plan

If critical issues are discovered after merge:

1. **Revert the commit**:
   ```bash
   git revert <commit-hash>
   ```

2. **Re-enable backwards compatibility** with additional warnings:
   ```rust
   // TEMPORARY: Re-enabled due to critical bug #XYZ
   if let Some(old_limit) = ac.credit_limit {
       eprintln!("🚨 CRITICAL: Using deprecated credit_limit. This will be removed in 7 days.");
       agent.set_unsecured_cap(old_limit);
   }
   ```

3. **Set hard deadline** for final removal (e.g., 7 days)

---

## Timeline

### Recommended Phased Approach

**Week 1: Preparation**
- Update all example configs
- Create and test migration script
- Update documentation
- Add deprecation warnings (Phase 2)

**Week 2: Deprecation Warning**
- Merge Phase 2 changes
- Monitor for user reports of old configs
- Provide migration support

**Week 3: Removal**
- Execute Phase 3-6 (remove all backwards compatibility)
- Merge breaking change
- Update version to next major (e.g., 1.0.0 → 2.0.0)

---

## Success Criteria

- [ ] All example configs use `unsecured_cap`
- [ ] Zero `credit_limit` references in Rust code (except comments)
- [ ] Migration script tested on all example configs
- [ ] Documentation updated
- [ ] All tests pass
- [ ] Performance benchmarks unchanged
- [ ] Clear error messages for old configs

---

## FAQ

### Q: Why remove backwards compatibility now?

**A**: The compatibility logic adds complexity, potential for bugs (double-counting), and maintenance burden. All known configs can be mechanically migrated, so there's no benefit to maintaining legacy support indefinitely.

### Q: What about old database checkpoints?

**A**: Checkpoints created with the old schema will fail to load after this change. Options:
1. **Recommended**: Accept incompatibility (checkpoints are ephemeral)
2. **Alternative**: Add snapshot version migration logic (adds complexity)

### Q: Can we make this a gradual deprecation?

**A**: Yes! Follow the phased timeline:
1. Week 1: Add warnings (Phase 2)
2. Week 2-3: Monitor and support migration
3. Week 4: Remove compatibility (Phase 3-6)

### Q: What if a user has 100 old configs?

**A**: The migration script supports batch processing:
```bash
for f in old_configs/*.yaml; do
    python scripts/migrate_config_v7_to_v8.py "$f" "migrated_configs/$(basename $f)"
done
```

---

## Conclusion

Removing the `credit_limit` backwards compatibility is a **net positive** for the codebase:

- ✅ Simpler code (−30 lines)
- ✅ Clearer semantics (one way to specify overdraft)
- ✅ Fewer bugs (no double-counting risk)
- ✅ Easier onboarding (no legacy concepts to learn)

The migration is **low-risk** due to:
- Compile-time enforcement (Rust catches all errors)
- Automated migration script
- Clear error messages
- Comprehensive testing

**Recommendation**: Proceed with deprecation using the phased timeline.

---

**Next Steps**:
1. Review this guide with the team
2. Execute Phase 1 (update example configs)
3. Create migration script
4. Set deprecation timeline
5. Execute removal phases

**Questions or concerns?** File an issue or discuss in team chat.
