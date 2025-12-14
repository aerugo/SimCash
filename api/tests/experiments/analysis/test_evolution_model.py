"""Tests for evolution model dataclasses.

TDD tests for LLMInteractionData, IterationEvolution, AgentEvolution,
and build_evolution_output().
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from payment_simulator.experiments.analysis.evolution_model import (
    AgentEvolution,
    IterationEvolution,
    LLMInteractionData,
    build_evolution_output,
)


class TestLLMInteractionData:
    """Tests for LLMInteractionData dataclass."""

    def test_is_immutable(self) -> None:
        """Verify frozen dataclass cannot be modified."""
        llm = LLMInteractionData(
            system_prompt="System prompt",
            user_prompt="User prompt",
            raw_response="Response",
        )

        with pytest.raises(FrozenInstanceError):
            llm.system_prompt = "Modified"  # type: ignore[misc]

    def test_stores_all_fields(self) -> None:
        """Verify all fields are accessible."""
        llm = LLMInteractionData(
            system_prompt="System",
            user_prompt="User",
            raw_response="Response",
        )

        assert llm.system_prompt == "System"
        assert llm.user_prompt == "User"
        assert llm.raw_response == "Response"


class TestIterationEvolution:
    """Tests for IterationEvolution dataclass."""

    def test_is_immutable(self) -> None:
        """Verify frozen dataclass cannot be modified."""
        iteration = IterationEvolution(
            policy={"version": "2.0"},
        )

        with pytest.raises(FrozenInstanceError):
            iteration.policy = {}  # type: ignore[misc]

    def test_optional_fields_default_none(self) -> None:
        """Verify optional fields default to None."""
        iteration = IterationEvolution(
            policy={"version": "2.0"},
        )

        assert iteration.explanation is None
        assert iteration.diff is None
        assert iteration.llm is None
        assert iteration.cost is None
        assert iteration.accepted is None

    def test_all_fields_can_be_set(self) -> None:
        """Verify all fields can be provided."""
        llm = LLMInteractionData(
            system_prompt="System",
            user_prompt="User",
            raw_response="Response",
        )

        iteration = IterationEvolution(
            policy={"version": "2.0", "parameters": {"threshold": 100}},
            explanation="Optimized threshold",
            diff="Changed: parameters.threshold (50 -> 100)",
            llm=llm,
            cost=15000,  # INV-1: Integer cents
            accepted=True,
        )

        assert iteration.policy == {"version": "2.0", "parameters": {"threshold": 100}}
        assert iteration.explanation == "Optimized threshold"
        assert iteration.diff == "Changed: parameters.threshold (50 -> 100)"
        assert iteration.llm is not None
        assert iteration.cost == 15000
        assert iteration.accepted is True


class TestAgentEvolution:
    """Tests for AgentEvolution dataclass."""

    def test_is_immutable(self) -> None:
        """Verify frozen dataclass cannot be modified."""
        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={},
        )

        with pytest.raises(FrozenInstanceError):
            agent.agent_id = "BANK_B"  # type: ignore[misc]

    def test_stores_iterations_dict(self) -> None:
        """Verify iterations dictionary structure."""
        iteration1 = IterationEvolution(policy={"v": 1})
        iteration2 = IterationEvolution(policy={"v": 2})

        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={
                "iteration_1": iteration1,
                "iteration_2": iteration2,
            },
        )

        assert agent.agent_id == "BANK_A"
        assert len(agent.iterations) == 2
        assert "iteration_1" in agent.iterations
        assert "iteration_2" in agent.iterations


class TestBuildEvolutionOutput:
    """Tests for build_evolution_output function."""

    def test_formats_correctly(self) -> None:
        """Verify output matches expected JSON structure."""
        iteration = IterationEvolution(
            policy={"version": "2.0"},
            cost=10000,
            accepted=True,
        )

        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={"iteration_1": iteration},
        )

        output = build_evolution_output([agent])

        assert "BANK_A" in output
        assert "iteration_1" in output["BANK_A"]
        assert "policy" in output["BANK_A"]["iteration_1"]
        assert output["BANK_A"]["iteration_1"]["policy"] == {"version": "2.0"}
        assert output["BANK_A"]["iteration_1"]["cost"] == 10000
        assert output["BANK_A"]["iteration_1"]["accepted"] is True

    def test_handles_optional_fields_excluded_when_none(self) -> None:
        """Verify None fields are excluded from output."""
        iteration = IterationEvolution(
            policy={"version": "2.0"},
            # All optional fields left as None
        )

        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={"iteration_1": iteration},
        )

        output = build_evolution_output([agent])

        iteration_output = output["BANK_A"]["iteration_1"]
        assert "policy" in iteration_output
        assert "explanation" not in iteration_output
        assert "diff" not in iteration_output
        assert "llm" not in iteration_output
        assert "cost" not in iteration_output
        assert "accepted" not in iteration_output

    def test_includes_llm_data_when_present(self) -> None:
        """Verify LLM data is included in output."""
        llm = LLMInteractionData(
            system_prompt="System",
            user_prompt="User",
            raw_response="Response",
        )

        iteration = IterationEvolution(
            policy={"version": "2.0"},
            llm=llm,
        )

        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={"iteration_1": iteration},
        )

        output = build_evolution_output([agent])

        assert "llm" in output["BANK_A"]["iteration_1"]
        assert output["BANK_A"]["iteration_1"]["llm"]["system_prompt"] == "System"
        assert output["BANK_A"]["iteration_1"]["llm"]["user_prompt"] == "User"
        assert output["BANK_A"]["iteration_1"]["llm"]["raw_response"] == "Response"

    def test_handles_multiple_agents(self) -> None:
        """Verify multiple agents are handled correctly."""
        agent_a = AgentEvolution(
            agent_id="BANK_A",
            iterations={"iteration_1": IterationEvolution(policy={"a": 1})},
        )
        agent_b = AgentEvolution(
            agent_id="BANK_B",
            iterations={"iteration_1": IterationEvolution(policy={"b": 2})},
        )

        output = build_evolution_output([agent_a, agent_b])

        assert "BANK_A" in output
        assert "BANK_B" in output
        assert output["BANK_A"]["iteration_1"]["policy"] == {"a": 1}
        assert output["BANK_B"]["iteration_1"]["policy"] == {"b": 2}

    def test_iteration_keys_are_1_indexed(self) -> None:
        """Verify iteration keys use 1-indexed format."""
        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={
                "iteration_1": IterationEvolution(policy={"v": 1}),
                "iteration_2": IterationEvolution(policy={"v": 2}),
                "iteration_3": IterationEvolution(policy={"v": 3}),
            },
        )

        output = build_evolution_output([agent])

        # Keys should be iteration_1, iteration_2, etc. (1-indexed)
        assert "iteration_1" in output["BANK_A"]
        assert "iteration_2" in output["BANK_A"]
        assert "iteration_3" in output["BANK_A"]
        # NOT iteration_0
        assert "iteration_0" not in output["BANK_A"]

    def test_output_is_json_serializable(self) -> None:
        """Verify output can be serialized to JSON."""
        llm = LLMInteractionData(
            system_prompt="System",
            user_prompt="User",
            raw_response='{"key": "value"}',
        )

        iteration = IterationEvolution(
            policy={"nested": {"deep": {"value": 123}}},
            explanation="Test",
            diff="Some diff",
            llm=llm,
            cost=12345,
            accepted=True,
        )

        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={"iteration_1": iteration},
        )

        output = build_evolution_output([agent])

        # Should not raise
        json_str = json.dumps(output)
        assert isinstance(json_str, str)

        # Round-trip should work
        parsed = json.loads(json_str)
        assert parsed == output

    def test_handles_empty_evolutions(self) -> None:
        """Verify empty list produces empty output."""
        output = build_evolution_output([])
        assert output == {}

    def test_handles_agent_with_no_iterations(self) -> None:
        """Verify agent with empty iterations dict."""
        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={},
        )

        output = build_evolution_output([agent])

        assert "BANK_A" in output
        assert output["BANK_A"] == {}
