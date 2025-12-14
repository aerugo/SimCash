"""Data models for policy evolution output.

Provides immutable dataclasses representing policy evolution data
for JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMInteractionData:
    """LLM interaction data for a single iteration.

    Captures the prompts and response for audit/analysis purposes.

    Attributes:
        system_prompt: Full system prompt sent to LLM.
        user_prompt: Full user prompt with policy and context.
        raw_response: Raw LLM response before parsing.

    Example:
        >>> data = LLMInteractionData(
        ...     system_prompt="You are a policy optimizer.",
        ...     user_prompt="Improve this policy...",
        ...     raw_response='{"threshold": 100}',
        ... )
        >>> data.system_prompt
        'You are a policy optimizer.'
    """

    system_prompt: str
    user_prompt: str
    raw_response: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with all fields.
        """
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "raw_response": self.raw_response,
        }


@dataclass(frozen=True)
class IterationEvolution:
    """Policy evolution data for a single iteration.

    Captures the policy state and metadata at a specific iteration.
    All costs are integer cents (INV-1).

    Attributes:
        policy: The policy dict at this iteration.
        explanation: Optional explanation from LLM reasoning.
        diff: Optional diff from previous iteration.
        llm: Optional LLM interaction data (when --llm flag used).
        cost: Cost in integer cents (INV-1).
        accepted: Whether the policy change was accepted.

    Example:
        >>> evolution = IterationEvolution(
        ...     policy={"version": "2.0", "threshold": 100},
        ...     diff="~ threshold: 90 -> 100",
        ...     cost=15000,
        ...     accepted=True,
        ... )
        >>> evolution.cost
        15000
    """

    policy: dict[str, Any]
    explanation: str | None = None
    diff: str | None = None
    llm: LLMInteractionData | None = None
    cost: int | None = None
    accepted: bool | None = None

    def to_dict(self, include_llm: bool = True) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Args:
            include_llm: Whether to include LLM data in output.

        Returns:
            Dict with non-None fields.
        """
        result: dict[str, Any] = {"policy": self.policy}

        if self.explanation is not None:
            result["explanation"] = self.explanation

        if self.diff:
            result["diff"] = self.diff

        if include_llm and self.llm is not None:
            result["llm"] = self.llm.to_dict()

        if self.cost is not None:
            result["cost"] = self.cost

        if self.accepted is not None:
            result["accepted"] = self.accepted

        return result


@dataclass(frozen=True)
class AgentEvolution:
    """Policy evolution history for a single agent.

    Contains all iteration evolution data for one agent.

    Attributes:
        agent_id: The agent identifier (e.g., "BANK_A").
        iterations: Mapping of iteration key to evolution data.
            Keys are "iteration_1", "iteration_2", etc. (1-indexed).

    Example:
        >>> agent_evo = AgentEvolution(
        ...     agent_id="BANK_A",
        ...     iterations={
        ...         "iteration_1": IterationEvolution(policy={"v": "2.0"}),
        ...     },
        ... )
        >>> agent_evo.agent_id
        'BANK_A'
    """

    agent_id: str
    iterations: dict[str, IterationEvolution]

    def to_dict(self, include_llm: bool = True) -> dict[str, dict[str, Any]]:
        """Convert to dictionary for JSON serialization.

        Args:
            include_llm: Whether to include LLM data in output.

        Returns:
            Dict mapping iteration keys to evolution dicts.
        """
        return {
            key: evo.to_dict(include_llm=include_llm)
            for key, evo in self.iterations.items()
        }


def build_evolution_output(
    evolutions: list[AgentEvolution],
    include_llm: bool = True,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert evolution data to output JSON structure.

    Args:
        evolutions: List of AgentEvolution objects.
        include_llm: Whether to include LLM data in output.

    Returns:
        Dict with structure: {agent_id: {iteration_N: {...}}}

    Example:
        >>> evos = [
        ...     AgentEvolution(
        ...         agent_id="BANK_A",
        ...         iterations={"iteration_1": IterationEvolution(policy={})},
        ...     ),
        ... ]
        >>> output = build_evolution_output(evos)
        >>> "BANK_A" in output
        True
    """
    return {
        evo.agent_id: evo.to_dict(include_llm=include_llm)
        for evo in evolutions
    }
