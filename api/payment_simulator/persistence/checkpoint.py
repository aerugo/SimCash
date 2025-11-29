"""Checkpoint Manager for Save/Load Simulation.

Manages persistence of simulation checkpoints to DuckDB database.
Enables pause/resume, rollback, and debugging capabilities.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

import polars as pl

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.models import CheckpointType, SimulationCheckpointRecord


class CheckpointManager:
    """Manages simulation checkpoints in database.

    Responsibilities:
    - Save orchestrator state snapshots to database
    - Load orchestrator state from database
    - List and filter checkpoints
    - Validate checkpoint integrity (hashes)
    - Track checkpoint metadata
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize checkpoint manager.

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager

    # =========================================================================
    # Save Checkpoint
    # =========================================================================

    def save_checkpoint(
        self,
        orchestrator: Any,  # PyOrchestrator instance
        simulation_id: str,
        config: dict[str, Any],  # FFI dict used to create the orchestrator
        checkpoint_type: str,
        description: str | None,
        created_by: str,
    ) -> str:
        """Save orchestrator state to database as checkpoint.

        Args:
            orchestrator: Orchestrator instance to save
            simulation_id: ID of simulation this checkpoint belongs to
            config: FFI dict configuration used to create the orchestrator
            checkpoint_type: Type of checkpoint (manual/auto/eod/final)
            description: Human-readable description
            created_by: User or system that created checkpoint

        Returns:
            Checkpoint ID (UUID)

        Raises:
            ValueError: If simulation_id is empty or checkpoint_type is invalid
        """
        # Validate inputs
        if not simulation_id:
            raise ValueError("simulation_id cannot be empty")

        if checkpoint_type not in [ct.value for ct in CheckpointType]:
            raise ValueError(
                f"checkpoint_type must be one of {[ct.value for ct in CheckpointType]}, got: {checkpoint_type}"
            )

        # Get state JSON from orchestrator
        state_json = orchestrator.save_state()

        # Parse state to extract metadata
        state_dict = json.loads(state_json)

        # Generate checkpoint ID
        checkpoint_id = str(uuid.uuid4())

        # Compute state hash for integrity validation
        state_hash = hashlib.sha256(state_json.encode("utf-8")).hexdigest()

        # Serialize config to JSON
        config_json = json.dumps(config, sort_keys=True)

        # Extract config hash from state
        config_hash = state_dict["config_hash"]

        # Create checkpoint record
        checkpoint_record = SimulationCheckpointRecord(
            checkpoint_id=checkpoint_id,
            simulation_id=simulation_id,
            checkpoint_tick=state_dict["current_tick"],
            checkpoint_day=state_dict["current_day"],
            checkpoint_timestamp=datetime.now(),
            state_json=state_json,
            state_hash=state_hash,
            config_json=config_json,
            config_hash=config_hash,
            checkpoint_type=CheckpointType(checkpoint_type),
            description=description,
            created_by=created_by,
            num_agents=len(state_dict["agents"]),
            num_transactions=len(state_dict["transactions"]),
            total_size_bytes=len(state_json),
        )

        # Convert to Polars DataFrame
        checkpoint_df = pl.DataFrame([checkpoint_record.model_dump()])

        # Write to database using DuckDB INSERT FROM SELECT pattern
        self.db.conn.execute("INSERT INTO simulation_checkpoints SELECT * FROM checkpoint_df")

        return checkpoint_id

    # =========================================================================
    # Load Checkpoint
    # =========================================================================

    def load_checkpoint(self, checkpoint_id: str) -> tuple[Any, dict[str, Any]]:
        """Load orchestrator from checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to load

        Returns:
            Tuple of (Orchestrator instance, config dict)
            The config dict is the FFI dict that was used to create the original simulation

        Raises:
            ValueError: If checkpoint not found or integrity check fails
        """
        # Retrieve checkpoint from database
        checkpoint = self.get_checkpoint(checkpoint_id)

        if checkpoint is None:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        # Validate state hash
        state_json = checkpoint["state_json"]
        computed_hash = hashlib.sha256(state_json.encode("utf-8")).hexdigest()

        if computed_hash != checkpoint["state_hash"]:
            raise ValueError(
                f"Checkpoint integrity check failed: state hash mismatch "
                f"(expected: {checkpoint['state_hash']}, computed: {computed_hash})"
            )

        # Load config from checkpoint (stored as JSON)
        config = json.loads(checkpoint["config_json"])

        # Import here to avoid circular dependency
        from payment_simulator._core import Orchestrator

        # Load orchestrator from state
        # The Orchestrator.load_state() will validate config hash
        try:
            orchestrator = Orchestrator.load_state(config, state_json)
        except Exception as e:
            # Re-raise with more context
            if "config" in str(e).lower() or "mismatch" in str(e).lower():
                raise ValueError(f"Config mismatch: {e}") from e
            raise

        return orchestrator, config

    # =========================================================================
    # Query Checkpoints
    # =========================================================================

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Retrieve checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint data as dict, or None if not found
        """
        query = f"""
            SELECT *
            FROM simulation_checkpoints
            WHERE checkpoint_id = '{checkpoint_id}'
        """

        result = self.db.conn.execute(query).fetchall()

        if not result:
            return None

        # Convert row to dict
        columns = [desc[0] for desc in self.db.conn.description]
        checkpoint = dict(zip(columns, result[0]))

        return checkpoint

    def list_checkpoints(
        self,
        simulation_id: str | None = None,
        checkpoint_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List checkpoints with optional filtering.

        Args:
            simulation_id: Filter by simulation ID
            checkpoint_type: Filter by checkpoint type
            limit: Maximum number of results

        Returns:
            List of checkpoint metadata dicts (ordered by tick)
        """
        query = "SELECT * FROM simulation_checkpoints WHERE 1=1"

        if simulation_id:
            query += f" AND simulation_id = '{simulation_id}'"

        if checkpoint_type:
            query += f" AND checkpoint_type = '{checkpoint_type}'"

        # Order by tick (chronological)
        query += " ORDER BY checkpoint_tick ASC"

        if limit:
            query += f" LIMIT {limit}"

        result = self.db.conn.execute(query).fetchall()

        # Convert rows to dicts
        columns = [desc[0] for desc in self.db.conn.description]
        checkpoints = [dict(zip(columns, row)) for row in result]

        return checkpoints

    def get_latest_checkpoint(self, simulation_id: str) -> dict[str, Any] | None:
        """Get the most recent checkpoint for a simulation.

        Args:
            simulation_id: Simulation identifier

        Returns:
            Latest checkpoint data as dict, or None if no checkpoints exist
        """
        query = f"""
            SELECT *
            FROM simulation_checkpoints
            WHERE simulation_id = '{simulation_id}'
            ORDER BY checkpoint_tick DESC
            LIMIT 1
        """

        result = self.db.conn.execute(query).fetchall()

        if not result:
            return None

        columns = [desc[0] for desc in self.db.conn.description]
        checkpoint = dict(zip(columns, result[0]))

        return checkpoint

    # =========================================================================
    # Delete Checkpoint
    # =========================================================================

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            True if deleted, False if checkpoint didn't exist
        """
        # Check if exists
        exists = self.get_checkpoint(checkpoint_id) is not None

        if not exists:
            return False

        # Delete
        query = f"""
            DELETE FROM simulation_checkpoints
            WHERE checkpoint_id = '{checkpoint_id}'
        """

        self.db.conn.execute(query)

        return True
