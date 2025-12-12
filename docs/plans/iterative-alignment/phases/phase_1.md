# Phase 1: Minimal Field Set for Castro Initial Liquidity Game

## Goal

Create a minimal configuration for the Castro 2-period Initial Liquidity Game that gives the LLM the clearest possible signal to find the Nash equilibrium.

## TDD Approach

### Test 1: Verify Transaction Schedule Matches Paper

**File**: `api/tests/castro/test_castro_equilibrium.py`

```python
def test_transaction_schedule_matches_paper():
    """Verify exp1_2period.yaml matches Castro paper Section 6.3."""
    # Agent A: P^A = [0, 0.15] → 0 at tick 0, 15000 at tick 1
    # Agent B: P^B = [0.15, 0.05] → 15000 at tick 0, 5000 at tick 1

    # Bank A sends to Bank B: 15000 at tick 1
    # Bank B sends to Bank A: 15000 at tick 0, 5000 at tick 1

    config = load_scenario("experiments/castro/configs/exp1_2period.yaml")
    events = config["scenario_events"]

    # Verify Bank A outgoing
    a_to_b = [e for e in events if e["from_agent"] == "BANK_A"]
    assert len(a_to_b) == 1
    assert a_to_b[0]["amount"] == 15000
    assert a_to_b[0]["schedule"]["tick"] == 1

    # Verify Bank B outgoing
    b_to_a = [e for e in events if e["from_agent"] == "BANK_B"]
    assert len(b_to_a) == 2
    # 15000 at tick 0, 5000 at tick 1
```

### Test 2: Verify Optimal Policy Achieves Expected Costs

**File**: `api/tests/castro/test_castro_equilibrium.py`

```python
def test_optimal_policy_costs():
    """Verify Nash equilibrium policy achieves theoretical minimum costs."""
    # Bank A posts 0 collateral → receives 15000 from B → pays 15000 to B
    # Bank A cost = 0 (no collateral, uses incoming payment)

    # Bank B posts 20000 collateral → pays 15000+5000 = 20000
    # Bank B cost = collateral_cost_per_tick_bps * 20000 * ticks

    optimal_a_policy = create_optimal_bank_a_policy()  # posts 0
    optimal_b_policy = create_optimal_bank_b_policy()  # posts 20000

    result = run_simulation(
        scenario="exp1_2period.yaml",
        policies={"BANK_A": optimal_a_policy, "BANK_B": optimal_b_policy}
    )

    # Bank A should have near-zero cost
    assert result.costs["BANK_A"] < 100  # Small tolerance

    # Bank B's cost should be exactly collateral cost
    expected_b_cost = 20000 * 0.05 * 2  # 500 bps * 20000 * 2 ticks
    assert abs(result.costs["BANK_B"] - expected_b_cost) < 100
```

### Test 3: Verify Suboptimal Policy Is Penalized

```python
def test_suboptimal_policy_has_higher_cost():
    """If Bank A posts collateral when it doesn't need to, cost should increase."""
    suboptimal_a_policy = create_policy_with_collateral(amount=10000)
    optimal_a_policy = create_policy_with_collateral(amount=0)

    result_suboptimal = run_simulation(policies={"BANK_A": suboptimal_a_policy, ...})
    result_optimal = run_simulation(policies={"BANK_A": optimal_a_policy, ...})

    assert result_suboptimal.costs["BANK_A"] > result_optimal.costs["BANK_A"]
```

### Test 4: Verify Minimal Field Set Is Sufficient

```python
def test_minimal_field_set():
    """Ensure minimal fields can express optimal policy."""
    minimal_fields = [
        "system_tick_in_day",     # Distinguish t=0 from t=1
        "balance",                # Current liquidity
        "remaining_collateral_capacity",  # Available to post
        "posted_collateral",      # Already posted
        "ticks_to_deadline",      # For payment decisions
    ]

    # Verify optimal policy can be expressed with just these fields
    optimal_policy = create_optimal_policy_minimal_fields()

    for field in get_fields_used_in_policy(optimal_policy):
        assert field in minimal_fields, f"Policy uses non-minimal field: {field}"
```

## Implementation Steps

### Step 1: Create Test File

Create `api/tests/castro/test_castro_equilibrium.py` with tests above.

### Step 2: Create Simplified exp1.yaml

Modify `experiments/castro/experiments/exp1.yaml`:

**Before (too many fields):**
```yaml
policy_constraints:
  allowed_fields:
    - system_tick_in_day
    - ticks_remaining_in_day
    - current_tick
    - balance
    - effective_liquidity
    - ticks_to_deadline
    - remaining_amount
    - amount
    - priority
    - queue1_total_value
    - outgoing_queue_size
    - max_collateral_capacity
    - posted_collateral
```

**After (minimal):**
```yaml
policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
      description: "Fraction of max_collateral_capacity to post at t=0"

  allowed_fields:
    - system_tick_in_day           # Distinguish t=0 (post collateral) from t>=1
    - balance                      # Current settlement account balance
    - remaining_collateral_capacity  # How much more collateral can be posted
    - posted_collateral            # Already posted amount
    - ticks_to_deadline            # For payment release decisions

  allowed_actions:
    payment_tree:
      - Release
      - Hold
    strategic_collateral_tree:
      - PostCollateral
      - HoldCollateral
```

### Step 3: Enable Castro Mode

Add `castro_mode: true` to experiment config and ensure system prompt uses it.

### Step 4: Create Optimal Seed Policies

Create seed policies that represent:
1. **Optimal Bank A**: Post 0 collateral at t=0, always release payments
2. **Optimal Bank B**: Post 20000 collateral at t=0, always release payments
3. **Suboptimal variants**: For comparison testing

### Step 5: Run Tests

```bash
cd api
.venv/bin/python -m pytest tests/castro/test_castro_equilibrium.py -v
```

## Files to Create/Modify

1. **Create**: `api/tests/castro/__init__.py`
2. **Create**: `api/tests/castro/test_castro_equilibrium.py`
3. **Modify**: `experiments/castro/experiments/exp1.yaml`
4. **Create**: `experiments/castro/policies/optimal_bank_a.json`
5. **Create**: `experiments/castro/policies/optimal_bank_b.json`

## Success Criteria

- [ ] All TDD tests pass
- [ ] Optimal policy achieves expected costs (A~0, B~2000)
- [ ] Minimal field set is documented and working
- [ ] Experiment runs without validation errors

## Time Estimate

~2-3 hours for implementation and testing

## Dependencies

- Rust simulator must be built (`uv sync --extra dev`)
- Experiment runner must be working
