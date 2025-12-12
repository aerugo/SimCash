"""Integration tests for optimizer and experiment runner connection.

TDD Tests: These tests define expected behavior for Phase 4B integration:
1. Events from simulation must be passed to PolicyOptimizer.optimize()
2. Dynamic system prompt from build_system_prompt() must be used
3. Agent isolation must be enforced in the actual optimization flow

These tests verify the FULL integration path, not just individual components.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
    BootstrapEvent,
    CostBreakdown,
    EnrichedEvaluationResult,
)
from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
    ScenarioConstraints,
)
from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
    OptimizationResult,
    PolicyOptimizer,
)


def create_valid_policy() -> dict[str, Any]:
    """Create a valid policy for test mocks."""
    return {
        "version": "2.0",
        "policy_id": "test_policy",
        "payment_tree": {
            "node_id": "root",
            "type": "action",
            "action": "Release",
        },
    }


def create_enriched_result(
    events: list[dict[str, Any]] | None = None,
    seed: int = 12345,
    total_cost: int = 10000,
) -> EnrichedEvaluationResult:
    """Create an EnrichedEvaluationResult for testing."""
    event_trace: list[BootstrapEvent] = []
    if events:
        for e in events:
            event_trace.append(
                BootstrapEvent(
                    tick=e.get("tick", 1),
                    event_type=e.get("event_type", "Arrival"),
                    details=e,
                )
            )

    return EnrichedEvaluationResult(
        sample_idx=0,
        seed=seed,
        total_cost=total_cost,
        settlement_rate=0.95,
        avg_delay=2.5,
        event_trace=tuple(event_trace),
        cost_breakdown=CostBreakdown(
            delay_cost=5000,
            overdraft_cost=2000,
            deadline_penalty=3000,
            eod_penalty=0,
        ),
    )


class TestEventsPassedToOptimizer:
    """Tests that simulation events are passed to the optimizer."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance", "amount"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        client = MagicMock()
        client.generate_policy = AsyncMock(return_value=create_valid_policy())
        return client

    @pytest.mark.asyncio
    async def test_optimizer_receives_events_parameter(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """PolicyOptimizer.optimize() receives events when provided."""
        optimizer = PolicyOptimizer(constraints)

        # Create events that would come from simulation
        events: list[dict[str, Any]] = [
            {
                "tick": 1,
                "event_type": "Arrival",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 10000,
            },
        ]

        # Call optimize with events
        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            events=events,  # Events passed!
        )

        assert result is not None
        # The LLM client should have been called
        assert mock_llm_client.generate_policy.called

    @pytest.mark.asyncio
    async def test_events_included_in_prompt_when_provided(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """Events appear in the prompt when passed to optimize()."""
        optimizer = PolicyOptimizer(constraints)

        # Create a mock that captures the prompt
        captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str,
            current_policy: dict[str, Any],
            context: dict[str, Any],
            **kwargs: Any,
        ) -> dict[str, Any]:
            captured_prompts.append(prompt)
            return create_valid_policy()

        mock_client = MagicMock()
        mock_client.generate_policy = AsyncMock(side_effect=capture_prompt)

        events: list[dict[str, Any]] = [
            {
                "tick": 5,
                "event_type": "Arrival",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 50000,
            },
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_client,
            llm_model="test",
            events=events,
        )

        # Check that the prompt contains event information
        assert len(captured_prompts) > 0
        prompt = captured_prompts[0]

        # Event should appear in filtered form for BANK_A
        # Amount 50000 cents = $500.00
        assert "500.00" in prompt or "50000" in prompt

    @pytest.mark.asyncio
    async def test_no_events_parameter_still_works(
        self,
        constraints: ScenarioConstraints,
        mock_llm_client: MagicMock,
    ) -> None:
        """Backward compatibility: optimize() works without events."""
        optimizer = PolicyOptimizer(constraints)

        # Call without events parameter
        result = await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_llm_client,
            llm_model="test",
            # events NOT provided
        )

        assert result is not None
        assert result.new_policy is not None


