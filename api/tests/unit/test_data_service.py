"""TDD Tests for DataService.

Phase 2: Test-Driven Development for the unified data access layer.

The DataService should:
1. Delegate all data access to StateProvider
2. Return data matching Pydantic model structure
3. Ensure field names are consistent with CLI output
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from payment_simulator.cli.execution.state_provider import (
    AccumulatedCosts,
    StateProvider,
)

# ============================================================================
# Phase 2.1: DataService exists and can be imported
# ============================================================================


class TestDataServiceExists:
    """TDD tests to verify DataService module exists."""

    def test_data_service_importable(self) -> None:
        """DataService should be importable."""
        try:
            from payment_simulator.api.services.data_service import DataService

            assert DataService is not None
        except ImportError:
            pytest.fail(
                "Cannot import DataService. "
                "Create api/services/data_service.py"
            )

    def test_data_service_takes_state_provider(self) -> None:
        """DataService should accept StateProvider in constructor."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        service = DataService(mock_provider)
        assert service is not None


# ============================================================================
# Phase 2.2: get_costs() method
# ============================================================================


class TestDataServiceGetCosts:
    """TDD tests for DataService.get_costs() method."""

    def test_get_costs_exists(self) -> None:
        """DataService should have get_costs() method."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        service = DataService(mock_provider)
        assert hasattr(service, "get_costs")

    def test_get_costs_delegates_to_provider(self) -> None:
        """get_costs() should delegate to StateProvider."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=100,
            delay_cost=200,
            collateral_cost=50,
            penalty_cost=30,
            split_friction_cost=0,
            deadline_penalty=30,
            total_cost=380,
        )

        service = DataService(mock_provider)
        costs = service.get_costs(["BANK_A"])

        mock_provider.get_agent_accumulated_costs.assert_called_once_with("BANK_A")
        assert "BANK_A" in costs
        assert costs["BANK_A"]["total_cost"] == 380

    def test_get_costs_multiple_agents(self) -> None:
        """get_costs() should handle multiple agents."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)

        def mock_costs(agent_id: str) -> AccumulatedCosts:
            if agent_id == "BANK_A":
                return AccumulatedCosts(
                    liquidity_cost=100,
                    delay_cost=200,
                    collateral_cost=0,
                    penalty_cost=0,
                    split_friction_cost=0,
                    deadline_penalty=0,
                    total_cost=300,
                )
            else:
                return AccumulatedCosts(
                    liquidity_cost=50,
                    delay_cost=100,
                    collateral_cost=0,
                    penalty_cost=0,
                    split_friction_cost=0,
                    deadline_penalty=0,
                    total_cost=150,
                )

        mock_provider.get_agent_accumulated_costs.side_effect = mock_costs

        service = DataService(mock_provider)
        costs = service.get_costs(["BANK_A", "BANK_B"])

        assert len(costs) == 2
        assert costs["BANK_A"]["total_cost"] == 300
        assert costs["BANK_B"]["total_cost"] == 150

    def test_get_costs_returns_all_canonical_fields(self) -> None:
        """get_costs() should return all canonical cost fields."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=100,
            delay_cost=200,
            collateral_cost=50,
            penalty_cost=30,
            split_friction_cost=10,
            deadline_penalty=30,
            total_cost=390,
        )

        service = DataService(mock_provider)
        costs = service.get_costs(["BANK_A"])

        agent_costs = costs["BANK_A"]
        # All canonical fields must be present
        assert "liquidity_cost" in agent_costs
        assert "delay_cost" in agent_costs
        assert "collateral_cost" in agent_costs
        assert "deadline_penalty" in agent_costs
        assert "split_friction_cost" in agent_costs
        assert "total_cost" in agent_costs


# ============================================================================
# Phase 2.3: get_agent_state() method
# ============================================================================


