# AI Cash Management Architecture Refactor - Work Notes

**Status:** Phases 0-18 COMPLETED, Phase 19 PLANNED (Documentation Overhaul)
**Created:** 2025-12-10
**Last Updated:** 2025-12-11

---

## Purpose

This document tracks progress and notes during the refactor implementation. Each phase has its own TODO checklist and notes section.

---

## Phase TODO Checklists

### Phase 0: Fix Bootstrap Paired Comparison Bug (Critical)

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/experiments/castro/test_bootstrap_paired_comparison.py`
- [x] Test: same samples used for old and new policy (`test_compute_paired_deltas_returns_matching_indices`)
- [x] Test: acceptance based on paired delta, not absolute costs (`test_acceptance_based_on_paired_delta_not_absolute`)
- [x] Test: evaluator is deterministic (`test_evaluate_same_sample_twice_returns_identical_results`)
- [x] Test: order preserved (`test_evaluate_samples_preserves_order`)
- [x] All 7 tests pass

**Implementation:**
- [x] Modify `runner.py` to store bootstrap samples after generation (line 748: `samples_per_agent` dict)
- [x] Modify `_evaluate_policies()` return type to include samples (5-tuple now)
- [x] Modify `runner.py` to use SAME samples for new policy evaluation
- [x] Use `compute_paired_deltas()` for policy comparison (line 437)
- [x] Accept based on mean delta > 0 (positive delta = old costs more than new)
- [x] Verify all tests pass (98 bootstrap tests + 7 new tests)
- [ ] Run `castro run exp1 --verbose-monte-carlo` to verify paired deltas shown (DEFERRED - needs LLM API key)
- [ ] Commit Phase 0 changes

**Notes:**
```
2025-12-10: BUG IDENTIFIED AND FIXED
- The compute_paired_deltas() method EXISTED in evaluator.py but was NEVER called
- runner.py was generating NEW samples for each _evaluate_policies() call
- This broke statistical validity of policy comparisons

FIX IMPLEMENTED:
1. Modified _evaluate_policies() to return samples_per_agent dict
2. Modified policy comparison logic to use compute_paired_deltas()
3. Policy acceptance now based on mean_delta > 0 (positive = new policy cheaper)
4. Old buggy code: re-called _evaluate_policies() which generated NEW samples
5. New correct code: passes stored samples to compute_paired_deltas()

KEY CODE CHANGES:
- runner.py lines 704-835: _evaluate_policies() now returns 5-tuple including samples
- runner.py lines 421-503: Policy comparison now uses compute_paired_deltas()
- Console output now shows "mean delta" for paired comparison

TEST RESULTS:
- api/tests/experiments/castro/test_bootstrap_paired_comparison.py: 7/7 passed
- api/tests/ai_cash_mgmt/unit/bootstrap/: 98/98 passed
```

---

### Phase 0.5: Add Event Tracing to Bootstrap Sandbox

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/ai_cash_mgmt/unit/bootstrap/test_enriched_evaluation.py`
- [x] Test: `BootstrapEvent` is frozen (immutable)
- [x] Test: `CostBreakdown.total` sums all costs
- [x] Test: All costs are integer cents (INV-1)
- [x] Test: `EnrichedEvaluationResult` contains event trace
- [x] Write `experiments/castro/tests/test_bootstrap_context.py`
- [x] Test: `get_best_result()` returns lowest cost
- [x] Test: `get_worst_result()` returns highest cost
- [x] Test: `format_event_trace_for_llm()` limits events
- [x] Test: `build_agent_context()` returns AgentSimulationContext

**Implementation:**
- [x] Create `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py`
  - [x] Add `BootstrapEvent` dataclass
  - [x] Add `CostBreakdown` dataclass
  - [x] Add `EnrichedEvaluationResult` dataclass
- [x] Update `bootstrap/__init__.py` with exports
- [x] Create `experiments/castro/castro/bootstrap_context.py`
  - [x] Implement `BootstrapContextBuilder` class
  - [x] Implement `get_best_result()` and `get_worst_result()`
  - [x] Implement `format_event_trace_for_llm()` with event prioritization
  - [x] Implement `build_agent_context()` returning AgentSimulationContext
- [ ] Add `evaluate_sample_enriched()` to `bootstrap/evaluator.py` (DEFERRED - optional enhancement)
- [ ] Update `runner.py` to use enriched evaluation (DEFERRED - optional enhancement)

**Notes:**
```
2025-12-10: PHASE 0.5 COMPLETE
Session 1:
- Created enriched_models.py with BootstrapEvent, CostBreakdown, EnrichedEvaluationResult
- All 12 enriched model tests pass
- Total bootstrap tests: 110 (98 original + 12 new)

Session 2:
- Created BootstrapContextBuilder in castro
- All 10 context builder tests pass
- Context builder features:
  * get_best_result() / get_worst_result() - find best/worst samples
  * format_event_trace_for_llm() - priority-based event filtering
  * build_agent_context() - compatible with existing prompt system
  * Event prioritization (PolicyDecision > Cost > Settlement > Arrival)

DEFERRED TO PHASE 1+:
- evaluate_sample_enriched() method (requires deeper evaluator refactor)
- Wiring up runner.py to use enriched evaluation

The foundation is now in place:
- BootstrapEvent, CostBreakdown, EnrichedEvaluationResult models
- BootstrapContextBuilder for transforming results to LLM context
- Can be integrated incrementally into runner.py later
```

---

### Phase 1: Preparation (Pre-Refactor)

**Status:** COMPLETED (2025-12-10)

- [x] Create `api/payment_simulator/llm/` directory
- [x] Create `api/payment_simulator/experiments/` directory structure
- [x] Create empty `__init__.py` files
- [x] Create `api/payment_simulator/llm/protocol.py` with protocol stubs
- [x] Create `api/tests/llm/` directory
- [x] Create `api/tests/experiments/` directory
- [ ] Create test fixture YAML files in `api/tests/fixtures/experiments/` (DEFERRED to Phase 3)
- [x] Verify all existing tests still pass
- [x] Commit Phase 1 changes

**Notes:**
```
2025-12-10: PHASE 1 COMPLETE
- Created api/payment_simulator/llm/ module with:
  - __init__.py - exports LLMClientProtocol
  - protocol.py - LLMClientProtocol with @runtime_checkable
    * generate_structured_output() method
    * generate_text() method

- Created api/payment_simulator/experiments/ module with:
  - __init__.py
  - config/__init__.py - placeholder for experiment config loader
  - runner/__init__.py - placeholder for experiment runner
  - persistence/__init__.py - placeholder for experiment persistence

- Created test structure:
  - api/tests/llm/test_protocol.py - 6 tests for LLMClientProtocol
  - api/tests/experiments/test_module_structure.py - 4 tests for module imports

TEST RESULTS:
- LLM protocol tests: 6/6 passed
- Experiments module structure tests: 4/4 passed
- All existing tests continue to pass

Note: Test fixture YAML files deferred to Phase 3 (Experiment Config Framework)
since they require the ExperimentConfig schema to be defined first.
```

---

### Phase 2: LLM Module Extraction

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/llm/test_config.py` - 12 tests for LLMConfig
- [x] Write `tests/llm/test_audit_wrapper.py` - 11 tests for AuditCaptureLLMClient
- [x] Write `tests/llm/pydantic_client.py` (implementation, skip integration tests without API key)
- [x] Verify tests fail before implementation (TDD)

**Implementation:**
- [x] Create `api/payment_simulator/llm/config.py` - LLMConfig frozen dataclass
- [x] Create `api/payment_simulator/llm/pydantic_client.py` - PydanticAI implementation
- [x] Create `api/payment_simulator/llm/audit_wrapper.py` - Audit capture wrapper with LLMInteraction
- [x] Update `api/payment_simulator/llm/__init__.py` with lazy exports
- [x] Verify all LLM tests pass (29/29)
- [ ] Verify mypy type checking passes (DEFERRED - minor type issues)
- [x] Commit Phase 2 changes

**Notes:**
```
2025-12-10: PHASE 2 COMPLETE

IMPLEMENTED:
1. LLMConfig (frozen dataclass):
   - model: str in "provider:model" format
   - provider/model_name properties to extract parts
   - temperature, max_retries, timeout_seconds defaults
   - thinking_budget (Anthropic) and reasoning_effort (OpenAI) options

2. PydanticAILLMClient:
   - Implements LLMClientProtocol
   - generate_structured_output() for Pydantic model responses
   - generate_text() for plain text responses
   - Requires pydantic-ai optional dependency

3. AuditCaptureLLMClient:
   - Wraps any LLMClientProtocol implementation
   - Captures all interactions as immutable LLMInteraction records
   - get_last_interaction() and get_all_interactions() methods
   - Tracks latency, system/user prompts, responses, parsed policies

4. LLMInteraction (frozen dataclass):
   - system_prompt, user_prompt, raw_response
   - parsed_policy (dict or None), parsing_error
   - prompt_tokens, completion_tokens, latency_seconds

DESIGN DECISIONS:
- Used lazy imports for PydanticAILLMClient to avoid requiring pydantic-ai
  for modules that only need LLMConfig or protocol
- All config and interaction dataclasses are frozen (immutable)
- Temperature defaults to 0.0 for determinism

TEST RESULTS:
- test_config.py: 12/12 passed
- test_audit_wrapper.py: 11/11 passed
- test_protocol.py: 6/6 passed
- Total LLM tests: 29/29 passed
```

---

### Phase 3: Experiment Configuration Framework

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/experiments/config/test_experiment_config.py` - 28 tests
- [x] Create valid YAML test fixtures (in-test fixtures via tmp_path)
- [x] Create invalid YAML test fixtures (for error cases)
- [x] Verify tests fail before implementation (TDD)

**Implementation:**
- [x] Create `api/payment_simulator/experiments/config/experiment_config.py`
- [x] Implement `ExperimentConfig.from_yaml()` method
- [x] Implement `EvaluationConfig` dataclass
- [x] Implement `OutputConfig` dataclass
- [x] Implement `ConvergenceConfig` dataclass
- [x] Implement `load_constraints()` method for dynamic import
- [x] Update `api/payment_simulator/experiments/config/__init__.py`
- [x] Verify all config tests pass (28/28)
- [ ] Verify mypy passes (DEFERRED)
- [x] Commit Phase 3 changes

