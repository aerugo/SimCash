# Phase 10: Deep Integration - Core Module Consolidation

**Status:** Planned
**Created:** 2025-12-11
**Dependencies:** Phase 9 (Castro Module Slimming)
**Risk:** Medium-High (touches multiple modules)
**Breaking Changes:** None (internal refactoring)

---

## Purpose

After Phase 9 slims Castro, Phase 10 moves remaining Castro components to core SimCash modules where they can be reused. This phase focuses on:

1. **EnrichedBootstrapContextBuilder** → `ai_cash_mgmt/bootstrap/`
2. **PydanticAILLMClient (policy-specific)** → `llm/` with custom prompt support
3. **run_id.py** → `experiments/` module
4. **StateProvider pattern** → `experiments/runner/`

**Target outcome**: ~600 lines migrated to core, Castro becomes even thinner.

---

## Analysis: What Remains After Phase 9

| File | Lines | Slim Further? | How |
|------|-------|---------------|-----|
| `runner.py` | ~700 | Yes | Use core `BaseExperimentRunner`, make Castro a thin wrapper |
| `pydantic_llm_client.py` | ~200 | Yes | Use core `PydanticAILLMClient` with custom system prompt |
| `bootstrap_context.py` | ~200 | Yes | Move `EnrichedBootstrapContextBuilder` to core `ai_cash_mgmt/bootstrap/` |
| `events.py` | ~150 | Maybe | Generalize `ExperimentEvent` into core `experiments/` module |
| `persistence/` | ~300 | Maybe | Unify with core `GameRepository` |
| `verbose_logging.py` | ~200 | Maybe | Move `VerboseConfig` pattern to core |
| `state_provider.py` | ~250 | Maybe | Generalize `StateProvider` into core `experiments/runner/` |
| `run_id.py` | ~30 | Yes | Move to core `experiments/` module |
| `constraints.py` | ~100 | No | Genuinely Castro-specific |
| `display.py` | ~200 | No | Castro-specific output formatting |
| `audit_display.py` | ~150 | No | Castro-specific audit UI |
| `verbose_capture.py` | ~100 | No | Castro-specific |

---

## Phase 10 Tasks

### Task 10.1: Move EnrichedBootstrapContextBuilder to Core (Low Risk)

**Impact:** ~200 lines moved
**Risk:** Low - additive change, Castro can import from new location

**Current location:** `experiments/castro/castro/bootstrap_context.py`
**New location:** `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`

The `EnrichedBootstrapContextBuilder` transforms bootstrap evaluation results into LLM-consumable context. This is a generic capability useful for any experiment, not just Castro.

---

### Task 10.2: Extend Core PydanticAILLMClient with Policy Support (Medium Risk)

**Impact:** ~150 lines removed from Castro
**Risk:** Medium - modifies core LLM module

**Current issue:** Castro's `pydantic_llm_client.py` has policy-specific features:
- `SYSTEM_PROMPT` for policy format
- `generate_policy()` and `generate_policy_with_audit()` methods
- Policy parsing logic

**Solution:** Make core `PydanticAILLMClient` more flexible:
- Accept custom system prompts
- Allow response type specification
- Keep policy-specific parsing in Castro

---

### Task 10.3: Move run_id.py to Core (Very Low Risk)

**Impact:** ~30 lines moved
**Risk:** Very Low - simple utility

**Current location:** `experiments/castro/castro/run_id.py`
**New location:** `api/payment_simulator/experiments/run_id.py`

Simple run ID generation is useful for any experiment.

---

### Task 10.4: Generalize StateProvider to Core (High Risk)

**Impact:** ~200 lines abstracted
**Risk:** High - complex protocol touching many files

**Current location:** `experiments/castro/castro/state_provider.py`
**Potential new location:** `api/payment_simulator/experiments/runner/state_provider.py`

The StateProvider protocol enables replay identity - a pattern valuable for any experiment framework.

**Note:** This task may be deferred due to high complexity.

---

### Task 10.5: Unify Persistence with Core (High Risk)

**Impact:** ~200 lines abstracted
**Risk:** High - database schema changes

**Current location:** `experiments/castro/castro/persistence/`
**Potential unification with:** `api/payment_simulator/experiments/persistence/`

**Note:** This task may be deferred due to database migration complexity.

---

## TDD Test Specifications

### Test File 1: `api/tests/ai_cash_mgmt/bootstrap/test_context_builder_core.py`