class TestDataServiceGetAgentState:
    """TDD tests for DataService.get_agent_state() method."""

    def test_get_agent_state_exists(self) -> None:
        """DataService should have get_agent_state() method."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        service = DataService(mock_provider)
        assert hasattr(service, "get_agent_state")

    def test_get_agent_state_delegates_to_provider(self) -> None:
        """get_agent_state() should delegate to StateProvider."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_balance.return_value = 500_000_00
        mock_provider.get_agent_unsecured_cap.return_value = 200_000_00
        mock_provider.get_queue1_size.return_value = 3
        mock_provider.get_queue2_size.return_value = 1
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=0,
            delay_cost=0,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            deadline_penalty=0,
            total_cost=0,
        )

        service = DataService(mock_provider)
        state = service.get_agent_state("BANK_A")

        mock_provider.get_agent_balance.assert_called_once_with("BANK_A")
        mock_provider.get_agent_unsecured_cap.assert_called_once_with("BANK_A")
        assert state["balance"] == 500_000_00
        assert state["unsecured_cap"] == 200_000_00

    def test_get_agent_state_returns_complete_state(self) -> None:
        """get_agent_state() should return complete agent state."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_balance.return_value = 500_000_00
        mock_provider.get_agent_unsecured_cap.return_value = 200_000_00
        mock_provider.get_queue1_size.return_value = 3
        mock_provider.get_queue2_size.return_value = 1
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=100,
            delay_cost=200,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            deadline_penalty=0,
            total_cost=300,
        )

        service = DataService(mock_provider)
        state = service.get_agent_state("BANK_A")

        # All state fields must be present
        assert "balance" in state
        assert "unsecured_cap" in state
        assert "queue1_size" in state
        assert "queue2_size" in state
        assert "costs" in state
        # Derived fields
        assert "liquidity" in state
        assert "headroom" in state

    def test_get_agent_state_calculates_derived_fields(self) -> None:
        """get_agent_state() should calculate liquidity and headroom."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_balance.return_value = 500_000_00
        mock_provider.get_agent_unsecured_cap.return_value = 200_000_00
        mock_provider.get_queue1_size.return_value = 0
        mock_provider.get_queue2_size.return_value = 0
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=0,
            delay_cost=0,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            deadline_penalty=0,
            total_cost=0,
        )

        service = DataService(mock_provider)
        state = service.get_agent_state("BANK_A")

        # liquidity = balance + unsecured_cap
        assert state["liquidity"] == 500_000_00 + 200_000_00
        # headroom = unsecured_cap - max(0, -balance) (positive balance means full headroom)
        assert state["headroom"] == 200_000_00

    def test_get_agent_state_headroom_with_overdraft(self) -> None:
        """get_agent_state() should calculate correct headroom with overdraft."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        # Negative balance (using credit line)
        mock_provider.get_agent_balance.return_value = -50_000_00
        mock_provider.get_agent_unsecured_cap.return_value = 200_000_00
        mock_provider.get_queue1_size.return_value = 0
        mock_provider.get_queue2_size.return_value = 0
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=100,
            delay_cost=0,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            deadline_penalty=0,
            total_cost=100,
        )

        service = DataService(mock_provider)
        state = service.get_agent_state("BANK_A")

        # liquidity = balance + unsecured_cap = -50000 + 200000 = 150000
        assert state["liquidity"] == -50_000_00 + 200_000_00
        # headroom = unsecured_cap - max(0, -balance) = 200000 - 50000 = 150000
        assert state["headroom"] == 200_000_00 - 50_000_00


# ============================================================================
# Phase 2.4: Integration with Factory
# ============================================================================


class TestDataServiceWithFactory:
    """TDD tests for DataService integration with APIStateProviderFactory."""

    def test_data_service_works_with_live_provider(self) -> None:
        """DataService should work with live OrchestratorStateProvider."""
        try:
            from payment_simulator.api.dependencies import container
            from payment_simulator.api.services.data_service import DataService
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Required modules not yet implemented")

        # Create a live simulation
        config = {
            "simulation": {
                "ticks_per_day": 10,
                "num_days": 1,
                "rng_seed": 12345,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500_000_00,
                    "unsecured_cap": 200_000_00,
                    "policy": {"type": "Fifo"},
                },
            ],
        }

        sim_id, _orch = container.simulation_service.create_simulation(config)

        try:
            factory = APIStateProviderFactory()
            provider = factory.create(sim_id, db_manager=None)

            service = DataService(provider)
            costs = service.get_costs(["BANK_A"])

            assert "BANK_A" in costs
            assert "total_cost" in costs["BANK_A"]
        finally:
            container.simulation_service.delete_simulation(sim_id)

    def test_data_service_returns_typed_dict(self) -> None:
        """DataService methods should return proper dict structures."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_accumulated_costs.return_value = AccumulatedCosts(
            liquidity_cost=100,
            delay_cost=200,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            deadline_penalty=0,
            total_cost=300,
        )

        service = DataService(mock_provider)
        costs = service.get_costs(["BANK_A"])

        # Should be a dict, not a Pydantic model
        assert isinstance(costs, dict)
        assert isinstance(costs["BANK_A"], dict)


# ============================================================================
# Phase 4: get_metrics() method for system-wide metrics
# ============================================================================


