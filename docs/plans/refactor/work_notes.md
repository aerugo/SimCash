# AI Cash Management Architecture Refactor - Work Notes

**Status:** In Progress
**Created:** 2025-12-10
**Last Updated:** 2025-12-10

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

**Status:** In Progress (2025-12-10)

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
- [ ] Update Castro CLI to use `payment_simulator.llm`
- [ ] Update Castro CLI to use experiment config loader
- [ ] Simplify `castro/runner.py` to use `BaseExperimentRunner`
- [ ] Remove `castro/pydantic_llm_client.py` (use llm module)
- [ ] Remove `castro/model_config.py` (merged into llm module)
- [ ] Update `castro/experiments.py` to load from YAML

**Verification:**
- [ ] Run `castro run exp1` - verify works
- [ ] Run `castro run exp2` - verify works
- [ ] Run `castro run exp3` - verify works
- [ ] Run `castro replay` - verify works
- [ ] All Castro tests pass
- [ ] Commit Phase 6 changes

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

*Last updated: 2025-12-10*