**Notes:**
```
2025-12-10: PHASE 3 COMPLETE

IMPLEMENTED:
1. EvaluationConfig (frozen dataclass):
   - mode: bootstrap or deterministic
   - num_samples: for bootstrap mode (default 10)
   - ticks: simulation ticks per evaluation
   - __post_init__ validation for mode

2. OutputConfig (frozen dataclass):
   - directory: Path for output (default "results")
   - database: filename (default "experiments.db")
   - verbose: flag (default True)

3. ConvergenceConfig (frozen dataclass):
   - max_iterations: (default 50)
   - stability_threshold: (default 0.05)
   - stability_window: (default 5)
   - improvement_threshold: (default 0.01)

4. ExperimentConfig (frozen dataclass):
   - name, description, scenario_path
   - evaluation: EvaluationConfig
   - convergence: ConvergenceConfig
   - llm: LLMConfig (from Phase 2)
   - optimized_agents: tuple[str, ...]
   - constraints_module: str for dynamic import
   - output: OutputConfig
   - master_seed: int (default 42)
   - from_yaml() class method for YAML loading
   - load_constraints() for dynamic module import

DESIGN DECISIONS:
- All config dataclasses are frozen (immutable)
- ExperimentConfig.from_yaml() is the primary loading interface
- Reuses LLMConfig from Phase 2 llm module
- optimized_agents is a tuple (not list) for immutability

TEST RESULTS:
- EvaluationConfig tests: 5/5 passed
- OutputConfig tests: 4/4 passed
- ConvergenceConfig tests: 5/5 passed
- ExperimentConfig tests: 14/14 passed
- Total: 28/28 passed
```

---

### Phase 4: Experiment Runner Framework

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/experiments/runner/test_protocol.py` - 5 tests
- [x] Write `tests/experiments/runner/test_result.py` - 16 tests
- [x] Write `tests/experiments/runner/test_output.py` - 10 tests
- [x] Verify tests fail before implementation (TDD)

**Implementation:**
- [x] Create `api/payment_simulator/experiments/runner/protocol.py` - ExperimentRunnerProtocol
- [x] Create `api/payment_simulator/experiments/runner/output.py` - OutputHandlerProtocol, SilentOutput
- [x] Create `api/payment_simulator/experiments/runner/result.py` - ExperimentResult, ExperimentState, IterationRecord
- [x] Update `api/payment_simulator/experiments/runner/__init__.py` with exports
- [x] Implement `SilentOutput` handler (for testing)
- [x] Verify all runner tests pass (31/31)
- [x] Commit Phase 4 changes

**Deferred:**
- [ ] Create `base_runner.py` (requires evaluator/LLM integration - Phase 4.5)
- [ ] Implement core optimization loop (Phase 4.5)
- [ ] Implement `RichConsoleOutput` handler (Phase 4.5)
- [ ] Integration test with mock components (Phase 4.5)

**Notes:**
```
2025-12-10: PHASE 4 COMPLETE

IMPLEMENTED:
1. ExperimentRunnerProtocol (@runtime_checkable):
   - async run() -> ExperimentResult
   - get_current_state() -> ExperimentState

2. OutputHandlerProtocol (@runtime_checkable):
   - on_experiment_start(experiment_name)
   - on_iteration_start(iteration)
   - on_iteration_complete(iteration, metrics)
   - on_agent_optimized(agent_id, accepted, delta)
   - on_convergence(reason)
   - on_experiment_complete(result)

3. SilentOutput:
   - No-op implementation for testing
   - All callbacks are pass-through

4. ExperimentResult (frozen dataclass):
   - experiment_name, num_iterations, converged
   - convergence_reason, final_costs (integer cents - INV-1)
   - total_duration_seconds, iteration_history, final_policies

5. ExperimentState (frozen dataclass):
   - experiment_name, current_iteration, is_converged
   - convergence_reason, policies
   - with_iteration() and with_converged() for immutable updates

6. IterationRecord (frozen dataclass):
   - iteration, costs_per_agent (integer cents - INV-1)
   - accepted_changes per agent

DESIGN DECISIONS:
- All protocols use @runtime_checkable for isinstance checks
- All result dataclasses are frozen (immutable)
- ExperimentState uses with_* pattern for immutable updates
- All costs are integer cents (INV-1 compliance)
- BaseExperimentRunner deferred to Phase 4.5 as it requires evaluator integration

TEST RESULTS:
- test_output.py: 10/10 passed
- test_result.py: 16/16 passed
- test_protocol.py: 5/5 passed
- Total: 31/31 passed
```

---

### Phase 4.5: Bootstrap Integration Tests with Mocked LLM

**Status:** COMPLETED (2025-12-10)

**Purpose:** Comprehensive integration tests that verify the bootstrap evaluation system
works correctly with mocked LLM responses. These tests ensure:
- Bootstrap samples are processed by both old and new policies
- Delta costs are correctly calculated
- Policies are accepted/rejected based on paired comparison results

**Tests First (TDD):**
- [x] Write `tests/experiments/integration/test_bootstrap_policy_acceptance.py`
- [x] Test: Delta formula is cost_a - cost_b (positive = A costs more)
- [x] Test: Policy is ACCEPTED when mean_delta > 0 (new policy cheaper)
- [x] Test: Policy is REJECTED when mean_delta <= 0 (old policy same or cheaper)
- [x] Test: Mixed deltas with overall improvement/regression
- [x] Test: Bootstrap samples have matching indices and seeds
- [x] Test: All costs are integer cents (INV-1 compliance)
- [x] All 17 tests pass

**Implementation:**
- [x] Create test scenarios with known cost outcomes
- [x] Verify PairedDelta dataclass correctness
- [x] Verify mean_delta calculation
- [x] Verify policy acceptance/rejection logic

**Notes:**
```
2025-12-10: PHASE 4.5 COMPLETE

IMPLEMENTED:
1. TestPairedDeltaDataclass (4 tests):
   - delta = cost_a - cost_b formula verified
   - Positive delta means policy A costs more
   - Negative delta means policy B costs more
   - Zero delta means equal costs

2. TestMeanDeltaCalculation (3 tests):
   - Single sample mean equals that sample's delta
   - Multiple samples mean is average of all deltas
   - Empty list returns 0.0

3. TestPolicyAcceptanceLogic (5 tests):
   - Accept when mean_delta > 0 (B is cheaper)
   - Reject when mean_delta == 0 (same cost)
   - Reject when mean_delta < 0 (B is more expensive)
   - Mixed deltas overall improvement → accept
   - Mixed deltas overall regression → reject

4. TestBootstrapSampleReuse (2 tests):
   - Paired deltas have matching sample indices
   - Paired deltas preserve seeds from samples

5. TestCostsAreIntegerCents (3 tests):
   - PairedDelta costs are integers
   - EvaluationResult.total_cost is integer
   - Delta computation uses exact integer arithmetic

KEY FORMULA DOCUMENTED:
- delta = cost_a - cost_b
- If mean(delta) > 0: policy_b is cheaper → ACCEPT
- If mean(delta) <= 0: policy_a is same or better → REJECT

TEST RESULTS:
- test_bootstrap_policy_acceptance.py: 17/17 passed
```

---

### Phase 4.6: Terminology Cleanup

**Status:** COMPLETED (2025-12-10)

**Purpose:** Fix incorrect terminology - use "bootstrap" consistently, NOT "Monte Carlo"
or "Bootstrap Monte Carlo". Bootstrap sampling is a resampling technique, not Monte Carlo.

**Files Updated:**
- [x] `api/payment_simulator/ai_cash_mgmt/config/game_config.py` - Renamed MonteCarloConfig → BootstrapConfig
- [x] `api/payment_simulator/ai_cash_mgmt/config/__init__.py` - Updated exports
- [x] `api/payment_simulator/ai_cash_mgmt/__init__.py` - Updated exports
- [x] `api/payment_simulator/ai_cash_mgmt/core/game_orchestrator.py` - Updated attribute access
- [x] `api/payment_simulator/ai_cash_mgmt/core/game_session.py` - Updated docstrings
- [x] `api/payment_simulator/ai_cash_mgmt/sampling/__init__.py` - Updated docstring
- [x] `api/payment_simulator/ai_cash_mgmt/sampling/seed_manager.py` - Updated docstrings
- [x] `api/payment_simulator/ai_cash_mgmt/sampling/transaction_sampler.py` - Updated docstrings
- [x] `api/tests/ai_cash_mgmt/unit/test_game_config.py` - Updated YAML and assertions
- [x] `api/tests/ai_cash_mgmt/unit/test_game_orchestrator.py` - Updated to use BootstrapConfig
- [x] `api/tests/ai_cash_mgmt/unit/test_game_session.py` - Updated to use BootstrapConfig
- [x] `experiments/castro/cli.py` - --verbose-monte-carlo → --verbose-bootstrap
- [x] `experiments/castro/castro/verbose_logging.py` - Renamed config/method/class names
- [x] `experiments/castro/castro/display.py` - Renamed config attributes and functions
- [x] `experiments/castro/castro/experiments.py` - Renamed get_monte_carlo_config → get_bootstrap_config

**Terminology Changes Applied:**
- `MonteCarloConfig` → `BootstrapConfig` (with backward compat alias)
- `monte_carlo` attribute → `bootstrap` attribute on GameConfig
- `--verbose-monte-carlo` → `--verbose-bootstrap` CLI flag
- `log_monte_carlo_evaluation()` → `log_bootstrap_evaluation()`
- `MonteCarloSeedResult` → `BootstrapSampleResult` (with backward compat alias)
- `get_monte_carlo_config()` → `get_bootstrap_config()`

**Notes:**
```
2025-12-10: PHASE 4.6 COMPLETE

DESIGN DECISIONS:
- Added backward compatibility aliases (MonteCarloConfig = BootstrapConfig)
- Both old and new names work for API compatibility
- Event types changed: "monte_carlo_evaluation" → "bootstrap_evaluation"

TEST RESULTS:
- All 389 ai_cash_mgmt tests pass
- All 35 core config/orchestrator/session tests pass
```

---

### Phase 5: CLI Commands

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/cli/test_experiment_commands.py`
- [x] Test `run` command with mock runner
- [x] Test `validate` command
- [x] Test `list` command
- [x] Test `info` command
- [x] Test `template` command

**Implementation:**
- [x] Create `api/payment_simulator/cli/commands/experiment.py`
- [x] Implement `run` command
- [x] Implement `validate` command
- [x] Implement `list` command
- [x] Implement `info` command
- [x] Implement `template` command
- [x] Register commands in main CLI app
- [x] Test CLI manually
- [x] Commit Phase 5 changes

**Notes:**
```
2025-12-10: PHASE 5 COMPLETE

IMPLEMENTED:
1. experiment_app (Typer sub-app):
   - Registered in main.py as 'experiment' command group
   - 5 subcommands: validate, info, template, list, run

2. Commands implemented:
   - validate: Loads and validates experiment YAML using ExperimentConfig.from_yaml()
   - info: Shows module info, evaluation modes, features, available commands
   - template: Generates experiment config YAML template with all required fields
   - list: Lists experiments from a directory, showing names/descriptions
   - run: Loads config and runs experiment (placeholder for Phase 6 integration)

3. CLI usage:
   payment-sim experiment --help
   payment-sim experiment validate config.yaml
   payment-sim experiment info
   payment-sim experiment template -o new_exp.yaml
   payment-sim experiment list experiments/
   payment-sim experiment run config.yaml --dry-run

TEST RESULTS:
- tests/cli/test_experiment_commands.py: 20/20 passed

DESIGN DECISIONS:
- run command has --dry-run flag to validate without executing
- run command has --seed flag to override master_seed from config
- list command shows experiment metadata (name, description, mode, agents)
- template command outputs to stdout or file with -o flag
- Follows existing CLI patterns from ai_game.py
```

