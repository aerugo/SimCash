# Policy Evolution Display — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 2, Items 5-7

## Goal

Show how policies evolve across days during LLM optimization: a timeline of policy versions, parameter trajectory charts, and diff view between days. The data already exists in the game state — this is about surfacing it in the UI.

## Web Invariants

- **WEB-INV-1**: Policy Reality — displayed policy versions must match what the engine executed
- **WEB-INV-2**: Agent Isolation — each agent's policy evolution shown independently

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/components/PolicyTimeline.tsx` | Horizontal timeline showing policy versions per day with accept/reject status |
| `web/frontend/src/components/PolicyDiff.tsx` | Side-by-side diff of two policy JSON versions |
| `web/frontend/src/components/ParameterChart.tsx` | Line chart of parameter values over days |
| `web/frontend/src/components/PolicyTreeView.tsx` | Render a policy decision tree as a nested visual |
| `web/backend/app/policy_diff.py` | Compute structural diff between two policy JSONs |
| `web/backend/tests/test_policy_diff.py` | Tests for diff logic |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/main.py` | Add `/api/games/{id}/policy-history` and `/api/games/{id}/policy-diff` endpoints |
| `web/backend/app/game.py` | Ensure policy versions are stored per day per agent |
| `web/frontend/src/views/GameView.tsx` | Add Policy Evolution tab/panel |
| `web/frontend/src/types.ts` | Add policy history types |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: policy history endpoint + diff logic | 2h | 10 tests |
| 2 | Frontend: PolicyTimeline + ParameterChart | 3h | tsc + build |
| 3 | Frontend: PolicyDiff + PolicyTreeView | 3h | tsc + build |
| 4 | Integration + UI protocol | 1h | UI protocol |

## Phase 1: Backend — Policy History & Diff

### Policy History Endpoint

```
GET /api/games/{id}/policy-history?agent_id=BANK_A
→ {
    "agent_id": "BANK_A",
    "days": [
      {
        "day": 0,
        "policy": { ... },
        "parameters": {"initial_liquidity_fraction": 1.0},
        "status": "initial",
        "cost": 99600
      },
      {
        "day": 1,
        "policy": { ... },
        "parameters": {"initial_liquidity_fraction": 0.45},
        "status": "accepted",  // "accepted" | "rejected" | "initial" | "no_optimization"
        "cost": 52300,
        "reasoning_summary": "Reduced liquidity to save costs..."
      }
    ]
  }
```

### Policy Diff Logic (`policy_diff.py`)

```python
def diff_policies(old: dict, new: dict) -> PolicyDiff:
    """Compute structural diff between two policy JSONs."""
    # Returns: changed_parameters, added_nodes, removed_nodes, modified_conditions
```

```
GET /api/games/{id}/policy-diff?agent_id=BANK_A&day_a=2&day_b=3
→ {
    "changed_parameters": [
      {"name": "initial_liquidity_fraction", "old": 0.45, "new": 0.38}
    ],
    "tree_changes": {
      "payment_tree": "unchanged",
      "bank_tree": "modified"  // or "unchanged" | "added" | "removed"
    },
    "node_changes": [
      {"node_id": "N1", "change": "condition_modified", "old": "balance > 500000", "new": "balance > 300000"}
    ]
  }
```

### Tests

1. `test_diff_identical_policies` — no changes detected
2. `test_diff_parameter_change` — parameter change detected
3. `test_diff_action_change` — Release → Hold detected
4. `test_diff_condition_change` — threshold change detected
5. `test_diff_tree_added` — new tree appears (e.g., bank_tree added)
6. `test_diff_node_added` — new condition node inserted
7. `test_diff_node_removed` — condition node removed (simplified)
8. `test_history_endpoint_returns_all_days` — correct day count
9. `test_history_endpoint_agent_isolation` — BANK_A history ≠ BANK_B history
10. `test_history_endpoint_includes_status` — accepted/rejected markers present

## Phase 2: Frontend — Timeline + Parameter Chart

**PolicyTimeline.tsx**: Horizontal scrollable timeline with day markers. Each day shows:
- Day number
- Status icon: ⭐ best, ✅ accepted, ❌ rejected, ⏸ no optimization
- Key parameter value as tooltip
- Click to select day (shows full policy below)

**ParameterChart.tsx**: recharts LineChart showing parameter trajectories:
- X axis: day number
- Y axis: parameter value
- One line per parameter
- Markers for accepted (green) vs rejected (red) days
- Tooltip with exact values

## Phase 3: Frontend — Diff + Tree View

**PolicyDiff.tsx**: Two-column layout:
- Left: Day N policy (with changed sections highlighted red)
- Right: Day N+1 policy (changed sections highlighted green)
- Parameter changes shown as a summary table above
- Tree structure changes annotated

**PolicyTreeView.tsx**: Render a policy JSON as a visual tree:
- Condition nodes: diamond shape with expression text
- Action nodes: rectangle with action name + parameters
- Lines connecting parent to children (true/false branches)
- Depth-based indentation (CSS tree, not SVG)

## Phase 4: Integration + UI Protocol

### UI Test Protocol

```
Protocol: W2-Policy-Evolution
Wave: 2

1. Create a game with real or mock LLM optimization
2. Run 5 days
3. Navigate to Policy Evolution tab
4. VERIFY: Timeline shows 5 day markers
5. VERIFY: Day 0 marked as "initial"
6. VERIFY: At least one day shows "accepted" or "rejected"
7. Click day 3
8. VERIFY: Full policy JSON displayed
9. VERIFY: Parameter values shown
10. Switch to Parameter Chart tab
11. VERIFY: Line chart shows parameter values over 5 days
12. VERIFY: Accepted/rejected markers visible
13. Open diff between day 2 and day 3
14. VERIFY: Changed parameters highlighted
15. VERIFY: If no changes, diff says "identical"
16. Open PolicyTreeView for day 3's policy
17. VERIFY: Tree structure renders (condition/action nodes visible)

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] Policy history endpoint returns all days with correct status
- [ ] Diff logic correctly identifies parameter, condition, and structural changes
- [ ] Timeline visually shows policy evolution
- [ ] Parameter chart renders trajectories
- [ ] Agent isolation: each agent's history is independent
- [ ] WEB-INV-1 verified: displayed policies match stored policies
