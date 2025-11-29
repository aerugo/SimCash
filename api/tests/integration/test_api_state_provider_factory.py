"""TDD Tests for APIStateProviderFactory.

Phase 1: Test-Driven Development for the StateProvider factory.

The factory should:
1. Return OrchestratorStateProvider for live (in-memory) simulations
2. Return DatabaseStateProvider for persisted simulations
3. Raise appropriate errors when simulation not found
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.persistence import PersistenceManager
from payment_simulator.cli.execution.runner import SimulationConfig, SimulationRunner
from payment_simulator.cli.execution.state_provider import (
    DatabaseStateProvider,
    OrchestratorStateProvider,
    StateProvider,
)
from payment_simulator.cli.execution.strategies import QuietOutputStrategy
from payment_simulator.config.loader import SimulationConfig as PySimConfig
from payment_simulator.persistence.connection import DatabaseManager


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_config() -> dict[str, Any]:
    """API-style configuration."""
    return {
        "simulation": {
            "ticks_per_day": 20,
            "num_days": 1,
            "rng_seed": 54321,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 500_000_00,
                "unsecured_cap": 200_000_00,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 500_000_00,
                "unsecured_cap": 200_000_00,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def ffi_config(api_config: dict[str, Any]) -> dict[str, Any]:
    """Convert API config to FFI format."""
    sim_config = PySimConfig.from_dict(api_config)
    return sim_config.to_ffi_dict()


@pytest.fixture
def db_manager(tmp_path: Path) -> Generator[DatabaseManager, None, None]:
    """Create database manager."""
    db_path = tmp_path / "test_factory.db"
    manager = DatabaseManager(str(db_path))
    manager.setup()
    yield manager


@pytest.fixture
def live_simulation(
    api_config: dict[str, Any],
) -> Generator[tuple[str, Orchestrator], None, None]:
    """Create a live simulation via API."""
    from payment_simulator.api.dependencies import container

    # Create simulation via service
    sim_id, orch = container.simulation_service.create_simulation(api_config)

    # Run some ticks
    for _ in range(10):
        orch.tick()

    yield sim_id, orch

    # Cleanup
    container.simulation_service.delete_simulation(sim_id)


@pytest.fixture
def persisted_simulation(
    db_manager: DatabaseManager,
    ffi_config: dict[str, Any],
    api_config: dict[str, Any],
) -> str:
    """Create a persisted-only simulation (not in memory)."""
    # Create orchestrator
    orch = Orchestrator.new(ffi_config)

    ticks_per_day = api_config["simulation"]["ticks_per_day"]
    num_days = api_config["simulation"]["num_days"]

    # Generate unique sim_id
    sim_id = f"test-persist-{uuid.uuid4().hex[:8]}"

    # Insert simulation record
    conn = db_manager.get_connection()
    conn.execute(
        """
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents, config_json,
            status, started_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            sim_id,
            "test.yaml",
            "test-hash",
            api_config["simulation"]["rng_seed"],
            ticks_per_day,
            num_days,
            len(api_config["agents"]),
            json.dumps(api_config),
            "completed",
        ],
    )

    # Run simulation with persistence
    sim_config = SimulationConfig(
        total_ticks=ticks_per_day * num_days,
        ticks_per_day=ticks_per_day,
        num_days=num_days,
        persist=True,
        full_replay=True,
    )
    persistence = PersistenceManager(db_manager, sim_id, full_replay=True)
    output = QuietOutputStrategy()

    with patch("sys.stdout", new_callable=StringIO):
        runner = SimulationRunner(orch, sim_config, output, persistence)
        runner.run()

    return sim_id


# ============================================================================
# Phase 1.1: Factory exists and can be imported
# ============================================================================


class TestAPIStateProviderFactoryExists:
    """TDD tests to verify factory module exists."""

    def test_factory_module_importable(self) -> None:
        """APIStateProviderFactory should be importable."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )

            assert APIStateProviderFactory is not None
        except ImportError:
            pytest.fail(
                "Cannot import APIStateProviderFactory. "
                "Create api/services/state_provider_factory.py"
            )

    def test_factory_has_create_method(self) -> None:
        """Factory should have create() method."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )

            assert hasattr(APIStateProviderFactory, "create")
        except ImportError:
            pytest.skip("Factory not yet implemented")


