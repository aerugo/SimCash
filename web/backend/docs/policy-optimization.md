# AI Policy Optimization

*How LLMs learn to be cash managers*

## The Multi-Day Loop

Each "game" runs for multiple simulated trading days. The optimization loop is:

1. Day starts → banks commit liquidity according to their current policy
2. Rust engine runs the full day (all ticks) with stochastic payment arrivals
3. Day ends → costs tallied, events collected per agent
4. AI analyzes each agent's results independently (information isolation)
5. AI proposes improved policy (new `initial_liquidity_fraction` + decision tree)
6. Optional: bootstrap evaluation compares new vs old policy statistically
7. If accepted, next day uses new policy; if rejected, keeps old policy

## Information Isolation

This is critical: each agent sees **only its own** costs, events, and
transaction history. No counterparty balances, policies, or cost breakdowns. The only
signal about other agents comes from incoming payment timing — just like in real RTGS
systems where participants see settlement messages but not others' internal positions.

> ⚠️ Crucially, agents are **not told the environment is stationary**. They don't
> know that iterations use the same payment parameters (or identical schedules in deterministic
> scenarios). Any regularity must be inferred from observed data. This is a realistic
> constraint — real cash managers don't have perfect knowledge of the data-generating process.

## The Prompt

The PolicyOptimizer builds a 50,000+ token prompt containing:

- Current performance metrics and cost breakdown
- Verbose simulation output from best and worst performing seeds
- Full iteration history with acceptance status
- Parameter trajectories across iterations
- Optimization guidance based on cost analysis
- Policy schema (valid JSON structure)

## Policy Format

The LLM outputs a JSON policy with two key components:

```json
{
  "version": "2.0",
  "policy_id": "optimized_v5",
  "parameters": {
    "initial_liquidity_fraction": 0.085
  },
  "payment_tree": {
    "type": "condition", "field": "ticks_to_deadline",
    "operator": "<=", "value": 2,
    "true_branch": {"type": "action", "action": "Release"},
    "false_branch": {"type": "action", "action": "Hold"}
  },
  "bank_tree": {
    "type": "action", "action": "NoAction"
  }
}
```

## Constraint Validation

Every LLM output is validated against scenario constraints (parameter ranges, allowed
fields, valid actions). Invalid policies trigger retry with error feedback — up to 3
attempts before falling back to the current policy.
