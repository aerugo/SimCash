"""Type stubs for payment_simulator._core (Rust FFI module).

This stub file provides type hints for the Rust Orchestrator class
exposed via PyO3. The actual implementation is in payment_simulator_core_rs.
"""

from typing import Any

# =============================================================================
# Orchestrator Class
# =============================================================================


class Orchestrator:
    """Python wrapper for Rust simulation Orchestrator.

    This class provides the main entry point for controlling simulations.
    """

    @staticmethod
    def new(config: dict[str, Any]) -> Orchestrator:
        """Create a new Orchestrator from configuration dict."""
        ...

    def tick(self) -> dict[str, Any]:
        """Advance simulation by one tick.

        Returns:
            TickResult dict with keys: tick, num_settlements, num_arrivals,
            total_settled_value, num_policy_decisions, day
        """
        ...

    def current_tick(self) -> int:
        """Get the current tick number."""
        ...

    def current_day(self) -> int:
        """Get the current day number."""
        ...

    def get_agent_balance(self, agent_id: str) -> int | None:
        """Get agent's current balance in cents."""
        ...

    def get_agent_unsecured_cap(self, agent_id: str) -> int | None:
        """Get agent's credit limit in cents."""
        ...

    def get_arrival_rate(self, agent_id: str) -> float | None:
        """Get agent's arrival rate."""
        ...

    def get_agent_state(self, agent_id: str) -> dict[str, Any]:
        """Get full agent state dict."""
        ...

    def get_agent_limits(self, agent_id: str) -> dict[str, Any]:
        """Get agent's payment limits configuration."""
        ...

    def get_agent_current_outflows(self, agent_id: str) -> dict[str, Any]:
        """Get agent's current outflow tracking data."""
        ...

    def post_collateral(self, agent_id: str, amount: int) -> dict[str, Any]:
        """Post collateral for an agent.

        Returns result dict with success/failure info.
        """
        ...

    def withdraw_collateral(self, agent_id: str, amount: int) -> dict[str, Any]:
        """Withdraw collateral for an agent.

        Returns result dict with success/failure info.
        """
        ...

    def get_agent_ids(self) -> list[str]:
        """Get list of all agent IDs in simulation."""
        ...

    def get_lsm_cycles_for_day(self, day: int) -> list[dict[str, Any]]:
        """Get LSM cycle data for a specific day."""
        ...

    def withdraw_from_rtgs(self, tx_id: str) -> dict[str, Any]:
        """Withdraw a transaction from RTGS queue."""
        ...

    def resubmit_to_rtgs(self, tx_id: str, rtgs_priority: str) -> dict[str, Any]:
        """Resubmit a transaction to RTGS queue with new priority."""
        ...

    def queue_size(self) -> int:
        """Get total size of RTGS queue."""
        ...

    def get_transactions_for_day(self, day: int) -> list[dict[str, Any]]:
        """Get all transactions for a specific day."""
        ...

    def get_daily_agent_metrics(self, day: int) -> list[dict[str, Any]]:
        """Get agent metrics for a specific day."""
        ...

    def get_agent_policies(self) -> list[dict[str, Any]]:
        """Get policy configuration for all agents."""
        ...

    def save_state(self) -> str:
        """Serialize simulation state to JSON string."""
        ...

    def get_collateral_events_for_day(self, day: int) -> list[dict[str, Any]]:
        """Get collateral events for a specific day."""
        ...

    def get_agent_accumulated_costs(self, agent_id: str) -> dict[str, Any]:
        """Get accumulated costs for an agent.

        Returns dict with keys: liquidity_cost, delay_cost, collateral_cost,
        penalty_cost, split_friction_cost, total_cost
        """
        ...

    def get_system_metrics(self) -> dict[str, Any]:
        """Get system-wide simulation metrics."""
        ...

    def get_transaction_counts_debug(self) -> dict[str, Any]:
        """Get transaction count debug information."""
        ...

    def get_tick_events(self, tick: int) -> list[dict[str, Any]]:
        """Get all events for a specific tick.

        Returns list of event dicts, each containing event_type, tick,
        and event-specific fields.
        """
        ...

    def get_all_events(self) -> list[dict[str, Any]]:
        """Get all events from the simulation."""
        ...

    def get_transaction_details(self, tx_id: str) -> dict[str, Any] | None:
        """Get details for a specific transaction.

        Returns dict with keys: tx_id, sender_id, receiver_id, amount,
        remaining_amount, priority, deadline_tick, status, is_divisible
        """
        ...

    def get_rtgs_queue_contents(self) -> list[str]:
        """Get list of transaction IDs in RTGS queue."""
        ...

    def get_agent_collateral_posted(self, agent_id: str) -> int | None:
        """Get collateral posted by agent in cents."""
        ...

    def get_agent_allowed_overdraft_limit(self, agent_id: str) -> int | None:
        """Get agent's allowed overdraft limit."""
        ...

    def get_transactions_near_deadline(self, within_ticks: int) -> list[dict[str, Any]]:
        """Get transactions approaching their deadline.

        Returns list of transaction dicts with keys: tx_id, sender_id,
        receiver_id, amount, remaining_amount, deadline_tick, ticks_until_deadline
        """
        ...

    def get_overdue_transactions(self) -> list[dict[str, Any]]:
        """Get all currently overdue transactions.

        Returns list of overdue transaction dicts with keys: tx_id, sender_id,
        receiver_id, amount, remaining_amount, deadline_tick, overdue_since_tick,
        ticks_overdue, deadline_penalty_cost, estimated_delay_cost, total_overdue_cost
        """
        ...

    def get_queue1_size(self, agent_id: str) -> int:
        """Get size of agent's internal queue (Queue 1)."""
        ...

    def get_queue2_size(self) -> int:
        """Get total size of RTGS queue (Queue 2) across all agents."""
        ...

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get list of transaction IDs in agent's internal queue."""
        ...

    def submit_transaction(
        self,
        sender: str,
        receiver: str,
        amount: int,
        deadline_tick: int,
        priority: int,
        divisible: bool,
    ) -> str:
        """Submit a new transaction to the simulation.

        Returns the transaction ID.
        """
        ...

    def submit_transaction_with_rtgs_priority(
        self,
        sender: str,
        receiver: str,
        amount: int,
        deadline_tick: int,
        priority: int,
        divisible: bool,
        rtgs_priority: str,
    ) -> str:
        """Submit a transaction with explicit RTGS priority.

        Args:
            rtgs_priority: "HighlyUrgent", "Urgent", or "Normal"

        Returns the transaction ID.
        """
        ...

    @staticmethod
    def load_state(config: dict[str, Any], state_json: str) -> Orchestrator:
        """Load orchestrator from saved state JSON."""
        ...

    # Properties
    @property
    def previous_cumulative_arrivals(self) -> int:
        """Get cumulative arrivals from previous tick."""
        ...


# =============================================================================
# Module-level functions
# =============================================================================


def get_policy_schema() -> str:
    """Get the policy schema documentation as JSON string."""
    ...


def validate_policy(policy_json: str) -> str:
    """Validate a policy tree JSON string.

    Returns JSON string with validation results:
    - On success: {"valid": true, "policy_id": "...", "trees": {...}}
    - On failure: {"valid": false, "errors": [...]}
    """
    ...


# =============================================================================
# Enums
# =============================================================================


class RtgsPriority:
    """RTGS queue priority levels."""

    High: RtgsPriority
    Medium: RtgsPriority
    Low: RtgsPriority
