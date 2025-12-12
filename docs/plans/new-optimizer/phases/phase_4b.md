# Phase 4B: Complete Experiment Runner Integration

## Objective

Complete the integration of the new optimizer prompt system with the experiment runner. The building blocks (schema injection, system prompt builder, event filter, user prompt builder) exist and are tested, but are NOT wired into the actual optimization flow.

## Current State

### What Exists (but is NOT used):
1. `PolicyOptimizer.get_system_prompt()` - builds filtered schema prompt
2. `PolicyOptimizer.optimize(events=...)` - accepts events for filtering
3. `event_filter.py` - filters events by agent isolation rules
4. `user_prompt_builder.py` - builds user prompt with filtered events

### What's Missing:
1. `OptimizationLoop._optimize_agent()` does NOT pass events to optimizer
2. `ExperimentLLMClient` uses static `config.system_prompt`, not dynamic builder
3. Events collected in simulation are never used for agent isolation

## Architecture Change

### Before (Current):
```
OptimizationLoop._optimize_agent()
    │
    ├─ _run_simulation_with_events() → EnrichedEvaluationResult (events collected)
    │                                   └─ events DISCARDED!
    │
    └─ PolicyOptimizer.optimize()
           │
           ├─ build_single_agent_context() → User prompt (no events)
           │
           └─ ExperimentLLMClient.generate_policy()
                  └─ Uses config.system_prompt (static YAML)
```

### After (Target):
```
OptimizationLoop._optimize_agent()
    │
    ├─ _run_simulation_with_events() → EnrichedEvaluationResult (events)
    │                                   └─ events PASSED to optimizer
    │
    └─ PolicyOptimizer.optimize(events=collected_events)
           │
           ├─ get_system_prompt() → Filtered schema prompt (cached)
           │
           ├─ build_user_prompt() with event filtering → Agent-isolated events
           │
           └─ ExperimentLLMClient.generate_policy(system_prompt=dynamic)
                  └─ Uses dynamic system prompt from builder
```

## TDD Approach

### Test File: `api/tests/experiments/integration/test_optimizer_runner_integration.py`

### Test Group 1: Events Passed to Optimizer

```python
class TestEventsPassedToOptimizer:
    """Tests that simulation events are passed to the optimizer."""

    @pytest.fixture
    def mock_policy_optimizer(self) -> MagicMock:
        """Create mock optimizer that captures calls."""
        optimizer = MagicMock(spec=PolicyOptimizer)
        optimizer.optimize = AsyncMock(return_value=OptimizationResult(...))
        return optimizer

    @pytest.mark.asyncio
    async def test_optimize_agent_passes_events(
        self, optimization_loop: OptimizationLoop, mock_policy_optimizer: MagicMock
    ) -> None:
        """_optimize_agent passes simulation events to optimizer."""
        # Setup
        optimization_loop._policy_optimizer = mock_policy_optimizer
        optimization_loop._current_enriched_results = [
            EnrichedEvaluationResult(
                sample_idx=0,
                seed=12345,
                total_cost=10000,
                event_trace=(BootstrapEvent(tick=1, event_type="Arrival", details={}),),
                ...
            )
        ]

        # Execute
        await optimization_loop._optimize_agent("BANK_A", current_cost=10000)

        # Verify events were passed
        call_kwargs = mock_policy_optimizer.optimize.call_args.kwargs
        assert "events" in call_kwargs
        assert call_kwargs["events"] is not None
        assert len(call_kwargs["events"]) > 0

    @pytest.mark.asyncio
    async def test_events_converted_to_dict_format(
        self, optimization_loop: OptimizationLoop, mock_policy_optimizer: MagicMock
    ) -> None:
        """Events are converted from BootstrapEvent to dict format."""
        # Setup with BootstrapEvent objects
        bootstrap_event = BootstrapEvent(
            tick=1,
            event_type="Arrival",
            details={"sender_id": "BANK_A", "receiver_id": "BANK_B", "amount": 10000}
        )
        optimization_loop._current_enriched_results = [
            EnrichedEvaluationResult(
                event_trace=(bootstrap_event,),
                ...
            )
        ]
        optimization_loop._policy_optimizer = mock_policy_optimizer

        # Execute
        await optimization_loop._optimize_agent("BANK_A", current_cost=10000)

        # Verify events are dicts
        events = mock_policy_optimizer.optimize.call_args.kwargs["events"]
        assert all(isinstance(e, dict) for e in events)
        assert events[0]["event_type"] == "Arrival"
```

### Test Group 2: Dynamic System Prompt

```python
class TestDynamicSystemPrompt:
    """Tests for dynamic system prompt integration."""

    @pytest.mark.asyncio
    async def test_llm_client_receives_dynamic_system_prompt(
        self, optimization_loop: OptimizationLoop
    ) -> None:
        """LLM client receives dynamically-built system prompt."""
        # Setup mock LLM client that captures system prompt
        mock_client = MagicMock()
        mock_client.generate_policy = AsyncMock(return_value=valid_policy)
        mock_client.captured_system_prompt = None

        async def capture_call(prompt, current_policy, context, system_prompt=None):
            mock_client.captured_system_prompt = system_prompt
            return valid_policy

        mock_client.generate_policy.side_effect = capture_call
        optimization_loop._llm_client = mock_client

        # Execute
        await optimization_loop._optimize_agent("BANK_A", current_cost=10000)

        # Verify dynamic system prompt was passed
        assert mock_client.captured_system_prompt is not None
        # Should include filtered schema content
        assert "payment_tree" in mock_client.captured_system_prompt

    @pytest.mark.asyncio
    async def test_system_prompt_includes_filtered_actions(
        self, optimization_loop: OptimizationLoop
    ) -> None:
        """System prompt includes only allowed actions from constraints."""
        # Setup with specific constraints
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]}
        )
        optimization_loop._constraints = constraints

        # Get system prompt
        system_prompt = optimization_loop._policy_optimizer.get_system_prompt()

        assert "Release" in system_prompt
        assert "Hold" in system_prompt
        # Split should NOT be in prompt if not in allowed_actions
```

