"""
Policy Snapshot Tracking

Functions for:
- Computing deterministic policy hashes for deduplication
- Creating policy snapshot records (database-only storage)
- Capturing initial policies at simulation start
- Loading policy templates from disk into database

Updated: Database-only storage (no file I/O at runtime)
Phase 4: Policy Snapshot Tracking
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import PolicyCreatedBy


def compute_policy_hash(policy_json: str) -> str:
    """Compute deterministic SHA256 hash of policy JSON.

    Normalizes JSON before hashing to ensure whitespace differences
    don't affect the hash.

    Args:
        policy_json: JSON string representing policy

    Returns:
        64-character hex string (SHA256)

    Examples:
        >>> compute_policy_hash('{"type": "fifo"}')
        'a1b2c3d4...'  # 64 chars

        >>> # Whitespace doesn't affect hash
        >>> hash1 = compute_policy_hash('{"type":"fifo"}')
        >>> hash2 = compute_policy_hash('{"type": "fifo"}')
        >>> hash1 == hash2
        True
    """
    # Normalize JSON (parse and re-serialize with consistent formatting)
    policy_dict = json.loads(policy_json)
    normalized_json = json.dumps(policy_dict, sort_keys=True, separators=(",", ":"))

    # Compute SHA256 hash
    hash_bytes = hashlib.sha256(normalized_json.encode("utf-8")).digest()
    return hash_bytes.hex()


def create_policy_snapshot(
    simulation_id: str,
    agent_id: str,
    snapshot_day: int,
    snapshot_tick: int,
    policy_json: str,
    created_by: str,
) -> dict[str, Any]:
    """Create policy snapshot record with hash.

    Policies are stored only in database (no file operations).

    Args:
        simulation_id: Simulation identifier
        agent_id: Agent identifier
        snapshot_day: Day when policy changed
        snapshot_tick: Tick when policy changed
        policy_json: JSON string representing policy
        created_by: Who/what created policy ("init", "manual", "llm")

    Returns:
        Dictionary matching PolicySnapshotRecord schema

    Examples:
        >>> snapshot = create_policy_snapshot(
        ...     simulation_id="sim-001",
        ...     agent_id="BANK_A",
        ...     snapshot_day=0,
        ...     snapshot_tick=0,
        ...     policy_json='{"type": "fifo"}',
        ...     created_by="init"
        ... )
        >>> snapshot["policy_hash"]
        'a1b2c3d4...'  # 64 chars
        >>> "policy_file_path" in snapshot
        False
    """
    # Compute hash
    policy_hash = compute_policy_hash(policy_json)

    # Create snapshot record (no file operations)
    snapshot = {
        "simulation_id": simulation_id,
        "agent_id": agent_id,
        "snapshot_day": snapshot_day,
        "snapshot_tick": snapshot_tick,
        "policy_hash": policy_hash,
        "policy_json": policy_json,
        "created_by": created_by,
    }

    return snapshot


def capture_initial_policies(
    agent_configs: list[dict[str, Any]],
    simulation_id: str,
) -> list[dict[str, Any]]:
    """Capture initial policies for all agents at simulation start.

    Policies are stored only in database (no file storage).

    Args:
        agent_configs: List of agent configuration dicts (each with 'id' and 'policy' keys)
        simulation_id: Simulation identifier

    Returns:
        List of policy snapshot dicts for all agents

    Examples:
        >>> agent_configs = [
        ...     {"id": "BANK_A", "opening_balance": 1000000,
        ...      "unsecured_cap": 500000, "policy": {"type": "Fifo"}},
        ...     {"id": "BANK_B", "opening_balance": 2000000,
        ...      "unsecured_cap": 300000, "policy": {"type": "Fifo"}},
        ... ]
        >>> snapshots = capture_initial_policies(agent_configs, "sim-001")
        >>> len(snapshots)
        2
        >>> snapshots[0]["agent_id"]
        'BANK_A'
    """
    snapshots = []

    for agent_config in agent_configs:
        agent_id = agent_config["id"]
        policy_config = agent_config["policy"]

        # Convert policy config to JSON
        policy_json = json.dumps(policy_config, sort_keys=True)

        # Create snapshot (no file operations)
        snapshot = create_policy_snapshot(
            simulation_id=simulation_id,
            agent_id=agent_id,
            snapshot_day=0,
            snapshot_tick=0,
            policy_json=policy_json,
            created_by=PolicyCreatedBy.INIT.value,
        )

        snapshots.append(snapshot)

    return snapshots


def load_policy_templates(
    policy_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Load policy template files from disk into database-ready format.

    Scans policy_dir for *.json files and creates snapshot records.
    These are loaded once per database at setup.

    Args:
        policy_dir: Directory containing policy template JSON files.
                   Defaults to simulator/policies/

    Returns:
        List of policy snapshot dicts ready for database insertion

    Examples:
        >>> templates = load_policy_templates()
        >>> len(templates) > 0
        True
        >>> templates[0]["simulation_id"]
        'templates'
        >>> "fifo" in {t["agent_id"] for t in templates}
        True
    """
    if policy_dir is None:
        # Default to simulator/policies/ (from project root)
        # policy_tracking.py -> persistence -> payment_simulator -> api -> cashman (project root)
        policy_dir = Path(__file__).parent.parent.parent.parent / "simulator" / "policies"

    templates = []

    # Scan for JSON files
    for json_file in policy_dir.glob("*.json"):
        # Skip subdirectories like defaults/
        if not json_file.is_file():
            continue

        # Read policy JSON
        policy_json = json_file.read_text()

        # Create a snapshot record for this template
        # Use simulation_id="templates" to mark as template catalog
        template = create_policy_snapshot(
            simulation_id="templates",
            agent_id=json_file.stem,  # e.g., "fifo", "liquidity_aware"
            snapshot_day=0,
            snapshot_tick=0,
            policy_json=policy_json,
            created_by=PolicyCreatedBy.INIT.value,
        )

        templates.append(template)

    return templates