# ============================================================================
# Phase 1.2: Factory returns correct provider type
# ============================================================================


class TestFactoryReturnsCorrectProviderType:
    """TDD tests for factory returning correct StateProvider type."""

    def test_factory_returns_orchestrator_provider_for_live(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """Factory should return OrchestratorStateProvider for live simulation."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)

        assert isinstance(provider, OrchestratorStateProvider), (
            f"Expected OrchestratorStateProvider for live simulation, "
            f"got {type(provider).__name__}"
        )

    def test_factory_returns_database_provider_for_persisted(
        self, persisted_simulation: str, db_manager: DatabaseManager
    ) -> None:
        """Factory should return DatabaseStateProvider for persisted simulation."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id = persisted_simulation

        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)

        assert isinstance(provider, DatabaseStateProvider), (
            f"Expected DatabaseStateProvider for persisted simulation, "
            f"got {type(provider).__name__}"
        )

    def test_factory_returns_state_provider_protocol(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """Factory should return object implementing StateProvider protocol."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)

        assert isinstance(provider, StateProvider), (
            f"Provider should implement StateProvider protocol, "
            f"got {type(provider).__name__}"
        )


# ============================================================================
# Phase 1.3: Provider returns correct data
# ============================================================================


class TestProviderReturnsCorrectData:
    """TDD tests verifying providers return correct data."""

    def test_live_provider_returns_agent_costs(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """Live provider should return agent accumulated costs."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)

        costs = provider.get_agent_accumulated_costs("BANK_A")

        # Should have all canonical fields
        assert "liquidity_cost" in costs
        assert "delay_cost" in costs
        assert "collateral_cost" in costs
        assert "deadline_penalty" in costs
        assert "total_cost" in costs

    def test_persisted_provider_returns_agent_costs(
        self, persisted_simulation: str, db_manager: DatabaseManager
    ) -> None:
        """Persisted provider should return agent accumulated costs."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id = persisted_simulation

        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)

        costs = provider.get_agent_accumulated_costs("BANK_A")

        # Should have all canonical fields
        assert "liquidity_cost" in costs
        assert "delay_cost" in costs
        assert "collateral_cost" in costs
        assert "deadline_penalty" in costs
        assert "total_cost" in costs

    def test_live_provider_returns_agent_balance(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """Live provider should return agent balance."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)

        balance = provider.get_agent_balance("BANK_A")

        assert isinstance(balance, int)
        assert balance >= 0 or balance < 0  # Can be negative (overdraft)


# ============================================================================
# Phase 1.4: Error handling
# ============================================================================


class TestFactoryErrorHandling:
    """TDD tests for factory error handling."""

    def test_factory_raises_for_nonexistent_simulation(
        self, db_manager: DatabaseManager
    ) -> None:
        """Factory should raise error for nonexistent simulation."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
                SimulationNotFoundError,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        factory = APIStateProviderFactory()

        with pytest.raises(SimulationNotFoundError):
            factory.create("nonexistent-sim-id", db_manager)

    def test_factory_works_without_db_for_live(
        self, live_simulation: tuple[str, Orchestrator]
    ) -> None:
        """Factory should work without db_manager for live simulations."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        # db_manager=None should work for live simulations
        provider = factory.create(sim_id, db_manager=None)

        assert isinstance(provider, OrchestratorStateProvider)


# ============================================================================
# Phase 1.5: Factory integration with existing API
# ============================================================================


class TestFactoryAPIIntegration:
    """Tests verifying factory integrates with existing API patterns."""

    def test_factory_can_be_used_as_dependency(self) -> None:
        """Factory should be usable as FastAPI dependency."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
                get_state_provider_factory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        # Should be able to call as dependency
        factory = get_state_provider_factory()
        assert isinstance(factory, APIStateProviderFactory)

    def test_factory_provider_data_matches_direct_orchestrator(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """Factory-created provider should return same data as direct Orchestrator access."""
        try:
            from payment_simulator.api.services.state_provider_factory import (
                APIStateProviderFactory,
            )
        except ImportError:
            pytest.skip("Factory not yet implemented")

        sim_id, orch = live_simulation

        # Get costs via factory
        factory = APIStateProviderFactory()
        provider = factory.create(sim_id, db_manager)
        factory_costs = provider.get_agent_accumulated_costs("BANK_A")

        # Get costs via direct orchestrator
        direct_provider = OrchestratorStateProvider(orch)
        direct_costs = direct_provider.get_agent_accumulated_costs("BANK_A")

        # Should be identical
        assert factory_costs["liquidity_cost"] == direct_costs["liquidity_cost"]
        assert factory_costs["delay_cost"] == direct_costs["delay_cost"]
        assert factory_costs["deadline_penalty"] == direct_costs["deadline_penalty"]
        assert factory_costs["total_cost"] == direct_costs["total_cost"]


# ============================================================================
# Phase 4.3: Factory get_transaction_stats() for /metrics endpoint
# ============================================================================


class TestFactoryGetTransactionStats:
    """TDD tests for get_transaction_stats() method."""

    def test_factory_has_get_transaction_stats_method(self) -> None:
        """Factory should have get_transaction_stats() method."""
        from payment_simulator.api.services.state_provider_factory import (
            APIStateProviderFactory,
        )

        factory = APIStateProviderFactory()
        assert hasattr(factory, "get_transaction_stats")

    def test_get_transaction_stats_returns_required_fields(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """get_transaction_stats() should return dict with required fields."""
        from payment_simulator.api.services.state_provider_factory import (
            APIStateProviderFactory,
        )

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        stats = factory.get_transaction_stats(sim_id, db_manager)

        # Should have all fields needed by DataService.get_metrics()
        assert "total_arrivals" in stats
        assert "total_settlements" in stats
        assert "avg_delay_ticks" in stats
        assert "max_delay_ticks" in stats

    def test_get_transaction_stats_live_returns_integers(
        self, live_simulation: tuple[str, Orchestrator], db_manager: DatabaseManager
    ) -> None:
        """Live simulation stats should have correct types."""
        from payment_simulator.api.services.state_provider_factory import (
            APIStateProviderFactory,
        )

        sim_id, _orch = live_simulation

        factory = APIStateProviderFactory()
        stats = factory.get_transaction_stats(sim_id, db_manager)

        assert isinstance(stats["total_arrivals"], int)
        assert isinstance(stats["total_settlements"], int)
        assert isinstance(stats["max_delay_ticks"], int)
        assert isinstance(stats["avg_delay_ticks"], (int, float))

    def test_get_transaction_stats_persisted(
        self, persisted_simulation: str, db_manager: DatabaseManager
    ) -> None:
        """Persisted simulation should return transaction stats from database."""
        from payment_simulator.api.services.state_provider_factory import (
            APIStateProviderFactory,
        )

        sim_id = persisted_simulation

        factory = APIStateProviderFactory()
        stats = factory.get_transaction_stats(sim_id, db_manager)

        # Should have required fields
        assert "total_arrivals" in stats
        assert "total_settlements" in stats
        assert "avg_delay_ticks" in stats
        assert "max_delay_ticks" in stats

        # Values should be non-negative
        assert stats["total_arrivals"] >= 0
        assert stats["total_settlements"] >= 0
        assert stats["max_delay_ticks"] >= 0
        assert stats["avg_delay_ticks"] >= 0

    def test_get_transaction_stats_raises_for_nonexistent(
        self, db_manager: DatabaseManager
    ) -> None:
        """get_transaction_stats() should raise for nonexistent simulation."""
        from payment_simulator.api.services.state_provider_factory import (
            APIStateProviderFactory,
            SimulationNotFoundError,
        )

        factory = APIStateProviderFactory()

        with pytest.raises(SimulationNotFoundError):
            factory.get_transaction_stats("nonexistent-sim", db_manager)
