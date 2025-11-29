"""Service layer for simulation management.

This module provides the SimulationService class which encapsulates
all business logic for creating, managing, and executing simulations.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig, ValidationError

if TYPE_CHECKING:
    from payment_simulator.persistence.connection import DatabaseManager


class SimulationNotFoundError(Exception):
    """Raised when a simulation cannot be found."""

    def __init__(self, simulation_id: str) -> None:
        self.simulation_id = simulation_id
        super().__init__(f"Simulation not found: {simulation_id}")


class SimulationService:
    """Service for managing simulation lifecycle.

    This service handles:
    - Simulation creation from configuration
    - State retrieval and queries
    - Tick execution
    - Simulation deletion

    All orchestrator interactions are encapsulated here,
    providing a clean interface for the API layer.
    """

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        """Initialize the simulation service.

        Args:
            db_manager: Optional database manager for persistence features
        """
        self._simulations: dict[str, Orchestrator] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._db_manager = db_manager

    @property
    def db_manager(self) -> DatabaseManager | None:
        """Get the database manager."""
        return self._db_manager

    @db_manager.setter
    def db_manager(self, value: DatabaseManager | None) -> None:
        """Set the database manager."""
        self._db_manager = value

    def create_simulation(
        self, config_dict: dict[str, Any]
    ) -> tuple[str, Orchestrator]:
        """Create a new simulation from configuration.

        Args:
            config_dict: Simulation configuration dictionary

        Returns:
            Tuple of (simulation_id, orchestrator)

        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If orchestrator creation fails
        """
        # Validate config using Pydantic
        try:
            config = SimulationConfig.from_dict(config_dict)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        # Convert to FFI dict
        ffi_dict = config.to_ffi_dict()

        # Create orchestrator
        try:
            orchestrator = Orchestrator.new(ffi_dict)
        except Exception as e:
            raise RuntimeError(f"Failed to create orchestrator: {e}") from e

        # Generate unique ID
        sim_id = str(uuid.uuid4())

        # Store both original and FFI configs
        self._simulations[sim_id] = orchestrator
        self._configs[sim_id] = {"original": config_dict, "ffi": ffi_dict}

        return sim_id, orchestrator

    def get_simulation(self, sim_id: str) -> Orchestrator:
        """Get an orchestrator by simulation ID.

        Args:
            sim_id: The simulation ID

        Returns:
            The orchestrator instance

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
        """
        if sim_id not in self._simulations:
            raise SimulationNotFoundError(sim_id)
        return self._simulations[sim_id]

    def get_config(self, sim_id: str) -> dict[str, Any]:
        """Get the configuration for a simulation.

        Args:
            sim_id: The simulation ID

        Returns:
            Dict with 'original' and 'ffi' config versions

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
        """
        if sim_id not in self._configs:
            raise SimulationNotFoundError(sim_id)
        return self._configs[sim_id]

    def get_state(self, sim_id: str) -> dict[str, Any]:
        """Get full simulation state.

        Args:
            sim_id: The simulation ID

        Returns:
            Dictionary containing:
            - simulation_id: The simulation ID
            - current_tick: Current tick number
            - current_day: Current day number
            - agents: Dict of agent states (balance, queue1_size, unsecured_cap)
            - queue2_size: Size of RTGS queue

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
        """
        orch = self.get_simulation(sim_id)
        config = self.get_config(sim_id)

        # Collect agent states
        agents: dict[str, dict[str, int]] = {}

        # Handle both YAML format ("agents") and FFI format ("agent_configs")
        original_config = config["original"]
        agent_list = original_config.get("agents") or original_config.get(
            "agent_configs", []
        )

        for agent_id in orch.get_agent_ids():
            # Find agent config
            agent_config = next(
                (a for a in agent_list if a["id"] == agent_id), None
            )
            unsecured_cap = agent_config.get("unsecured_cap", 0) if agent_config else 0

            agents[agent_id] = {
                "balance": orch.get_agent_balance(agent_id) or 0,
                "queue1_size": orch.get_queue1_size(agent_id),
                "unsecured_cap": unsecured_cap,
            }

        return {
            "simulation_id": sim_id,
            "current_tick": orch.current_tick(),
            "current_day": orch.current_day(),
            "agents": agents,
            "queue2_size": orch.get_queue2_size(),
        }

    def list_simulations(self) -> list[dict[str, Any]]:
        """List all active simulations.

        Returns:
            List of simulation summaries with ID, current_tick, current_day
        """
        return [
            {
                "simulation_id": sim_id,
                "current_tick": orch.current_tick(),
                "current_day": orch.current_day(),
            }
            for sim_id, orch in self._simulations.items()
        ]

    def delete_simulation(self, sim_id: str) -> None:
        """Delete a simulation.

        This operation is idempotent - deleting a non-existent
        simulation does not raise an error.

        Args:
            sim_id: The simulation ID
        """
        if sim_id in self._simulations:
            del self._simulations[sim_id]
            del self._configs[sim_id]

    def tick(self, sim_id: str) -> dict[str, Any]:
        """Execute a single simulation tick.

        Args:
            sim_id: The simulation ID

        Returns:
            Tick result dictionary with:
            - tick: The tick number that was executed
            - num_arrivals: Number of new arrivals
            - num_settlements: Number of settlements
            - num_lsm_releases: Number of LSM releases
            - total_cost: Total cost incurred

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
        """
        orch = self.get_simulation(sim_id)
        return orch.tick()

    def tick_multiple(
        self, sim_id: str, count: int
    ) -> list[dict[str, Any]]:
        """Execute multiple simulation ticks.

        Args:
            sim_id: The simulation ID
            count: Number of ticks to execute

        Returns:
            List of tick result dictionaries

        Raises:
            SimulationNotFoundError: If simulation doesn't exist
        """
        orch = self.get_simulation(sim_id)
        results = []
        for _ in range(count):
            results.append(orch.tick())
        return results

    def has_simulation(self, sim_id: str) -> bool:
        """Check if a simulation exists.

        Args:
            sim_id: The simulation ID

        Returns:
            True if simulation exists, False otherwise
        """
        return sim_id in self._simulations

    def clear_all(self) -> None:
        """Clear all simulations. Used for testing cleanup."""
        self._simulations.clear()
        self._configs.clear()
