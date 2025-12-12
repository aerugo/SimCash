# Phase 4: Integration with Optimization Loop

## Objective
Wire the new prompt builders into the existing optimization infrastructure, replacing the old `build_single_agent_context` with the new modular system:
- System prompt: Schema-filtered, scenario-specific (built once per session)
- User prompt: Agent-filtered events, iteration history (built per iteration)

## Key Integration Points

### Current Architecture
```
PolicyOptimizer.optimize()
    └── build_single_agent_context()  ← Single combined prompt
        └── Returns user prompt only (system prompt in LLMConfig)
```

### New Architecture
```
PolicyOptimizer.optimize()
    └── build_system_prompt(constraints)        ← Built once, cached
    └── build_user_prompt(agent_id, policy, events)  ← Per iteration
        └── filter_events_for_agent()           ← Agent isolation
```

## Files to Modify

### 1. `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py`
- Add imports for new prompt builders
- Add `_system_prompt` caching
- Replace `build_single_agent_context` call with `build_user_prompt`
- Pass simulation events for agent filtering

### 2. `api/payment_simulator/experiments/runner/llm_client.py`
- May need updates to support dynamic system prompt

### 3. `api/payment_simulator/experiments/runner/optimization.py` (if exists)
- Update to pass events through to optimizer

## TDD Approach

### Test Group 1: System Prompt Caching
```python
class TestSystemPromptCaching:
    """Tests for system prompt caching in optimizer."""

    def test_system_prompt_built_once():
        """System prompt is built once and cached."""
        optimizer = PolicyOptimizer(constraints)
        optimizer.set_cost_rates(rates)

        prompt1 = optimizer.get_system_prompt()
        prompt2 = optimizer.get_system_prompt()

        assert prompt1 is prompt2  # Same object (cached)

    def test_system_prompt_includes_filtered_schema():
        """System prompt includes schema filtered by constraints."""
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]}
        )
        optimizer = PolicyOptimizer(constraints)

        prompt = optimizer.get_system_prompt()

        assert "Release" in prompt
        assert "Hold" in prompt
        assert "Split" not in prompt

    def test_system_prompt_rebuilds_after_constraints_change():
        """System prompt rebuilds if constraints change."""
        optimizer = PolicyOptimizer(constraints)
        prompt1 = optimizer.get_system_prompt()

        optimizer.update_constraints(new_constraints)
        prompt2 = optimizer.get_system_prompt()

        assert prompt1 != prompt2
```

### Test Group 2: User Prompt with Event Filtering
```python
class TestUserPromptEventFiltering:
    """Tests for event filtering in user prompt."""

    def test_user_prompt_filters_events():
        """User prompt only includes target agent's events."""
        optimizer = PolicyOptimizer(constraints)
        events = [
            {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_C"},
        ]

        result = await optimizer.optimize(
            agent_id="BANK_A",
            events=events,
            ...
        )

        # BANK_B -> BANK_C transaction should not appear
        # This is tested via mock LLM checking the prompt content

    def test_user_prompt_includes_current_policy():
        """User prompt includes current policy JSON."""
        optimizer = PolicyOptimizer(constraints)
        policy = {"payment_tree": {"type": "action", "action": "Release"}}

        user_prompt = optimizer._build_user_prompt(
            agent_id="BANK_A",
            current_policy=policy,
            events=[],
            history=[],
        )

        assert "Release" in user_prompt
        assert "BANK_A" in user_prompt

    def test_user_prompt_includes_history():
        """User prompt includes iteration history."""
        optimizer = PolicyOptimizer(constraints)
        history = [
            {"iteration": 1, "total_cost": 10000},
            {"iteration": 2, "total_cost": 8000},
        ]

        user_prompt = optimizer._build_user_prompt(
            agent_id="BANK_A",
            current_policy={},
            events=[],
            history=history,
        )

        assert "iteration" in user_prompt.lower()
```