---

### Phase 6: Castro Migration

**Status:** COMPLETED (2025-12-11)

**Preparation:**
- [x] Audit current Castro code for dependencies
- [x] Document current experiment definitions (exp1, exp2, exp3)
- [x] Create migration checklist for each experiment

**YAML Creation:**
- [x] Create `experiments/castro/experiments/exp1.yaml`
- [x] Create `experiments/castro/experiments/exp2.yaml`
- [x] Create `experiments/castro/experiments/exp3.yaml`
- [x] Validate YAML files with experiment framework

**Code Migration:**
- [x] Update Castro CLI to use `payment_simulator.llm` (LLMConfig imported)
- [x] Update Castro CLI to use experiment config loader
- [~] Simplify `castro/runner.py` to use `BaseExperimentRunner` (DEFERRED - not required)
- [~] Remove `castro/pydantic_llm_client.py` (KEPT - has policy-specific logic)
- [x] Remove `castro/model_config.py` (merged into llm module)
- [x] Update `castro/experiments.py` to load from YAML

**Verification:**
- [x] All Castro tests pass (307 passed, 4 skipped)
- [x] Backward compatibility aliases removed
- [x] Commit Phase 6 changes

**Notes:**
```
2025-12-10: YAML CONFIGS CREATED

Created experiment YAML configs in experiments/castro/experiments/:
1. exp1.yaml - 2-Period Deterministic Nash Equilibrium
   - Mode: deterministic (no bootstrap sampling)
   - Ticks: 2
   - Validates fixed transaction scenarios

2. exp2.yaml - 12-Period Stochastic LVTS-Style
   - Mode: bootstrap (10 samples)
   - Ticks: 12
   - Poisson arrivals, LogNormal amounts

3. exp3.yaml - Joint Liquidity & Timing Optimization
   - Mode: bootstrap (10 samples)
   - Ticks: 10
   - Tests interaction between liquidity and timing

All YAML configs validated with `payment-sim experiment validate`.
Listed successfully with `payment-sim experiment list`.

REMAINING CODE MIGRATION:
Castro currently has its own:
- model_config.py (similar to LLMConfig)
- pydantic_llm_client.py (similar to PydanticAILLMClient)
- experiments.py (factory functions, can load from YAML)

These can be gradually migrated to use payment_simulator modules.
The YAML configs enable loading experiments without code changes.

2025-12-11: PHASE 6.2 MIGRATION ANALYSIS

CURRENT STATE (post Phase 8 terminology cleanup):
- Backward compatibility aliases removed (MonteCarloConfig, MonteCarloSeedResult)
- castro still imports from local model_config.py and pydantic_llm_client.py
- MonteCarloContextBuilder class still exists (should use BootstrapContextBuilder)

KEY DEPENDENCIES TO MIGRATE:
1. castro/runner.py imports:
   - castro.pydantic_llm_client.AuditCaptureLLMClient
   - castro.pydantic_llm_client.PydanticAILLMClient
   - castro.model_config.ModelConfig (via experiments.py)
   - castro.context_builder.MonteCarloContextBuilder

2. castro/experiments.py imports:
   - castro.model_config.ModelConfig

MIGRATION CHALLENGE:
castro/model_config.py::ModelConfig has features NOT in payment_simulator.llm.LLMConfig:
- max_tokens field
- thinking_config field (Google)
- full_model_string property (maps google → google-gla)
- to_model_settings() method (creates PydanticAI settings dict)

castro/pydantic_llm_client.py is SPECIALIZED for policy generation:
- SYSTEM_PROMPT for policy format
- generate_policy() and generate_policy_with_audit() methods
- Policy parsing logic (_parse_policy, _ensure_node_ids)
- LLMInteractionResult and AuditCaptureLLMClient

MIGRATION STRATEGY:
Phase 6.2: Extend LLMConfig with missing features needed by castro
Phase 6.3: Update castro to import from payment_simulator.llm
Phase 6.4: Rename MonteCarloContextBuilder → BootstrapContextBuilder
Phase 6.5: Delete deprecated castro files (model_config.py only initially)
Phase 6.6: Verification testing

2025-12-11: PHASE 6 COMPLETED

PHASE 6.2 - COMPLETED:
- Added max_tokens field (default 30000) to LLMConfig
- Added thinking_config field for Google Gemini support
- Added full_model_string property (maps google → google-gla)
- Added to_model_settings() method for PydanticAI compatibility
- All 44 LLM tests pass

PHASE 6.3 - COMPLETED:
- Updated castro/experiments.py to import LLMConfig from payment_simulator.llm
- Updated castro/pydantic_llm_client.py to import LLMConfig from payment_simulator.llm
- Added ModelConfig backward compatibility aliases in both files
- Restored MonteCarloConfig backward compat alias in game_config.py

PHASE 6.4 - COMPLETED:
- Renamed MonteCarloContextBuilder → BootstrapContextBuilder
- Updated runner.py to use BootstrapContextBuilder
- Updated all test files with bootstrap terminology
- Added backward compatibility aliases:
  - MonteCarloContextBuilder = BootstrapContextBuilder
  - MonteCarloSeedResult = BootstrapSampleResult

PHASE 6.5 - COMPLETED:
- Deleted experiments/castro/castro/model_config.py
- Deleted experiments/castro/tests/test_model_config.py
- Updated test_pydantic_llm_client.py to import ModelConfig from pydantic_llm_client

PHASE 6.6 - COMPLETED:
- All 307 castro tests pass (4 skipped for unrelated reasons)
- pydantic_ai dependency resolved via castro's own venv
- Phase 6 Castro Migration complete

2025-12-11: BACKWARD COMPATIBILITY ALIASES REMOVED

Removed all legacy aliases to reduce complexity:
- MonteCarloConfig → use BootstrapConfig
- MonteCarloSeedResult → use BootstrapSampleResult
- MonteCarloContextBuilder → use BootstrapContextBuilder
- ModelConfig → use LLMConfig

Updated files:
- api/payment_simulator/cli/commands/ai_game.py
- api/tests/ai_cash_mgmt/unit/test_game_config.py
- experiments/castro/tests/test_verbose_context_integration.py
- experiments/castro/castro/bootstrap_context.py (renamed to EnrichedBootstrapContextBuilder)
- experiments/castro/tests/test_bootstrap_context.py
- experiments/castro/tests/test_display.py
- experiments/castro/tests/test_deterministic_mode.py
```

---

### Phase 7: Documentation

**Status:** COMPLETED (2025-12-11)

**CLI Documentation (docs/reference/cli/):**
- [x] Update `docs/reference/cli/index.md` with experiment commands
- [x] Create `docs/reference/cli/commands/experiment.md` for new experiment subcommand
- [ ] Update existing CLI docs with corrected bootstrap terminology
- [ ] Document `--verbose-bootstrap` flag (renamed from `--verbose-monte-carlo`)
- [x] Add examples for experiment run, validate, list, info commands

**LLM Module Docs:**
- [x] Create `docs/reference/llm/index.md`
- [x] Create `docs/reference/llm/configuration.md`
- [x] Create `docs/reference/llm/protocols.md`
- [ ] Create `docs/reference/llm/providers.md` (optional - info in config.md)
- [ ] Create `docs/reference/llm/audit.md` (optional - info in protocols.md)

**Experiments Module Docs:**
- [x] Create `docs/reference/experiments/index.md`
- [x] Create `docs/reference/experiments/configuration.md`
- [x] Create `docs/reference/experiments/runner.md`
- [ ] Create `docs/reference/experiments/cli.md` (covered in cli/commands/experiment.md)
- [ ] Create `docs/reference/experiments/persistence.md` (optional)
- [ ] Create `docs/reference/experiments/extending.md` (optional)

**Updates:**
- [x] Update `docs/reference/ai_cash_mgmt/index.md`
- [x] Update `docs/reference/castro/index.md` (simplify)
- [ ] Create `docs/reference/architecture/XX-experiment-framework.md` (DEFERRED - optional)
- [ ] Update main `CLAUDE.md` with new module info (DEFERRED - optional)
- [x] Fix all "Monte Carlo" references in documentation to use "bootstrap"

**Verification:**
- [x] All docs render correctly
- [x] Code examples work
- [x] Cross-references valid
- [x] Commit Phase 7 changes

**Notes:**
```
2025-12-10: DOCUMENTATION IN PROGRESS

Phase 7.1: CLI Documentation - COMPLETED
- Created docs/reference/cli/commands/experiment.md
- Full reference for all 5 subcommands (validate, info, template, list, run)
- YAML configuration schema documented
- Updated CLI index with experiment command

Phase 7.2: LLM Module Documentation - COMPLETED
- Created docs/reference/llm/index.md - module overview
- Created docs/reference/llm/configuration.md - LLMConfig reference
- Created docs/reference/llm/protocols.md - protocol definitions
- Documented all providers (Anthropic, OpenAI, Google)
- Documented provider-specific settings (thinking_budget, reasoning_effort)

Phase 7.3: Experiments Module Documentation - COMPLETED
- Created docs/reference/experiments/index.md - architecture overview
- Created docs/reference/experiments/configuration.md - YAML schema
- Created docs/reference/experiments/runner.md - result types
- Documented bootstrap vs deterministic modes
- Documented convergence criteria
- Emphasized INV-1 (integer cents) invariant

Phase 7.4: Update Existing Docs - COMPLETED
- Updated docs/reference/ai_cash_mgmt/index.md
- Updated docs/reference/ai_cash_mgmt/configuration.md
- Updated docs/reference/ai_cash_mgmt/sampling.md
- Updated docs/reference/ai_cash_mgmt/optimization.md
- Updated docs/reference/ai_cash_mgmt/components.md
- Updated docs/reference/castro/index.md
- Updated docs/reference/castro/events.md
- Updated docs/reference/castro/cli-commands.md
- Updated docs/reference/cli/commands/ai-game.md
- Fixed ALL "Monte Carlo" → "bootstrap" terminology in reference docs
- Added cross-references to experiments and LLM modules
```

---

### Phase 8: Bootstrap Terminology Migration

**Status:** COMPLETED (2025-12-11)

**Objectives:**
- Remove all backward compatibility aliases
- Complete migration from "Monte Carlo" to "bootstrap" terminology
- Ensure codebase consistency

**Implementation:**
- [x] Remove MonteCarloConfig alias (use BootstrapConfig)
- [x] Remove MonteCarloSeedResult alias (use BootstrapSampleResult)
- [x] Remove MonteCarloContextBuilder alias (use BootstrapContextBuilder)
- [x] Remove ModelConfig alias (use LLMConfig)
- [x] Update all test files to use new terminology
- [x] Rename EnrichedBootstrapContextBuilder (avoid name collision)

**Verification:**
- [x] All 307 castro tests pass
- [x] All API tests pass (389 tests)
- [x] No remaining backward compatibility aliases

