# Phase 8: Investigate Zero Deltas in Bootstrap Paired Evaluation

## Problem Statement

When running experiment 2 with gpt-5.2, the Bootstrap Paired Evaluation shows all deltas as zero:

```
Bootstrap Paired Evaluation (50 samples) - BANK_A:
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Sample ┃ Delta (¢) ┃ Note      ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│     #1 │         0 │ no change │
│     #2 │         0 │ no change │
...
```

The LLM proposes policy changes (e.g., `initial_liquidity_fraction: 0.4` → `0.45`), but the evaluator reports no cost difference.

## Hypotheses

### H1: Policy not being applied in sandbox simulation
The `BootstrapPolicyEvaluator` may not be correctly applying the new policy when running sandbox simulations.

### H2: Sandbox config doesn't use the policy parameter
The `initial_liquidity_fraction` parameter may not affect the sandbox simulation because:
- The sandbox only has 3 agents (SOURCE, AGENT, SINK)
- The parameter might only affect collateral posting at tick 0
- The sandbox may not have collateral mechanics enabled

### H3: Cost calculation ignores the policy effect
The cost breakdown may be computed identically regardless of policy because:
- All transactions settle immediately (100% settlement rate)
- No delay costs accrue
- No overdraft costs accrue

### H4: Same transactions, same outcome
If all transactions settle immediately regardless of policy, the cost will be identical.

## Investigation Steps

### Step 1: Add debug logging to BootstrapPolicyEvaluator

**File:** `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`

Add logging to see:
1. What policy is being passed to each evaluation
2. What sandbox config is generated
3. What costs are computed for each policy

### Step 2: Trace a single sample evaluation

Run a minimal test that:
1. Creates one bootstrap sample
2. Evaluates with policy A (e.g., `initial_liquidity_fraction: 0.5`)
3. Evaluates with policy B (e.g., `initial_liquidity_fraction: 0.1`)
4. Prints detailed cost breakdown for each

### Step 3: Check if SandboxConfigBuilder uses policy parameters

**File:** `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`

Verify:
1. Does `build_sandbox_config()` accept policy parameters?
2. Does it configure the AGENT's opening balance based on `initial_liquidity_fraction`?
3. Is collateral posting enabled in the sandbox?

### Step 4: Verify the scenario has cost sensitivity

Check if exp2's scenario configuration has:
1. Costs that would vary with liquidity (delay costs, overdraft costs)
2. Transactions that could fail to settle immediately
3. Collateral mechanics that respond to `initial_liquidity_fraction`

## Expected Findings

Most likely cause: **The sandbox simulation doesn't connect policy parameters to simulation behavior.**

The `initial_liquidity_fraction` parameter is meant to control how much collateral an agent posts at the start of the day. But the sandbox may:
1. Not have collateral mechanics
2. Give the AGENT unlimited liquidity
3. Not use the policy tree at all (just settle everything immediately)

## Resolution Options

### Option A: Wire policy parameters to sandbox config
Modify `SandboxConfigBuilder` to:
1. Accept policy parameters
2. Set AGENT's opening balance = `initial_liquidity_fraction * max_collateral`
3. Enable cost accrual in sandbox

### Option B: Different evaluation approach
Instead of sandbox simulation, evaluate policies by:
1. Replaying historical events with different policy decisions
2. Computing counterfactual costs based on policy rules

### Option C: Fix the scenario to be policy-sensitive
Modify exp2's configuration to:
1. Have tighter liquidity constraints
2. Enable costs that respond to timing decisions
3. Create scenarios where policy actually matters

## TDD Tests

```python
def test_different_policies_produce_different_costs():
    """Verify that policy changes actually affect evaluation costs."""
    # Create a sample with transactions
    sample = create_test_bootstrap_sample()

    # Evaluate with high liquidity policy
    high_liq_policy = create_policy(initial_liquidity_fraction=0.9)
    high_liq_cost = evaluator.evaluate_single(sample, high_liq_policy)

    # Evaluate with low liquidity policy
    low_liq_policy = create_policy(initial_liquidity_fraction=0.1)
    low_liq_cost = evaluator.evaluate_single(sample, low_liq_policy)

    # Costs should differ
    assert high_liq_cost != low_liq_cost, "Policy should affect cost"


def test_sandbox_config_uses_policy_parameters():
    """Verify sandbox config reflects policy parameters."""
    policy = create_policy(initial_liquidity_fraction=0.3)

    config = sandbox_builder.build_sandbox_config(
        sample=sample,
        policy=policy,
        max_collateral=100000,
    )

    # AGENT's opening balance should reflect the fraction
    agent_config = next(a for a in config["agents"] if a["id"] == "AGENT")
    assert agent_config["opening_balance"] == 30000  # 0.3 * 100000
```

## Success Criteria

- [ ] Root cause identified
- [ ] Fix implemented (if straightforward)
- [ ] Test added to prevent regression
- [ ] Experiment 2 shows non-zero deltas when policy changes

## Files to Investigate

1. `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` - BootstrapPolicyEvaluator
2. `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py` - SandboxConfigBuilder
3. `api/payment_simulator/experiments/runner/optimization.py` - _evaluate_policy_pair()
4. `experiments/castro/configs/exp2_12period.yaml` - Scenario configuration