class TestDataServiceGetMetrics:
    """TDD tests for DataService.get_metrics() method."""

    def test_get_metrics_exists(self) -> None:
        """DataService should have get_metrics() method."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        service = DataService(mock_provider)
        assert hasattr(service, "get_metrics")

    def test_get_metrics_returns_dict_with_required_fields(self) -> None:
        """get_metrics() should return dict with all SystemMetrics fields."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)

        # Set up mock for agents
        mock_provider.get_agent_balance.side_effect = lambda aid: 100_000_00
        mock_provider.get_queue1_size.side_effect = lambda aid: 2
        mock_provider.get_queue2_size.side_effect = lambda aid: 1

        service = DataService(mock_provider)

        # Need to pass transaction data for metrics calculation
        metrics = service.get_metrics(
            agent_ids=["BANK_A", "BANK_B"],
            transaction_stats={
                "total_arrivals": 100,
                "total_settlements": 95,
                "avg_delay_ticks": 3.5,
                "max_delay_ticks": 12,
            },
        )

        # All SystemMetrics fields must be present
        required_fields = {
            "total_arrivals",
            "total_settlements",
            "settlement_rate",
            "avg_delay_ticks",
            "max_delay_ticks",
            "queue1_total_size",
            "queue2_total_size",
            "peak_overdraft",
            "agents_in_overdraft",
        }

        missing = required_fields - set(metrics.keys())
        assert not missing, f"get_metrics() missing fields: {missing}"

    def test_get_metrics_calculates_settlement_rate(self) -> None:
        """get_metrics() should correctly calculate settlement rate."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_balance.return_value = 100_000_00
        mock_provider.get_queue1_size.return_value = 0
        mock_provider.get_queue2_size.return_value = 0

        service = DataService(mock_provider)

        metrics = service.get_metrics(
            agent_ids=["BANK_A"],
            transaction_stats={
                "total_arrivals": 100,
                "total_settlements": 80,
                "avg_delay_ticks": 0.0,
                "max_delay_ticks": 0,
            },
        )

        # settlement_rate = total_settlements / total_arrivals = 80/100 = 0.8
        assert metrics["settlement_rate"] == 0.8

    def test_get_metrics_calculates_queue_totals(self) -> None:
        """get_metrics() should sum queue sizes across all agents."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_balance.return_value = 100_000_00

        # BANK_A has 3 in queue1, 1 in queue2
        # BANK_B has 2 in queue1, 2 in queue2
        def mock_queue1(agent_id: str) -> int:
            return 3 if agent_id == "BANK_A" else 2

        def mock_queue2(agent_id: str) -> int:
            return 1 if agent_id == "BANK_A" else 2

        mock_provider.get_queue1_size.side_effect = mock_queue1
        mock_provider.get_queue2_size.side_effect = mock_queue2

        service = DataService(mock_provider)

        metrics = service.get_metrics(
            agent_ids=["BANK_A", "BANK_B"],
            transaction_stats={
                "total_arrivals": 10,
                "total_settlements": 10,
                "avg_delay_ticks": 0.0,
                "max_delay_ticks": 0,
            },
        )

        assert metrics["queue1_total_size"] == 5  # 3 + 2
        assert metrics["queue2_total_size"] == 3  # 1 + 2

    def test_get_metrics_calculates_overdraft_stats(self) -> None:
        """get_metrics() should calculate overdraft statistics from balances."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_queue1_size.return_value = 0
        mock_provider.get_queue2_size.return_value = 0

        # BANK_A: positive balance (no overdraft)
        # BANK_B: negative balance -50000 (in overdraft)
        # BANK_C: negative balance -100000 (in overdraft, peak)
        def mock_balance(agent_id: str) -> int:
            balances = {
                "BANK_A": 100_000_00,
                "BANK_B": -50_000_00,
                "BANK_C": -100_000_00,
            }
            return balances.get(agent_id, 0)

        mock_provider.get_agent_balance.side_effect = mock_balance

        service = DataService(mock_provider)

        metrics = service.get_metrics(
            agent_ids=["BANK_A", "BANK_B", "BANK_C"],
            transaction_stats={
                "total_arrivals": 10,
                "total_settlements": 10,
                "avg_delay_ticks": 0.0,
                "max_delay_ticks": 0,
            },
        )

        # peak_overdraft is absolute value of most negative balance
        assert metrics["peak_overdraft"] == 100_000_00
        # 2 agents have negative balance
        assert metrics["agents_in_overdraft"] == 2

    def test_get_metrics_handles_zero_arrivals(self) -> None:
        """get_metrics() should handle zero arrivals without division by zero."""
        try:
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("DataService not yet implemented")

        mock_provider = Mock(spec=StateProvider)
        mock_provider.get_agent_balance.return_value = 100_000_00
        mock_provider.get_queue1_size.return_value = 0
        mock_provider.get_queue2_size.return_value = 0

        service = DataService(mock_provider)

        metrics = service.get_metrics(
            agent_ids=["BANK_A"],
            transaction_stats={
                "total_arrivals": 0,
                "total_settlements": 0,
                "avg_delay_ticks": 0.0,
                "max_delay_ticks": 0,
            },
        )

        # settlement_rate should be 0.0 when no arrivals
        assert metrics["settlement_rate"] == 0.0