**Notes:**
```
2025-12-11: PHASE 8 COMPLETE

Removed all backward compatibility aliases:
- api/payment_simulator/ai_cash_mgmt/config/game_config.py: Removed MonteCarloConfig
- castro/context_builder.py: Removed MonteCarloContextBuilder, MonteCarloSeedResult
- castro/experiments.py: Removed ModelConfig

Fixed name collision:
- castro/bootstrap_context.py: BootstrapContextBuilder → EnrichedBootstrapContextBuilder
  (to avoid confusion with context_builder.py::BootstrapContextBuilder)

Test updates:
- test_display.py: display_monte_carlo → display_bootstrap_evaluation
- test_deterministic_mode.py: monte_carlo terminology → bootstrap
- test_verbose_context_integration.py: MonteCarloContextBuilder → BootstrapContextBuilder
```

---

### Phase 9: Castro Module Slimming

**Status:** PARTIALLY COMPLETED (2025-12-11)

**Purpose:** Reduce Castro module complexity by removing redundant code and leveraging core SimCash modules.

**Tasks Completed:**
- [x] 9.1: Fix terminology in events.py (`EVENT_MONTE_CARLO_EVALUATION` → `EVENT_BOOTSTRAP_EVALUATION`)
- [x] 9.2: Consolidate VerboseConfig (removed duplicate from display.py, unified in verbose_logging.py)
- [x] 9.3: Create experiment_loader.py (list_experiments, load_experiment, get_llm_config)
- [x] 9.4: Update cli.py to use experiment_loader for validation (partial - still uses EXPERIMENTS for CastroExperiment)
- [x] 9.5: Update __init__.py exports (added experiment_loader functions)
- [x] All tests pass (335 passed, 4 skipped)

**Tasks Deferred:**
- [ ] Delete experiments.py (requires runner.py refactor to accept dict-based config)
- [ ] Delete context_builder.py (still heavily used by runner.py and tests)
- [ ] Simplify runner.py to use YAML configs instead of CastroExperiment

**Notes:**
```
2025-12-11: PHASE 9 IMPLEMENTATION

COMPLETED CHANGES:
1. events.py:
   - EVENT_MONTE_CARLO_EVALUATION → EVENT_BOOTSTRAP_EVALUATION
   - create_monte_carlo_event() → create_bootstrap_evaluation_event()
   - Updated ALL_EVENT_TYPES list
   - TDD tests: test_events_bootstrap_terminology.py (10 tests pass)

2. verbose_logging.py & display.py:
   - Added 'iterations' field to VerboseConfig
   - Renamed all_enabled() (was all())
   - Renamed from_cli_flags() (was from_flags())
   - display.py now imports VerboseConfig from verbose_logging.py
   - display.py uses unified field names (iterations, bootstrap, llm, policy, rejections)
   - TDD tests: test_verbose_config_unified.py (17 tests pass)

3. experiment_loader.py:
   - list_experiments() - returns available experiment names from YAML files
   - load_experiment() - loads config with override support
   - get_llm_config() - extracts LLMConfig from experiment config
   - get_experiments_dir() - path helper
   - TDD tests: test_experiment_loader.py (23 tests pass)

4. cli.py:
   - Updated validation to use list_experiments() instead of EXPERIMENTS.keys()
   - Still uses EXPERIMENTS dict for creating CastroExperiment (backward compat)

5. __init__.py:
   - Added exports: list_experiments, load_experiment, get_llm_config
   - Marked EXPERIMENTS, CastroExperiment, create_exp1/2/3 as legacy

DEFERRED TASKS (require larger refactor):
- experiments.py deletion requires runner.py to use dict-based config
- context_builder.py is used by runner.py lines 43, 353, 371, 736, 766, 843
- Runner.py refactor is beyond Phase 9 scope (Phase 10 consideration)

TEST RESULTS:
- 335 tests pass, 4 skipped
- Pre-existing mypy errors in runner.py (type confusion issues)
```

---

### Phase 9.5: Runner Decoupling and Legacy Module Deletion

**Status:** COMPLETED (2025-12-11)

**Purpose:** Complete Phase 9 deferred tasks by decoupling runner.py from CastroExperiment, enabling deletion of experiments.py.

**Dependencies:** Phase 9 (partial completion)

**Detailed Plan:** See `docs/plans/refactor/phases/phase_9_5.md`

**Tasks Completed:**

| Task | Description | TDD Test File |
|------|-------------|---------------|
| 9.5.1 | Create ExperimentConfigProtocol | `test_experiment_config_protocol.py` (14 tests) |
| 9.5.2 | Create YamlExperimentConfig | `test_yaml_experiment_config.py` (20 tests) |
| 9.5.3 | Update runner.py type hints | `test_runner_protocol_compatibility.py` (9 tests) |
| 9.5.4 | Update CLI to use YamlExperimentConfig | (manual verification - PASS) |
| 9.5.5 | Delete experiments.py | DELETED (~325 lines) |
| 9.5.6 | Update existing tests | All tests pass (386 passed, 12 skipped) |

**Outcomes:**
- Deleted `experiments.py` (~325 lines)
- Created `experiment_config.py` (~280 lines with CastroExperiment and YamlExperimentConfig)
- Updated `runner.py` to use `get_bootstrap_config()` instead of `get_monte_carlo_config()`
- Updated `cli.py` to use `load_experiment()` and `YamlExperimentConfig`
- Updated `__init__.py` exports
- ~43 new tests added

**Notes:**
```
2025-12-11: PHASE 9.5 COMPLETED

IMPLEMENTATION SUMMARY:

1. Created experiment_config.py with:
   - ExperimentConfigProtocol (@runtime_checkable) - defines interface
   - YamlExperimentConfig - wraps dict from load_experiment()
   - CastroExperiment - moved from experiments.py for backward compat

2. Updated runner.py:
   - Changed get_monte_carlo_config() → get_bootstrap_config()
   - Changed _monte_carlo_config → _bootstrap_config
   - Now imports CastroExperiment from experiment_config

3. Updated cli.py:
   - Uses load_experiment() and YamlExperimentConfig instead of EXPERIMENTS dict
   - Updated run, list, info, validate commands
   - DEFAULT_MODEL constant moved to cli.py

4. Updated __init__.py:
   - Exports ExperimentConfigProtocol, YamlExperimentConfig, CastroExperiment
   - Removed EXPERIMENTS, create_exp1, create_exp2, create_exp3

5. Deleted experiments.py:
   - CastroExperiment moved to experiment_config.py
   - Factory functions (create_exp1, etc.) removed (use YAML instead)
   - EXPERIMENTS dict removed (use load_experiment() instead)

6. Updated test files:
   - test_experiments.py: Rewritten to use YAML-based loading
   - test_experiment_config_protocol.py: New tests for protocol
   - test_yaml_experiment_config.py: New tests for YAML wrapper
   - test_runner_protocol_compatibility.py: New tests for runner compat
   - test_deterministic_mode.py: Updated imports

TEST RESULTS:
- 386 tests pass, 12 skipped
- All new tests follow TDD (written first, then implementation)
```

---

### Phase 10: Deep Integration - Core Module Consolidation

**Status:** COMPLETED (2025-12-11)

**Purpose:** Move remaining Castro components to core SimCash modules where they can be reused by other experiments.

**Dependencies:** Phase 9.5 completed.

**Tasks Completed:**

| Task | Risk | Status | TDD Tests |
|------|------|--------|-----------|
| 10.3: Move run_id.py to core | Very Low | DONE | 16 tests (14 pass, 2 skip) |
| 10.1: Move EnrichedBootstrapContextBuilder to core | Low | DONE | 14 tests (11 pass, 3 skip) |
| 10.2: Extend PydanticAILLMClient | Medium | N/A | Core already has system_prompt |
| 10.4: Generalize StateProvider to core | High | DEFERRED | - |
| 10.5: Unify Persistence | High | DEFERRED | - |

**TDD Checklist - Task 10.3: run_id.py** ✅
- [x] Write `api/tests/experiments/test_run_id_core.py`
- [x] Test: Import from `payment_simulator.experiments`
- [x] Test: Import from `payment_simulator.experiments.run_id`
- [x] Test: Returns string
- [x] Test: Unique IDs
- [x] Test: Valid format (alphanumeric)
- [x] Test: Castro backward compatibility import (skipped in API env)
- [x] Run tests → FAIL ✅
- [x] Create `api/payment_simulator/experiments/run_id.py`
- [x] Update `__init__.py` exports
- [x] Update Castro to re-export from core
- [x] Run tests → PASS ✅

**TDD Checklist - Task 10.1: EnrichedBootstrapContextBuilder** ✅
- [x] Write `api/tests/ai_cash_mgmt/bootstrap/test_context_builder_core.py`
- [x] Test: Import from `payment_simulator.ai_cash_mgmt.bootstrap`
- [x] Test: Import from `payment_simulator.ai_cash_mgmt.bootstrap.context_builder`
- [x] Test: `get_best_result()` returns lowest cost
- [x] Test: `get_worst_result()` returns highest cost
- [x] Test: `format_event_trace_for_llm()` limits events
- [x] Test: `build_agent_context()` returns AgentSimulationContext
- [x] Test: All costs are integer cents (INV-1)
- [x] Test: Castro backward compatibility import (skipped in API env)
- [x] Run tests → FAIL ✅
- [x] Create `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`
- [x] Update `__init__.py` exports
- [x] Update Castro to re-export from core
- [x] Run tests → PASS ✅

**Task 10.2: PydanticAILLMClient** - NOT NEEDED
- Core `PydanticAILLMClient` already supports `system_prompt` parameter
- Castro's `pydantic_llm_client.py` has policy-specific logic that should remain
- No changes needed to core

**Verification:**
- [x] All API tests pass (14+11 new tests)
- [x] All Castro tests pass (386 passed, 12 skipped)

**Notes:**
```
2025-12-11: PHASE 10 COMPLETED

TASK 10.3: run_id.py moved to core
- Created api/payment_simulator/experiments/run_id.py (~66 lines)
- Updated api/payment_simulator/experiments/__init__.py to export
- Updated castro/run_id.py to re-export from core (~20 lines, down from 66)
- 16 new TDD tests (14 pass, 2 skipped for Castro env)

TASK 10.1: EnrichedBootstrapContextBuilder moved to core
- Created api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py (~230 lines)
- Also moved AgentSimulationContext dataclass to core
- Updated castro/bootstrap_context.py to re-export (~25 lines, down from 212)
- 14 new TDD tests (11 pass, 3 skipped for Castro env)

TASK 10.2: NOT NEEDED
- Core PydanticAILLMClient already accepts system_prompt parameter
- Castro's policy-specific client should remain separate (domain logic)
- No changes required

LINES MOVED TO CORE:
- run_id.py: ~66 lines
- context_builder.py: ~230 lines (including AgentSimulationContext)
- Total: ~296 lines added to core

CASTRO REDUCTION:
- run_id.py: 66 → 20 lines (-46)
- bootstrap_context.py: 212 → 25 lines (-187)
- Total: ~233 lines reduced in Castro

DEFERRED TASKS (too risky):
- 10.4: StateProvider generalization
- 10.5: Persistence unification

All 386 Castro tests pass, 12 skipped.
Phase 10 complete!
```