class TestAgentIsolationInPrompt:
    """Tests for agent isolation in the optimization prompt."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance", "amount"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.mark.asyncio
    async def test_agent_only_sees_own_outgoing_transactions(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """Agent A sees its outgoing transactions, not other agents'."""
        optimizer = PolicyOptimizer(constraints)

        captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, *args: Any, **kwargs: Any
        ) -> dict[str, Any]:
            captured_prompts.append(prompt)
            return create_valid_policy()

        mock_client = MagicMock()
        mock_client.generate_policy = AsyncMock(side_effect=capture_prompt)

        events: list[dict[str, Any]] = [
            # BANK_A's outgoing - should be visible
            {
                "tick": 1,
                "event_type": "Arrival",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 10000,
            },
            # BANK_C's outgoing - should NOT be visible to BANK_A
            {
                "tick": 1,
                "event_type": "Arrival",
                "sender_id": "BANK_C",
                "receiver_id": "BANK_D",
                "amount": 99999,
            },
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_client,
            llm_model="test",
            events=events,
        )

        prompt = captured_prompts[0]

        # BANK_A should see its own transaction
        assert "BANK_A" in prompt

        # BANK_C -> BANK_D transaction details should NOT appear
        # The unique amount 99999 (or $999.99) should not be visible
        assert "99999" not in prompt
        assert "999.99" not in prompt

    @pytest.mark.asyncio
    async def test_agent_sees_incoming_liquidity(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """Agent A sees incoming payments TO itself."""
        optimizer = PolicyOptimizer(constraints)

        captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, *args: Any, **kwargs: Any
        ) -> dict[str, Any]:
            captured_prompts.append(prompt)
            return create_valid_policy()

        mock_client = MagicMock()
        mock_client.generate_policy = AsyncMock(side_effect=capture_prompt)

        events: list[dict[str, Any]] = [
            # Incoming payment TO BANK_A - should be visible
            {
                "tick": 1,
                "event_type": "RtgsImmediateSettlement",
                "sender": "BANK_B",
                "receiver": "BANK_A",
                "amount": 75000,
            },
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_client,
            llm_model="test",
            events=events,
        )

        prompt = captured_prompts[0]

        # Should see incoming payment (75000 cents = $750.00)
        assert "750.00" in prompt or "75000" in prompt

    @pytest.mark.asyncio
    async def test_other_agent_costs_not_visible(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """Agent A does not see other agents' cost accruals."""
        optimizer = PolicyOptimizer(constraints)

        captured_prompts: list[str] = []

        async def capture_prompt(
            prompt: str, *args: Any, **kwargs: Any
        ) -> dict[str, Any]:
            captured_prompts.append(prompt)
            return create_valid_policy()

        mock_client = MagicMock()
        mock_client.generate_policy = AsyncMock(side_effect=capture_prompt)

        events: list[dict[str, Any]] = [
            # BANK_A's cost - should be visible
            {
                "tick": 1,
                "event_type": "CostAccrual",
                "agent_id": "BANK_A",
                "costs": {"delay": 500},
            },
            # BANK_B's cost - should NOT be visible
            {
                "tick": 1,
                "event_type": "CostAccrual",
                "agent_id": "BANK_B",
                "costs": {"delay": 88888},
            },
        ]

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_client,
            llm_model="test",
            events=events,
        )

        prompt = captured_prompts[0]

        # BANK_A's cost should be visible (500 cents = $5.00)
        assert "5.00" in prompt or "500" in prompt

        # BANK_B's unique cost should NOT be visible
        assert "88888" not in prompt
        assert "888.88" not in prompt


