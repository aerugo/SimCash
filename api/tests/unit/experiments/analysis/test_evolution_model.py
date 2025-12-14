"""Unit tests for evolution model dataclasses."""

from __future__ import annotations

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
        data = LLMInteractionData(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
        )

        with pytest.raises(AttributeError):
            data.system_prompt = "new"  # type: ignore[misc]

    def test_to_dict_includes_all_fields(self) -> None:
        """Verify to_dict returns all fields."""
        data = LLMInteractionData(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
        )
        result = data.to_dict()

        assert result["system_prompt"] == "sys"
        assert result["user_prompt"] == "user"
        assert result["raw_response"] == "response"


class TestIterationEvolution:
    """Tests for IterationEvolution dataclass."""

    def test_is_immutable(self) -> None:
        """Verify frozen dataclass cannot be modified."""
        evo = IterationEvolution(policy={"version": "2.0"})

        with pytest.raises(AttributeError):
            evo.policy = {}  # type: ignore[misc]

    def test_to_dict_includes_policy(self) -> None:
        """Verify policy is always included in to_dict."""
        evo = IterationEvolution(policy={"version": "2.0", "threshold": 100})
        result = evo.to_dict()

        assert "policy" in result
        assert result["policy"]["threshold"] == 100

    def test_to_dict_excludes_none_fields(self) -> None:
        """Verify None fields are excluded from output."""
        evo = IterationEvolution(
            policy={"version": "2.0"},
            explanation=None,
            diff=None,
        )
        result = evo.to_dict()

        assert "explanation" not in result
        assert "diff" not in result

    def test_to_dict_includes_non_none_fields(self) -> None:
        """Verify non-None optional fields are included."""
        evo = IterationEvolution(
            policy={"version": "2.0"},
            explanation="LLM reasoning here",
            diff="~ threshold: 100 -> 200",
            cost=15000,
            accepted=True,
        )
        result = evo.to_dict()

        assert result["explanation"] == "LLM reasoning here"
        assert result["diff"] == "~ threshold: 100 -> 200"
        assert result["cost"] == 15000
        assert result["accepted"] is True

    def test_to_dict_includes_llm_when_requested(self) -> None:
        """Verify LLM data is included when include_llm=True."""
        llm_data = LLMInteractionData(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
        )
        evo = IterationEvolution(policy={}, llm=llm_data)
        result = evo.to_dict(include_llm=True)

        assert "llm" in result
        assert result["llm"]["system_prompt"] == "sys"

    def test_to_dict_excludes_llm_when_not_requested(self) -> None:
        """Verify LLM data is excluded when include_llm=False."""
        llm_data = LLMInteractionData(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
        )
        evo = IterationEvolution(policy={}, llm=llm_data)
        result = evo.to_dict(include_llm=False)

        assert "llm" not in result

    def test_empty_diff_is_excluded(self) -> None:
        """Verify empty diff string is excluded from output."""
        evo = IterationEvolution(policy={}, diff="")
        result = evo.to_dict()

        # Empty string is falsy, should be excluded
        assert "diff" not in result


class TestAgentEvolution:
    """Tests for AgentEvolution dataclass."""

    def test_is_immutable(self) -> None:
        """Verify frozen dataclass cannot be modified."""
        agent = AgentEvolution(agent_id="BANK_A", iterations={})

        with pytest.raises(AttributeError):
            agent.agent_id = "BANK_B"  # type: ignore[misc]

    def test_to_dict_formats_correctly(self) -> None:
        """Verify to_dict returns proper structure."""
        agent = AgentEvolution(
            agent_id="BANK_A",
            iterations={
                "iteration_1": IterationEvolution(policy={"v": "2.0"}),
                "iteration_2": IterationEvolution(policy={"v": "2.0", "t": 100}),
            },
        )
        result = agent.to_dict()

        assert "iteration_1" in result
        assert "iteration_2" in result
        assert result["iteration_1"]["policy"]["v"] == "2.0"
        assert result["iteration_2"]["policy"]["t"] == 100


class TestBuildEvolutionOutput:
    """Tests for build_evolution_output function."""

    def test_formats_correctly(self) -> None:
        """Verify output matches expected JSON structure."""
        evolutions = [
            AgentEvolution(
                agent_id="BANK_A",
                iterations={
                    "iteration_1": IterationEvolution(policy={"threshold": 100}),
                },
            ),
            AgentEvolution(
                agent_id="BANK_B",
                iterations={
                    "iteration_1": IterationEvolution(policy={"threshold": 200}),
                },
            ),
        ]
        output = build_evolution_output(evolutions)

        assert "BANK_A" in output
        assert "BANK_B" in output
        assert output["BANK_A"]["iteration_1"]["policy"]["threshold"] == 100
        assert output["BANK_B"]["iteration_1"]["policy"]["threshold"] == 200

    def test_handles_empty_list(self) -> None:
        """Verify empty input returns empty dict."""
        output = build_evolution_output([])
        assert output == {}

    def test_respects_include_llm_flag(self) -> None:
        """Verify include_llm flag is passed through."""
        llm_data = LLMInteractionData(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
        )
        evolutions = [
            AgentEvolution(
                agent_id="BANK_A",
                iterations={
                    "iteration_1": IterationEvolution(policy={}, llm=llm_data),
                },
            ),
        ]

        # With LLM
        output_with = build_evolution_output(evolutions, include_llm=True)
        assert "llm" in output_with["BANK_A"]["iteration_1"]

        # Without LLM
        output_without = build_evolution_output(evolutions, include_llm=False)
        assert "llm" not in output_without["BANK_A"]["iteration_1"]
