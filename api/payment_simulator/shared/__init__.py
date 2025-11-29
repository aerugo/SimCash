"""Shared data contracts for CLI and API output consistency.

This module contains canonical data structures that define the SINGLE SOURCE
OF TRUTH for field names and types. Both CLI display functions and API
Pydantic models MUST use these contracts to ensure output consistency.

Usage:
    from payment_simulator.shared.data_contracts import CostBreakdownContract

    # In CLI code:
    costs = CostBreakdownContract(
        liquidity_cost=raw_costs["liquidity_cost"],
        delay_cost=raw_costs["delay_cost"],
        ...
    )
    print(f"Total: ${costs.total_cost / 100:.2f}")

    # In API code:
    from payment_simulator.api.models.costs import AgentCostBreakdown
    model = AgentCostBreakdown.from_contract(costs)
"""

from payment_simulator.shared.data_contracts import (
    AgentStateContract,
    CostBreakdownContract,
    SystemMetricsContract,
)

__all__ = [
    "AgentStateContract",
    "CostBreakdownContract",
    "SystemMetricsContract",
]
