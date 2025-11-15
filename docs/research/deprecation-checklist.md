# Backwards Compatibility Removal Checklist

**Reference Guide**: See `deprecate-backwards-compatibility-guide.md` for full context.

**Quick Reference**: Use this checklist when executing the actual deprecation.

---

## Files to Modify

### Rust Backend

#### 1. `backend/src/orchestrator/engine.rs`

**Lines 138-168**: AgentConfig struct
```rust
// REMOVE:
pub credit_limit: i64,

// CHANGE:
pub unsecured_cap: Option<i64>,  // FROM: Optional
// TO:
pub unsecured_cap: i64,          // TO: Required
```

**Lines 809-818**: Agent initialization backwards compatibility
```rust
// DELETE ENTIRE BLOCK (10 lines):
// BACKWARD COMPATIBILITY: If unsecured_cap not specified but credit_limit is,
// set unsecured_cap = credit_limit ...
if let Some(cap) = ac.unsecured_cap {
    agent.set_unsecured_cap(cap);
} else if ac.credit_limit > 0 {
    agent.set_unsecured_cap(ac.credit_limit);
}

// REPLACE WITH:
agent.set_unsecured_cap(ac.unsecured_cap);
```

**Line ~800**: Agent::new() call
```rust
// CHANGE:
let mut agent = Agent::new(ac.id.clone(), ac.opening_balance, ac.credit_limit);
// TO:
let mut agent = Agent::new(ac.id.clone(), ac.opening_balance);
```

---

#### 2. `backend/src/models/agent.rs`

**Agent struct definition** (find and remove):
```rust
// REMOVE THIS FIELD:
pub credit_limit: i64,
```

**Lines 555-559**: available_liquidity() method
```rust
// DELETE:
// BACKWARD COMPATIBILITY: Use MAX(credit_limit, unsecured_cap) ...
let unsecured_headroom = self.credit_limit.max(self.unsecured_cap);

// REPLACE WITH:
let unsecured_headroom = self.unsecured_cap;
```

**Line 336**: from_snapshot() default
```rust
// REMOVE THIS LINE:
unsecured_cap: 0, // Default for snapshots (backward compatibility)

// Agent::from_snapshot() signature - REMOVE parameter:
pub fn from_snapshot(
    id: String,
    balance: i64,
    credit_limit: i64,  // ← REMOVE THIS
    unsecured_cap: i64,
    // ...
)
```

**Agent::new() signature**:
```rust
// CHANGE:
pub fn new(id: String, opening_balance: i64, credit_limit: i64) -> Self {
    Agent {
        credit_limit,  // ← REMOVE
        unsecured_cap: 0,
        // ...
    }
}

// TO:
pub fn new(id: String, opening_balance: i64) -> Self {
    Agent {
        unsecured_cap: 0,  // Default to no overdraft
        // ...
    }
}
```

---

#### 3. `backend/src/ffi/types.rs`

**Lines 175-210**: parse_agent_config()
```rust
// CHANGE:
let credit_limit: i64 = extract_required(py_agent, "credit_limit")?;
let unsecured_cap: Option<i64> = extract_optional(py_agent, "unsecured_cap")?;

// TO:
let unsecured_cap: i64 = extract_required(py_agent, "unsecured_cap")?;

// ADD VALIDATION:
if py_agent.contains("credit_limit")? {
    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
        format!(
            "Agent '{}': 'credit_limit' field is no longer supported. \
             Use 'unsecured_cap' instead. See docs/research/deprecate-backwards-compatibility-guide.md",
            id
        )
    ));
}
```

---

#### 4. `backend/src/ffi/orchestrator.rs`

**Search for**: `"credit_limit"`

**Action**: Remove all dict insertions for credit_limit in FFI serialization functions (e.g., get_agent_snapshot, get_all_agents, etc.)

```rust
// REMOVE LINES LIKE:
dict.insert("credit_limit".to_string(), agent.credit_limit.into());
```

---

### Example Configurations

#### 5. `examples/configs/advanced_policy_crisis.yaml`

**All 4 agents** (METRO_CENTRAL, REGIONAL_TRUST, MOMENTUM_CAPITAL, CORRESPONDENT_HUB):
```yaml
# CHANGE:
credit_limit: 2000000

# TO:
unsecured_cap: 2000000
```

---

### Documentation

#### 6. `README.md`

**Lines 520-521, 705, 709**: Example configs
```yaml
# CHANGE:
credit_limit: 200000

# TO:
unsecured_cap: 200000
```

---

#### 7. `CLAUDE.md`

**Action**: Remove the "Backwards Compatibility Logic Explained" section

**Add**: Breaking changes note (see deprecation guide for template)

---

