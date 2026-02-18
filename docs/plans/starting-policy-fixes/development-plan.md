# Starting Policy Fixes — Development Plan

## Problem Statement

The Starting Policy feature (Wave 2B) has three connected issues stemming from one root cause: **library policy files lack `initial_liquidity_fraction`, which is the key parameter the game engine needs.**

### How the System Works (from docs)

The SimCash engine has two independent controls per agent:

1. **`liquidity_allocation_fraction`** — top-level agent config field (0.0–1.0). Determines what fraction of `liquidity_pool` to allocate at day start. This is the **BIS Box 3 liquidity-delay trade-off** knob.

2. **`policy`** — decision tree for per-tick payment processing (Release/Hold/Split). Configured via `Fifo`, `FromJson`, `InlineJson`, etc.

The **LLM optimization system** (ai_cash_mgmt) bridges these: the `CASTRO_CONSTRAINTS` define `initial_liquidity_fraction` as an allowed parameter (`float, 0.0–1.0, default 0.25`). When the LLM generates a policy, it includes `initial_liquidity_fraction` in the `parameters` block. The web backend's `game.py` then reads this parameter and sets `agent_cfg["liquidity_allocation_fraction"]` accordingly.

### The Gap

**Library policies** (`simulator/policies/*.json`) are hand-crafted decision tree examples. They define tree parameters like `urgency_threshold`, `buffer_multiplier`, etc., but do NOT include `initial_liquidity_fraction` because:
- They were written as tree logic examples, not full game policies
- `initial_liquidity_fraction` is a game-level allocation concept, not a tree evaluation parameter
- The tree parameters are used during per-tick evaluation; the fraction is used once at day start

When the Starting Policies feature sends a library policy to `game.py`, the backend does:
```python
fraction = policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
```
This always returns 1.0 for library policies → agents commit 100% of pool → the tree's Hold/Release logic barely matters.

### Symptoms

| # | Symptom | Cause |
|---|---------|-------|
| 1 | Dropdown shows "frac=?" | `parameters.initial_liquidity_fraction` missing from library files |
| 2 | Day 0 shows fraction=1.0 with any starting policy | Backend defaults missing fraction to 1.0 |
| 3 | Starting policies don't meaningfully change Day 1 | Same — fraction is always 1.0 regardless of tree |

## Fix Design

### Phase 1: Add `initial_liquidity_fraction` to library policies

The simplest, most correct fix: **add `initial_liquidity_fraction` to each library policy file's `parameters` block.** This makes library policies work the same way LLM-generated policies do.

Each policy gets a fraction that matches its character:

| Policy | Fraction | Rationale |
|--------|----------|-----------|
| `fifo` | 1.0 | FIFO commits everything (baseline) |
| `aggressive_market_maker` | 0.35 | Low liquidity, high throughput |
| `cautious_liquidity_preserver` | 0.70 | High buffer, conservative |
| `balanced_cost_optimizer` | 0.50 | Balanced starting point |
| `deadline` | 0.50 | Moderate — holds until urgent |
| `liquidity_aware` | 0.60 | Slightly conservative |
| `liquidity_splitting` | 0.55 | Moderate — splitting reduces per-payment needs |
| `efficient_splitting` | 0.50 | Balanced |
| `momentum_investment_bank` | 0.40 | Aggressive momentum strategy |
| `goliath_national_bank` | 0.30 | Large bank, minimal allocation needed |
| `smart_budget_manager` | 0.45 | Budget-conscious |
| `adaptive_liquidity_manager` | 0.50 | Adaptive — starts balanced |
| `sophisticated_adaptive_bank` | 0.45 | Sophisticated — slightly lean |
| Target2 variants | 0.50–0.65 | Depends on strategy |

**File changes**: Each `simulator/policies/*.json` gets `"initial_liquidity_fraction": X.XX` added to its `parameters` block.

**Why this is correct**: The LLM optimization system already treats `initial_liquidity_fraction` as a policy parameter. Library policies should too — they're meant to be complete, usable policies. A tree without a fraction is like a car without fuel.

**Note**: This touches files outside `web/` (the `simulator/policies/` directory). These are data files, not engine code — no invariants at risk. But flag for Hugi's approval.

**Tests**:
- `test_all_library_policies_have_fraction` — Every policy in `simulator/policies/` must have `parameters.initial_liquidity_fraction` (0.0–1.0)
- `test_library_fraction_matches_character` — Spot-check that aggressive policies have low fractions, conservative have high

### Phase 2: Frontend displays fraction correctly

**File: `web/frontend/src/views/HomeView.tsx`**

The dropdown already reads `p.parameters.initial_liquidity_fraction`. Once Phase 1 adds the field, "frac=?" becomes "frac=0.35" automatically. No code change needed for the display fix.

**Additionally**: Add a per-agent fraction override slider so users can tweak the starting fraction:

```
BANK_A  [Aggressive Market Maker ▾]  frac=0.35  [====|-------] 0.35
BANK_B  [Default (FIFO)          ▾]  frac=1.00  [============] 1.00  
BANK_C  [Cautious Preserver      ▾]  frac=0.70  [========|---] 0.70
```

- Selecting a policy auto-fills the slider with its `initial_liquidity_fraction`
- User can override (0.00–1.00, step 0.05)
- Override fraction is injected into the policy JSON before sending to backend

**State change**:
```typescript
// Before:
agentPolicies: Record<string, string>  // agent_id → policy_id

// After:  
agentPolicies: Record<string, { policyId: string; fraction: number }>
```

**Tests**:
- Selecting a policy updates fraction slider to library value
- Manual fraction override persists across policy re-selections
- Launch payload includes overridden fraction in policy JSON

### Phase 3: Backend applies fraction from starting policy

**File: `web/backend/app/game.py`**

The current code already works correctly IF the policy JSON contains `initial_liquidity_fraction`:
```python
fraction = policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
agent_cfg["liquidity_allocation_fraction"] = fraction
agent_cfg["policy"] = {"type": "InlineJson", "json_string": json.dumps(policy)}
```

After Phase 1, library policies will have this field. After Phase 2, the frontend may override it. No backend changes needed — the frontend injects the fraction into the policy JSON string before sending.

**Verification tests**:
- `test_starting_policy_fraction_applied` — Day 0 state shows fraction from starting policy
- `test_starting_policy_fraction_reaches_engine` — Engine's `liquidity_allocation_fraction` matches policy's fraction
- `test_starting_policy_override_fraction` — Frontend-overridden fraction takes effect

## Implementation Order

1. **Phase 1** (5 min): Add `initial_liquidity_fraction` to all 29 policy files. Write validation test.
2. **Phase 2** (30 min): Add fraction slider to HomeView. Wire fraction into launch payload.
3. **Phase 3** (15 min): Write integration tests verifying fraction flows through to engine.

## Scope

- **Files modified**: 29 policy JSON files, 1 frontend component, 1 test file
- **New files**: 0
- **Estimated effort**: ~1 hour
- **Risk**: Low — additive data changes to policy files, no engine code changes

## Not In Scope

- Changing how LLM optimization outputs fractions (already works)
- Changing the Rust engine (not needed)
- Adding fraction as a separate API field (unnecessary — it's already a policy parameter)
