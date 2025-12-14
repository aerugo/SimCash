"""Policy evolution service.

Service layer for extracting policy evolution data from experiments.
Orchestrates repository queries, diff calculation, and model building.

Example:
    >>> from payment_simulator.experiments.persistence import ExperimentRepository
    >>> from payment_simulator.experiments.analysis.evolution_service import (
    ...     PolicyEvolutionService,
    ... )
    >>> repo = ExperimentRepository(Path("experiments.db"))
    >>> service = PolicyEvolutionService(repo)
    >>> evolution = service.get_evolution(
    ...     run_id="exp1-20251209-143022-a1b2c3",
    ...     include_llm=True,
    ...     agent_filter="BANK_A",
    ...     start_iteration=1,
    ...     end_iteration=10,
    ... )
"""

from __future__ import annotations

from typing import Any

from payment_simulator.experiments.analysis.evolution_model import (
    AgentEvolution,
    IterationEvolution,
    LLMInteractionData,
)
from payment_simulator.experiments.analysis.policy_diff import compute_policy_diff
from payment_simulator.experiments.persistence import (
    EventRecord,
    ExperimentRepository,
)

# Event type constant (matches runner/audit.py)
EVENT_LLM_INTERACTION = "llm_interaction"


class PolicyEvolutionService:
    """Service for extracting policy evolution data from experiments.

    Queries the repository for iteration and event data, computes diffs,
    and builds the evolution model.

    Example:
        >>> service = PolicyEvolutionService(repo)
        >>> evolution = service.get_evolution(
        ...     run_id="exp1-20251209-143022-a1b2c3",
        ...     include_llm=True,
        ...     agent_filter="BANK_A",
        ...     start_iteration=1,
        ...     end_iteration=10,
        ... )
    """

    def __init__(self, repository: ExperimentRepository) -> None:
        """Initialize with experiment repository.

        Args:
            repository: ExperimentRepository for database access.
        """
        self._repo = repository

    def get_evolution(
        self,
        run_id: str,
        include_llm: bool = False,
        agent_filter: str | None = None,
        start_iteration: int | None = None,
        end_iteration: int | None = None,
    ) -> list[AgentEvolution]:
        """Extract policy evolution for an experiment.

        Args:
            run_id: Experiment run ID.
            include_llm: Whether to include LLM prompts/responses.
            agent_filter: Optional agent ID to filter by.
            start_iteration: Start iteration (1-indexed, inclusive).
            end_iteration: End iteration (1-indexed, inclusive).

        Returns:
            List of AgentEvolution objects, one per agent.

        Raises:
            ValueError: If run_id not found in database.
        """
        # Verify experiment exists
        experiment = self._repo.load_experiment(run_id)
        if experiment is None:
            raise ValueError(f"Experiment run not found: {run_id}")

        # Get all iterations
        iterations = self._repo.get_iterations(run_id)

        if not iterations:
            return []

        # Convert 1-indexed user input to 0-indexed internal
        start_idx = (start_iteration - 1) if start_iteration is not None else 0
        end_idx = (end_iteration - 1) if end_iteration is not None else len(iterations) - 1

        # Clamp to valid range
        start_idx = max(0, start_idx)
        end_idx = min(len(iterations) - 1, end_idx)

        # Get all LLM events if needed
        llm_events_by_iter_agent: dict[tuple[int, str], EventRecord] = {}
        if include_llm:
            all_events = self._repo.get_all_events(run_id)
            for event in all_events:
                if event.event_type == EVENT_LLM_INTERACTION:
                    agent_id = event.event_data.get("agent_id", "")
                    key = (event.iteration, agent_id)
                    llm_events_by_iter_agent[key] = event

        # Build agent evolutions
        # First, collect all agents from all iterations
        all_agents: set[str] = set()
        for iteration in iterations:
            all_agents.update(iteration.policies.keys())

        # Filter agents if requested
        if agent_filter is not None:
            if agent_filter in all_agents:
                all_agents = {agent_filter}
            else:
                return []  # Agent not found

        # Build evolution for each agent
        result: list[AgentEvolution] = []

        for agent_id in sorted(all_agents):
            agent_iterations: dict[str, IterationEvolution] = {}

            # Track previous policy for diff calculation
            previous_policy: dict[str, Any] | None = None

            for iteration in iterations:
                iter_num = iteration.iteration  # 0-indexed

                # Skip iterations outside range
                if iter_num < start_idx or iter_num > end_idx:
                    continue

                # Get agent's policy for this iteration
                policy = iteration.policies.get(agent_id)
                if policy is None:
                    continue

                # Get cost and accepted status
                cost = iteration.costs_per_agent.get(agent_id)
                accepted = iteration.accepted_changes.get(agent_id)

                # Compute diff from previous iteration
                diff = compute_policy_diff(previous_policy, policy)
                previous_policy = policy

                # Get LLM data if requested
                llm_data: LLMInteractionData | None = None
                if include_llm:
                    llm_event = llm_events_by_iter_agent.get((iter_num, agent_id))
                    if llm_event is not None:
                        llm_data = self._extract_llm_data(llm_event)

                # Create iteration evolution
                iteration_key = f"iteration_{iter_num + 1}"  # 1-indexed output
                agent_iterations[iteration_key] = IterationEvolution(
                    policy=policy,
                    diff=diff,
                    llm=llm_data,
                    cost=cost,
                    accepted=accepted,
                )

            # Only add agent if it has iterations in the requested range
            if agent_iterations:
                result.append(
                    AgentEvolution(
                        agent_id=agent_id,
                        iterations=agent_iterations,
                    )
                )

        return result

    def _extract_llm_data(self, event: EventRecord) -> LLMInteractionData | None:
        """Extract LLM interaction data from an event record.

        Args:
            event: EventRecord containing LLM interaction data.

        Returns:
            LLMInteractionData if data is available, None otherwise.
        """
        data = event.event_data

        system_prompt = data.get("system_prompt")
        user_prompt = data.get("user_prompt")
        raw_response = data.get("raw_response")

        # All three fields are required
        if system_prompt is None or user_prompt is None or raw_response is None:
            return None

        return LLMInteractionData(
            system_prompt=str(system_prompt),
            user_prompt=str(user_prompt),
            raw_response=str(raw_response),
        )