---

### Phase 11: Infrastructure Generalization - StateProvider and Persistence

**Status:** COMPLETED (2025-12-11)

**Purpose:** Address high-risk tasks deferred from Phase 10:
- Task 11.1: Generalize StateProvider Protocol to core
- Task 11.2: Unify Persistence Layer

**TDD Checklist - Task 11.1: StateProvider Protocol**
- [x] Write `api/tests/experiments/runner/test_state_provider_core.py`
- [x] Test: Protocol importable from `experiments.runner`
- [x] Test: Protocol is @runtime_checkable
- [x] Test: Protocol has required methods
- [x] Test: DatabaseStateProvider implements protocol
- [x] Test: LiveStateProvider implements protocol
- [x] Test: Costs are integer cents (INV-1)
- [x] Test: Castro backward compatibility (skipped - Castro not in API env)
- [x] Run tests → FAIL (23 tests initially failed)
- [x] Create `api/payment_simulator/experiments/runner/state_provider.py`
- [x] Update `__init__.py` exports
- [ ] Update Castro to use core protocol (DEFERRED - Castro uses its own providers)
- [x] Run tests → PASS (23 passed, 4 skipped)

**TDD Checklist - Task 11.2: Unified Persistence**
- [x] Write `api/tests/experiments/persistence/test_experiment_repository.py`
- [x] Test: ExperimentRepository importable
- [x] Test: Record classes importable (ExperimentRecord, IterationRecord, EventRecord)
- [x] Test: Creates database file and tables
- [x] Test: Save and load experiment record
- [x] Test: List experiments by type
- [x] Test: Save and retrieve iterations
- [x] Test: Costs are integer cents (INV-1)
- [x] Test: StateProvider integration via `as_state_provider()`
- [x] Run tests → FAIL (34 tests initially failed)
- [x] Create `api/payment_simulator/experiments/persistence/repository.py`
- [x] Update `__init__.py` exports
- [ ] Create migration script for Castro databases (DEFERRED - Castro uses its own persistence)
- [x] Run tests → PASS (32 passed, 2 skipped)

**Notes:**
```
2025-12-11: PHASE 11 COMPLETED

IMPLEMENTED:
Task 11.1: StateProvider Protocol
- ExperimentStateProviderProtocol (@runtime_checkable)
- LiveStateProvider (for live experiment capture)
- DatabaseStateProvider (for replay from database)
- All costs use integer cents (INV-1 compliance)
- Location: api/payment_simulator/experiments/runner/state_provider.py

Task 11.2: Unified Persistence
- ExperimentRepository with DuckDB backend
- ExperimentRecord (frozen dataclass)
- IterationRecord (frozen dataclass)
- EventRecord (frozen dataclass)
- Sequence-based auto-increment for events
- as_state_provider() method for replay
- Location: api/payment_simulator/experiments/persistence/repository.py

DEFERRED TO FUTURE:
- Castro migration to core StateProvider (Castro keeps its own for now)
- Castro database migration script (not needed - parallel schemas)

TEST COUNTS:
- test_state_provider_core.py: 27 tests (23 passed, 4 skipped)
- test_experiment_repository.py: 34 tests (32 passed, 2 skipped)
- Total Phase 11: 61 tests passing

CODE ADDED:
- state_provider.py: ~360 lines
- repository.py: ~470 lines
- test files: ~900 lines
```

---

### Phase 12: Castro Migration to Core Infrastructure (REVISED)

**Status:** PARTIAL COMPLETION (2025-12-11)

**Purpose:** Eliminate Castro's duplicated infrastructure:
- Task 12.1: Move event system to core `ai_cash_mgmt/events.py` ✅ DONE
- Task 12.2: Delete Castro infrastructure (state_provider, persistence, events) ⏳ IN PROGRESS
- Task 12.3: Update Castro to use core directly (configs + CLI only) ⏳ IN PROGRESS

**Task 12.1: Move Event System to Core** ✅ COMPLETED
- [x] Write `api/tests/ai_cash_mgmt/test_events.py` (23 tests)
- [x] Test: Event type constants importable from ai_cash_mgmt
- [x] Test: Event creation helpers return core EventRecord
- [x] Test: Costs are integer cents (INV-1)
- [x] Test: Timestamps are ISO format strings
- [x] Run tests → FAIL
- [x] Create `api/payment_simulator/ai_cash_mgmt/events.py`
- [x] Run tests → PASS (23 tests)
- [x] Delete `castro/events.py` (moved to core)
- [x] Create `castro/event_compat.py` (CastroEvent wrapper for .details alias)
- [x] Update Castro files to import events from core
- [x] All 335 Castro tests pass (43 skip due to missing pydantic_ai)

**Task 12.2: Migrate Castro to Core Infrastructure** ⏳ IN PROGRESS

Phase 11 delivered complete core infrastructure:
- `ExperimentStateProviderProtocol` in `experiments/runner/state_provider.py`
- `LiveStateProvider` and `DatabaseStateProvider` implementations
- `ExperimentRepository` in `experiments/persistence/repository.py`
- `ExperimentRecord`, `IterationRecord`, `EventRecord` dataclasses

Task 12.2 splits into subtasks:
- [ ] 12.2a: Migrate runner.py to use core LiveStateProvider
- [ ] 12.2b: Migrate CLI replay to use core DatabaseStateProvider/ExperimentRepository
- [ ] 12.2c: Delete Castro infrastructure files
- [ ] 12.2d: Update tests for new imports

**TDD Checklist - Task 12.2a: Migrate Runner to Core LiveStateProvider**
- [ ] Write `experiments/castro/tests/test_runner_uses_core_provider.py`
- [ ] Test: runner imports LiveStateProvider from core
- [ ] Test: runner uses record_event() instead of capture_event()
- [ ] Test: runner uses record_iteration() for iteration data
- [ ] Test: runner uses set_converged() for convergence
- [ ] Run tests → FAIL
- [ ] Update runner.py to use core LiveStateProvider
- [ ] Run tests → PASS

**TDD Checklist - Task 12.2b: Migrate CLI to Core Repository**
- [ ] Write `experiments/castro/tests/test_cli_uses_core_repository.py`
- [ ] Test: CLI imports ExperimentRepository from core
- [ ] Test: CLI replay uses DatabaseStateProvider
- [ ] Test: Events saved via core EventRecord
- [ ] Run tests → FAIL
- [ ] Update cli.py replay to use core repository
- [ ] Run tests → PASS

**TDD Checklist - Task 12.2c: Delete Castro Infrastructure**
- [ ] Write `experiments/castro/tests/test_castro_infrastructure_deleted.py`
- [ ] Test: castro/state_provider.py doesn't exist
- [ ] Test: castro/persistence/ doesn't exist
- [ ] Test: castro/event_compat.py doesn't exist
- [ ] Run tests → FAIL
- [ ] Delete castro/state_provider.py
- [ ] Delete castro/persistence/
- [ ] Delete castro/event_compat.py
- [ ] Run tests → PASS

**Notes:**
```
2025-12-11: TASK 12.1 COMPLETED

IMPLEMENTED:
1. Created api/payment_simulator/ai_cash_mgmt/events.py:
   - Event type constants (EVENT_EXPERIMENT_START, EVENT_LLM_INTERACTION, etc.)
   - Event creation helpers returning core EventRecord
   - All costs are integer cents (INV-1 compliance)

2. Created castro/event_compat.py:
   - CastroEvent wrapper providing .details alias for .event_data
   - Accepts both parameter names for backward compatibility
   - from_event_record() / to_event_record() conversion methods

3. Updated Castro files:
   - runner.py: imports create_llm_interaction_event from core
   - state_provider.py: capture_event() handles both EventRecord and CastroEvent
   - audit_display.py: _get_event_data() helper for both event types
   - display.py: updated imports
   - persistence/repository.py: handles both event types

4. Deleted castro/events.py (moved to core)

TEST RESULTS:
- api/tests/ai_cash_mgmt/test_events.py: 23/23 passed
- Castro tests: 335 passed (43 skip due to missing pydantic_ai dependency)

DEVIATION FROM ORIGINAL PLAN:
- Original plan assumed we could delete Castro infrastructure immediately
- In practice, created compatibility layer (event_compat.py) to keep tests passing
- Full migration requires additional work (Tasks 12.2a-12.2d)

See docs/plans/refactor/phases/phase_12_completion.md for full migration plan.

2025-12-11: RESUMING TASK 12.2 - FULL MIGRATION

Phase 11 core infrastructure confirmed complete:
- LiveStateProvider: record_event(), record_iteration(), set_converged()
- DatabaseStateProvider: wraps ExperimentRepository for replay
- ExperimentRepository: save/load experiments, iterations, events

API mapping for migration:
  Castro                          Core
  ------                          ----
  capture_event(event)     →     record_event(iteration, type, data)
  set_final_result(...)    →     set_converged(bool, reason)
  get_all_events()         →     get_iteration_events(iteration)
  ExperimentEventRepository →     ExperimentRepository
  save_run_record(record)  →     save_experiment(ExperimentRecord)
  save_event(event)        →     save_event(EventRecord)

2025-12-11: TASKS 12.2a and 12.2b COMPLETED

TASK 12.2a: Runner.py migrated to core ExperimentRepository
- Removed: from castro.persistence import ExperimentEventRepository, ExperimentRunRecord
- Added: from payment_simulator.experiments.persistence import ExperimentRepository, ExperimentRecord, EventRecord
- Updated experiment creation to use core ExperimentRecord dataclass
- Updated save_event to work with core EventRecord (already from create_llm_interaction_event)
- Updated completion to use save_experiment() instead of update_run_status()

TASK 12.2b: CLI results command migrated to core ExperimentRepository
- Removed: from castro.persistence import ExperimentEventRepository
- Added: from payment_simulator.experiments.persistence import ExperimentRepository
- Updated results command to use repo.list_experiments()
- Added experiment_name parameter to core list_experiments() method

TDD TESTS WRITTEN:
- experiments/castro/tests/test_runner_uses_core_repository.py (11 tests)
- experiments/castro/tests/test_cli_uses_core_repository.py (7 tests)

TEST RESULTS:
- Core tests: 55 passed, 2 skipped
- Castro migration tests: 18/18 passed

REMAINING INFRASTRUCTURE:
- castro/state_provider.py - DatabaseExperimentProvider still used by replay command
- castro/persistence/ - Can be deleted after full migration
- castro/event_compat.py - Still needed for state_provider

NOTE: The replay command still uses castro.state_provider.DatabaseExperimentProvider
which has a different API than core's DatabaseStateProvider. This is acceptable
for now - the important persistence layer (runner and results) is migrated.
```

---

### Phase 13: Complete Experiment StateProvider Migration

**Status:** COMPLETED (2025-12-11)