### Test Group 3: Agent Isolation End-to-End

```python
class TestAgentIsolationEndToEnd:
    """Tests for agent isolation in actual optimization flow."""

    @pytest.mark.asyncio
    async def test_agent_only_sees_own_transactions(
        self, optimization_loop: OptimizationLoop
    ) -> None:
        """Agent A only sees its own transactions in LLM prompt."""
        # Setup events with multiple agents
        events = [
            BootstrapEvent(tick=1, event_type="Arrival", details={
                "sender_id": "BANK_A", "receiver_id": "BANK_B", "amount": 10000
            }),
            BootstrapEvent(tick=1, event_type="Arrival", details={
                "sender_id": "BANK_C", "receiver_id": "BANK_D", "amount": 99999
            }),
        ]
        optimization_loop._current_enriched_results = [
            EnrichedEvaluationResult(event_trace=tuple(events), ...)
        ]

        # Capture the prompt sent to LLM
        captured_prompt = None
        async def capture(prompt, *args, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return valid_policy

        optimization_loop._llm_client.generate_policy = capture

        # Execute for BANK_A
        await optimization_loop._optimize_agent("BANK_A", current_cost=10000)

        # BANK_A should see its outgoing transaction
        assert "BANK_A" in captured_prompt
        # BANK_C -> BANK_D should NOT be visible (isolation)
        assert "99999" not in captured_prompt
        assert "$999.99" not in captured_prompt
```

## Implementation Steps

### Step 1: Write Integration Tests (TDD)

Create `api/tests/experiments/integration/test_optimizer_runner_integration.py` with tests above.

### Step 2: Update LLMClientProtocol

Add optional `system_prompt` parameter to `generate_policy`:

```python
# In policy_optimizer.py
class LLMClientProtocol(Protocol):
    async def generate_policy(
        self,
        prompt: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
        system_prompt: str | None = None,  # NEW
    ) -> dict[str, Any]:
        ...
```

### Step 3: Update ExperimentLLMClient

Accept dynamic system prompt, fall back to config:

```python
# In llm_client.py
async def generate_policy(
    self,
    prompt: str,
    current_policy: dict[str, Any],
    context: dict[str, Any],
    system_prompt: str | None = None,  # NEW
) -> dict[str, Any]:
    # Use dynamic system prompt if provided, else fall back to config
    effective_system_prompt = system_prompt or self.system_prompt or ""
    ...
```

### Step 4: Update PolicyOptimizer.optimize()

Pass system prompt to LLM client:

```python
# In policy_optimizer.py, optimize() method
# Get cached system prompt
system_prompt = self.get_system_prompt(cost_rates)

# Pass to LLM client
new_policy = await llm_client.generate_policy(
    prompt=prompt,
    current_policy=current_policy,
    context={"iteration": current_iteration},
    system_prompt=system_prompt,  # NEW
)
```

### Step 5: Update OptimizationLoop._optimize_agent()

Pass events to optimizer:

```python
# In optimization.py, _optimize_agent() method

# Collect events from current evaluation results
collected_events: list[dict[str, Any]] = []
for result in self._current_enriched_results:
    for event in result.event_trace:
        collected_events.append({
            "tick": event.tick,
            "event_type": event.event_type,
            **event.details,
        })

# Pass events to optimizer
opt_result = await self._policy_optimizer.optimize(
    agent_id=agent_id,
    current_policy=current_policy,
    ...
    events=collected_events,  # NEW
)
```

### Step 6: Run Tests and Verify

```bash
# Run new integration tests
uv run pytest tests/experiments/integration/test_optimizer_runner_integration.py -v

# Run all optimizer tests
uv run pytest tests/ai_cash_mgmt/ -v

# Run mypy
uv run mypy payment_simulator/
```

## Acceptance Criteria

1. [ ] New integration tests pass
2. [ ] Events from simulation are passed to `PolicyOptimizer.optimize()`
3. [ ] Dynamic system prompt is passed to LLM client
4. [ ] Agent isolation is enforced in actual optimization flow
5. [ ] Backward compatibility maintained (config system_prompt still works as fallback)
6. [ ] All existing tests pass
7. [ ] mypy passes

## Files to Modify

| File | Changes |
|------|---------|
| `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py` | Pass system_prompt to LLM client |
| `api/payment_simulator/experiments/runner/llm_client.py` | Accept system_prompt parameter |
| `api/payment_simulator/experiments/runner/optimization.py` | Pass events to optimizer |
| `api/tests/experiments/integration/test_optimizer_runner_integration.py` | NEW: Integration tests |

## Notes

- The `best_seed_output` and `worst_seed_output` are pre-formatted strings, not raw events
- For full isolation, these should also be filtered, but that's a separate concern
- Backward compatibility is critical - existing YAML configs should still work