### Test Group 3: Integration with LLM Client
```python
class TestLLMClientIntegration:
    """Tests for integration with ExperimentLLMClient."""

    def test_optimizer_uses_dynamic_system_prompt():
        """Optimizer passes system prompt to LLM client."""
        constraints = ScenarioConstraints(...)
        optimizer = PolicyOptimizer(constraints)
        mock_client = MockLLMClient()

        await optimizer.optimize(
            agent_id="BANK_A",
            llm_client=mock_client,
            ...
        )

        # Verify system prompt was passed
        assert mock_client.last_system_prompt is not None
        assert "Release" in mock_client.last_system_prompt

    def test_optimizer_passes_filtered_events():
        """Optimizer filters events before building prompt."""
        events = [
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", ...},
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_B", ...},
        ]
        mock_client = MockLLMClient()

        await optimizer.optimize(
            agent_id="BANK_A",
            events=events,
            llm_client=mock_client,
            ...
        )

        # BANK_B's outgoing should be filtered
        assert "BANK_B" not in mock_client.last_user_prompt or "receiver" in mock_client.last_user_prompt
```

### Test Group 4: Backward Compatibility
```python
class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_optimize_works_without_events():
        """Optimize works when events not provided (backward compat)."""
        optimizer = PolicyOptimizer(constraints)

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            # events not provided
            ...
        )

        # Should not crash, just show "no events"

    def test_optimize_works_with_legacy_parameters():
        """All existing parameters still work."""
        optimizer = PolicyOptimizer(constraints)

        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=5,
            current_metrics={"total_cost_mean": 12500},
            iteration_history=[...],
            best_seed_output="...",
            worst_seed_output="...",
            ...
        )

        assert result is not None
```

## Implementation Plan

### Step 1: Create Integration Tests (TDD)
Create `api/tests/ai_cash_mgmt/integration/test_optimizer_prompt_integration.py`

### Step 2: Add Events Parameter to PolicyOptimizer
Modify `PolicyOptimizer.optimize()` to accept `events` parameter.

### Step 3: Add System Prompt Caching
Add `_system_prompt: str | None` field and `get_system_prompt()` method.

### Step 4: Replace Prompt Building
Replace `build_single_agent_context()` call with:
1. `build_system_prompt()` (cached)
2. `build_user_prompt()` with filtered events

### Step 5: Update LLM Client Integration
Ensure the system prompt is passed correctly to the LLM.

### Step 6: Run Tests and Verify
Run all new and existing tests.

## API Changes

### PolicyOptimizer.optimize() - New Parameter
```python
async def optimize(
    self,
    agent_id: str,
    current_policy: dict[str, Any],
    current_iteration: int,
    current_metrics: dict[str, Any],
    llm_client: LLMClientProtocol,
    llm_model: str,
    current_cost: float = 0.0,
    iteration_history: list[SingleAgentIterationRecord] | None = None,
    # NEW: Simulation events for filtering
    events: list[dict[str, Any]] | None = None,
    # Existing parameters...
    best_seed_output: str | None = None,
    worst_seed_output: str | None = None,
    ...
) -> OptimizationResult:
```

### New Methods
```python
def get_system_prompt(self) -> str:
    """Get or build cached system prompt."""

def set_cost_rates(self, rates: dict[str, Any]) -> None:
    """Set cost rates for system prompt."""

def _build_user_prompt(
    self,
    agent_id: str,
    current_policy: dict[str, Any],
    events: list[dict[str, Any]],
    history: list[dict[str, Any]],
    cost_breakdown: dict[str, Any] | None = None,
) -> str:
    """Build user prompt with filtered events."""
```

## Acceptance Criteria

1. [ ] Integration tests pass
2. [ ] System prompt is cached (not rebuilt every call)
3. [ ] Events are filtered by agent isolation rules
4. [ ] Backward compatible with existing callers
5. [ ] All existing optimizer tests still pass
6. [ ] mypy passes

## Dependencies

- Phase 1: `schema_injection.py`
- Phase 2: `system_prompt_builder.py`
- Phase 3: `event_filter.py`, `user_prompt_builder.py`

## Notes

- The `best_seed_output` and `worst_seed_output` parameters currently contain raw verbose logs
- These need to be filtered through `filter_events_for_agent()` to maintain isolation
- The LLMClientProtocol may need updating to support dynamic system prompts
