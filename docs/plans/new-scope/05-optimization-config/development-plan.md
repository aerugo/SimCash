# Optimization Configuration — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 3, Items 9-10

## Goal

Make two things configurable: (1) how often optimization occurs (every N days, manual, or event-triggered) and (2) how much freedom the LLM has (constraint depth presets from "simple: one float" to "full: all actions and conditions").

## Web Invariants

- **WEB-INV-1**: Policy Reality — wider constraints must produce policies the engine actually executes
- **WEB-INV-4**: Cost Consistency — changing optimization interval must not break cost accounting

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/constraint_presets.py` | Predefined constraint sets: Simple, Standard, Full, Castro |
| `web/backend/tests/test_optimization_config.py` | Tests for interval logic and constraint presets |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/game.py` | Add `optimization_interval` to Game, skip optimization on non-optimization days |
| `web/backend/app/streaming_optimizer.py` | Accept constraint preset, pass wider constraints to PolicyOptimizer |
| `web/backend/app/main.py` | Accept optimization config in game creation |
| `web/backend/app/models.py` | Add optimization config fields to CreateGameRequest |
| `web/frontend/src/components/GameConfigPanel.tsx` | Add interval + constraint depth selectors |
| `web/frontend/src/types.ts` | Add optimization config types |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: optimization interval in Game | 2h | 8 tests |
| 2 | Backend: constraint presets | 2h | 10 tests |
| 3 | Frontend: config UI + integration | 2h | tsc + build + UI protocol |

## Phase 1: Optimization Interval

### Changes to `game.py`

```python
class Game:
    def __init__(self, ..., optimization_interval: int = 1):
        self.optimization_interval = optimization_interval
    
    def should_optimize(self, day_num: int) -> bool:
        """Returns True if this day should trigger LLM optimization."""
        if self.optimization_interval <= 0:
            return False  # manual mode
        return day_num > 0 and day_num % self.optimization_interval == 0
```

In `run_day()`, wrap the optimization call:
```python
if self.use_llm and self.should_optimize(day_num):
    # run optimization
else:
    # play with current policy (no LLM call)
```

### Tests

1. `test_interval_1_optimizes_every_day` — days 1,2,3,4 all optimize
2. `test_interval_3_skips_days` — day 1,2 skip, day 3 optimizes, day 4,5 skip, day 6 optimizes
3. `test_interval_0_never_optimizes` — manual mode, no optimization ever
4. `test_day_0_never_optimizes` — first day always plays default policy
5. `test_skipped_days_use_current_policy` — on non-optimization days, policy unchanged
6. `test_optimization_day_may_change_policy` — on optimization days, policy can change
7. `test_interval_in_game_creation` — POST /api/games accepts optimization_interval
8. `test_interval_default_is_1` — backward compatible

## Phase 2: Constraint Presets

### Constraint Presets (`constraint_presets.py`)

```python
CONSTRAINT_PRESETS = {
    "simple": {
        "name": "Simple (Liquidity Only)",
        "description": "Optimize initial_liquidity_fraction. Payment tree stays Release-all.",
        "allowed_parameters": [
            {"name": "initial_liquidity_fraction", "param_type": "float", "min_value": 0.0, "max_value": 1.0}
        ],
        "allowed_fields": [],
        "allowed_actions": {
            "payment_tree": ["Release"],
            "bank_tree": ["NoAction"]
        }
    },
    "standard": {
        "name": "Standard (Release/Hold/Split)",
        "description": "Optimize liquidity fraction + payment timing decisions.",
        "allowed_parameters": [
            {"name": "initial_liquidity_fraction", ...},
            {"name": "urgency_threshold", "param_type": "int", "min_value": 0, "max_value": 20},
            {"name": "liquidity_buffer", "param_type": "float", "min_value": 0.0, "max_value": 5.0}
        ],
        "allowed_fields": [
            "balance", "effective_liquidity", "ticks_to_deadline", "amount",
            "priority", "queue1_total_value", "ticks_remaining_in_day", "day_progress_fraction"
        ],
        "allowed_actions": {
            "payment_tree": ["Release", "Hold", "Split"],
            "bank_tree": ["SetReleaseBudget", "NoAction"]
        }
    },
    "full": {
        "name": "Full (All Actions)",
        "description": "Maximum LLM freedom. All actions, fields, and tree types.",
        "allowed_parameters": [...],  # 10+ parameters
        "allowed_fields": [...],      # 30+ fields
        "allowed_actions": {
            "payment_tree": ["Release", "Hold", "Split", "StaggerSplit", "ReleaseWithCredit", "Reprioritize"],
            "bank_tree": ["SetReleaseBudget", "SetState", "AddState", "NoAction"],
            "strategic_collateral_tree": ["PostCollateral", "WithdrawCollateral", "HoldCollateral"],
            "end_of_tick_collateral_tree": ["PostCollateral", "WithdrawCollateral", "HoldCollateral"]
        }
    },
    "castro": {
        "name": "Castro Paper (Replication)",
        "description": "Exact constraints from Castro et al. (2025).",
        ...  # matches CASTRO_CONSTRAINTS from existing codebase
    }
}
```

### Tests

1. `test_simple_preset_allows_only_fraction` — validate Release-only
2. `test_standard_preset_allows_hold` — Hold is allowed
3. `test_standard_preset_allows_conditions` — fields list enables condition nodes
4. `test_full_preset_allows_all_trees` — 4 tree types present
5. `test_full_preset_allows_collateral` — collateral actions present
6. `test_castro_preset_matches_paper` — identical to CASTRO_CONSTRAINTS
7. `test_preset_in_game_creation` — POST /api/games accepts constraint_preset
8. `test_preset_feeds_into_optimizer` — streaming_optimizer uses the constraints
9. `test_wider_constraints_produce_complex_policy` — with real/mock LLM, standard preset → policy has conditions (not just Release)
10. `test_simple_constraints_reject_hold` — policy with Hold action rejected under simple preset

## Phase 3: Frontend + Integration

### GameConfigPanel additions

```
Optimization Settings:
  Interval: [Every day ▾] (1/2/5/custom/manual)
  Constraint Depth: [Simple ▾] (Simple/Standard/Full/Castro)
    ℹ️ "Simple: Tune liquidity fraction only"
    ℹ️ "Standard: Release/Hold/Split with conditions"  
    ℹ️ "Full: All actions and tree types"
```

Tooltips explain what each level allows.

### UI Test Protocol

```
Protocol: W3-Optimization-Config
Wave: 3

1. Create game with interval=3, constraint_depth="standard"
2. Step through days 0-6
3. VERIFY: Day 0 plays default policy
4. VERIFY: Days 1-2 show "Playing with current policy" (no reasoning panel activity)
5. VERIFY: Day 3 triggers optimization (reasoning panel shows LLM output)
6. VERIFY: Optimized policy has condition nodes (not just Release-all)
7. VERIFY: Days 4-5 use day 3's policy without optimization
8. VERIFY: Day 6 triggers optimization again
9. Create another game with constraint_depth="simple"
10. Run 3 days with optimization
11. VERIFY: Policy changes are parameter-only (no conditions added)

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] Optimization interval controls when LLM is called
- [ ] Skipped days play with current policy (no LLM cost)
- [ ] Constraint presets produce appropriately complex policies
- [ ] Wider constraints → policies with conditions; simple → parameter only
- [ ] WEB-INV-1: complex policies actually execute in the engine