#### 8. `docs/policy_dsl_guide.md`

**Line 895**: Update field reference
```markdown
# CHANGE:
| `available_liquidity` | `f64` (cents) | ⚠️ **Deprecated**: `balance + credit_limit + ...` |

# TO:
| `available_liquidity` | `f64` (cents) | `balance + unsecured_cap + posted_collateral` ... |
```

---

### Tests

#### 9. Search and Replace in All Test Files

**Command**:
```bash
cd backend
grep -rl "credit_limit" tests/ | xargs sed -i 's/credit_limit/unsecured_cap/g'

cd api
grep -rl "credit_limit" tests/ | xargs sed -i 's/credit_limit/unsecured_cap/g'
```

**Manual review required**: Verify no semantic changes (e.g., test names might reference "credit_limit" as a concept)

---

#### 10. Update Test Fixtures

**Pattern to find**:
```rust
// In Rust tests
let config = AgentConfig {
    id: "BANK_A".to_string(),
    opening_balance: 1_000_000,
    credit_limit: 200_000,
    unsecured_cap: None,
    // ...
};

// CHANGE TO:
let config = AgentConfig {
    id: "BANK_A".to_string(),
    opening_balance: 1_000_000,
    unsecured_cap: 200_000,  // No longer Option
    // ...
};
```

---

#### 11. Remove Backwards Compatibility Tests

**Files to check**:
- `backend/tests/test_release_flags.rs`
- `backend/tests/test_lsm_t2_compliant.rs`

**Action**: Remove tests with names like:
- `test_*_backward_compatible*`
- `test_*_legacy*`
- `test_*_credit_limit*`

**Verify each test** before deletion to ensure it's truly testing backwards compatibility and not a legitimate feature.

---

### Migration Script

#### 12. Create `scripts/migrate_config_v7_to_v8.py`

**See deprecation guide for full script**

**Quick template**:
```python
#!/usr/bin/env python3
import sys
import yaml

def migrate_config(input_path, output_path):
    with open(input_path) as f:
        config = yaml.safe_load(f)

    for agent in config.get("agents", []):
        if "credit_limit" in agent and "unsecured_cap" not in agent:
            agent["unsecured_cap"] = agent["credit_limit"]
            print(f"✓ Migrated {agent['id']}")

    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":
    migrate_config(sys.argv[1], sys.argv[2])
```

---

## Verification Commands

### Before Changes
```bash
# Count references (should be many)
git grep -c "credit_limit" -- '*.rs' '*.py' '*.yaml'
```

### After Changes
```bash
# Count references (should be ~0, except migration script and docs)
git grep "credit_limit" -- '*.rs' '*.py' '*.yaml' | \
    grep -v "migrate_config" | \
    grep -v "deprecate-backwards" | \
    grep -v "deprecation-checklist"

# Should return empty or only comment references
```

### Test Suite
```bash
# Rust
cd backend
cargo test --no-default-features

# Python
cd api
uv run pytest

# Integration
cd api
uv run pytest tests/integration/
```

---

## Execution Order

1. ✅ Create migration script (`scripts/migrate_config_v7_to_v8.py`)
2. ✅ Migrate example configs (`examples/configs/*.yaml`)
3. ✅ Update documentation (`README.md`, `CLAUDE.md`, `docs/*.md`)
4. ✅ Update Rust structs (`AgentConfig`, `Agent`)
5. ✅ Remove backwards compatibility logic (engine.rs, agent.rs)
6. ✅ Update FFI layer (types.rs, orchestrator.rs)
7. ✅ Update tests (search/replace, remove obsolete tests)
8. ✅ Run test suite
9. ✅ Verify with grep (no remaining references)
10. ✅ Commit with breaking change message

---

## Estimated Time

- **Preparation** (migration script, config updates): 1 hour
- **Rust changes** (structs, logic removal): 2 hours
- **Test updates** (fixtures, removal): 1-2 hours
- **Documentation**: 1 hour
- **Testing and verification**: 1 hour

**Total**: 6-7 hours of focused work

---

## Rollback

If issues arise:
```bash
git revert <commit-hash>
```

Or manually restore:
```bash
git checkout HEAD~1 -- backend/src/orchestrator/engine.rs
git checkout HEAD~1 -- backend/src/models/agent.rs
# ... etc
```

---

## Success Criteria

- [ ] Zero compilation errors
- [ ] All tests pass
- [ ] No `credit_limit` in code (except comments/docs/migration)
- [ ] Example configs use new schema
- [ ] Migration script tested on all examples
- [ ] Clear error message when old config is used

---

**Last Updated**: 2025-11-15
**Status**: Ready for execution
**See Also**: `deprecate-backwards-compatibility-guide.md`