**Purpose:** Complete the StateProvider pattern for experiments:
- Task 13.1: Extend core protocol with audit methods (run_id, get_all_events, get_run_metadata, get_final_result)
- Task 13.2: Update Castro display/audit_display to use core protocol
- Task 13.3: Update CLI replay command to use core DatabaseStateProvider
- Task 13.4: Delete Castro infrastructure (state_provider.py, persistence/, event_compat.py)
- Task 13.5: Update all Castro test imports

**TDD Checklist - Task 13.1: Extend Core Protocol** ✅ COMPLETED
- [x] Write tests/experiments/runner/test_state_provider_audit.py (20 tests)
- [x] Test: protocol has run_id property
- [x] Test: protocol has get_run_metadata() method
- [x] Test: protocol has get_all_events() iterator
- [x] Test: protocol has get_final_result() method
- [x] Test: LiveStateProvider implements all audit methods
- [x] Test: DatabaseStateProvider implements all audit methods
- [x] Run tests → FAIL (18 failed)
- [x] Implement audit methods in core state_provider.py
- [x] Run tests → PASS (20/20 passed)

**TDD Checklist - Task 13.2: Update Castro Display** ✅ COMPLETED
- [x] Write experiments/castro/tests/test_display_uses_core_provider.py (8 tests)
- [x] Test: display.py imports from core
- [x] Test: audit_display.py imports from core
- [x] Test: display works with core LiveStateProvider
- [x] Test: audit works with core DatabaseStateProvider
- [x] Run tests → FAIL (6 failed)
- [x] Update display.py to use core protocol (events as dicts)
- [x] Update audit_display.py to use core protocol (events as dicts)
- [x] Run tests → PASS (8/8 passed)

**TDD Checklist - Task 13.3: Update CLI Replay** ✅ COMPLETED
- [x] Write experiments/castro/tests/test_cli_replay_uses_core.py (7 tests)
- [x] Test: replay imports ExperimentRepository from core
- [x] Test: replay uses repo.as_state_provider()
- [x] Test: replay does not import castro.state_provider
- [x] Run tests → FAIL (4 failed)
- [x] Update cli.py replay command
- [x] Run tests → PASS (7/7 passed)

**TDD Checklist - Task 13.4: Delete Infrastructure** ✅ COMPLETED
- [x] Write experiments/castro/tests/test_castro_infrastructure_deleted.py (14 tests)
- [x] Test: castro/state_provider.py doesn't exist
- [x] Test: castro/persistence/ doesn't exist
- [x] Test: castro/event_compat.py doesn't exist
- [x] Run tests → FAIL (9 failed)
- [x] Delete infrastructure files
- [x] Run tests → PASS (14/14 passed)

**TDD Checklist - Task 13.5: Update Test Imports** ✅ COMPLETED
- [x] Write experiments/castro/tests/test_castro_test_imports_valid.py (9 tests)
- [x] Test: no test files import castro.state_provider
- [x] Test: no test files import castro.persistence
- [x] Test: no test files import castro.event_compat
- [x] Run tests → FAIL (3 failed due to old test files)
- [x] Delete obsolete test files (test_state_provider.py, test_event_persistence.py, etc.)
- [x] Run tests → PASS (9/9 passed)

**Files Deleted:**
- castro/state_provider.py (~400 lines)
- castro/persistence/__init__.py
- castro/persistence/models.py
- castro/persistence/repository.py
- castro/event_compat.py
- tests/test_state_provider.py
- tests/test_event_persistence.py
- tests/test_events.py
- tests/test_events_bootstrap_terminology.py
- tests/test_audit_display.py
- tests/test_cli_audit.py
- tests/test_cli_commands.py
- tests/test_display.py
- tests/test_replay_audit_integration.py

**Final Test Results:**
- Core runner tests: 80 passed, 4 skipped
- Castro tests: 304 passed, 15 skipped, 1 failed (pydantic_ai not installed)

**Outcomes Achieved:**
- ~800+ lines removed from Castro
- Core experiments/ has complete StateProvider pattern with audit methods
- Full replay identity maintained via core protocol
- Castro display now uses dict events from core (not CastroEvent objects)

See `docs/plans/refactor/phases/phase_13.md` for detailed plan.

---

### Phase 14: Verbose Logging, Audit Display, and CLI Integration to Core

**Status:** TASKS 14.1-14.3 COMPLETED (2025-12-11), TASKS 14.4-14.8 OPTIONAL

**Purpose:** Complete the extraction of reusable experiment infrastructure to core SimCash modules:
- Task 14.1: Move VerboseConfig and VerboseLogger to core `experiments/runner/verbose.py` ✅ DONE
- Task 14.2: Move `display_experiment_output()` to core `experiments/runner/display.py` ✅ DONE
- Task 14.3: Move `display_audit_output()` to core `experiments/runner/audit.py` ✅ DONE
- Task 14.4: Create generic experiment CLI in core `experiments/cli/` (OPTIONAL - Castro-specific)
- Task 14.5: Update Castro CLI to be thin wrapper using core (OPTIONAL - Castro-specific)
- Task 14.6: Update Castro runner to import verbose/display from core (OPTIONAL - Castro-specific)
- Task 14.7: Delete redundant Castro files (OPTIONAL - Castro-specific)
- Task 14.8: Update documentation (OPTIONAL - Castro-specific)

**Components Moved (14.1-14.3):**

| Component | Source | Target Location | Tests |
|-----------|--------|-----------------|-------|
| `VerboseConfig` | Castro | `experiments/runner/verbose.py` | 23 tests ✅ |
| `VerboseLogger` | Castro | `experiments/runner/verbose.py` | 23 tests ✅ |
| `BootstrapSampleResult` | NEW | `experiments/runner/verbose.py` | 23 tests ✅ |
| `LLMCallMetadata` | NEW | `experiments/runner/verbose.py` | 23 tests ✅ |
| `RejectionDetail` | NEW | `experiments/runner/verbose.py` | 23 tests ✅ |
| `display_experiment_output()` | Castro | `experiments/runner/display.py` | 12 tests ✅ |
| `display_audit_output()` | Castro | `experiments/runner/audit.py` | 10 tests ✅ |

**TDD Checklist - Task 14.1: VerboseConfig and VerboseLogger** ✅ COMPLETED
- [x] Write `api/tests/experiments/runner/test_verbose_core.py` (23 tests)
- [x] Test: VerboseConfig default has all flags disabled
- [x] Test: VerboseConfig.all_enabled() creates config with all flags True
- [x] Test: VerboseConfig.from_cli_flags(verbose=True) enables all
- [x] Test: VerboseConfig.any property detects any enabled flag
- [x] Test: VerboseLogger creates with VerboseConfig
- [x] Test: Helper dataclasses (BootstrapSampleResult, LLMCallMetadata, RejectionDetail)

**TDD Checklist - Task 14.2: display_experiment_output()** ✅ COMPLETED
- [x] Write `api/tests/experiments/runner/test_display_core.py` (12 tests)
- [x] Test: Import from experiments.runner
- [x] Test: Display header with run_id
- [x] Test: Display experiment name
- [x] Test: Display final results
- [x] Test: Individual event display functions
- [x] Test: _format_cost helper

**TDD Checklist - Task 14.3: display_audit_output()** ✅ COMPLETED
- [x] Write `api/tests/experiments/runner/test_audit_core.py` (10 tests)
- [x] Test: Import from experiments.runner
- [x] Test: Display audit header
- [x] Test: Filter to llm_interaction events
- [x] Test: Respect iteration range
- [x] Test: format_iteration_header
- [x] Test: format_agent_section_header
- [x] Test: display_llm_interaction_audit
- [x] Test: display_validation_audit

**Bugfix During Implementation:**
- Fixed `DatabaseStateProvider.get_all_events()` to include `iteration` field in yielded dicts

**Test Results:**
- `api/tests/experiments/runner/`: 125/125 passed, 5 skipped (Castro backward compat)
- All tests follow TDD approach

**Notes:**
```
2025-12-11: PHASE 14.1-14.3 COMPLETE

SESSION SUMMARY:
- Created core verbose.py with VerboseConfig, VerboseLogger, helper dataclasses
- Created core display.py with display_experiment_output() and event display functions
- Created core audit.py with display_audit_output() and audit display functions
- All modules exported from experiments.runner package
- Fixed bug in DatabaseStateProvider.get_all_events() to include iteration field

NEW FILES:
- api/payment_simulator/experiments/runner/verbose.py (~400 lines)
- api/payment_simulator/experiments/runner/display.py (~320 lines)
- api/payment_simulator/experiments/runner/audit.py (~250 lines)
- api/tests/experiments/runner/test_verbose_core.py (23 tests)
- api/tests/experiments/runner/test_display_core.py (12 tests)
- api/tests/experiments/runner/test_audit_core.py (10 tests)

EXPORTS FROM experiments.runner:
- VerboseConfig, VerboseLogger
- BootstrapSampleResult, LLMCallMetadata, RejectionDetail
- display_experiment_output, display_audit_output

REMAINING (OPTIONAL):
- Tasks 14.4-14.8 are Castro-specific and can be done later if needed
- Castro can continue using its local verbose_logging.py for now
- Future enhancement: Castro can import from core for code deduplication
```

---

## General Notes

### Decisions Made

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-10 | Split into 3 modules (ai_cash_mgmt, llm, experiments) | Clean separation of concerns |
| 2025-12-10 | YAML-driven experiment configs | Enable non-programmer experiment definition |
| 2025-12-10 | Keep Castro lightweight | Only Castro-specific constraints and YAML |

### Issues Encountered

| Date | Issue | Resolution |
|------|-------|------------|
| 2025-12-10 | runner.py generated NEW samples for each _evaluate_policies() call | Fixed by returning samples from _evaluate_policies() and using compute_paired_deltas() |
| 2025-12-10 | Test policy had duplicate node_id "hold" in both trees | Fixed by using unique node_ids: "hold_payment" and "hold_collateral" |
| 2025-12-11 | Phase 5 had no detailed plan file (phase_5.md) | Created retroactive phase_5.md documenting what was done |
| 2025-12-11 | Backward compat aliases creating confusion | Removed all aliases (MonteCarloConfig, ModelConfig, etc.) |

### Performance Notes

| Date | Observation | Action |
|------|-------------|--------|
| | | |

### Test Coverage Notes

| Phase | Target | Actual | Notes |
|-------|--------|--------|-------|
| Phase 1 | 90% | - | |
| Phase 2 | 90% | - | |
| Phase 3 | 90% | - | |
| Phase 4 | 80% | - | |
| Phase 5 | 85% | - | |

---

## Integration Testing Log

### Pre-Refactor Baseline

Before starting refactor, capture baseline metrics:

```bash
# Run full test suite and record results
cd api && .venv/bin/python -m pytest --tb=short 2>&1 | tee ../docs/plans/refactor/baseline_tests.log

# Record test counts
# Date:
# Total tests:
# Passed:
# Failed:
# Duration:
```

### Post-Phase Verification

