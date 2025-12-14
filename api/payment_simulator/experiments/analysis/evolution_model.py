"""Evolution model dataclasses.

Immutable data structures for representing policy evolution
across experiment iterations.

Example:
    >>> from payment_simulator.experiments.analysis.evolution_model import (
    ...     IterationEvolution,
    ...     AgentEvolution,
    ...     build_evolution_output,
    ... )
    >>> iteration = IterationEvolution(policy={"version": "2.0"}, cost=15000)
    >>> agent = AgentEvolution(agent_id="BANK_A", iterations={"iteration_1": iteration})
    >>> output = build_evolution_output([agent])
    >>> print(output)
    {'BANK_A': {'iteration_1': {'policy': {'version': '2.0'}, 'cost': 15000}}}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMInteractionData:
    """LLM interaction data for a single iteration.

    Stores the prompts and response from an LLM call during
    policy optimization. Only included when --llm flag is used.

    Attributes:
        system_prompt: Full system prompt sent to LLM.
        user_prompt: Full user prompt with policy and context.
        raw_response: Raw LLM response before parsing.
    """

    system_prompt: str
    user_prompt: str
    raw_response: str


@dataclass(frozen=True)
class IterationEvolution:
    """Policy evolution data for a single iteration.

    Represents one iteration's policy state and optional metadata.
    All costs are integer cents (INV-1 compliance).

    Attributes:
        policy: The policy dict at this iteration.
        explanation: Optional explanation (from LLM reasoning).
        diff: Optional diff from previous iteration (human-readable).
        llm: Optional LLM interaction data (when --llm flag used).
        cost: Cost in integer cents (INV-1). None if not available.
        accepted: Whether the policy change was accepted. None if not available.
    """

    policy: dict[str, Any]
    explanation: str | None = None
    diff: str | None = None
    llm: LLMInteractionData | None = None
    cost: int | None = None
    accepted: bool | None = None


@dataclass(frozen=True)
class AgentEvolution:
    """Policy evolution history for a single agent.

    Contains the complete history of how an agent's policy evolved
    across iterations.

    Attributes:
        agent_id: The agent identifier (e.g., "BANK_A").
        iterations: Mapping of iteration key (e.g., "iteration_1") to evolution data.
            Keys are 1-indexed for user-facing output.
    """

    agent_id: str
    iterations: dict[str, IterationEvolution]


def build_evolution_output(
    evolutions: list[AgentEvolution],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert evolution data to output JSON structure.

    Transforms the domain model into a JSON-serializable dictionary
    suitable for CLI output.

    Args:
        evolutions: List of AgentEvolution objects.

    Returns:
        Dict with structure: {agent_id: {iteration_N: {...}}}
        None fields are excluded from output.

    Example:
        >>> agent = AgentEvolution(
        ...     agent_id="BANK_A",
        ...     iterations={"iteration_1": IterationEvolution(policy={"v": 1})}
        ... )
        >>> build_evolution_output([agent])
        {'BANK_A': {'iteration_1': {'policy': {'v': 1}}}}
    """
    result: dict[str, dict[str, dict[str, Any]]] = {}

    for agent in evolutions:
        agent_output: dict[str, dict[str, Any]] = {}

        for iteration_key, iteration in agent.iterations.items():
            iteration_output = _iteration_to_dict(iteration)
            agent_output[iteration_key] = iteration_output

        result[agent.agent_id] = agent_output

    return result


def _iteration_to_dict(iteration: IterationEvolution) -> dict[str, Any]:
    """Convert IterationEvolution to dictionary.

    Excludes None fields for cleaner output.

    Args:
        iteration: IterationEvolution to convert.

    Returns:
        Dictionary with non-None fields only.
    """
    result: dict[str, Any] = {
        "policy": iteration.policy,
    }

    # Add optional fields only if they have values
    if iteration.explanation is not None:
        result["explanation"] = iteration.explanation

    if iteration.diff is not None:
        result["diff"] = iteration.diff

    if iteration.llm is not None:
        result["llm"] = {
            "system_prompt": iteration.llm.system_prompt,
            "user_prompt": iteration.llm.user_prompt,
            "raw_response": iteration.llm.raw_response,
        }

    if iteration.cost is not None:
        result["cost"] = iteration.cost

    if iteration.accepted is not None:
        result["accepted"] = iteration.accepted

    return result
