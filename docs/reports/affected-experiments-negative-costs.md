# Affected Experiments — Negative Cost Bug

**Date:** 2026-02-27
**Root Cause:** `_compute_cost_deltas()` in `3dca4bbf` subtracted previous day's daily costs from current day's daily costs, treating them as cumulative. Engine resets accumulators at day boundaries, so they're already per-day. Result: negative values when day N cost < day N-1 cost.
**Fix:** `4f39e28e` (removes delta layer), `1b596876` (integration tests). Deployed as `simcash-00168-v29`.

## Affected: 62 experiments

All multi-day (`num_days > 1`) experiments with `optimization_schedule=every_scenario_day` that have at least 1 completed day. The LLM optimizer received corrupted cost data, so policy optimization trajectories are poisoned even where stored cost values appear non-negative.

### Corruption types

- **NEG_ORIG (1):** Original `total_cost`/`per_agent_costs` fields contain negatives (checkpoint re-serialized by early buggy code `3dca4bbf` that wrote deltas into original fields)
- **NEG_DAY (8):** Separate `day_total_cost`/`day_per_agent_costs`/`day_costs` fields contain negatives (written by `a70a5601` which added separate delta fields)
- **POISONED_TRAJECTORY (53):** Stored costs may appear non-negative, but the optimizer read `day_*` fields at runtime, received wrong values, and made optimization decisions based on corrupted data. Results are unreliable.

### Experiment IDs

```
0496e8bc  113f54f9  152ab75d  161d71d5  1cfeedc4  1e0ca865
1f4e3fc7  1f83ebfb  21262d54  2dd973f8  298704f4  35439789
3efa325c  45e8aa95  4d0f0870  4d44829f  50893387  524fc873
54ca8546  566738d6  5e2a4376  640c740c  64f0b9e6  6f6f3afb
70377092  747025f3  79785ad6  7e1c3f08  7e314cdd  82d30b0f
84ef6b87  865236c5  92040487  95361864  9f279e14  9f5ebd66
a1521a92  a54b3f8a  aaf1ff62  afdf2cfe  b140728c  b7468923
bb6ea1d2  bf2e390e  c084839a  c3092a1e  c6c18a8a  c75741f7
c8bcbc79  ce84d3e7  d8aba24e  daafc265  e1009f5a  e22310ce
e68d887d  ea0794a3  f0eb80e9  f149fabd  f7f91666  fe133c9f
ff26b685  ff6fc861
```

### Not affected: 246 experiments

All single-day (`num_days=1`) experiments, and multi-day experiments without `every_scenario_day` schedule, or with 0 completed days. `_get_previous_day_in_round()` returns `None` when `_scenario_num_days <= 1`, so the delta subtraction never executes.

### Action required

All 62 experiments above should be re-run. The fix is deployed — new runs will store correct per-day costs directly from the engine.