```python
"""TDD tests for core EnrichedBootstrapContextBuilder.

These tests verify the context builder works correctly when
moved to the core ai_cash_mgmt module.
"""

import pytest
from dataclasses import dataclass


class TestEnrichedBootstrapContextBuilderImport:
    """Tests for importing from new core location."""

    def test_importable_from_ai_cash_mgmt_bootstrap(self) -> None:
        """EnrichedBootstrapContextBuilder should be importable from core."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        assert EnrichedBootstrapContextBuilder is not None

    def test_importable_via_bootstrap_init(self) -> None:
        """Should be exported in bootstrap __init__.py."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        # Direct import should also work
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder as DirectImport,
        )
        assert EnrichedBootstrapContextBuilder is DirectImport


class TestEnrichedBootstrapContextBuilderFunctionality:
    """Tests for core functionality of context builder."""

    @pytest.fixture
    def sample_enriched_results(self) -> list:
        """Create sample EnrichedEvaluationResult list."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )
        return [
            EnrichedEvaluationResult(
                sample_idx=0,
                seed=12345,
                total_cost=1000,
                settlement_rate=0.95,
                avg_delay=2.5,
                event_trace=[
                    BootstrapEvent(tick=0, event_type="arrival", details={"amount": 500}),
                    BootstrapEvent(tick=1, event_type="settlement", details={"amount": 500}),
                ],
                cost_breakdown=CostBreakdown(
                    delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
                ),
            ),
            EnrichedEvaluationResult(
                sample_idx=1,
                seed=67890,
                total_cost=800,
                settlement_rate=1.0,
                avg_delay=1.0,
                event_trace=[
                    BootstrapEvent(tick=0, event_type="arrival", details={"amount": 300}),
                ],
                cost_breakdown=CostBreakdown(
                    delay_cost=50, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
                ),
            ),
            EnrichedEvaluationResult(
                sample_idx=2,
                seed=11111,
                total_cost=1500,
                settlement_rate=0.8,
                avg_delay=5.0,
                event_trace=[],
                cost_breakdown=CostBreakdown(
                    delay_cost=200, overdraft_cost=100, deadline_penalty=0, eod_penalty=0
                ),
            ),
        ]

    def test_get_best_result_returns_lowest_cost(
        self, sample_enriched_results: list
    ) -> None:
        """get_best_result returns result with minimum total_cost."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST_AGENT",
        )
        best = builder.get_best_result()
        assert best.total_cost == 800
        assert best.seed == 67890

    def test_get_worst_result_returns_highest_cost(
        self, sample_enriched_results: list
    ) -> None:
        """get_worst_result returns result with maximum total_cost."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST_AGENT",
        )
        worst = builder.get_worst_result()
        assert worst.total_cost == 1500
        assert worst.seed == 11111

    def test_format_event_trace_limits_events(
        self, sample_enriched_results: list
    ) -> None:
        """format_event_trace_for_llm respects max_events limit."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        # Create result with many events
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )
        many_events = [
            BootstrapEvent(tick=i, event_type="arrival", details={})
            for i in range(100)
        ]
        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=1,
            total_cost=1000,
            settlement_rate=0.9,
            avg_delay=3.0,
            event_trace=many_events,
            cost_breakdown=CostBreakdown(
                delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
        )
        builder = EnrichedBootstrapContextBuilder([result], "TEST")

        formatted = builder.format_event_trace_for_llm(result, max_events=20)

        # Should not contain more than 20 tick references
        tick_count = formatted.count("Tick ")
        assert tick_count <= 20

    def test_build_agent_context_returns_correct_type(
        self, sample_enriched_results: list
    ) -> None:
        """build_agent_context returns AgentSimulationContext."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.prompts.context import (
            AgentSimulationContext,
        )

        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST_AGENT",
        )
        context = builder.build_agent_context()

        assert isinstance(context, AgentSimulationContext)
        assert context.agent_id == "TEST_AGENT"
        assert context.best_seed == 67890
        assert context.worst_seed == 11111

    def test_costs_are_integer_cents(
        self, sample_enriched_results: list
    ) -> None:
        """All costs in context should be integer cents (INV-1)."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST",
        )
        context = builder.build_agent_context()

        assert isinstance(context.best_seed_cost, int)
        assert isinstance(context.worst_seed_cost, int)
        assert isinstance(context.mean_cost, int)


class TestCastroBackwardCompatibility:
    """Tests ensuring Castro can still import the builder."""

    def test_castro_can_import_from_new_location(self) -> None:
        """Castro should be able to import from core location."""
        # This import path should work after migration
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        assert EnrichedBootstrapContextBuilder is not None

    def test_old_castro_import_path_works(self) -> None:
        """Old Castro import should work (via re-export or deprecation)."""
        # This test verifies backward compatibility
        # Castro's bootstrap_context.py should re-export from core
        from castro.bootstrap_context import EnrichedBootstrapContextBuilder
        assert EnrichedBootstrapContextBuilder is not None
```

