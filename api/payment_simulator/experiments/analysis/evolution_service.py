"""Policy evolution service for extracting evolution data from experiments.

Orchestrates queries and diff computation to build the full evolution
history for an experiment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from payment_simulator.experiments.analysis.evolution_model import (
    AgentEvolution,
    IterationEvolution,
    LLMInteractionData,
)
from payment_simulator.experiments.analysis.policy_diff import compute_policy_diff

if TYPE_CHECKING:
    from payment_simulator.experiments.persistence import ExperimentRepository


class PolicyEvolutionService:
    """Service for extracting policy evolution data from experiments.

    Coordinates database queries, diff computation, and data assembly
    to produce the full policy evolution history.

    Example:
        >>> from payment_simulator.experiments.persistence import ExperimentRepository
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
            ValueError: If run_id not found.
        """
        # Verify experiment exists
        experiment = self._repo.load_experiment(run_id)
        if experiment is None:
            msg = f"Experiment not found: {run_id}"
            raise ValueError(msg)

        # Get all iterations
        iterations = self._repo.get_iterations(run_id)
        if not iterations:
            return []

        # Convert 1-indexed user input to 0-indexed internal
        start_idx = (start_iteration - 1) if start_iteration is not None else None
        end_idx = (end_iteration - 1) if end_iteration is not None else None

        # Filter iterations by range
        filtered_iterations = []
        for it in iterations:
            if start_idx is not None and it.iteration < start_idx:
                continue
            if end_idx is not None and it.iteration > end_idx:
                continue
            filtered_iterations.append(it)

        # Collect all agent IDs
        all_agent_ids: set[str] = set()
        for it in filtered_iterations:
            all_agent_ids.update(it.policies.keys())

        # Filter by agent if specified
        if agent_filter is not None:
            if agent_filter not in all_agent_ids:
                # Agent doesn't exist - return empty
                return []
            all_agent_ids = {agent_filter}

        # Get all events if we need LLM data
        all_events = self._repo.get_all_events(run_id) if include_llm else []

        # Build evolution for each agent
        evolutions: list[AgentEvolution] = []
        for agent_id in sorted(all_agent_ids):
            agent_evo = self._build_agent_evolution(
                agent_id=agent_id,
                iterations=filtered_iterations,
                all_iterations=iterations,  # For diff computation
                events=all_events,
                include_llm=include_llm,
                start_idx=start_idx,
            )
            evolutions.append(agent_evo)

        return evolutions

    def _build_agent_evolution(
        self,
        agent_id: str,
        iterations: list[Any],  # IterationRecord
        all_iterations: list[Any],  # For getting previous iteration's policy
        events: list[Any],  # EventRecord
        include_llm: bool,
        start_idx: int | None,
    ) -> AgentEvolution:
        """Build evolution data for a single agent.

        Args:
            agent_id: Agent identifier.
            iterations: Filtered iteration records.
            all_iterations: All iteration records (for diff).
            events: Event records for LLM data.
            include_llm: Whether to include LLM data.
            start_idx: Start index (0-indexed) for diff boundary.

        Returns:
            AgentEvolution for this agent.
        """
        iteration_evos: dict[str, IterationEvolution] = {}

        # Build lookup for all iterations for diff computation
        iter_lookup = {it.iteration: it for it in all_iterations}

        for it in iterations:
            # Get policy for this agent
            policy = it.policies.get(agent_id, {})
            cost = it.costs_per_agent.get(agent_id)
            accepted = it.accepted_changes.get(agent_id)

            # Compute diff from previous iteration
            diff: str | None = None
            prev_idx = it.iteration - 1
            if prev_idx >= 0 and prev_idx in iter_lookup:
                prev_policy = iter_lookup[prev_idx].policies.get(agent_id, {})
                diff = compute_policy_diff(prev_policy, policy) or None

            # Get LLM data if requested
            llm_data: LLMInteractionData | None = None
            if include_llm:
                llm_data = self._extract_llm_data(events, it.iteration, agent_id)

            # Build iteration evolution
            iter_evo = IterationEvolution(
                policy=policy,
                explanation=None,  # Could extract from LLM reasoning if available
                diff=diff,
                llm=llm_data,
                cost=cost,
                accepted=accepted,
            )

            # Use 1-indexed key for output
            key = f"iteration_{it.iteration + 1}"
            iteration_evos[key] = iter_evo

        return AgentEvolution(agent_id=agent_id, iterations=iteration_evos)

    def _extract_llm_data(
        self,
        events: list[Any],  # EventRecord
        iteration: int,
        agent_id: str,
    ) -> LLMInteractionData | None:
        """Extract LLM interaction data from events.

        Args:
            events: All event records for the experiment.
            iteration: Iteration number (0-indexed).
            agent_id: Agent identifier.

        Returns:
            LLMInteractionData if found, None otherwise.
        """
        for event in events:
            if event.iteration != iteration:
                continue

            # Check for LLM-related event types
            if event.event_type not in (
                "llm_call_complete",
                "llm_call",
                "policy_generation",
            ):
                continue

            # Check if this event is for our agent
            event_agent = event.event_data.get("agent_id")
            if event_agent is not None and event_agent != agent_id:
                continue

            # Extract prompts and response
            system_prompt = event.event_data.get("system_prompt", "")
            user_prompt = event.event_data.get("user_prompt", "")
            raw_response = event.event_data.get("raw_response", "")

            # Only return if we have meaningful data
            if system_prompt or user_prompt or raw_response:
                return LLMInteractionData(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response=raw_response,
                )

        return None
