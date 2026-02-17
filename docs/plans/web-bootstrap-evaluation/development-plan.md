# Bootstrap Evaluation - Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Summary

Add proper bootstrap paired evaluation to the web `Game` class, matching the paper's methodology. The current `num_eval_samples` parameter does naive averaging across independent seeds. The paper requires: paired comparison (old vs new policy on same seeds), delta_sum acceptance, coefficient of variation (CV) rejection, and confidence interval (CI) checking. This is the core scientific methodology that distinguishes rigorous policy evaluation from noise.

## Critical Invariants to Respect

- **INV-1**: Money is i64 — all delta values, costs, CI bounds in integer cents
- **INV-2**: Determinism — same seeds in paired comparison = same results
- **INV-3**: FFI Minimal — use `SimulationConfig.to_ffi_dict()` exclusively
- **INV-GAME-1**: Policy Reality — `initial_liquidity_fraction` MUST produce different costs
- **INV-GAME-2**: Agent Isolation — each agent evaluated independently
- **INV-GAME-3**: Bootstrap Identity — web bootstrap evaluation must use same acceptance criteria as experiment runner

## Current State Analysis

### What Exists

1. **`Game.run_day()`**: Multi-sample averaging via `num_eval_samples` — runs N seeds, averages costs. No pairing.
2. **`Game._run_single_sim()`**: Runs one simulation at a given seed. Returns costs per agent.
3. **`BootstrapPolicyEvaluator`** in `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`: Full paired comparison with `PairedDelta` dataclass. Uses bootstrap samples from `BootstrapSampler`.
4. **Experiment runner**: Uses bootstrap evaluation for accept/reject decisions with CV threshold and CI checks.

### What's Missing

- No paired comparison in web Game (old policy vs new policy on same seeds)
- No delta_sum calculation (sum of paired differences)
- No CV check (reject if cost variance too high — noisy result)
- No CI check (reject if 95% CI crosses zero — not statistically significant)
- No acceptance/rejection metadata in reasoning results
- Game always accepts proposed policies

### Key Difference: Web vs Experiment Runner

The experiment runner uses `BootstrapSampler` to resample historical transaction data. The web game generates fresh stochastic scenarios each seed. For the web, "bootstrap" means: run N seeds with old policy, run same N seeds with new policy, compute paired deltas. Same statistical methodology, different data source.

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/backend/app/bootstrap_eval.py` | Does not exist | New `WebBootstrapEvaluator` class |
| `web/backend/app/game.py` | Naive averaging, always-accept | Wire bootstrap evaluation into optimize_policies |
| `web/backend/app/models.py` | No evaluation models | Add `EvaluationResult` Pydantic model |
| `web/frontend/src/types.ts` | `GameOptimizationResult` has basic fields | Add bootstrap metadata fields |
| `web/frontend/src/components/GameView.tsx` | Shows reasoning text only | Show accept/reject + delta stats |
| `web/backend/tests/test_bootstrap_eval.py` | Does not exist | Comprehensive bootstrap tests |

## Phase Overview

| Phase | Description | Key Deliverables |
|-------|-------------|-----------------|
| 1 | Backend: Implement `WebBootstrapEvaluator` with paired comparison | Paired delta computation, CV calculation, CI check |
| 2 | Backend: Wire into `Game.optimize_policies()` for accept/reject | Evaluation before acceptance, rejection metadata |
| 3 | Backend: Add acceptance/rejection metadata to reasoning results | `EvaluationMetadata` in response, delta_sum, cv, ci |
| 4 | Frontend: Display accepted/rejected status + delta stats | Badges, delta values, CV display |
| 5 | Test bootstrap logic matches experiment runner behavior | Determinism tests, acceptance criteria tests |