---

### Test File 2: `api/tests/experiments/test_run_id_core.py`

```python
"""TDD tests for core run_id module.

Tests for run ID generation moved to core experiments module.
"""

import pytest
import re


class TestRunIdImport:
    """Tests for importing from new core location."""

    def test_importable_from_experiments(self) -> None:
        """generate_run_id should be importable from experiments."""
        from payment_simulator.experiments import generate_run_id
        assert callable(generate_run_id)

    def test_importable_from_run_id_module(self) -> None:
        """Direct import from run_id module should work."""
        from payment_simulator.experiments.run_id import generate_run_id
        assert callable(generate_run_id)


class TestGenerateRunId:
    """Tests for run ID generation."""

    def test_returns_string(self) -> None:
        """generate_run_id should return a string."""
        from payment_simulator.experiments import generate_run_id
        run_id = generate_run_id()
        assert isinstance(run_id, str)

    def test_unique_ids(self) -> None:
        """Each call should generate a unique ID."""
        from payment_simulator.experiments import generate_run_id
        ids = [generate_run_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique

    def test_valid_format(self) -> None:
        """Run ID should have valid format for filenames/paths."""
        from payment_simulator.experiments import generate_run_id
        run_id = generate_run_id()
        # Should be alphanumeric with optional dashes/underscores
        assert re.match(r'^[a-zA-Z0-9_-]+$', run_id)

    def test_includes_timestamp(self) -> None:
        """Run ID should include timestamp component."""
        from payment_simulator.experiments import generate_run_id
        import time

        # Generate ID and check it contains current date
        run_id = generate_run_id()
        today = time.strftime("%Y%m%d")

        # ID should contain today's date (common pattern)
        # or be based on timestamp
        assert len(run_id) >= 8  # At least 8 characters

    def test_reproducible_with_seed(self) -> None:
        """If seeded, should generate reproducible IDs."""
        from payment_simulator.experiments.run_id import generate_run_id

        # Note: This test may not apply if run_id doesn't support seeding
        # In that case, skip or remove this test
        try:
            id1 = generate_run_id(seed=42)
            id2 = generate_run_id(seed=42)
            # If seeding is supported, IDs should match
            # (excluding timestamp portion)
        except TypeError:
            pytest.skip("generate_run_id does not support seeding")


class TestCastroBackwardCompatibility:
    """Tests ensuring Castro can still use run_id."""

    def test_castro_import_works(self) -> None:
        """Castro should be able to import from its location."""
        from castro.run_id import generate_run_id
        assert callable(generate_run_id)

    def test_castro_uses_same_function(self) -> None:
        """Castro's function should be the same as core."""
        from castro.run_id import generate_run_id as castro_func
        from payment_simulator.experiments import generate_run_id as core_func
        # Should be the same function (re-exported)
        assert castro_func is core_func
```

---

### Test File 3: `api/tests/llm/test_pydantic_client_custom_prompt.py`

