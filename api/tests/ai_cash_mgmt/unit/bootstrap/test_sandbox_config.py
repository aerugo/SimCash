"""Unit tests for SandboxConfigBuilder.

Phase 4: Sandbox Config Builder - TDD Tests

Tests for:
- Building 3-agent sandbox configuration (SOURCE, target, SINK)
- Converting BootstrapSample to scenario_events
- Proper agent configuration
- Incoming liquidity scheduled as SOURCE->TARGET transfers
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)
from payment_simulator.ai_cash_mgmt.bootstrap.sandbox_config import (
    SandboxConfigBuilder,
)
from payment_simulator.config.schemas import SimulationConfig


class TestSandboxAgentStructure:
    """Test 3-agent sandbox structure."""

    def test_creates_three_agents(self) -> None:
        """Sandbox config creates exactly 3 agents."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert len(config.agents) == 3

    def test_agent_ids_correct(self) -> None:
        """Sandbox has SOURCE, target agent, and SINK."""
        sample = BootstrapSample(
            agent_id="BANK_X",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        agent_ids = {a.id for a in config.agents}
        assert "SOURCE" in agent_ids
        assert "BANK_X" in agent_ids
        assert "SINK" in agent_ids

    def test_source_has_infinite_liquidity(self) -> None:
        """SOURCE agent has very high balance for infinite liquidity."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        source = next(a for a in config.agents if a.id == "SOURCE")
        # Should have very high balance (essentially infinite)
        assert source.opening_balance >= 10_000_000_000  # 10 billion cents

    def test_sink_has_infinite_capacity(self) -> None:
        """SINK agent has very high credit limit for infinite capacity."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        sink = next(a for a in config.agents if a.id == "SINK")
        # Should have very high credit limit (to absorb all payments)
        assert sink.unsecured_cap >= 10_000_000_000  # 10 billion cents


class TestTargetAgentConfiguration:
    """Test target agent configuration."""

    def test_target_agent_has_correct_balance(self) -> None:
        """Target agent has specified opening balance."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=2_500_000,
            credit_limit=750_000,
        )

        target = next(a for a in config.agents if a.id == "BANK_A")
        assert target.opening_balance == 2_500_000

    def test_target_agent_has_correct_credit_limit(self) -> None:
        """Target agent has specified credit limit."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        target = next(a for a in config.agents if a.id == "BANK_A")
        assert target.unsecured_cap == 500_000

    def test_target_agent_uses_provided_policy(self) -> None:
        """Target agent uses the provided policy configuration."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "LiquidityAware", "target_buffer": 100000, "urgency_threshold": 5},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        target = next(a for a in config.agents if a.id == "BANK_A")
        # Policy should be LiquidityAware type
        assert target.policy.type == "LiquidityAware"  # type: ignore[union-attr]


class TestOutgoingTransactionEvents:
    """Test conversion of outgoing transactions to scenario events."""

    def test_outgoing_txns_become_scenario_events(self) -> None:
        """Outgoing transactions create CustomTransactionArrival events."""
        outgoing = (
            RemappedTransaction(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=100000,
                priority=5,
                arrival_tick=10,
                deadline_tick=20,
                settlement_tick=None,
            ),
            RemappedTransaction(
                tx_id="tx-002",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=200000,
                priority=7,
                arrival_tick=15,
                deadline_tick=25,
                settlement_tick=None,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=outgoing,
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert config.scenario_events is not None
        # Find events for outgoing transactions
        outgoing_events = [
            e for e in config.scenario_events
            if e.type == "CustomTransactionArrival" and e.from_agent == "BANK_A"  # type: ignore[union-attr]
        ]
        assert len(outgoing_events) == 2

    def test_outgoing_event_properties(self) -> None:
        """Outgoing transaction events have correct properties."""
        outgoing = (
            RemappedTransaction(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=150000,
                priority=8,
                arrival_tick=5,
                deadline_tick=15,
                settlement_tick=None,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=outgoing,
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert config.scenario_events is not None
        event = config.scenario_events[0]
        assert event.from_agent == "BANK_A"  # type: ignore[union-attr]
        assert event.to_agent == "SINK"  # type: ignore[union-attr]
        assert event.amount == 150000  # type: ignore[union-attr]
        assert event.priority == 8  # type: ignore[union-attr]
        assert event.schedule.tick == 5  # type: ignore[union-attr]


class TestIncomingLiquidityEvents:
    """Test conversion of incoming liquidity beats to scenario events."""

    def test_incoming_creates_source_to_target_transfers(self) -> None:
        """Incoming settlements create SOURCE->TARGET direct transfers."""
        incoming = (
            RemappedTransaction(
                tx_id="tx-in-001",
                sender_id="SOURCE",
                receiver_id="BANK_A",
                amount=50000,
                priority=5,
                arrival_tick=0,
                deadline_tick=10,
                settlement_tick=5,  # Liquidity arrives at tick 5
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=incoming,
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert config.scenario_events is not None
        # Find direct transfer events
        transfer_events = [
            e for e in config.scenario_events
            if e.type == "DirectTransfer"
        ]
        assert len(transfer_events) == 1

        event = transfer_events[0]
        assert event.from_agent == "SOURCE"  # type: ignore[union-attr]
        assert event.to_agent == "BANK_A"  # type: ignore[union-attr]
        assert event.amount == 50000  # type: ignore[union-attr]
        # Should be scheduled at settlement_tick (when liquidity arrives)
        assert event.schedule.tick == 5  # type: ignore[union-attr]

    def test_multiple_incoming_at_same_tick_aggregated(self) -> None:
        """Multiple incoming at same tick can be separate events."""
        incoming = (
            RemappedTransaction(
                tx_id="tx-in-001",
                sender_id="SOURCE",
                receiver_id="BANK_A",
                amount=30000,
                priority=5,
                arrival_tick=0,
                deadline_tick=10,
                settlement_tick=5,
            ),
            RemappedTransaction(
                tx_id="tx-in-002",
                sender_id="SOURCE",
                receiver_id="BANK_A",
                amount=20000,
                priority=5,
                arrival_tick=0,
                deadline_tick=10,
                settlement_tick=5,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=incoming,
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert config.scenario_events is not None
        # Should have events for both incoming transactions
        transfer_events = [
            e for e in config.scenario_events
            if e.type == "DirectTransfer"
        ]
        assert len(transfer_events) == 2


class TestSimulationSettings:
    """Test simulation settings in generated config."""

    def test_uses_sample_total_ticks(self) -> None:
        """Simulation uses total_ticks from sample."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=75,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # ticks_per_day should match total_ticks
        assert config.simulation.ticks_per_day == 75

    def test_single_day_simulation(self) -> None:
        """Sandbox runs single-day simulation."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert config.simulation.num_days == 1

    def test_uses_sample_seed(self) -> None:
        """Simulation uses seed from sample."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=99999,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        assert config.simulation.rng_seed == 99999


class TestConfigValidation:
    """Test that generated config is valid."""

    def test_generated_config_is_valid_simulation_config(self) -> None:
        """Generated config is a valid SimulationConfig."""
        outgoing = (
            RemappedTransaction(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=100000,
                priority=5,
                arrival_tick=10,
                deadline_tick=20,
                settlement_tick=None,
            ),
        )
        incoming = (
            RemappedTransaction(
                tx_id="tx-in-001",
                sender_id="SOURCE",
                receiver_id="BANK_A",
                amount=50000,
                priority=5,
                arrival_tick=0,
                deadline_tick=10,
                settlement_tick=5,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=outgoing,
            incoming_settlements=incoming,
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # Should be valid SimulationConfig
        assert isinstance(config, SimulationConfig)

        # Should be convertible to FFI dict without errors
        ffi_dict = config.to_ffi_dict()
        assert "agent_configs" in ffi_dict
        assert len(ffi_dict["agent_configs"]) == 3

    def test_no_arrivals_config_is_valid(self) -> None:
        """Empty sample produces valid config."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # Should still be valid
        assert isinstance(config, SimulationConfig)
        ffi_dict = config.to_ffi_dict()
        assert "agent_configs" in ffi_dict


class TestCostRatesConfiguration:
    """Test cost rates in generated config."""

    def test_default_cost_rates(self) -> None:
        """Default cost rates are applied."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        # Should have cost rates
        assert config.cost_rates is not None

    def test_custom_cost_rates(self) -> None:
        """Custom cost rates can be provided."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        builder = SandboxConfigBuilder()
        config = builder.build_config(
            sample=sample,
            target_policy={"type": "Fifo"},
            opening_balance=1_000_000,
            credit_limit=500_000,
            cost_rates={
                "overdraft_bps_per_tick": 0.01,
                "delay_cost_per_tick_per_cent": 0.001,
            },
        )

        assert config.cost_rates.overdraft_bps_per_tick == 0.01
        assert config.cost_rates.delay_cost_per_tick_per_cent == 0.001
