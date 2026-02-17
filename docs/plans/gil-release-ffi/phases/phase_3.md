# Phase 3: Thread-Parallel Day Evaluation

**Status**: Planned  
**Depends on**: Phase 1 (GIL-release FFI methods)

## Objective

Parallelize the multi-sample day evaluation loop in `Game.run_day()` when `num_eval_samples > 1`. Each sample runs on a separate thread using `run_and_get_all_costs()`.

## Invariants

- INV-1: Day costs are identical whether computed sequentially or in parallel
- INV-2: Representative run (first seed) still provides events and balance history for UI display
- INV-3: All 20 `test_game_engine.py` tests continue to pass

## Approach

The first sample (representative run) must still use the existing `_run_single_sim()` path because we need events, balance history, and tick events for the UI. Only the **additional** samples (indices 1..N) can be parallelized — they only contribute cost data.

```python
def run_day(self) -> GameDay:
    seed = self._base_seed + self.current_day

    # Representative run — full data for UI (sequential, existing code)
    all_events, balance_history, costs, per_agent_costs, total_cost, tick_events = self._run_single_sim(seed)

    if self.num_eval_samples > 1:
        # Additional samples — only need costs (parallel)
        extra_seeds = [seed + i * 1000 for i in range(1, self.num_eval_samples)]

        with concurrent.futures.ThreadPoolExecutor() as pool:
            futures = {s: pool.submit(self._run_cost_only, s) for s in extra_seeds}
            extra_results = {s: futures[s].result() for s in extra_seeds}

        # Average costs across all samples (representative + extras)
        # ... same averaging logic as before
```

## Files Changed

| File | Action |
|------|--------|
| `web/backend/app/game.py` | Modify — parallelize extra samples in `run_day()` |
| `web/backend/tests/test_gil_release.py` | Add `TestParallelDayEval` |

## Verification

```bash
uv run pytest web/backend/tests/test_game_engine.py -v
uv run pytest web/backend/tests/test_gil_release.py -v
uv run pytest web/backend/tests/ -v --ignore=.../test_real_llm.py
```