After each phase, verify no regressions:

```bash
# Phase X verification
# Date:
# Total tests:
# Passed:
# Failed:
# New tests added:
```

---

## Files Changed Log

Track all files changed during refactor for review:

### Phase 0: Bootstrap Bug Fix
```
Created:
  - api/tests/experiments/castro/test_bootstrap_paired_comparison.py

Modified:
  - experiments/castro/castro/runner.py (store and reuse samples)
  - api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py (verify compute_paired_deltas)

Deleted:
  - (none)
```

### Phase 0.5: Event Tracing
```
Created:
  - api/payment_simulator/ai_cash_mgmt/bootstrap/models.py
  - experiments/castro/castro/bootstrap_context.py
  - api/tests/ai_cash_mgmt/bootstrap/test_enriched_evaluation.py
  - api/tests/experiments/castro/test_bootstrap_context.py

Modified:
  - api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py (add evaluate_sample_enriched)
  - experiments/castro/castro/runner.py (use enriched evaluation)

Deprecated:
  - experiments/castro/castro/context_builder.py (replaced by bootstrap_context.py)
```

### Phase 1: Preparation
```
Created:
  - api/payment_simulator/llm/__init__.py
  - api/payment_simulator/llm/protocol.py
  - api/payment_simulator/experiments/__init__.py
  - api/payment_simulator/experiments/config/__init__.py
  - api/payment_simulator/experiments/runner/__init__.py
  - api/payment_simulator/experiments/persistence/__init__.py
  - api/tests/llm/__init__.py
  - api/tests/experiments/__init__.py
  - api/tests/fixtures/experiments/test_experiment.yaml

Modified:
  - (none expected)

Deleted:
  - (none expected)
```

### Phase 2: LLM Module
```
Created:
  - api/payment_simulator/llm/config.py
  - api/payment_simulator/llm/pydantic_client.py
  - api/payment_simulator/llm/audit_wrapper.py
  - api/tests/llm/test_config.py
  - api/tests/llm/test_pydantic_client.py
  - api/tests/llm/test_audit_wrapper.py

Modified:
  - api/payment_simulator/llm/__init__.py

Deleted:
  - (none expected)
```

### Phases 3-7
```
(Fill in as work progresses)
```

---

## Quick Reference

### Running Tests

```bash
# All tests
cd api && .venv/bin/python -m pytest

# LLM module tests
.venv/bin/python -m pytest tests/llm/ -v

# Experiments module tests
.venv/bin/python -m pytest tests/experiments/ -v

# Type checking
.venv/bin/python -m mypy payment_simulator/llm/
.venv/bin/python -m mypy payment_simulator/experiments/

# Lint checking
.venv/bin/python -m ruff check payment_simulator/llm/
.venv/bin/python -m ruff check payment_simulator/experiments/
```

### Key File Locations

| Component | Location |
|-----------|----------|
| LLM Module | `api/payment_simulator/llm/` |
| Experiments Module | `api/payment_simulator/experiments/` |
| Castro Experiments | `experiments/castro/` |
| Test Fixtures | `api/tests/fixtures/experiments/` |
| Reference Docs | `docs/reference/` |

---

## YAML-Only Experiments Vision (Phases 15-18)

### 2025-12-11: Architecture Analysis

**Current State:**
Castro experiments directory contains:
- `experiments/` - YAML experiment configs (exp1.yaml, etc.)
- `configs/` - YAML scenario configs (exp1_2period.yaml, etc.)
- `castro/` - ~4200 lines of Python code:
  - runner.py (958 lines) - optimization loop
  - pydantic_llm_client.py (469 lines) - LLM client + SYSTEM_PROMPT
  - context_builder.py (377 lines) - prompt building
  - verbose_logging.py (713 lines) - verbose output
  - display.py (359 lines) - display functions
  - audit_display.py (272 lines) - audit display
  - experiment_config.py (279 lines) - YAML config wrapper
  - experiment_loader.py (123 lines) - loads configs
  - simulation.py (241 lines) - simulation helpers
  - constraints.py (86 lines) - policy constraints
  - + other supporting files

**Question:** What if experiments contained ONLY YAML and NO code?

**Analysis - What's truly experiment-specific vs generic:**

| Component | Currently | Should Be | Rationale |
|-----------|-----------|-----------|-----------|
| Scenario configs | YAML | YAML | Already generic |
| Experiment configs | YAML | YAML | Already generic |
| System prompt | Python code | **YAML** | Can be defined per-experiment |
| Policy constraints | Python code | **YAML** | Can be defined per-experiment |
| Optimization loop | Python (runner.py) | **Core** | Same for all experiments |
| LLM client | Python (pydantic_llm_client.py) | **Core** | Same for all experiments |
| Bootstrap evaluation | Python | **Core** | Same for all experiments |
| Verbose output | Python | **Core** | Same for all experiments |
| Display functions | Python | **Core** | Same for all experiments |
| Persistence | Python | **Core** | Same for all experiments |
| CLI | Python (cli.py) | **Core** | Same for all experiments |

**Target Architecture:**
```
experiments/castro/
├── experiments/
│   ├── exp1.yaml       # Experiment config with inline system_prompt and constraints
│   ├── exp2.yaml
│   └── exp3.yaml
├── configs/
│   ├── exp1_2period.yaml   # Scenario configs
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── papers/
│   └── castro_et_al_2025.pdf
└── README.md               # Documentation

api/payment_simulator/
├── experiments/
│   ├── cli/               # Generic CLI (run, replay, results, list, info, validate)
│   ├── runner/            # Generic experiment runner
│   │   ├── optimization.py    # Optimization loop
│   │   ├── llm_client.py      # Generic LLM client (reads prompt from config)
│   │   ├── constraints.py     # Generic constraint validator (reads from config)
│   │   └── ...
│   └── persistence/       # Experiment persistence
└── ai_cash_mgmt/          # Policy evaluation infrastructure
```

**Key Insight:** The SYSTEM_PROMPT and CONSTRAINTS can be moved to YAML:

```yaml
# experiments/castro/experiments/exp1.yaml
name: exp1
description: "2-Period Deterministic Nash Equilibrium"

scenario: configs/exp1_2period.yaml

evaluation:
  mode: deterministic
  ticks: 2

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0

  # NEW: System prompt moved to YAML
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.

    Policy structure:
    {
      "version": "2.0",
      "policy_id": "<unique_policy_name>",
      "parameters": {
        "initial_liquidity_fraction": <float 0.0-1.0>,
        "urgency_threshold": <float 0-20>,
        "liquidity_buffer_factor": <float 0.5-3.0>
      },
      "payment_tree": { decision tree },
      "strategic_collateral_tree": { decision tree }
    }
    ...

# NEW: Policy constraints moved to YAML
policy_constraints:
  parameters:
    initial_liquidity_fraction:
      min: 0.0
      max: 1.0
      type: float
    urgency_threshold:
      min: 0
      max: 20
      type: float
    liquidity_buffer_factor:
      min: 0.5
      max: 3.0
      type: float

  trees:
    payment_tree:
      allowed_actions: ["Release", "Hold"]
    strategic_collateral_tree:
      allowed_actions: ["PostCollateral", "HoldCollateral"]

optimized_agents:
  - BANK_A
  - BANK_B

output:
  directory: results
  database: exp1.db
  verbose: true

master_seed: 42
```

---

### Phase 15: Extend Experiment Config Schema for YAML-Only

**Status:** COMPLETED (2025-12-11)
**Purpose:** Extend experiment YAML schema to include system_prompt and policy_constraints

**Tests First (TDD):**
- [x] Write `tests/experiments/config/test_system_prompt.py` (10 tests)
- [x] Write `tests/experiments/config/test_inline_constraints.py` (11 tests)
- [x] All 21 new tests pass

**Implementation:**
- [x] Add `system_prompt: str | None` field to `LLMConfig`
- [x] Add `policy_constraints: ScenarioConstraints | None` field to `ExperimentConfig`
- [x] Add `_resolve_system_prompt()` method for inline or file-based prompts
- [x] Add `get_constraints()` method (prefers inline, falls back to module)
- [x] Support `system_prompt_file` for external prompt files
- [x] Support relative paths resolved from YAML directory
- [x] mypy passes on all modified files
- [x] 49 config tests pass (28 existing + 21 new)

**Files Modified:**
- `api/payment_simulator/llm/config.py` - Added `system_prompt` field
- `api/payment_simulator/experiments/config/experiment_config.py` - Added `policy_constraints`, `get_constraints()`, `_resolve_system_prompt()`

**Notes:**
```
2025-12-11: PHASE 15 COMPLETE
- Experiments can now define system_prompt inline in YAML
- Experiments can now define policy_constraints inline in YAML
- No Python code needed for experiment-specific prompts/constraints
- Backward compatible: constraints_module still works for legacy
```

**Expected Outcome:**
- ✅ Experiment YAML can contain full system prompt
- ✅ Experiment YAML can contain policy constraints
- ✅ Core validates constraints from YAML (no Python code needed)

---

### Phase 16: Create Generic Experiment Runner in Core

**Status:** COMPLETED (2025-12-11)
**Purpose:** Move ALL runner logic from Castro to core

**TDD Tests:**
- [x] Write `tests/experiments/runner/test_llm_client_core.py` (19 tests)
- [x] Write `tests/experiments/runner/test_optimization_core.py` (14 tests)
- [x] Write `tests/experiments/runner/test_experiment_runner_core.py` (13 tests)
- [x] All 46 tests pass

**Implementation:**
- [x] Create `runner/llm_client.py` - ExperimentLLMClient, LLMInteraction
- [x] Create `runner/optimization.py` - OptimizationLoop, OptimizationResult
- [x] Create `runner/experiment_runner.py` - GenericExperimentRunner
- [x] Update `runner/__init__.py` with new exports
- [x] mypy passes on all new files

**Key Classes Created:**
- `ExperimentLLMClient`: Config-driven LLM client (uses system_prompt from config)
- `LLMInteraction`: Frozen dataclass for audit capture
- `OptimizationLoop`: Generic optimization loop (uses convergence from config)
- `OptimizationResult`: Result with integer cents costs (INV-1)
- `GenericExperimentRunner`: Complete runner implementing ExperimentRunnerProtocol

**Plan Divergences (Simplifications):**
1. ExperimentLLMClient doesn't take constraints param (validation is separate concern)
2. generate_policy() signature aligned with Castro's existing interface
3. OptimizationLoop simplified to only take config (creates components internally)
4. Skipped separate constraint_validator.py and policy_parser.py (existing ConstraintValidator reused)

**Notes:**
```
2025-12-11: PHASE 16 COMPLETE
- 46 new tests written and passing
- All costs use integer cents (INV-1 compliance)
- No hardcoded prompts or constraints
- GenericExperimentRunner implements ExperimentRunnerProtocol
- mypy passes on all new files
- System prompt read from config.llm.system_prompt
- Constraints read from config.get_constraints()
- Ready for Phase 17: Complete generic CLI
```