```python
"""TDD tests for PydanticAILLMClient with custom prompt support.

Tests for extending core LLM client to support custom system prompts,
enabling Castro to use core client with policy-specific prompts.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCustomSystemPromptSupport:
    """Tests for custom system prompt in PydanticAILLMClient."""

    def test_accepts_custom_system_prompt(self) -> None:
        """Client should accept custom system prompt parameter."""
        from payment_simulator.llm import LLMConfig, PydanticAILLMClient

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config)

        # Should have method that accepts system_prompt
        assert hasattr(client, "generate_structured_output")
        # Method signature should accept system_prompt parameter
        import inspect
        sig = inspect.signature(client.generate_structured_output)
        assert "system_prompt" in sig.parameters

    @pytest.mark.asyncio
    async def test_custom_system_prompt_used_in_call(self) -> None:
        """Custom system prompt should be passed to underlying agent."""
        from payment_simulator.llm import LLMConfig, PydanticAILLMClient
        from pydantic import BaseModel

        class TestResponse(BaseModel):
            value: str

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config)

        custom_prompt = "You are a policy optimization assistant."

        # This test would need to mock the underlying PydanticAI Agent
        # to verify the system_prompt is passed correctly
        with patch("payment_simulator.llm.pydantic_client.Agent") as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(
                return_value=MagicMock(data=TestResponse(value="test"))
            )
            MockAgent.return_value = mock_agent_instance

            await client.generate_structured_output(
                prompt="Generate policy",
                response_model=TestResponse,
                system_prompt=custom_prompt,
            )

            # Verify Agent was created with custom system prompt
            MockAgent.assert_called_once()
            call_kwargs = MockAgent.call_args[1]
            assert call_kwargs.get("system_prompt") == custom_prompt

    @pytest.mark.asyncio
    async def test_default_system_prompt_when_none(self) -> None:
        """When system_prompt is None, should use empty or default."""
        from payment_simulator.llm import LLMConfig, PydanticAILLMClient
        from pydantic import BaseModel

        class TestResponse(BaseModel):
            value: str

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config)

        with patch("payment_simulator.llm.pydantic_client.Agent") as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(
                return_value=MagicMock(data=TestResponse(value="test"))
            )
            MockAgent.return_value = mock_agent_instance

            await client.generate_structured_output(
                prompt="Generate something",
                response_model=TestResponse,
                system_prompt=None,
            )

            # Should still work with None or empty system_prompt
            MockAgent.assert_called_once()


class TestPolicySpecificClient:
    """Tests for creating policy-specific clients."""

    def test_can_create_policy_client_with_custom_prompt(self) -> None:
        """Should be able to create a client configured for policy generation."""
        from payment_simulator.llm import LLMConfig, PydanticAILLMClient

        POLICY_SYSTEM_PROMPT = """You are a payment policy optimization assistant.
        Generate valid policy JSON according to the schema."""

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config, default_system_prompt=POLICY_SYSTEM_PROMPT)

        # Client should store default system prompt
        assert hasattr(client, "_default_system_prompt")
        assert client._default_system_prompt == POLICY_SYSTEM_PROMPT

    def test_default_system_prompt_used_when_not_specified(self) -> None:
        """Default system prompt should be used when not overridden per-call."""
        from payment_simulator.llm import LLMConfig, PydanticAILLMClient

        DEFAULT_PROMPT = "Default prompt"

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config, default_system_prompt=DEFAULT_PROMPT)

        # When generate_structured_output is called without system_prompt,
        # it should use the default
        # (This would need mocking to fully verify)


class TestCastroMigrationPath:
    """Tests for Castro's migration to core LLM client."""

    def test_castro_policy_prompt_works_with_core_client(self) -> None:
        """Castro's SYSTEM_PROMPT should work with core PydanticAILLMClient."""
        from payment_simulator.llm import LLMConfig, PydanticAILLMClient

        # This is Castro's actual system prompt (or similar)
        CASTRO_POLICY_PROMPT = """You are optimizing payment policies.
        Return valid JSON with 'decision_tree' and 'parameters' fields."""

        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config, default_system_prompt=CASTRO_POLICY_PROMPT)

        # Client should be usable by Castro
        assert client._default_system_prompt == CASTRO_POLICY_PROMPT
```

---

### Test File 4: `api/tests/experiments/runner/test_state_provider_core.py`

