# Phase 4: Full Regression Suite + Performance Benchmark

**Status**: Planned  
**Depends on**: Phases 1-3

## Objective

Run every test suite in the project. Verify zero regressions. Benchmark the parallel vs sequential performance.

## Full Test Matrix

Run in this exact order:

```bash
# 1. Rust tests (105 expected, 0 failures)
export PATH="/Users/ned/.rustup/toolchains/stable-aarch64-apple-darwin/bin:$PATH"
cargo test --manifest-path simulator/Cargo.toml --no-default-features

# 2. Python API unit tests (581 expected, 0 failures)
cd /Users/ned/.openclaw/workspace-nash/SimCash/api
$HOME/Library/Python/3.9/bin/uv run pytest tests/unit/ -v --tb=short

# 3. Web backend tests — existing (63 expected, 0 failures)
$HOME/Library/Python/3.9/bin/uv run pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/ -v --tb=short \
  --ignore=/Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_real_llm.py \
  --ignore=/Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_gil_release.py

# 4. Web backend tests — new GIL-release tests
$HOME/Library/Python/3.9/bin/uv run pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_gil_release.py -v --tb=short

# 5. Frontend TypeScript compilation
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc -b --noEmit
```

## Performance Benchmark

Add to `test_gil_release.py`:

```python
class TestPerformanceBenchmark:
    """Not assertions — just timing data for the report."""

    def test_bootstrap_sequential_vs_parallel(self):
        """Compare bootstrap-10 timing: sequential vs ThreadPoolExecutor."""
        import time
        from app.bootstrap_eval import WebBootstrapEvaluator

        with open(EXP2_CONFIG) as f:
            raw = yaml.safe_load(f)

        old_policy = {...}  # fraction=0.5
        new_policy = {...}  # fraction=0.1

        # Sequential (parallel=False)
        evaluator_seq = WebBootstrapEvaluator(num_samples=10, parallel=False)
        t0 = time.perf_counter()
        evaluator_seq.evaluate(raw, "BANK_A", old_policy, new_policy, 42)
        t_seq = time.perf_counter() - t0

        # Parallel (default)
        evaluator_par = WebBootstrapEvaluator(num_samples=10, parallel=True)
        t0 = time.perf_counter()
        evaluator_par.evaluate(raw, "BANK_A", old_policy, new_policy, 42)
        t_par = time.perf_counter() - t0

        print(f"\nBootstrap-10 sequential: {t_seq*1000:.1f}ms")
        print(f"Bootstrap-10 parallel:   {t_par*1000:.1f}ms")
        print(f"Speedup: {t_seq/t_par:.2f}x")
```

## Success Criteria

| Suite | Expected | Actual |
|-------|----------|--------|
| Rust tests | 105 passed, 18 ignored | |
| Python API unit tests | 581 passed, 4 skipped | |
| Web backend (existing) | 63 passed | |
| Web backend (new) | ~15 passed | |
| Frontend TypeScript | Clean compile | |

## Commit

If all green:

```bash
git add -A
git commit -m "Add GIL-releasing FFI methods for thread-parallel simulation

- run_and_get_total_cost(): releases GIL, returns i64 cost
- run_and_get_all_costs(): releases GIL, returns JSON string
- WebBootstrapEvaluator now uses ThreadPoolExecutor
- Game.run_day() parallelizes extra eval samples
- Determinism verified: sequential == parallel for same seeds
- Thread safety verified: 10 concurrent sims produce correct results
- All existing test suites pass (105 Rust + 581 Python + 63 web)"
```
