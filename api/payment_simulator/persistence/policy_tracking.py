"""
Policy Snapshot Tracking

Functions for:
- Computing deterministic policy hashes for deduplication
- Saving policy JSON files to backend/policies/
- Creating policy snapshot records
- Capturing initial policies at simulation start

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


def save_policy_file(
    agent_id: str,
    version: str,
    policy_json: str,
    base_dir: Path,
) -> Path:
    """Save policy JSON to versioned file.

    Uses naming convention: {agent_id}_policy_{version}.json

    Args:
        agent_id: Agent identifier (e.g., "BANK_A")
        version: Version identifier (e.g., "v1", "v2", "init")
        policy_json: JSON string to save
        base_dir: Base directory for policy files

    Returns:
        Path to saved file

    Examples:
        >>> save_policy_file("BANK_A", "v1", '{"type": "fifo"}', Path("/tmp"))
        PosixPath('/tmp/BANK_A_policy_v1.json')
    """
    # Ensure base directory exists
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    # Construct file path
    filename = f"{agent_id}_policy_{version}.json"
    file_path = base_dir / filename

    # Write JSON file (pretty-printed for human readability)
    policy_dict = json.loads(policy_json)
    with file_path.open("w") as f:
        json.dump(policy_dict, f, indent=2)

    return file_path


def create_policy_snapshot(
    simulation_id: str,
    agent_id: str,
    snapshot_day: int,
    snapshot_tick: int,
    policy_json: str,
    created_by: str,
    policy_dir: Path,
    version: str | None = None,
) -> dict[str, Any]:
    """Create policy snapshot record with hash and file path.

    Args:
        simulation_id: Simulation identifier
        agent_id: Agent identifier
        snapshot_day: Day when policy changed
        snapshot_tick: Tick when policy changed
        policy_json: JSON string representing policy
        created_by: Who/what created policy ("init", "manual", "llm")
        policy_dir: Directory to save policy files
        version: Optional version identifier (defaults to "day{day}_tick{tick}")

    Returns:
        Dictionary matching PolicySnapshotRecord schema

    Examples:
        >>> snapshot = create_policy_snapshot(
        ...     simulation_id="sim-001",
        ...     agent_id="BANK_A",
        ...     snapshot_day=0,
        ...     snapshot_tick=0,
        ...     policy_json='{"type": "fifo"}',
        ...     created_by="init",
        ...     policy_dir=Path("/tmp/policies")
        ... )
        >>> snapshot["policy_hash"]
        'a1b2c3d4...'  # 64 chars
    """
    # Compute hash
    policy_hash = compute_policy_hash(policy_json)

    # Generate version if not provided
    if version is None:
        version = f"day{snapshot_day}_tick{snapshot_tick}"

    # Save policy file
    file_path = save_policy_file(agent_id, version, policy_json, policy_dir)

    # Create snapshot record
    snapshot = {
        "simulation_id": simulation_id,
        "agent_id": agent_id,
        "snapshot_day": snapshot_day,
        "snapshot_tick": snapshot_tick,
        "policy_hash": policy_hash,
        "policy_file_path": str(file_path),
        "policy_json": policy_json,
        "created_by": created_by,
    }

    return snapshot


def capture_initial_policies(
    agent_configs: list[dict[str, Any]],
    simulation_id: str,
    policy_dir: Path,
) -> list[dict[str, Any]]:
    """Capture initial policies for all agents at simulation start.

    Args:
        agent_configs: List of agent configuration dicts (each with 'id' and 'policy' keys)
        simulation_id: Simulation identifier
        policy_dir: Directory to save policy files

    Returns:
        List of policy snapshot dicts for all agents

    Examples:
        >>> agent_configs = [
        ...     {"id": "BANK_A", "opening_balance": 1000000,
        ...      "credit_limit": 500000, "policy": {"type": "Fifo"}},
        ...     {"id": "BANK_B", "opening_balance": 2000000,
        ...      "credit_limit": 300000, "policy": {"type": "Priority"}},
        ... ]
        >>> snapshots = capture_initial_policies(agent_configs, "sim-001", Path("/tmp"))
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

        # Create snapshot
        snapshot = create_policy_snapshot(
            simulation_id=simulation_id,
            agent_id=agent_id,
            snapshot_day=0,
            snapshot_tick=0,
            policy_json=policy_json,
            created_by=PolicyCreatedBy.INIT.value,
            policy_dir=policy_dir,
            version="init",
        )

        snapshots.append(snapshot)

    return snapshots