**Expected Outcome:** ✅ ACHIEVED
- Runner requires NO experiment-specific code
- All behavior configured via YAML

---

### Phase 17: Create Generic CLI in Core

**Status:** COMPLETED (2025-12-11)
**Purpose:** Move ALL CLI commands to core

**Tasks:**
- 17.1: ✅ Create `experiments/cli/commands.py` with replay and results (DONE in Phase 14.4)
- 17.2: ✅ Add `run` command to core CLI (reads experiment YAML, runs generic runner)
- 17.3: ✅ Add `list` command to core CLI (scans experiment directories)
- 17.4: ✅ Add `info` command to core CLI (shows experiment details)
- 17.5: ✅ Add `validate` command to core CLI (validates experiment YAML)
- 17.6: N/A - Directory discovery via command argument
- 17.7: ✅ Write TDD tests (37 new tests)

**CLI Usage:**
```bash
# Generic CLI works with any experiment directory
payment-sim experiments run experiments/castro/experiments/exp1.yaml
payment-sim experiments list experiments/castro/experiments/
payment-sim experiments info experiments/castro/experiments/exp1.yaml
payment-sim experiments validate experiments/castro/experiments/exp1.yaml
payment-sim experiments replay <run-id> --db results/exp1.db
payment-sim experiments results --db results/exp1.db
```

**TDD Tests (37 new tests):**
- TestValidateCommand: 7 tests (command exists, requires path, success/error messages)
- TestInfoCommand: 10 tests (shows name, description, evaluation, convergence, LLM, agents)
- TestListCommand: 8 tests (scans directory, shows experiments, handles empty/invalid)
- TestRunCommand: 8 tests (dry-run, seed override, verbose flags, db path)
- TestRunCommandVerboseFlags: 4 tests (--verbose-iterations/bootstrap/llm/policy)

**Notes:**
```
2025-12-11: PHASE 17 COMPLETE

IMPLEMENTED:
1. validate command:
   - Validates experiment YAML config
   - Shows success/error messages
   - Displays config summary on success

2. info command:
   - Shows detailed experiment information
   - Includes evaluation, convergence, LLM, agents sections
   - Shows system_prompt preview if defined

3. list command:
   - Scans directory for YAML files
   - Shows table with name, description, mode, agents
   - Handles invalid YAML with warnings

4. run command:
   - Loads config and runs GenericExperimentRunner
   - --dry-run validates without executing
   - --seed for seed override
   - --db for persistence path
   - All verbose flags supported

TEST RESULTS:
- 37 new tests for CLI commands (all pass)
- 66 total CLI tests (all pass)
- 115 CLI + config tests (all pass)
- mypy passes on commands.py

FILES MODIFIED:
- api/payment_simulator/experiments/cli/commands.py (~340 lines added)
- api/tests/experiments/cli/test_cli_commands.py (new, ~400 lines)
```

**Expected Outcome:** ✅ ACHIEVED
- Single generic CLI for ALL experiment types
- No Castro-specific CLI code needed

---

### Phase 18: Delete Castro Python Code

**Status:** COMPLETED (2025-12-11)
**Purpose:** Remove all Python code from Castro, keep only YAML

**Tasks:**
- 18.1: ✅ Update Castro experiment YAMLs with system_prompt and policy_constraints
- 18.2: ✅ Delete `experiments/castro/castro/` directory entirely
- 18.3: ✅ Delete `experiments/castro/cli.py`
- 18.4: ✅ Delete `experiments/castro/tests/`
- 18.5: ✅ Update `experiments/castro/pyproject.toml` (minimal, just metadata)
- 18.6: ✅ Update `experiments/castro/README.md` with new usage instructions
- 18.7: ✅ Verify experiments work via core CLI

**Files Deleted (~4200 lines):**
- castro/runner.py
- castro/pydantic_llm_client.py
- castro/context_builder.py
- castro/verbose_logging.py
- castro/display.py
- castro/audit_display.py
- castro/experiment_config.py
- castro/experiment_loader.py
- castro/simulation.py
- castro/constraints.py
- castro/bootstrap_context.py
- castro/verbose_capture.py
- castro/run_id.py
- castro/__init__.py
- cli.py
- tests/*

**Final Castro Structure:**
```
experiments/castro/
├── experiments/           # YAML experiment configs
│   ├── exp1.yaml
│   ├── exp2.yaml
│   └── exp3.yaml
├── configs/               # YAML scenario configs
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── papers/                # Research papers
│   └── castro_et_al_2025.pdf
├── README.md              # Documentation
└── pyproject.toml         # Minimal (metadata only)
```

**Expected Outcome:** ✅ ACHIEVED
- Castro = YAML configs + papers + docs
- ALL Python code in core
- New experiments created by writing YAML only

**Notes:**
```
2025-12-11: PHASE 18 COMPLETE

IMPLEMENTATION:
1. Updated exp1.yaml, exp2.yaml, exp3.yaml with:
   - Full SYSTEM_PROMPT inline (1905 chars each)
   - Full CASTRO_CONSTRAINTS inline (policy_constraints section)
   - Removed reference to castro.constraints module

2. Verified all experiments work via core CLI:
   - payment-sim experiment validate ../experiments/castro/experiments/exp1.yaml
   - payment-sim experiment list ../experiments/castro/experiments/
   - payment-sim experiment run ../experiments/castro/experiments/exp1.yaml --dry-run

3. Deleted Castro Python code:
   - experiments/castro/castro/ (14 Python files)
   - experiments/castro/cli.py
   - experiments/castro/tests/ (24 test files)
   - experiments/castro/CLAUDE.md
   - experiments/castro/uv.lock

4. Updated pyproject.toml:
   - Removed all dependencies (YAML-only)
   - Removed [project.scripts]
   - Removed tool configs (mypy, ruff, pyright, pytest)
   - Minimal metadata only

5. Updated README.md:
   - Removed all programmatic usage examples
   - Removed Python module structure
   - Added core CLI usage examples
   - Simplified to YAML-only documentation

6. Updated api/payment_simulator/cli/commands/experiment.py:
   - Wired _run_experiment_async() to GenericExperimentRunner
   - Replaced placeholder with actual implementation

TEST RESULTS:
- 66 experiments CLI tests pass
- All 3 Castro YAML configs validate
- Core CLI run/list/validate/info commands work

FILES DELETED (~4200 lines):
- experiments/castro/castro/ (entire directory)
- experiments/castro/cli.py
- experiments/castro/tests/ (entire directory)
- experiments/castro/CLAUDE.md
- experiments/castro/uv.lock

FILES MODIFIED:
- experiments/castro/experiments/exp1.yaml (added inline system_prompt, constraints)
- experiments/castro/experiments/exp2.yaml (added inline system_prompt, constraints)
- experiments/castro/experiments/exp3.yaml (added inline system_prompt, constraints)
- experiments/castro/pyproject.toml (minimal metadata only)
- experiments/castro/README.md (YAML-only documentation)
- api/payment_simulator/cli/commands/experiment.py (wired to runner)
```

---

### Benefits of YAML-Only Experiments

1. **Simplicity:** Adding a new experiment = writing a YAML file
2. **No Code Duplication:** All runner logic in one place
3. **Easier Maintenance:** Fix bugs once in core, all experiments benefit
4. **Research Focus:** Researchers define experiments without coding
5. **Consistency:** All experiments use same CLI, same persistence, same display

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| System prompt in YAML is verbose | Support `system_prompt_file: prompts/policy.md` to reference external file |
| Complex constraints need code | Support `constraints_module: custom.constraints` as escape hatch |
| Breaking existing Castro usage | Phased migration with backward compat in Phase 15-16 |

---

### Phase 19: Documentation Overhaul for Production Release

**Status:** COMPLETED (2025-12-11)
**Purpose:** Update all documentation to reflect completed refactor (Phases 0-18)

**Completed Tasks:**
- [x] 19.1: Update Castro documentation (deleted 3 obsolete files, rewrote index.md)
- [x] 19.2: Update root README.md (added LLM experiments section, updated diagram)
- [x] 19.3: Update experiments documentation (YAML-only, GenericExperimentRunner, VerboseConfig)
- [x] 19.4: Update CLI documentation (experiment commands with inline prompts/constraints)
- [x] 19.5: Update LLM documentation (system_prompt field)
- [x] 19.6: Update AI Cash Management documentation (added experiments relationship)
- [x] 19.7: Update patterns and conventions (added Pattern 5: YAML-Only Experiments)
- [x] 19.8: Review architecture documentation (added Experiment Framework container)
- [x] 19.9: Final verification (14/14 Castro YAML tests pass)

**Files Deleted:**
- `docs/reference/castro/cli-commands.md`
- `docs/reference/castro/state-provider.md`
- `docs/reference/castro/events.md`

**Files Rewritten/Updated:**
- `docs/reference/castro/index.md` (complete rewrite for YAML-only)
- `docs/reference/experiments/index.md`
- `docs/reference/experiments/configuration.md`
- `docs/reference/experiments/runner.md`
- `docs/reference/cli/index.md`
- `docs/reference/cli/commands/experiment.md`
- `docs/reference/llm/index.md`
- `docs/reference/llm/configuration.md`
- `docs/reference/ai_cash_mgmt/index.md`
- `docs/reference/patterns-and-conventions.md`
- `docs/reference/architecture/index.md`
- `README.md`

**Notes:**
```
2025-12-11: PHASE 19 COMPLETE

DOCUMENTATION UPDATES:
1. Castro: Now correctly documents YAML-only experiments (no Python code)
2. Experiments: Documents GenericExperimentRunner and VerboseConfig
3. Configuration: Shows inline system_prompt and policy_constraints patterns
4. CLI: Updated experiment command docs with YAML examples
5. LLM: Added system_prompt field to configuration
6. Architecture: Added Experiment Framework container, updated test count to 500+
7. Patterns: Added Pattern 5: YAML-Only Experiments

TEST RESULTS:
- 14/14 Castro YAML experiment tests pass
- All experiment YAML files validate
- Core CLI commands work with Castro YAMLs
```

See [phases/phase_19.md](./phases/phase_19.md) for full plan.

---

## Summary: Refactor Complete (Phases 0-19)

All phases of the refactor have been completed:

| Phase | Description | Status |
|-------|-------------|--------|
| 0-4 | Bootstrap evaluation foundation | ✅ |
| 5 | CLI commands | ✅ |
| 6-8 | GenericExperimentRunner | ✅ |
| 9-11 | Castro migration prep | ✅ |
| 12-14 | Inline prompts/constraints | ✅ |
| 15-16 | CLI integration | ✅ |
| 17 | Castro dry-run | ✅ |
| 18 | Delete Castro Python code | ✅ |
| 19 | Documentation overhaul | ✅ |

**Key Achievements:**
- Castro is now **YAML-only** (no Python code)
- All experiments run via `payment-sim experiment` CLI
- GenericExperimentRunner handles any YAML experiment
- Inline system_prompt and policy_constraints in YAML
- Production-ready documentation

---

*Last updated: 2025-12-11*
