"""Sandbox configuration builder for bootstrap policy evaluation.

This module builds 3-agent sandbox configurations from BootstrapSamples
for isolated policy evaluation.

The sandbox structure:
- SOURCE: Infinite liquidity agent that sends scheduled payments to target
- TARGET: The agent being evaluated with the test policy
- SINK: Infinite capacity agent that receives all outgoing payments

This design enables:
1. Controlled liquidity testing (incoming from SOURCE)
2. Policy evaluation in isolation
3. Deterministic scenarios based on bootstrap samples
"""

from __future__ import annotations

import json
from typing import Any, cast

from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)
from payment_simulator.config.policy_config_builder import StandardPolicyConfigBuilder
from payment_simulator.config.schemas import (
    AgentConfig,
    CostRates,
    CustomTransactionArrivalEvent,
    FifoPolicy,
    InlineJsonPolicy,
    LiquidityAwarePolicy,
    LsmConfig,
    OneTimeSchedule,
    PolicyConfig,
    ScenarioEvent,
    ScheduledSettlementEvent,
    SimulationConfig,
    SimulationSettings,
)

# Infinite liquidity constant (10 billion cents = $100 million)
INFINITE_LIQUIDITY = 10_000_000_000


class SandboxConfigBuilder:
    """Builds 3-agent sandbox configurations from bootstrap samples.

    Creates isolated simulation environments for policy evaluation:
    - SOURCE agent with infinite liquidity
    - Target agent with test policy
    - SINK agent with infinite capacity

    Uses StandardPolicyConfigBuilder for canonical policy parameter extraction,
    ensuring identical behavior with optimization.py (Policy Evaluation Identity).

    Example:
        ```python
        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=bootstrap_sample,
            target_policy={"type": "LiquidityAware", "target_buffer": 50000},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        ```
    """

    def __init__(self) -> None:
        """Initialize with StandardPolicyConfigBuilder for canonical extraction."""
        self._policy_builder = StandardPolicyConfigBuilder()

    def build_config(
        self,
        sample: BootstrapSample,
        target_policy: dict[str, Any],
        opening_balance: int,
        credit_limit: int,
        cost_rates: dict[str, float] | None = None,
        max_collateral_capacity: int | None = None,
        liquidity_pool: int | None = None,
    ) -> SimulationConfig:
        """Build sandbox configuration from bootstrap sample.

        Args:
            sample: BootstrapSample with remapped transactions.
            target_policy: Policy configuration dict for target agent.
            opening_balance: Opening balance for target agent (cents).
            credit_limit: Credit limit for target agent (cents).
            cost_rates: Optional cost rates override.
            max_collateral_capacity: Max collateral capacity for target agent (cents).
                Required for policies that use initial_collateral_fraction parameter.
            liquidity_pool: External liquidity pool for target agent (cents).
                Required for policies that use initial_liquidity_fraction parameter.

        Returns:
            SimulationConfig for 3-agent sandbox.
        """
        # Build agents
        source_agent = self._build_source_agent()
        target_agent = self._build_target_agent(
            agent_id=sample.agent_id,
            policy=target_policy,
            opening_balance=opening_balance,
            credit_limit=credit_limit,
            max_collateral_capacity=max_collateral_capacity,
            liquidity_pool=liquidity_pool,
        )
        sink_agent = self._build_sink_agent()

        # Build scenario events
        scenario_events = self._build_scenario_events(sample)

        # Build simulation settings
        settings = SimulationSettings(
            ticks_per_day=sample.total_ticks,
            num_days=1,
            rng_seed=sample.seed,
        )

        # Build cost rates
        rates = self._build_cost_rates(cost_rates)

        # Cast scenario events to the full union type
        events_for_config: list[ScenarioEvent] | None = None
        if scenario_events:
            events_for_config = cast(list[ScenarioEvent], scenario_events)

        return SimulationConfig(
            simulation=settings,
            agents=[source_agent, target_agent, sink_agent],
            cost_rates=rates,
            lsm_config=LsmConfig(),  # type: ignore[call-arg]
            scenario_events=events_for_config,
        )

    def _build_source_agent(self) -> AgentConfig:
        """Build SOURCE agent with infinite liquidity."""
        return AgentConfig(  # type: ignore[call-arg]
            id="SOURCE",
            opening_balance=INFINITE_LIQUIDITY,
            unsecured_cap=0,
            policy=FifoPolicy(),
        )

    def _build_target_agent(
        self,
        agent_id: str,
        policy: dict[str, Any],
        opening_balance: int,
        credit_limit: int,
        max_collateral_capacity: int | None = None,
        liquidity_pool: int | None = None,
    ) -> AgentConfig:
        """Build target agent with test policy.

        Uses StandardPolicyConfigBuilder for canonical parameter extraction,
        ensuring identical behavior with optimization.py (Policy Evaluation Identity).

        Args:
            agent_id: Agent ID.
            policy: Policy configuration dict.
            opening_balance: Opening balance in cents.
            credit_limit: Credit limit (unsecured_cap) in cents.
            max_collateral_capacity: Max collateral capacity in cents.
                Required for collateral-based liquidity policies.
            liquidity_pool: External liquidity pool in cents.
                Required for policies using initial_liquidity_fraction.
        """
        # Build base config for canonical extraction
        base_config: dict[str, Any] = {
            "opening_balance": opening_balance,
            "liquidity_pool": liquidity_pool,
            "max_collateral_capacity": max_collateral_capacity,
        }

        # Use canonical extraction via PolicyConfigBuilder
        liquidity_config = self._policy_builder.extract_liquidity_config(
            policy=policy,
            agent_config=base_config,
        )

        collateral_config = self._policy_builder.extract_collateral_config(
            policy=policy,
            agent_config=base_config,
        )

        return AgentConfig(  # type: ignore[call-arg]
            id=agent_id,
            opening_balance=liquidity_config.get("opening_balance", opening_balance),
            unsecured_cap=credit_limit,
            max_collateral_capacity=collateral_config.get("max_collateral_capacity"),
            liquidity_pool=liquidity_config.get("liquidity_pool"),
            liquidity_allocation_fraction=liquidity_config.get("liquidity_allocation_fraction"),
            policy=self._parse_policy(policy),
        )

    def _build_sink_agent(self) -> AgentConfig:
        """Build SINK agent with infinite capacity."""
        return AgentConfig(  # type: ignore[call-arg]
            id="SINK",
            opening_balance=0,
            unsecured_cap=INFINITE_LIQUIDITY,
            policy=FifoPolicy(),
        )

    def _parse_policy(self, policy_dict: dict[str, Any]) -> PolicyConfig:
        """Parse policy dict to PolicyConfig.

        Handles:
        - Simple policies with "type" field (Fifo, LiquidityAware)
        - Tree policies with decision tree structure (payment_tree, etc.)

        Args:
            policy_dict: Policy configuration dictionary.

        Returns:
            Appropriate PolicyConfig instance.
        """
        policy_type = policy_dict.get("type")

        if policy_type == "Fifo":
            return FifoPolicy()
        elif policy_type == "LiquidityAware":
            return LiquidityAwarePolicy(
                target_buffer=policy_dict["target_buffer"],
                urgency_threshold=policy_dict["urgency_threshold"],
            )
        elif self._is_tree_policy(policy_dict):
            # Tree policy format - use InlineJsonPolicy
            return InlineJsonPolicy(json_string=json.dumps(policy_dict))
        else:
            # Fallback for unknown policies
            return FifoPolicy()

    def _is_tree_policy(self, policy_dict: dict[str, Any]) -> bool:
        """Check if policy dict is a tree policy format.

        Tree policies are detected by the presence of decision tree keys.
        See docs/reference/policy/configuration.md for the schema.

        Args:
            policy_dict: Policy configuration dictionary.

        Returns:
            True if this is a tree policy format.
        """
        tree_keys = (
            "payment_tree",
            "bank_tree",
            "strategic_collateral_tree",
            "end_of_tick_collateral_tree",
        )
        return any(key in policy_dict for key in tree_keys)

    def _build_scenario_events(
        self, sample: BootstrapSample
    ) -> list[CustomTransactionArrivalEvent | ScheduledSettlementEvent]:
        """Build scenario events from bootstrap sample.

        Converts:
        - Outgoing transactions → CustomTransactionArrival (TARGET → SINK)
        - Incoming settlements → ScheduledSettlement (SOURCE → TARGET)

        Note: Incoming settlements use ScheduledSettlement (not DirectTransfer)
        so they go through the real RTGS engine and emit RtgsImmediateSettlement
        events. This is critical for bootstrap correctness.
        """
        events: list[CustomTransactionArrivalEvent | ScheduledSettlementEvent] = []

        # Outgoing transactions become CustomTransactionArrival events
        for tx in sample.outgoing_txns:
            outgoing_event = self._outgoing_to_event(tx, sample.agent_id)
            events.append(outgoing_event)

        # Incoming settlements become ScheduledSettlement events (liquidity beats)
        # Uses real RTGS engine, not DirectTransfer which bypasses it
        for tx in sample.incoming_settlements:
            if tx.settlement_tick is not None:
                settlement_event = self._incoming_to_scheduled_settlement(tx, sample.agent_id)
                events.append(settlement_event)

        return events

    def _outgoing_to_event(
        self, tx: RemappedTransaction, agent_id: str
    ) -> CustomTransactionArrivalEvent:
        """Convert outgoing transaction to scenario event."""
        # Calculate deadline as ticks from arrival
        deadline_ticks = tx.deadline_tick - tx.arrival_tick

        return CustomTransactionArrivalEvent(  # type: ignore[call-arg]
            from_agent=agent_id,
            to_agent="SINK",
            amount=tx.amount,
            priority=tx.priority,
            deadline=deadline_ticks if deadline_ticks > 0 else 1,
            schedule=OneTimeSchedule(tick=tx.arrival_tick),
        )

    def _incoming_to_scheduled_settlement(
        self, tx: RemappedTransaction, agent_id: str
    ) -> ScheduledSettlementEvent:
        """Convert incoming settlement to ScheduledSettlement (liquidity beat).

        Uses ScheduledSettlement instead of DirectTransfer so the settlement
        goes through the real RTGS engine and emits RtgsImmediateSettlement
        event. This is critical for bootstrap evaluation correctness.
        """
        # Schedule at settlement_tick (when liquidity arrives)
        tick = tx.settlement_tick if tx.settlement_tick is not None else 0

        return ScheduledSettlementEvent(
            from_agent="SOURCE",
            to_agent=agent_id,
            amount=tx.amount,
            schedule=OneTimeSchedule(tick=tick),
        )

    def _build_cost_rates(self, override: dict[str, float] | None) -> CostRates:
        """Build cost rates with optional overrides."""
        if override is None:
            return CostRates()  # type: ignore[call-arg]

        # Apply overrides to defaults
        return CostRates(**override)  # type: ignore[arg-type]
