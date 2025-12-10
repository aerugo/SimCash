# Phase 4.6: Terminology Cleanup (Monte Carlo → Bootstrap)

**Status:** In Progress
**Created:** 2025-12-10

## Purpose

Fix incorrect terminology throughout the codebase. The sampling technique used is **bootstrap resampling**, not Monte Carlo simulation. "Bootstrap Monte Carlo" is not a thing.

- **Bootstrap**: Resampling with replacement from historical data to estimate variance
- **Monte Carlo**: Random sampling from probability distributions to estimate integrals

Our evaluation system samples from historical transactions with replacement → this is **bootstrap**, not Monte Carlo.

## Scope

### 1. Core Config Class Rename
- `MonteCarloConfig` → `BootstrapConfig`
- `SampleMethod` enum: Already has `BOOTSTRAP` value (correct!)
- `monte_carlo` attribute → `bootstrap` attribute

### 2. Files to Update

#### API Core Files
| File | Changes |
|------|---------|
| `api/payment_simulator/ai_cash_mgmt/config/game_config.py` | Rename class, update docstrings |
| `api/payment_simulator/ai_cash_mgmt/config/__init__.py` | Update export |
| `api/payment_simulator/ai_cash_mgmt/__init__.py` | Update export |
| `api/payment_simulator/ai_cash_mgmt/core/game_orchestrator.py` | Update attribute access |
| `api/payment_simulator/ai_cash_mgmt/core/game_session.py` | Update docstrings |
| `api/payment_simulator/ai_cash_mgmt/sampling/__init__.py` | Update docstrings |
| `api/payment_simulator/ai_cash_mgmt/sampling/seed_manager.py` | Update comments |
| `api/payment_simulator/ai_cash_mgmt/sampling/transaction_sampler.py` | Update docstrings |
| `api/payment_simulator/cli/commands/ai_game.py` | Update if used |

#### API Test Files
| File | Changes |
|------|---------|
| `api/tests/ai_cash_mgmt/unit/test_game_config.py` | Update references |
| `api/tests/ai_cash_mgmt/unit/test_game_orchestrator.py` | Update MonteCarloConfig usages |
| `api/tests/ai_cash_mgmt/unit/test_game_session.py` | Update MonteCarloConfig usages |
| `api/tests/ai_cash_mgmt/unit/test_transaction_sampler.py` | Update docstring |
| `api/tests/ai_cash_mgmt/unit/test_policy_evaluator.py` | Update docstring |
| `api/tests/ai_cash_mgmt/integration/test_monte_carlo_validation.py` | Rename file + content |
| `api/tests/ai_cash_mgmt/integration/test_database_integration.py` | Update comments |

#### Castro Experiment Files
| File | Changes |
|------|---------|
| `experiments/castro/cli.py` | `--verbose-monte-carlo` → `--verbose-bootstrap` |
| `experiments/castro/castro/experiments.py` | Update `get_monte_carlo_config()` |
| `experiments/castro/castro/verbose_logging.py` | Update config names |
| `experiments/castro/castro/runner.py` | Update method calls |
| `experiments/castro/CLAUDE.md` | Update documentation |
| `experiments/castro/README.md` | Update documentation |
| `experiments/castro/architecture.md` | Update documentation |

### 3. CLI Flag Changes

| Old Flag | New Flag |
|----------|----------|
| `--verbose-monte-carlo` | `--verbose-bootstrap` |
| `--no-verbose-monte-carlo` | `--no-verbose-bootstrap` |

### 4. Method/Function Renames

| Old Name | New Name |
|----------|----------|
| `get_monte_carlo_config()` | `get_bootstrap_config()` |
| `log_monte_carlo_evaluation()` | `log_bootstrap_evaluation()` |
| `verbose_monte_carlo` parameter | `verbose_bootstrap` parameter |

## Implementation Order

1. **Phase 4.6.1**: Rename `MonteCarloConfig` → `BootstrapConfig` in core config
2. **Phase 4.6.2**: Update all API imports and usages
3. **Phase 4.6.3**: Update API tests
4. **Phase 4.6.4**: Update Castro CLI and experiments
5. **Phase 4.6.5**: Update documentation files
6. **Phase 4.6.6**: Run all tests to verify

## Verification

```bash
# Verify no remaining "Monte Carlo" references (except docs explaining the terminology)
grep -ri "monte.carlo" api/ experiments/ --include="*.py" | grep -v "test_bootstrap"

# Run all tests
cd api && .venv/bin/python -m pytest -v

# Run castro tests
cd experiments/castro && uv run pytest -v
```

## Notes

- Keep backward compatibility note in `BootstrapConfig` docstring explaining this was formerly called MonteCarloConfig
- The `SampleMethod.BOOTSTRAP` enum value is already correct
- Some references in grand_plan.md can stay as-is (historical context)