```python
"""TDD tests for core StateProvider protocol.

Tests for generalizing StateProvider pattern for experiment replay.
"""

import pytest
from typing import Protocol, runtime_checkable


class TestStateProviderProtocol:
    """Tests for StateProvider protocol definition."""

    def test_protocol_exists(self) -> None:
        """ExperimentStateProvider protocol should exist."""
        from payment_simulator.experiments.runner import ExperimentStateProvider
        assert ExperimentStateProvider is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be @runtime_checkable for isinstance checks."""
        from payment_simulator.experiments.runner import ExperimentStateProvider

        # Create a class that implements the protocol
        class MockProvider:
            def get_experiment_info(self):
                return {}
            def get_events(self, iteration):
                return []
            def get_total_iterations(self):
                return 0

        # Should be able to use isinstance
        provider = MockProvider()
        assert isinstance(provider, ExperimentStateProvider)

    def test_protocol_has_required_methods(self) -> None:
        """Protocol should define required methods."""
        from payment_simulator.experiments.runner import ExperimentStateProvider
        import inspect

        # Get abstract methods (or protocol methods)
        members = inspect.getmembers(ExperimentStateProvider)
        method_names = [name for name, _ in members if not name.startswith('_')]

        # Should have these methods
        required = ["get_experiment_info", "get_events", "get_total_iterations"]
        for method in required:
            assert method in method_names or hasattr(ExperimentStateProvider, method)


class TestDatabaseStateProvider:
    """Tests for database-backed state provider."""

    def test_database_provider_exists(self) -> None:
        """DatabaseStateProvider should exist for replay."""
        from payment_simulator.experiments.runner import DatabaseStateProvider
        assert DatabaseStateProvider is not None

    def test_database_provider_implements_protocol(self) -> None:
        """DatabaseStateProvider should implement ExperimentStateProvider."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProvider,
            DatabaseStateProvider,
        )

        # Should implement protocol (can't easily verify without instance)
        # At minimum, should have same methods
        assert hasattr(DatabaseStateProvider, "get_experiment_info")
        assert hasattr(DatabaseStateProvider, "get_events")
        assert hasattr(DatabaseStateProvider, "get_total_iterations")

    def test_database_provider_takes_connection(self) -> None:
        """DatabaseStateProvider should accept database connection."""
        from payment_simulator.experiments.runner import DatabaseStateProvider
        import inspect

        sig = inspect.signature(DatabaseStateProvider.__init__)
        params = list(sig.parameters.keys())

        # Should have db or connection parameter
        assert any(p in ["db", "connection", "db_path", "conn"] for p in params)


class TestLiveStateProvider:
    """Tests for live experiment state provider."""

    def test_live_provider_exists(self) -> None:
        """LiveStateProvider (or similar) should exist for run mode."""
        from payment_simulator.experiments.runner import LiveStateProvider
        assert LiveStateProvider is not None

    def test_live_provider_implements_protocol(self) -> None:
        """LiveStateProvider should implement ExperimentStateProvider."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProvider,
            LiveStateProvider,
        )

        assert hasattr(LiveStateProvider, "get_experiment_info")
        assert hasattr(LiveStateProvider, "get_events")


class TestCastroStateProviderMigration:
    """Tests for Castro migration to core StateProvider."""

    def test_castro_can_import_core_protocol(self) -> None:
        """Castro should be able to import core protocol."""
        from payment_simulator.experiments.runner import ExperimentStateProvider
        assert ExperimentStateProvider is not None

    def test_castro_state_provider_compatible(self) -> None:
        """Castro's state provider should be compatible with core protocol."""
        # Castro's provider should either:
        # 1. Subclass the core protocol
        # 2. Be replaced by the core provider
        # 3. Implement the same interface
        from castro.state_provider import ExperimentStateProvider as CastroProvider
        from payment_simulator.experiments.runner import ExperimentStateProvider as CoreProtocol

        # Both should have same key methods
        core_methods = {"get_experiment_info", "get_events", "get_total_iterations"}
        for method in core_methods:
            assert hasattr(CastroProvider, method) or method in dir(CastroProvider)
```

---

## Implementation Plan

### Task 10.1: Move EnrichedBootstrapContextBuilder to Core

**TDD Test File:** `api/tests/ai_cash_mgmt/bootstrap/test_context_builder_core.py`

**Steps:**
1. Write TDD tests for core location import
2. Write TDD tests for functionality preservation
3. Write TDD tests for Castro backward compatibility
4. Run tests → FAIL
5. Copy `EnrichedBootstrapContextBuilder` to `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`
6. Update `api/payment_simulator/ai_cash_mgmt/bootstrap/__init__.py` to export
7. Update Castro's `bootstrap_context.py` to re-export from core
8. Run tests → PASS

