# Review: `feature/interactive-web-sandbox` abd7271f..1eef02df

**Date:** 2025-07-22

---

## Verdict: Good fixes, one remaining bug

The phantom pool fix, dead code removal, rejected policy preservation, and cost relabeling are all correct. But there's a pre-existing key mismatch in the cost guidance that means most of the guidance logic has never actually fired.

---

## What's Correct

### Phantom pool fix (line 856) ✅
```python
liquidity_pool=agent_cfg.get("liquidity_pool"),
```
No fallback. `None` passes through correctly. This was the primary cause of zero costs.

### Rejected policy preservation ✅
- `game.py`: `result["rejected_policy"]` saved before `new_policy` set to None
- `GameDay.rejected_policies` dict persisted in checkpoints
- `streaming_optimizer.py`: `rejected_pol` passed to `SingleAgentIterationRecord`
- `single_agent_context.py`: rejected proposals shown with parameter summary and "do not repeat" guidance

Clean implementation. The tree summary (`condition on {field}`) is a nice touch for giving the LLM actionable context.

### Cost relabeling ✅
- `streaming_optimizer.py` line 125: `"liquidity_opportunity_cost"` instead of `"overdraft_cost"`
- `game.py` line 1348 (`_real_optimize`): same fix
- `single_agent_context.py`: new `liquidity_opp_pct` guidance block with correct advice ("lower initial_liquidity_fraction")

### Bootstrap diagnostics ✅
Cost min/max/mean logging per agent — good for debugging.

---

## Bug: Cost Breakdown Key Mismatch (Pre-existing)

`single_agent_context.py` `_build_optimization_guidance()` reads:
```python
delay_pct = (cb.get("delay", 0) / total) * 100
collateral_pct = (cb.get("collateral", 0) / total) * 100
overdraft_pct = (cb.get("overdraft", 0) / total) * 100
```

But the actual cost breakdown dict (from both `streaming_optimizer.py` and the paper's `optimization.py`) uses keys:
```python
{"delay_cost": ..., "overdraft_cost": ..., "deadline_penalty": ..., "eod_penalty": ..., "liquidity_opportunity_cost": ...}
```

The keys don't match: `"delay"` vs `"delay_cost"`, `"overdraft"` vs `"overdraft_cost"`, `"collateral"` vs nothing. So `delay_pct`, `collateral_pct`, and `overdraft_pct` are **always 0**. The threshold warnings (`⚠️ HIGH DELAY COSTS`, `⚠️ HIGH COLLATERAL COSTS`, etc.) have **never fired** — not in the paper's pipeline, not in Nash's web code.

Nash's new `liquidity_opportunity_cost` key works because he added it with the exact same key in both the dict and the `cb.get()` call. But the other three are broken.

**Fix** — align the keys in `_build_optimization_guidance()`:
```python
delay_pct = (cb.get("delay_cost", 0) / total) * 100
collateral_pct = (cb.get("collateral_cost", 0) / total) * 100
overdraft_pct = (cb.get("overdraft_cost", 0) / total) * 100
```

Or equivalently, add the `_cost` suffix to match the dict keys. Also check `_build_cost_analysis_section` (line ~182) for the same pattern.

Similarly, `user_prompt_builder.py` `_format_cost_components()` line 309 still has:
```python
("overdraft_cost", "Overdraft"),
```
This key no longer exists in the dict (Nash renamed it to `liquidity_opportunity_cost`). Add the new key:
```python
("overdraft_cost", "Overdraft (negative balance)"),
("liquidity_opportunity_cost", "Liquidity Opportunity Cost (idle capital)"),
("delay_cost", "Delay"),
("deadline_penalty", "Deadline Penalty"),
("eod_penalty", "EOD Penalty"),
("split_cost", "Split Cost"),
```

---

## Note on Cost Semantics

My previous report was wrong about a "double mislabeling." Looking at the code more carefully:

- The engine's `liquidity_cost` in `get_agent_accumulated_costs()` = overdraft cost (negative balance × bps)
- `game.py` computes `opportunity_cost = total - delay - penalty - overdraft - collateral - split` and stores it as `liquidity_cost` in the costs dict

So `game.py`'s `liquidity_cost` is genuinely opportunity cost, not the FFI's overdraft cost. Nash's rename to `liquidity_opportunity_cost` is correct for the value being passed. The actual FFI overdraft cost is consumed in the subtraction and not exposed separately in the web costs dict. If Nash wants to expose it separately (for the LLM to see both), he'd need to add it to the costs dict as a separate key.

For now, the rename is sufficient — the LLM gets the right signal.

---

## Still Open

1. **`_inject_policies_into_orch()`** not called in HTTP API path (Nash acknowledged, not yet fixed)
2. **Key mismatch bug** above — 5-line fix, should do before next Lehman Month run
