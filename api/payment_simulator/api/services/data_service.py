"""Unified data access service using StateProvider.

This service ensures all API data retrieval uses the same StateProvider
abstraction as CLI, guaranteeing consistency between live and persisted
simulation data access.

Usage:
    factory = APIStateProviderFactory()
    provider = factory.create(sim_id, db_manager)
    service = DataService(provider)

    costs = service.get_costs(["BANK_A", "BANK_B"])
    state = service.get_agent_state("BANK_A")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.cli.execution.state_provider import StateProvider


class DataService:
    """Unified data access through StateProvider.

    This service ensures all API data retrieval uses the same
    StateProvider abstraction as CLI, guaranteeing consistency.

    The DataService provides a thin wrapper that:
    1. Delegates all data access to the underlying StateProvider
    2. Returns dict structures matching Pydantic model expectations
    3. Calculates derived fields (liquidity, headroom)
    4. Uses canonical field names consistent with CLI output
    """

    def __init__(self, provider: StateProvider) -> None:
        """Initialize with StateProvider.

        Args:
            provider: StateProvider instance (OrchestratorStateProvider or DatabaseStateProvider)
        """
        self._provider = provider

    def get_costs(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get accumulated costs for all specified agents.

        Returns same structure as CLI cost breakdown display, with canonical
        field names: liquidity_cost, delay_cost, collateral_cost, deadline_penalty,
        split_friction_cost, total_cost.

        Args:
            agent_ids: List of agent IDs to get costs for

        Returns:
            Dict mapping agent_id -> cost breakdown dict
        """
        costs: dict[str, dict[str, Any]] = {}
        for agent_id in agent_ids:
            agent_costs = self._provider.get_agent_accumulated_costs(agent_id)
            costs[agent_id] = {
                "liquidity_cost": agent_costs["liquidity_cost"],
                "delay_cost": agent_costs["delay_cost"],
                "collateral_cost": agent_costs["collateral_cost"],
                "deadline_penalty": agent_costs["deadline_penalty"],
                "split_friction_cost": agent_costs["split_friction_cost"],
                "total_cost": agent_costs["total_cost"],
            }
        return costs

    def get_agent_state(self, agent_id: str) -> dict[str, Any]:
        """Get complete state for an agent.

        Returns full agent state including:
        - balance: Current balance in cents
        - unsecured_cap: Credit limit in cents
        - liquidity: balance + unsecured_cap (total available funds)
        - headroom: Remaining credit capacity
        - queue1_size: Transactions in internal queue
        - queue2_size: Transactions in RTGS queue
        - costs: Cost breakdown dict

        Args:
            agent_id: The agent ID

        Returns:
            Dict containing complete agent state
        """
        balance = self._provider.get_agent_balance(agent_id)
        unsecured_cap = self._provider.get_agent_unsecured_cap(agent_id)
        queue1_size = self._provider.get_queue1_size(agent_id)
        queue2_size = self._provider.get_queue2_size(agent_id)
        costs = self._provider.get_agent_accumulated_costs(agent_id)

        # Calculate derived fields
        liquidity = balance + unsecured_cap
        # headroom = remaining credit capacity
        # If balance is negative, we've used some credit, reducing headroom
        headroom = unsecured_cap - max(0, -balance)

        return {
            "balance": balance,
            "unsecured_cap": unsecured_cap,
            "liquidity": liquidity,
            "headroom": headroom,
            "queue1_size": queue1_size,
            "queue2_size": queue2_size,
            "costs": {
                "liquidity_cost": costs["liquidity_cost"],
                "delay_cost": costs["delay_cost"],
                "collateral_cost": costs["collateral_cost"],
                "deadline_penalty": costs["deadline_penalty"],
                "split_friction_cost": costs["split_friction_cost"],
                "total_cost": costs["total_cost"],
            },
        }

    def get_all_agent_states(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Get complete state for all specified agents.

        Args:
            agent_ids: List of agent IDs

        Returns:
            Dict mapping agent_id -> agent state dict
        """
        return {agent_id: self.get_agent_state(agent_id) for agent_id in agent_ids}


def get_data_service(provider: StateProvider) -> DataService:
    """Factory function for creating DataService.

    Args:
        provider: StateProvider instance

    Returns:
        DataService instance
    """
    return DataService(provider)
