#!/usr/bin/env python3
"""
Migrate old-schema configs (credit_limit) to new schema (unsecured_cap).

This script updates YAML configuration files from the Phase 7 schema (which used
`credit_limit` for overdraft capacity) to the Phase 8 schema (which uses
`unsecured_cap` for explicit unsecured overdraft capacity).

Usage:
    python scripts/migrate_config_v7_to_v8.py input.yaml output.yaml

    # Or migrate in-place:
    python scripts/migrate_config_v7_to_v8.py config.yaml config.yaml

    # Or use stdin/stdout:
    cat input.yaml | python scripts/migrate_config_v7_to_v8.py - - > output.yaml

Examples:
    # Migrate a single file
    python scripts/migrate_config_v7_to_v8.py \\
        examples/configs/old_config.yaml \\
        examples/configs/new_config.yaml

    # Batch migrate all configs in a directory
    for f in old_configs/*.yaml; do
        python scripts/migrate_config_v7_to_v8.py "$f" "migrated/$(basename $f)"
    done

Migration Strategy:
    - If agent has `credit_limit` but not `unsecured_cap`:
      → Add `unsecured_cap` with same value as `credit_limit`
      → Optionally remove `credit_limit` (controlled by --remove-old flag)

    - If agent has both `credit_limit` and `unsecured_cap`:
      → Keep `unsecured_cap`, optionally remove `credit_limit`
      → Warn if values differ

    - If agent has neither:
      → No changes (assumes no overdraft capacity)

Breaking Changes After Deprecation:
    Once the credit_limit field is fully deprecated, configurations with only
    `credit_limit` will fail to load. Use this script to migrate before upgrading.
"""

import sys
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, List


def migrate_agent_config(agent: Dict[str, Any], remove_old: bool = False, verbose: bool = True) -> Dict[str, Any]:
    """
    Migrate a single agent configuration from credit_limit to unsecured_cap.

    Args:
        agent: Agent configuration dictionary
        remove_old: If True, remove credit_limit field after migration
        verbose: If True, print migration actions

    Returns:
        Migrated agent configuration
    """
    agent_id = agent.get("id", "UNKNOWN")
    has_credit_limit = "credit_limit" in agent
    has_unsecured_cap = "unsecured_cap" in agent

    if has_credit_limit and not has_unsecured_cap:
        # Migration: credit_limit → unsecured_cap
        credit_limit_value = agent["credit_limit"]
        agent["unsecured_cap"] = credit_limit_value

        if verbose:
            print(f"✓ Migrated agent '{agent_id}': credit_limit={credit_limit_value} → unsecured_cap={credit_limit_value}")

        if remove_old:
            del agent["credit_limit"]
            if verbose:
                print(f"  └─ Removed credit_limit field")

    elif has_credit_limit and has_unsecured_cap:
        # Both fields present - warn if they differ
        credit_limit_value = agent["credit_limit"]
        unsecured_cap_value = agent["unsecured_cap"]

        if credit_limit_value != unsecured_cap_value:
            print(f"⚠️  WARNING: Agent '{agent_id}' has both credit_limit={credit_limit_value} "
                  f"and unsecured_cap={unsecured_cap_value}. Using unsecured_cap.")

        if remove_old:
            del agent["credit_limit"]
            if verbose:
                print(f"✓ Removed credit_limit from agent '{agent_id}' (kept unsecured_cap={unsecured_cap_value})")

    elif not has_credit_limit and not has_unsecured_cap:
        # Neither field present - no overdraft capacity (this is valid)
        if verbose:
            print(f"  Agent '{agent_id}': No overdraft capacity (neither field present)")

    else:
        # Only unsecured_cap present - already migrated
        if verbose:
            print(f"  Agent '{agent_id}': Already using unsecured_cap")

    return agent


def migrate_config(config: Dict[str, Any], remove_old: bool = False, verbose: bool = True) -> Dict[str, Any]:
    """
    Migrate entire configuration from credit_limit to unsecured_cap schema.

    Args:
        config: Full configuration dictionary
        remove_old: If True, remove credit_limit fields after migration
        verbose: If True, print migration actions

    Returns:
        Migrated configuration
    """
    if "agents" not in config:
        if verbose:
            print("⚠️  WARNING: No 'agents' section found in configuration")
        return config

    agents = config["agents"]
    if verbose:
        print(f"\nMigrating {len(agents)} agent(s)...")
        print("=" * 60)

    for agent in agents:
        migrate_agent_config(agent, remove_old=remove_old, verbose=verbose)

    if verbose:
        print("=" * 60)
        print(f"\n✓ Migration complete for {len(agents)} agent(s)")

    return config


def main():
    parser = argparse.ArgumentParser(
        description="Migrate payment simulator configs from credit_limit to unsecured_cap schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input_file",
        help="Input YAML config file (use '-' for stdin)",
    )
    parser.add_argument(
        "output_file",
        help="Output YAML config file (use '-' for stdout)",
    )
    parser.add_argument(
        "--remove-old",
        action="store_true",
        help="Remove credit_limit fields after migration (default: keep both)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress migration progress messages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be migrated without writing output",
    )

    args = parser.parse_args()

    # Read input
    if args.input_file == "-":
        config = yaml.safe_load(sys.stdin)
    else:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"❌ Error: Input file not found: {args.input_file}", file=sys.stderr)
            sys.exit(1)

        with open(input_path) as f:
            config = yaml.safe_load(f)

    # Migrate
    verbose = not args.quiet
    migrated_config = migrate_config(config, remove_old=args.remove_old, verbose=verbose)

    # Write output
    if args.dry_run:
        if verbose:
            print("\n[DRY RUN] Would write migrated config to:", args.output_file)
        sys.exit(0)

    if args.output_file == "-":
        yaml.dump(migrated_config, sys.stdout, default_flow_style=False, sort_keys=False)
    else:
        output_path = Path(args.output_file)
        with open(output_path, "w") as f:
            yaml.dump(migrated_config, f, default_flow_style=False, sort_keys=False)

        if verbose:
            print(f"\n✓ Wrote migrated configuration to: {output_path}")


if __name__ == "__main__":
    main()
