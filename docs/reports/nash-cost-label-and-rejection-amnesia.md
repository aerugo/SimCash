# Analysis: Cost Mislabeling + Rejected Policy Amnesia

**Date:** 2025-07-22  
**Branch:** `feature/interactive-web-sandbox` (abd7271f)  
**Request from:** Nash — two issues causing 0/140 acceptances on Lehman Month scenario

---

## Issue 1: Cost Mislabeling — "Overdraft" vs "Liquidity Opportunity Cost"

### The Bug

`web/backend/app/streaming_optimizer.py` line 125:
```python
cost_breakdown = {
    "delay_cost": agent_costs.get("delay_cost", 0),
    "overdraft_cost": agent_costs.get("liquidity_cost", 0),  # ← WRONG LABEL
    "deadline_penalty": agent_costs.get("penalty_cost", 0),
    "eod_penalty": 0,
}
```

This maps `liquidity_cost` (from `game.py`'s cost dict) to `overdraft_cost` in the prompt breakdown. The same mislabeling exists in `game.py`'s `_real_optimize()` (line ~1315, same pattern).

Then in `api/payment_simulator/ai_cash_mgmt/prompts/user_prompt_builder.py` line 309:
```python
("overdraft_cost", "Overdraft"),
```

So the LLM sees: `Overdraft: $X,XXX` when the real cost type is **liquidity opportunity cost** — the cost of *holding* too much capital idle.

### Why It Matters

These are opposite signals:
- **Overdraft cost** = balance went negative → you need MORE liquidity → increase fraction
- **Liquidity opportunity cost** = you're holding too much idle capital → you need LESS liquidity → decrease fraction

For agents like MID_BANK_2 and WEAK_BANK where the entire cost is liquidity opportunity cost (zero delay, zero penalties), the LLM sees "overdraft" and adds Hold/balance-check logic to conserve liquidity — exactly backwards. It should be reducing the fraction.

### The Fix

There are actually **two different cost concepts** being conflated. The engine tracks:

1. **`liquidity_cost`** in `get_agent_accumulated_costs()` → this is the overdraft cost (negative balance × `overdraft_bps_per_tick`). Named `liquidity_cost` in the FFI for historical reasons.

2. **Opportunity cost** = `total_cost - delay_cost - deadline_penalty - liquidity_cost - collateral_cost - split_friction_cost`. This is what `game.py` computes (line ~233 in `_run_single_sim`):
   ```python
   opportunity_cost = max(0, agent_total - delay - penalty - overdraft - collateral - split)
   costs[aid] = {
       "liquidity_cost": opportunity_cost,  # ← THIS IS OPPORTUNITY COST, NOT FFI liquidity_cost!
       ...
   }
   ```

So there's a double confusion:
1. `game.py` computes opportunity cost but labels it `liquidity_cost` in its costs dict
2. `streaming_optimizer.py` reads `liquidity_cost` and maps it to `overdraft_cost`
3. The prompt labels `overdraft_cost` as "Overdraft"

The actual FFI `liquidity_cost` (real overdraft cost) is consumed in the opportunity cost calculation and never exposed separately.

**Fix in `game.py` `_run_single_sim()`:**
```python
costs[aid] = {
    "opportunity_cost": opportunity_cost,  # Rename for clarity
    "delay_cost": delay,
    "penalty_cost": penalty,
    "overdraft_cost": overdraft,           # Actual overdraft from FFI
    "total": agent_total,
}
```

**Fix in `streaming_optimizer.py`:**
```python
cost_breakdown = {
    "delay_cost": agent_costs.get("delay_cost", 0),
    "overdraft_cost": agent_costs.get("overdraft_cost", 0),
    "opportunity_cost": agent_costs.get("opportunity_cost", 0),
    "deadline_penalty": agent_costs.get("penalty_cost", 0),
    "eod_penalty": 0,
}
```

**Fix in `user_prompt_builder.py` line 309:**
```python
component_names = [
    ("overdraft_cost", "Overdraft (negative balance)"),
    ("opportunity_cost", "Liquidity Opportunity Cost (idle capital)"),
    ("delay_cost", "Delay"),
    ("deadline_penalty", "Deadline Penalty"),
    ("eod_penalty", "EOD Penalty"),
    ("split_cost", "Split Cost"),
]
```

And fix the objectives text at line 235:
```python
"1. Minimize total cost (opportunity cost + delay + overdraft + penalties)",
```

**Also fix in `game.py` `_run_scenario_day()`** — same pattern around line 340:
```python
costs[aid] = {
    "opportunity_cost": day_opportunity,
    "delay_cost": day_delay,
    "penalty_cost": day_penalty,
    "overdraft_cost": day_overdraft,
    "total": day_total,
}
```

**Note:** This is a breaking change to the frontend — the keys in the cost dict change. Nash will need to update the frontend components that read `liquidity_cost`.

---

## Issue 2: Rejected Policy Amnesia

### The Bug

When bootstrap rejects a proposal, `_run_real_bootstrap()` sets:
```python
result["new_policy"] = None
result["new_fraction"] = None
```

Then `_apply_result()` sees `new_policy=None` and keeps the old policy. The `reasoning_history` stores this result, but the **iteration history shown to the LLM** only records the *applied* policy (from `day.policies`), not the proposed-and-rejected one.

In `streaming_optimizer.py` lines 132-160, the iteration history is built from `day.policies` — which only contains the policy that was actually used (the old one, since the proposal was rejected):

```python
day_policy = day.policies.get(agent_id, current_policy)
...
iteration_history.append(SingleAgentIterationRecord(
    iteration=i + 1,
    metrics={"total_cost_mean": day_agent_cost, ...},
    policy=day_policy,           # ← This is the KEPT policy, not the REJECTED proposal
    was_accepted=was_accepted,
    ...
))
```

The LLM sees 23 iterations all with `was_accepted=False` and the same policy parameters, but never sees WHAT was proposed and rejected. So it has no signal about what NOT to try → proposes the same thing repeatedly.

### The Fix

**Step 1:** Preserve the rejected proposal in `reasoning_history`.

This already partially works — `_apply_result()` appends the full `result` dict (including the original `new_policy` before it was set to None). But wait — `_run_real_bootstrap()` sets `result["new_policy"] = None` BEFORE `_apply_result()` is called. So the original proposal is lost.

**Fix in `_run_real_bootstrap()`** — preserve the proposed policy separately:
```python
if not accepted:
    result["accepted"] = False
    result["rejection_reason"] = rejection_reason
    result["reasoning"] += f" [REJECTED: {rejection_reason}]"
    result["rejected_policy"] = result["new_policy"]         # ← PRESERVE
    result["rejected_fraction"] = result.get("new_fraction")  # ← PRESERVE
    result["new_policy"] = None
    result["new_fraction"] = None
```

**Step 2:** Include rejected proposals in iteration history.

In `streaming_optimizer.py`, after building the `iteration_history` from `all_days`, enrich rejected iterations with the proposed policy from `reasoning_history`:

```python
# Enrich rejected iterations with what was actually proposed
reasoning = all_days_reasoning.get(agent_id, [])  # Game.reasoning_history[agent_id]
for i, record in enumerate(iteration_history):
    if not record.was_accepted and i < len(reasoning):
        rejected = reasoning[i].get("rejected_policy")
        if rejected:
            rejected_frac = rejected.get("parameters", {}).get("initial_liquidity_fraction")
            record.rejection_detail = f"Proposed fraction={rejected_frac}, rejected: {reasoning[i].get('rejection_reason', 'unknown')}"
```

This requires adding `rejection_detail: str | None = None` to `SingleAgentIterationRecord`.

**Step 3:** Show rejected proposals in the prompt.

In `single_agent_context.py` line ~393, after the REJECTED status:
```python
if status_text == "REJECTED" and record.rejection_detail:
    sections.append(f"**Rejected proposal:** {record.rejection_detail}")
```

### Alternative: Simpler Approach

If Nash wants a quicker fix without modifying the upstream prompt builders, he can add a "rejection memory" block to the prompt in `streaming_optimizer.py`:

```python
# Build rejection memory for LLM
rejection_memory = []
for entry in reasoning_history_for_agent:
    if entry.get("rejected_policy"):
        frac = entry["rejected_policy"].get("parameters", {}).get("initial_liquidity_fraction")
        reason = entry.get("rejection_reason", "")
        rejection_memory.append(f"- Tried fraction={frac} → REJECTED ({reason})")

if rejection_memory:
    rejection_context = "PREVIOUSLY REJECTED PROPOSALS (do NOT repeat these):\n" + "\n".join(rejection_memory)
    # Append to user prompt or pass as additional context
```

This is less elegant but avoids touching the upstream `SingleAgentIterationRecord` and prompt builders. Nash can decide based on how much time he wants to invest.

---

## Priority

1. **Cost mislabeling** — fix first, it's actively misleading the LLM on every iteration
2. **Rejection amnesia** — fix second, it causes wasted iterations but isn't as fundamentally wrong

Both together likely explain the 0/140 acceptance rate: the LLM is being told the wrong cost type (so it optimizes in the wrong direction), AND it can't learn from its rejected attempts (so it keeps making the same wrong move).