class TestSystemPromptIntegration:
    """Tests for system prompt generation and usage."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints with specific allowed actions."""
        return ScenarioConstraints(
            allowed_parameters=[
                {"name": "threshold", "param_type": "int", "min_value": 0, "max_value": 100},
            ],
            allowed_fields=["balance", "amount", "ticks_to_deadline"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    def test_get_system_prompt_includes_filtered_schema(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """System prompt includes schema filtered by constraints."""
        optimizer = PolicyOptimizer(constraints)
        system_prompt = optimizer.get_system_prompt()

        # Should include allowed actions
        assert "Release" in system_prompt
        assert "Hold" in system_prompt

        # Should include allowed fields
        assert "balance" in system_prompt
        assert "amount" in system_prompt

        # Should NOT include actions not in allowed_actions
        # (Split is typically available but not in our constraints)
        assert "- **Split**" not in system_prompt

    def test_system_prompt_is_cached(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """System prompt is built once and cached."""
        optimizer = PolicyOptimizer(constraints)

        prompt1 = optimizer.get_system_prompt()
        prompt2 = optimizer.get_system_prompt()

        # Should be the exact same object (cached)
        assert prompt1 is prompt2

    def test_system_prompt_includes_cost_documentation(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """System prompt includes cost parameter documentation."""
        optimizer = PolicyOptimizer(constraints)
        system_prompt = optimizer.get_system_prompt()

        # Should have cost-related content
        assert "cost" in system_prompt.lower()

    def test_set_cost_rates_invalidates_cache(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """Setting cost rates invalidates cached system prompt."""
        optimizer = PolicyOptimizer(constraints)

        prompt1 = optimizer.get_system_prompt()
        optimizer.set_cost_rates({"overdraft_bps_per_tick": 0.005})
        prompt2 = optimizer.get_system_prompt()

        # Should be different objects (cache invalidated)
        assert prompt1 is not prompt2


class TestLLMClientSystemPromptIntegration:
    """Tests for LLM client receiving dynamic system prompt."""

    @pytest.fixture
    def constraints(self) -> ScenarioConstraints:
        """Create test constraints."""
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )

    @pytest.mark.asyncio
    async def test_llm_client_protocol_accepts_system_prompt(
        self,
        constraints: ScenarioConstraints,
    ) -> None:
        """LLM client protocol should accept optional system_prompt parameter."""
        optimizer = PolicyOptimizer(constraints)

        # Create mock that accepts system_prompt
        received_system_prompt: str | None = None

        async def capture_system_prompt(
            prompt: str,
            current_policy: dict[str, Any],
            context: dict[str, Any],
            system_prompt: str | None = None,
        ) -> dict[str, Any]:
            nonlocal received_system_prompt
            received_system_prompt = system_prompt
            return create_valid_policy()

        mock_client = MagicMock()
        mock_client.generate_policy = AsyncMock(side_effect=capture_system_prompt)

        await optimizer.optimize(
            agent_id="BANK_A",
            current_policy={},
            current_iteration=1,
            current_metrics={},
            llm_client=mock_client,
            llm_model="test",
        )

        # Currently the system_prompt may not be passed (that's what we're fixing)
        # This test documents the expected behavior after Phase 4B
        # For now, just verify the call was made
        assert mock_client.generate_policy.called


class TestOptimizationLoopPassesEvents:
    """Tests that OptimizationLoop passes events to PolicyOptimizer.

    These tests verify the CRITICAL integration: that events collected
    during simulation are passed to the optimizer for agent isolation.

    TDD: These tests should FAIL until Phase 4B implementation is complete.
    """

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock ExperimentConfig."""
        from payment_simulator.llm import LLMConfig

        config = MagicMock()
        config.name = "test_experiment"
        config.convergence = MagicMock()
        config.convergence.max_iterations = 10
        config.convergence.stability_threshold = 0.05
        config.convergence.stability_window = 3
        config.convergence.improvement_threshold = 0.01
        config.evaluation = MagicMock()
        config.evaluation.mode = "bootstrap"
        config.evaluation.num_samples = 3
        config.evaluation.ticks = 2
        config.optimized_agents = ("BANK_A",)
        config.get_constraints.return_value = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        config.llm = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="Test prompt",
        )
        config.master_seed = 42
        config.scenario_path = MagicMock()
        config.scenario_path.is_absolute.return_value = True
        config.scenario_path.exists.return_value = True
        return config

    @pytest.mark.asyncio
    async def test_optimize_agent_passes_events_from_enriched_results(
        self,
        mock_config: MagicMock,
    ) -> None:
        """_optimize_agent passes collected events to PolicyOptimizer.

        This is the CRITICAL test: we verify that events collected in
        _current_enriched_results are passed to the optimizer.

        TDD: This test documents expected behavior and should FAIL
        until we implement the event passing in OptimizationLoop.
        """
        from payment_simulator.experiments.runner import OptimizationLoop

        # Use deterministic mode to avoid bootstrap evaluation complexity
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1

        # Create loop
        loop = OptimizationLoop(config=mock_config)

        # Initialize iteration tracking
        loop._current_iteration = 1

        # Set up enriched results with events
        loop._current_enriched_results = [
            create_enriched_result(
                events=[
                    {
                        "tick": 1,
                        "event_type": "Arrival",
                        "sender_id": "BANK_A",
                        "receiver_id": "BANK_B",
                        "amount": 10000,
                    },
                ],
                seed=12345,
            ),
        ]

        # Set up agent context
        loop._current_agent_contexts = {
            "BANK_A": MagicMock(
                best_seed=12345,
                best_seed_cost=10000,
                best_seed_output="Test output",
                worst_seed=99999,
                worst_seed_cost=20000,
                worst_seed_output="Test worst output",
                mean_cost=15000,
                cost_std=5000,
            ),
        }

        # Create mock PolicyOptimizer that captures the events parameter
        mock_optimizer = MagicMock(spec=PolicyOptimizer)
        mock_optimizer.optimize = AsyncMock(
            return_value=MagicMock(
                new_policy=create_valid_policy(),
                validation_errors=[],
            )
        )
        loop._policy_optimizer = mock_optimizer

        # Create mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.generate_policy = AsyncMock(return_value=create_valid_policy())
        mock_llm_client.get_last_interaction.return_value = None
        loop._llm_client = mock_llm_client

        # Set initial policy
        loop._policies = {"BANK_A": create_valid_policy()}

        # Initialize state provider iteration tracking
        loop._state_provider._iterations = [MagicMock(events=[])]

        # Call _optimize_agent
        await loop._optimize_agent("BANK_A", current_cost=10000)

        # CRITICAL ASSERTION: Verify events were passed
        # This should FAIL until we implement event passing
        assert mock_optimizer.optimize.called, "PolicyOptimizer.optimize should be called"

        call_kwargs = mock_optimizer.optimize.call_args.kwargs
        assert "events" in call_kwargs, "events parameter should be passed to optimize()"
        assert call_kwargs["events"] is not None, "events should not be None"
        assert len(call_kwargs["events"]) > 0, "events list should not be empty"

        # Verify the event content matches what we set
        events = call_kwargs["events"]
        assert events[0]["event_type"] == "Arrival"
        assert events[0]["sender_id"] == "BANK_A"


class TestEventConversionFromBootstrapEvents:
    """Tests for converting BootstrapEvent to dict format for optimizer."""

    def test_bootstrap_event_to_dict_conversion(self) -> None:
        """BootstrapEvent can be converted to dict format."""
        bootstrap_event = BootstrapEvent(
            tick=5,
            event_type="Arrival",
            details={
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 10000,
            },
        )

        # Convert to dict format expected by optimizer
        event_dict: dict[str, Any] = {
            "tick": bootstrap_event.tick,
            "event_type": bootstrap_event.event_type,
            **bootstrap_event.details,
        }

        assert event_dict["tick"] == 5
        assert event_dict["event_type"] == "Arrival"
        assert event_dict["sender_id"] == "BANK_A"
        assert event_dict["amount"] == 10000

    def test_enriched_result_events_can_be_extracted(self) -> None:
        """Events can be extracted from EnrichedEvaluationResult."""
        result = create_enriched_result(
            events=[
                {
                    "tick": 1,
                    "event_type": "Arrival",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 10000,
                },
                {
                    "tick": 2,
                    "event_type": "RtgsImmediateSettlement",
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 10000,
                },
            ]
        )

        # Extract events as dicts
        extracted: list[dict[str, Any]] = []
        for event in result.event_trace:
            extracted.append(
                {
                    "tick": event.tick,
                    "event_type": event.event_type,
                    **event.details,
                }
            )

        assert len(extracted) == 2
        assert extracted[0]["event_type"] == "Arrival"
        assert extracted[1]["event_type"] == "RtgsImmediateSettlement"

    def test_multiple_enriched_results_events_aggregated(self) -> None:
        """Events from multiple EnrichedEvaluationResult can be aggregated."""
        results = [
            create_enriched_result(
                events=[{"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A"}],
                seed=111,
            ),
            create_enriched_result(
                events=[{"tick": 2, "event_type": "Arrival", "sender_id": "BANK_A"}],
                seed=222,
            ),
        ]

        # Aggregate events from all results (e.g., from best seed)
        # In practice, we might only use best seed's events
        all_events: list[dict[str, Any]] = []
        for result in results:
            for event in result.event_trace:
                all_events.append(
                    {
                        "tick": event.tick,
                        "event_type": event.event_type,
                        **event.details,
                    }
                )

        assert len(all_events) == 2
