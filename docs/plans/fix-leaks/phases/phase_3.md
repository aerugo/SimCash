# Phase 3: Fix Cost Breakdown Isolation

**Status**: Pending
**Started**:
**Completed**:

---

## Objective

Ensure that the cost breakdown shown to each agent reflects only their own costs, not an aggregate of all agents' costs across the system.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - Cost values remain integer cents
- **INV-10** (NEW): Agent Isolation - Agent X must not see system-wide cost patterns

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Add tests to `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py`:

**Test Cases**:
1. `test_cost_breakdown_is_per_agent` - Cost breakdown reflects agent-specific costs
2. `test_different_agents_get_different_costs` - Agents with different costs see different breakdowns

```python
class TestCostBreakdownIsolation:
    """Tests for cost breakdown isolation.

    Enforces INV-10: Agent Isolation - Only own costs visible.
    """

    def test_cost_breakdown_is_per_agent(self) -> None:
        """Cost breakdown must reflect only the target agent's costs.

        When BANK_A has delay_cost=1000 and BANK_B has delay_cost=5000,
        BANK_A's prompt should show delay_cost=1000, not aggregated.
        """
        # Setup: EnrichedEvaluationResult with per_agent_costs
        # Extract cost breakdown for BANK_A
        # Assert: Reflects BANK_A's costs only

    def test_different_agents_get_different_costs(self) -> None:
        """Different agents must see different cost breakdowns.

        Verifies that cost extraction is truly per-agent.
        """
        # Setup: Results with different per-agent costs
        # Build context for BANK_A and BANK_B separately
        # Assert: Each sees their own costs
```

### Step 3.2: Implement to Pass Tests (GREEN)

The fix requires modifying `api/payment_simulator/experiments/runner/optimization.py`:

**Current Problem** (lines 1936-1956):
```python
# Aggregates ALL agents' costs - WRONG!
total_delay = sum(r.cost_breakdown.delay_cost for r in self._current_enriched_results)
total_overdraft = sum(r.cost_breakdown.overdraft_cost for r in self._current_enriched_results)
# ...
cost_breakdown = {
    "delay_cost": total_delay // num_samples,
    "overdraft_cost": total_overdraft // num_samples,
    # ...
}
```

**Fixed Implementation**:
```python
# Extract per-agent cost breakdown for the target agent
cost_breakdown: dict[str, int] | None = None
if self._current_enriched_results:
    # Use per-agent costs if available
    agent_costs = []
    for result in self._current_enriched_results:
        if result.per_agent_cost_breakdown and agent_id in result.per_agent_cost_breakdown:
            agent_costs.append(result.per_agent_cost_breakdown[agent_id])

    if agent_costs:
        # Average per-agent costs across samples
        num_samples = len(agent_costs)
        cost_breakdown = {
            "delay_cost": sum(c.delay_cost for c in agent_costs) // num_samples,
            "overdraft_cost": sum(c.overdraft_cost for c in agent_costs) // num_samples,
            "deadline_penalty": sum(c.deadline_penalty for c in agent_costs) // num_samples,
            "eod_penalty": sum(c.eod_penalty for c in agent_costs) // num_samples,
        }
    else:
        # Fallback to total costs (backward compatibility)
        # but note this is system-wide, not ideal
        num_samples = len(self._current_enriched_results)
        cost_breakdown = {
            "delay_cost": sum(r.cost_breakdown.delay_cost for r in self._current_enriched_results) // num_samples,
            # ...
        }
```

### Step 3.3: Refactor

- Extract cost aggregation to a helper method
- Ensure type safety
- Add logging for fallback case

---

## Implementation Details

### Prerequisites

Check if `EnrichedEvaluationResult` has `per_agent_cost_breakdown` field:

```python
@dataclass
class EnrichedEvaluationResult:
    # ...
    per_agent_costs: dict[str, int] | None = None  # Already exists
    per_agent_cost_breakdown: dict[str, CostBreakdown] | None = None  # May need to add
```

If `per_agent_cost_breakdown` doesn't exist, we may need to:
1. Add it to the model
2. Populate it during evaluation
3. Or compute it from events

### Fallback Strategy

If per-agent cost breakdown isn't available:
1. Log a warning (this indicates a gap in the system)
2. Fall back to system-wide average (current behavior)
3. Consider this a TODO for future improvement

### Edge Cases to Handle

- `per_agent_cost_breakdown` is None
- Agent not in `per_agent_cost_breakdown`
- Empty results list

---

## Files

| File | Action |
|------|--------|
| `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` | MODIFY - Add cost isolation tests |
| `api/payment_simulator/experiments/runner/optimization.py` | MODIFY - Per-agent cost extraction |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` | POSSIBLY MODIFY - Add per_agent_cost_breakdown if needed |

---

## Verification

```bash
# Run cost-specific tests
cd /home/user/SimCash/api
uv run python -m pytest tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py -v -k "cost"

# Run full test suite
uv run python -m pytest tests/ai_cash_mgmt/unit/ -v

# Type check
uv run python -m mypy payment_simulator/experiments/runner/optimization.py

# Lint
uv run python -m ruff check payment_simulator/experiments/runner/optimization.py
```

---

## Completion Criteria

- [ ] `test_cost_breakdown_is_per_agent` passes
- [ ] `test_different_agents_get_different_costs` passes
- [ ] All existing tests still pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] INV-10 (Agent Isolation) verified for cost breakdown