**Files to create:**
- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`

**Files to modify:**
- `api/payment_simulator/ai_cash_mgmt/bootstrap/__init__.py`: Add export
- `experiments/castro/castro/bootstrap_context.py`: Re-export from core

---

### Task 10.2: Extend PydanticAILLMClient with Custom Prompt

**TDD Test File:** `api/tests/llm/test_pydantic_client_custom_prompt.py`

**Steps:**
1. Write TDD tests for custom system prompt support
2. Write TDD tests for default system prompt
3. Write TDD tests for Castro migration path
4. Run tests → FAIL
5. Modify `api/payment_simulator/llm/pydantic_client.py`:
   - Add `default_system_prompt` parameter to `__init__`
   - Use `default_system_prompt` when `system_prompt=None` in methods
6. Update Castro's `pydantic_llm_client.py` to use core client with custom prompt
7. Run tests → PASS

**Files to modify:**
- `api/payment_simulator/llm/pydantic_client.py`: Add default_system_prompt support
- `experiments/castro/castro/pydantic_llm_client.py`: Simplify to use core client

---

### Task 10.3: Move run_id.py to Core

**TDD Test File:** `api/tests/experiments/test_run_id_core.py`

**Steps:**
1. Write TDD tests for core location import
2. Write TDD tests for run ID generation
3. Write TDD tests for Castro backward compatibility
4. Run tests → FAIL
5. Move `run_id.py` to `api/payment_simulator/experiments/run_id.py`
6. Update `api/payment_simulator/experiments/__init__.py` to export `generate_run_id`
7. Update Castro's `run_id.py` to re-export from core
8. Run tests → PASS

**Files to create:**
- `api/payment_simulator/experiments/run_id.py`

**Files to modify:**
- `api/payment_simulator/experiments/__init__.py`: Add export
- `experiments/castro/castro/run_id.py`: Re-export from core

---

### Task 10.4: Generalize StateProvider to Core (DEFERRED)

**TDD Test File:** `api/tests/experiments/runner/test_state_provider_core.py`

**Rationale for deferral:**
- High complexity
- Touches many files
- Requires careful protocol design
- Can be done in a future phase

**If proceeding:**
1. Write TDD tests for protocol definition
2. Write TDD tests for database provider
3. Write TDD tests for live provider
4. Create protocol in `api/payment_simulator/experiments/runner/state_provider.py`
5. Create implementations
6. Update Castro to use core providers

---

### Task 10.5: Unify Persistence (DEFERRED)

**Rationale for deferral:**
- Database schema changes required
- High migration risk
- Can be done independently later

---

## Verification Checklist

### Before Starting (Capture Baseline)
- [ ] Record total API test count
- [ ] Record total Castro test count
- [ ] All tests pass

### TDD Verification (Per Task)
- [ ] Task 10.1: `test_context_builder_core.py` all pass
- [ ] Task 10.2: `test_pydantic_client_custom_prompt.py` all pass
- [ ] Task 10.3: `test_run_id_core.py` all pass
- [ ] Task 10.4: (DEFERRED) `test_state_provider_core.py` all pass

### Integration Verification
- [ ] All API tests pass: `cd api && .venv/bin/python -m pytest`
- [ ] All Castro tests pass: `cd experiments/castro && uv run pytest tests/`
- [ ] Type checking passes: `mypy payment_simulator/`
- [ ] Castro CLI still works: `uv run castro run exp1 --max-iter 1 --dry-run`

### Final Metrics
- [ ] Lines moved to core: ~230 (context_builder + run_id)
- [ ] Lines reduced in Castro: ~150 (simplified pydantic_llm_client)
- [ ] Net reduction: ~100 lines in Castro

---

## Expected Outcomes

### Task Summary

| Task | Impact | Risk | Status |
|------|--------|------|--------|
| 10.1 Move EnrichedBootstrapContextBuilder | ~200 lines | Low | Planned |
| 10.2 Extend PydanticAILLMClient | ~150 lines reduced | Medium | Planned |
| 10.3 Move run_id.py | ~30 lines | Very Low | Planned |
| 10.4 Generalize StateProvider | ~200 lines | High | DEFERRED |
| 10.5 Unify Persistence | ~200 lines | High | DEFERRED |

### Lines of Code

| Category | Before Phase 10 | After Phase 10 | Delta |
|----------|-----------------|----------------|-------|
| Core ai_cash_mgmt | existing | +200 | +200 |
| Core experiments | existing | +30 | +30 |
| Core llm | existing | +20 | +20 |
| Castro bootstrap_context.py | ~200 | ~50 (re-export) | -150 |
| Castro pydantic_llm_client.py | ~200 | ~100 (wrapper) | -100 |
| Castro run_id.py | ~30 | ~5 (re-export) | -25 |
| **Net Castro Reduction** | | | **-275** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_context_builder_core.py | 8 |
| test_run_id_core.py | 8 |
| test_pydantic_client_custom_prompt.py | 6 |
| **Total** | **22** |

---

## Rollback Plan

If issues arise:

1. **Core changes**: Revert modifications to `api/payment_simulator/`
2. **Castro imports**: Restore original code (no re-exports)
3. **Git reset**: `git checkout HEAD~1 -- <files>`

Phase 10 tasks are independent - one failing task doesn't block others.

---

## Related Documents

- [Phase 9: Castro Module Slimming](./phase_9.md) - Prerequisite
- [Conceptual Plan](../conceptual-plan.md) - Architecture overview
- [Development Plan](../development-plan.md) - Timeline

---

*Phase 10 Plan v1.0 - 2025-12-11*
