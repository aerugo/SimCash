# Plan 04: Starting Policy Selection in Game Setup

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox
**Priority**: P2

## Goal

Allow users to assign **starting policies** to agents when creating a game. Currently all agents start with `fraction = 1.0` (100% FIFO). Users should be able to pick from the policy library, saved custom policies, or keep the default — per agent or for all agents at once.

## Problem

The Policy Editor and Game Setup are completely disconnected. A researcher can build a sophisticated policy (Hold when low balance, ReleaseWithCredit when urgent, PostCollateral as bank action) but has no way to use it as a starting policy in a game. The only entry point for custom policies is via LLM optimization (which starts from fraction=1.0 and evolves).

This matters because:
- Researchers may want to test a **specific** policy hypothesis without waiting for the LLM to discover it
- Comparing FIFO vs a hand-crafted policy in the same scenario is a basic research workflow
- The "Test Policy" button in the Policy Editor creates a bare-bones 1-day game, not a proper multi-day game

## Web Invariants

- **WEB-INV-1 (Policy Reality)**: Starting policies MUST enter the engine via the `InlineJson` path.
- **WEB-INV-2 (Agent Isolation)**: Different agents can have different starting policies.

## Files

### Modified

| File | Changes |
|------|---------|
| `web/backend/app/game.py` | Accept `starting_policies: dict[str, str]` (agent_id → policy JSON string) in game creation. Apply via `InlineJson` path on day 1. |
| `web/backend/app/main.py` | Update `CreateGameRequest` model to include optional `starting_policies`. |
| `web/backend/app/models.py` | Add `starting_policies` field to request model. |
| `web/frontend/src/views/HomeView.tsx` | Add "Starting Policies" section below Game Settings. Per-agent policy selector: "Default (FIFO)" / library policy / custom policy. Collapsible (hidden by default for simplicity). |
| `web/frontend/src/types.ts` | Add `starting_policies` to `GameSetupConfig`. |
| `web/backend/tests/test_game.py` | Add tests for games with starting policies. |

### NOT Modified

| File | Why |
|------|-----|
| `simulator/` | Engine already supports InlineJson policies |
| `web/backend/app/streaming_optimizer.py` | Starting policy is day-1 only; optimizer takes over from day 2 |

## Phase 1: Backend + Frontend Starting Policy Support

**Est. Time**: 4h

### Backend

1. **Update `CreateGameRequest`** (in `models.py` or `main.py`):
   ```python
   starting_policies: dict[str, str] | None = None
   # Maps agent_id → policy JSON string
   # If None or agent missing, use default (fraction=1.0)
   ```

2. **Update `Game.__init__`** (in `game.py`):
   - Accept `starting_policies` parameter
   - On day 1, for each agent: if a starting policy is provided, parse it and:
     - Extract `initial_liquidity_fraction` from `parameters`
     - Set `agent["policy"] = {"type": "InlineJson", "json_string": policy_json}`
     - Set `agent["liquidity_allocation_fraction"] = fraction`
   - This follows Pattern W-2 from PLANNING.md

3. **Validate starting policies** before game start:
   - Each policy JSON must parse as valid JSON
   - Each policy must have `version`, `policy_id`, `parameters.initial_liquidity_fraction`, `payment_tree`
   - Agent IDs in `starting_policies` must match scenario agent IDs

### Frontend

1. **Add collapsible "Starting Policies" section** to HomeView.tsx, below Game Settings:
   ```
   ▶ Starting Policies (click to expand)
   
   [Expanded:]
   BANK_A: [Default (FIFO) ▼]  ← dropdown
   BANK_B: [Default (FIFO) ▼]
   BANK_C: [Default (FIFO) ▼]
   
   [Apply to all: [Default (FIFO) ▼]]
   ```

2. **Dropdown options**:
   - "Default (FIFO)" — no policy sent, backend uses fraction=1.0
   - Library policies (fetched from `/api/policies/library`)
   - Custom saved policies (fetched from `/api/policies/custom`)
   - Each shows: name + fraction value

3. **Agent list is dynamic** — populated from the selected scenario's agent IDs (already available in scenario metadata).

4. **Include in game creation request**:
   ```typescript
   const config: GameSetupConfig = {
     ...existing,
     starting_policies: Object.fromEntries(
       Object.entries(selectedPolicies)
         .filter(([, v]) => v !== 'default')
         .map(([agentId, policyJson]) => [agentId, policyJson])
     ),
   };
   ```

5. **Current Policies panel** on game start should show the starting policy details (not just "fraction = 1.000") — show the policy ID and key actions if a custom policy is assigned.

### Tests

| Test | What it verifies |
|------|------------------|
| `test_create_game_with_starting_policy` | Game created with custom policy, day 1 uses it |
| `test_create_game_default_policy` | Game without starting_policies uses fraction=1.0 |
| `test_create_game_partial_starting_policies` | Some agents custom, some default |
| `test_create_game_invalid_starting_policy_rejected` | Bad JSON in starting policy returns 400 |
| `test_create_game_wrong_agent_id_rejected` | Policy for non-existent agent returns 400 |
| `test_starting_policy_enters_engine` | Day 1 simulation uses InlineJson policy (verify different costs than FIFO) |

### Verification

```bash
cd api && .venv/bin/python -m pytest ../web/backend/tests/test_game.py -v --tb=short
cd web/frontend && npx tsc -b && npm run build
```

### UI Test Protocol

```
Protocol: Starting Policy Selection
Wave: Create Tab Fixes

1. Open http://localhost:5173
2. Select "3 Banks, 6 Ticks" scenario
3. VERIFY: Starting Policies section visible (collapsed)
4. Expand Starting Policies
5. VERIFY: Three agent rows (BANK_A, BANK_B, BANK_C), all set to "Default (FIFO)"
6. For BANK_A, select "Balance-Aware Hold" from library
7. VERIFY: BANK_A shows "Balance-Aware Hold (frac=0.5)"
8. Click Start Game
9. VERIFY: Game starts. Current Policies panel shows BANK_A with "balance_hold" policy (fraction=0.5), BANK_B and BANK_C with fraction=1.0.
10. Click Next Day
11. VERIFY: Day 1 results show different costs for BANK_A vs BANK_B/C (custom policy should produce different behavior).

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] All existing tests pass
- [ ] 6 new tests pass
- [ ] Starting policies enter the Rust engine via InlineJson
- [ ] Per-agent policy selection works
- [ ] Default (no policy selected) preserves current fraction=1.0 behavior
- [ ] Different starting policy produces measurably different day-1 costs
- [ ] UI test protocol passes
