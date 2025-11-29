"""FastAPI dependencies for service injection.

This module provides dependency injection for API services,
enabling clean separation between HTTP routing and business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from payment_simulator.api.services import (
    SimulationService,
    TransactionService,
)
from payment_simulator.api.services.state_provider_factory import (
    APIStateProviderFactory,
)

if TYPE_CHECKING:
    from payment_simulator.persistence.connection import DatabaseManager


class ServiceContainer:
    """Container for all API services.

    This provides a central location for service instances,
    enabling dependency injection and testability.
    """

    def __init__(self) -> None:
        """Initialize the service container with default services."""
        self._simulation_service: SimulationService | None = None
        self._transaction_service: TransactionService | None = None
        self._db_manager: DatabaseManager | None = None

    @property
    def simulation_service(self) -> SimulationService:
        """Get the simulation service, creating if needed."""
        if self._simulation_service is None:
            self._simulation_service = SimulationService(self._db_manager)
        return self._simulation_service

    @property
    def transaction_service(self) -> TransactionService:
        """Get the transaction service, creating if needed."""
        if self._transaction_service is None:
            self._transaction_service = TransactionService(self.simulation_service)
        return self._transaction_service

    @property
    def db_manager(self) -> DatabaseManager | None:
        """Get the database manager."""
        return self._db_manager

    @db_manager.setter
    def db_manager(self, value: DatabaseManager | None) -> None:
        """Set the database manager and propagate to services."""
        self._db_manager = value
        if self._simulation_service is not None:
            self._simulation_service.db_manager = value

    def clear_all(self) -> None:
        """Clear all services (used for testing cleanup)."""
        if self._simulation_service is not None:
            self._simulation_service.clear_all()
        if self._transaction_service is not None:
            self._transaction_service.clear_all()


# Global service container instance
container = ServiceContainer()


def get_simulation_service() -> SimulationService:
    """Dependency that provides the SimulationService.

    Usage in endpoints:
        @router.get("/simulations")
        def list_sims(service: SimulationService = Depends(get_simulation_service)):
            ...
    """
    return container.simulation_service


def get_transaction_service() -> TransactionService:
    """Dependency that provides the TransactionService.

    Usage in endpoints:
        @router.post("/simulations/{sim_id}/transactions")
        def submit_tx(service: TransactionService = Depends(get_transaction_service)):
            ...
    """
    return container.transaction_service


def get_db_manager() -> Any:
    """Dependency that provides the DatabaseManager if configured.

    Checks both:
    1. Container-level db_manager (set via dependency injection)
    2. app.state.db_manager (set by test fixtures for backward compatibility)

    This supports both production use (via lifespan) and test fixtures.
    """
    # First check container
    if container.db_manager is not None:
        return container.db_manager

    # Fall back to app.state for backward compatibility with test fixtures
    # Import app lazily to avoid circular imports
    from payment_simulator.api.main import app

    if hasattr(app.state, "db_manager"):
        return app.state.db_manager

    return None


def get_state_provider_factory() -> APIStateProviderFactory:
    """Dependency that provides the StateProviderFactory.

    Usage in endpoints:
        @router.get("/simulations/{sim_id}/costs")
        def get_costs(
            sim_id: str,
            factory: APIStateProviderFactory = Depends(get_state_provider_factory),
            db_manager: Any = Depends(get_db_manager),
        ):
            provider = factory.create(sim_id, db_manager)
            ...
    """
    return APIStateProviderFactory()
