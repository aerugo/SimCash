"""Canonical data structures shared between CLI and API.

These define the SINGLE SOURCE OF TRUTH for field names and types.
Both CLI display functions and API Pydantic models MUST use these.

IMPORTANT: Field names in these contracts are CANONICAL. If you need
to change a field name, you MUST update ALL consumers:
- CLI display functions (output.py)
- API Pydantic models (api/models/*.py)
- StateProvider (state_provider.py)
- Tests

Example:
    >>> from payment_simulator.shared.data_contracts import CostBreakdownContract
    >>> costs = CostBreakdownContract(
    ...     liquidity_cost=100,
    ...     delay_cost=200,
    ...     collateral_cost=50,
    ...     deadline_penalty=1000,
    ...     split_friction_cost=25,
    ... )
    >>> costs.total_cost
    1375
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class CostBreakdownContract:
    """Canonical cost breakdown structure.

    IMPORTANT: These field names are the contract. Both CLI and API must use them.

    Fields:
        liquidity_cost: Overdraft/borrowing cost in cents
        delay_cost: Time-based delay cost in cents
        collateral_cost: Opportunity cost of posted collateral in cents
        deadline_penalty: One-time penalty when transaction goes overdue in cents
        split_friction_cost: Cost of splitting transactions in cents

    Properties:
        total_cost: Sum of all costs (calculated, not stored)
    """

    liquidity_cost: int
    delay_cost: int
    collateral_cost: int
    deadline_penalty: int  # CANONICAL NAME (not penalty_cost)
    split_friction_cost: int

    @property
    def total_cost(self) -> int:
        """Calculate total cost - same formula everywhere.

        This property ensures the total_cost calculation is consistent
        across CLI and API. Never calculate total_cost manually elsewhere.
        """
        return (
            self.liquidity_cost
            + self.delay_cost
            + self.collateral_cost
            + self.deadline_penalty
            + self.split_friction_cost
        )

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> CostBreakdownContract:
        """Create from dictionary, handling legacy field names.

        This method handles backward compatibility with legacy field names
        (e.g., penalty_cost -> deadline_penalty).

        Args:
            data: Dictionary with cost fields. May use either penalty_cost
                  or deadline_penalty for the deadline penalty field.

        Returns:
            CostBreakdownContract with canonical field names
        """
        # Handle legacy penalty_cost field
        deadline_penalty = data.get("deadline_penalty")
        if deadline_penalty is None:
            deadline_penalty = data.get("penalty_cost", 0)

        return cls(
            liquidity_cost=data.get("liquidity_cost", 0),
            delay_cost=data.get("delay_cost", 0),
            collateral_cost=data.get("collateral_cost", 0),
            deadline_penalty=deadline_penalty,
            split_friction_cost=data.get("split_friction_cost", 0),
        )


@dataclass(frozen=True)
class AgentStateContract:
    """Canonical agent state structure.

    Contains the complete state of an agent at a point in time.
    """

    agent_id: str
    balance: int
    unsecured_cap: int
    collateral_posted: int
    queue1_size: int
    queue2_size: int
    costs: CostBreakdownContract

    @property
    def liquidity(self) -> int:
        """Available liquidity = balance + credit."""
        return self.balance + self.unsecured_cap

    @property
    def headroom(self) -> int:
        """Available credit headroom.

        This is the amount of credit that can still be used before
        hitting the credit limit.
        """
        return self.unsecured_cap - max(0, -self.balance)


@dataclass(frozen=True)
class SystemMetricsContract:
    """Canonical system-wide metrics structure.

    Contains aggregate metrics for the entire simulation.
    """

    total_arrivals: int
    total_settlements: int
    total_lsm_releases: int

    @property
    def settlement_rate(self) -> float:
        """Settlement rate - same formula everywhere.

        Returns:
            Settlement rate as a float between 0.0 and 1.0.
            Returns 0.0 if no arrivals (to avoid division by zero).
        """
        if self.total_arrivals == 0:
            return 0.0
        return self.total_settlements / self.total_arrivals
