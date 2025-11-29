"""FastAPI application for Payment Simulator.

This module provides the main FastAPI application with a clean,
maintainable architecture using:
- Services: Business logic layer (SimulationService, TransactionService)
- Routers: Endpoint organization by domain
- Models: Pydantic schemas for requests/responses
- Dependencies: Dependency injection for services

The application exposes REST endpoints for simulation management,
transaction processing, checkpoints, and diagnostic data.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from payment_simulator.api.dependencies import container
from payment_simulator.api.routers import (
    checkpoints_router,
    diagnostics_router,
    simulations_router,
    transactions_router,
)

if TYPE_CHECKING:
    pass


# ============================================================================
# Backward Compatibility Layer
# ============================================================================
# These exports maintain backward compatibility with existing code that imports
# `manager` from main.py. New code should use the services directly via
# dependency injection.


class _ManagerProxy:
    """Proxy that provides backward compatibility with the old manager interface.

    This allows existing code and tests that use:
        from payment_simulator.api.main import manager
        manager.simulations.clear()

    To continue working while the implementation uses the new service layer.
    """

    @property
    def simulations(self) -> dict:
        """Access simulations dict for compatibility."""
        return container.simulation_service._simulations

    @property
    def configs(self) -> dict:
        """Access configs dict for compatibility."""
        return container.simulation_service._configs

    @property
    def transactions(self) -> dict:
        """Access transactions dict for compatibility."""
        return container.transaction_service._transactions

    @property
    def db_manager(self) -> Any:
        """Access db_manager for compatibility."""
        return container.db_manager

    @db_manager.setter
    def db_manager(self, value: Any) -> None:
        """Set db_manager for compatibility."""
        container.db_manager = value

    def create_simulation(
        self, config_dict: dict[str, Any]
    ) -> tuple[str, Any]:
        """Create simulation via service."""
        return container.simulation_service.create_simulation(config_dict)

    def get_simulation(self, sim_id: str) -> Any:
        """Get simulation via service."""
        return container.simulation_service.get_simulation(sim_id)

    def delete_simulation(self, sim_id: str) -> None:
        """Delete simulation via service."""
        container.simulation_service.delete_simulation(sim_id)
        container.transaction_service.cleanup_simulation(sim_id)

    def list_simulations(self) -> list[dict[str, Any]]:
        """List simulations via service."""
        return container.simulation_service.list_simulations()

    def get_state(self, sim_id: str) -> dict[str, Any]:
        """Get state via service."""
        return container.simulation_service.get_state(sim_id)

    def track_transaction(
        self,
        sim_id: str,
        tx_id: str,
        sender: str,
        receiver: str,
        amount: int,
        deadline_tick: int,
        priority: int,
        divisible: bool,
    ) -> None:
        """Track transaction via service."""
        container.transaction_service._track_transaction(
            sim_id=sim_id,
            tx_id=tx_id,
            sender=sender,
            receiver=receiver,
            amount=amount,
            deadline_tick=deadline_tick,
            priority=priority,
            divisible=divisible,
        )

    def get_transaction(
        self, sim_id: str, tx_id: str
    ) -> dict[str, Any] | None:
        """Get transaction via service."""
        try:
            return container.transaction_service.get_transaction(sim_id, tx_id)
        except Exception:
            return None

    def list_transactions(
        self,
        sim_id: str,
        status: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, Any]]:
        """List transactions via service."""
        try:
            return container.transaction_service.list_transactions(
                sim_id, status=status, agent=agent
            )
        except Exception:
            return []


# Global manager proxy for backward compatibility
manager = _ManagerProxy()


# ============================================================================
# FastAPI Application
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup/shutdown."""
    # Startup: Configure database if environment variable is set
    db_path = os.environ.get("PAYMENT_SIM_DB_PATH")
    if db_path:
        from payment_simulator.persistence.connection import DatabaseManager

        app.state.db_manager = DatabaseManager(db_path)
        app.state.db_manager.setup()
        container.db_manager = app.state.db_manager

    yield

    # Shutdown: cleanup simulations and close database
    container.clear_all()
    if hasattr(app.state, "db_manager") and app.state.db_manager:
        app.state.db_manager.close()


app = FastAPI(
    title="Payment Simulator API",
    description="REST API for Payment Simulator - Real-Time Gross Settlement System",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(simulations_router)
app.include_router(transactions_router)
app.include_router(checkpoints_router)
app.include_router(diagnostics_router)


# ============================================================================
# Health & Root Endpoints
# ============================================================================


@app.get("/health")
def health_check() -> dict[str, str | int]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_simulations": len(container.simulation_service._simulations),
    }


@app.get("/")
def root() -> dict[str, str]:
    """API root with basic info."""
    return {
        "name": "Payment Simulator API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# ============================================================================
# Re-exports for backward compatibility
# ============================================================================
# Re-export all models from the new location so existing code continues to work.
# New code should import from payment_simulator.api.models directly.

from payment_simulator.api.models import (  # noqa: E402, F401
    AgentCostBreakdown,
    AgentListResponse,
    AgentQueuesResponse,
    AgentStateSnapshot,
    AgentSummary,
    AgentTimelineResponse,
    CheckpointListResponse,
    CheckpointLoadRequest,
    CheckpointLoadResponse,
    CheckpointSaveRequest,
    CheckpointSaveResponse,
    CollateralEvent,
    CostResponse,
    CostTimelineResponse,
    DailyAgentMetric,
    EventListResponse,
    EventRecord,
    MetricsResponse,
    MultiTickResponse,
    NearDeadlineTransaction,
    NearDeadlineTransactionsResponse,
    OverdueTransaction,
    OverdueTransactionsResponse,
    QueueContents,
    QueueTransaction,
    RelatedTransaction,
    SimulationCreateResponse,
    SimulationListResponse,
    SimulationMetadataResponse,
    SimulationSummary,
    SystemMetrics,
    SystemStateSnapshot,
    TickCostDataPoint,
    TickResponse,
    TickStateResponse,
    TransactionDetail,
    TransactionEvent,
    TransactionLifecycleResponse,
    TransactionListResponse,
    TransactionResponse,
    TransactionSubmission,
)

# Re-export SimulationManager class for backward compatibility
# (some code may instantiate it directly)
from payment_simulator.api.services import (
    SimulationService as SimulationManager,  # noqa: E402, F401
)
