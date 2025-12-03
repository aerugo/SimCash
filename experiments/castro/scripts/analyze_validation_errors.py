#!/usr/bin/env python3
"""Analyze validation errors from Castro experiments.

This script reads the validation_errors table from experiment databases
and generates reports to help understand what types of policies fail
SimCash validation and why.

Usage:
    python analyze_validation_errors.py experiments/castro/results/*.db
    python analyze_validation_errors.py experiments/castro/results/exp1_v2.db --detailed
    python analyze_validation_errors.py experiments/castro/results/*.db --export errors.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb


def connect_db(db_path: str) -> duckdb.DuckDBPyConnection:
    """Connect to a database file."""
    return duckdb.connect(db_path, read_only=True)


def get_validation_errors(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """Get all validation errors from database."""
    try:
        result = conn.execute("""
            SELECT
                error_id,
                experiment_id,
                iteration_number,
                agent_id,
                attempt_number,
                policy_json,
                error_messages,
                error_category,
                was_fixed,
                fix_attempt_count,
                created_at
            FROM validation_errors
            ORDER BY created_at
        """).fetchall()
    except duckdb.CatalogException:
        # Table doesn't exist in this database
        return []

    columns = [
        "error_id", "experiment_id", "iteration_number", "agent_id",
        "attempt_number", "policy_json", "error_messages", "error_category",
        "was_fixed", "fix_attempt_count", "created_at"
    ]

    errors = []
    for row in result:
        error = dict(zip(columns, row))
        # Parse JSON fields
        error["policy"] = json.loads(error["policy_json"]) if error["policy_json"] else {}
        error["errors"] = json.loads(error["error_messages"]) if error["error_messages"] else []
        del error["policy_json"]
        del error["error_messages"]
        errors.append(error)

    return errors


def analyze_errors(errors: list[dict]) -> dict[str, Any]:
    """Analyze validation errors and return statistics."""
    if not errors:
        return {"total_errors": 0, "message": "No validation errors found"}

    # Count by category
    category_counts = Counter(e["error_category"] for e in errors)

    # Count by agent
    agent_counts = Counter(e["agent_id"] for e in errors)

    # Initial errors only (attempt_number == 0)
    initial_errors = [e for e in errors if e["attempt_number"] == 0]
    fixed_count = sum(1 for e in initial_errors if e["was_fixed"])
    fix_rate = (fixed_count / len(initial_errors) * 100) if initial_errors else 0

    # Average fix attempts
    avg_fix_attempts = (
        sum(e["fix_attempt_count"] for e in initial_errors) / len(initial_errors)
        if initial_errors else 0
    )

    # Error messages frequency
    all_error_msgs = []
    for e in errors:
        all_error_msgs.extend(e["errors"])
    error_msg_counts = Counter(all_error_msgs)

    # By experiment
    by_experiment = defaultdict(list)
    for e in errors:
        by_experiment[e["experiment_id"]].append(e)

    experiment_stats = {}
    for exp_id, exp_errors in by_experiment.items():
        initial = [e for e in exp_errors if e["attempt_number"] == 0]
        fixed = sum(1 for e in initial if e["was_fixed"])
        experiment_stats[exp_id] = {
            "total_errors": len(exp_errors),
            "initial_errors": len(initial),
            "fixed": fixed,
            "fix_rate": (fixed / len(initial) * 100) if initial else 0,
        }

    return {
        "total_errors": len(errors),
        "initial_errors": len(initial_errors),
        "fixed_count": fixed_count,
        "fix_rate": fix_rate,
        "avg_fix_attempts": avg_fix_attempts,
        "by_category": dict(category_counts.most_common()),
        "by_agent": dict(agent_counts),
        "top_error_messages": dict(error_msg_counts.most_common(20)),
        "by_experiment": experiment_stats,
    }


def extract_common_patterns(errors: list[dict]) -> dict[str, list[dict]]:
    """Extract common error patterns for learning."""
    patterns = defaultdict(list)

    for error in errors:
        category = error["error_category"]

        # Extract key info about the failing policy
        policy = error["policy"]
        params = policy.get("parameters", {})

        pattern_info = {
            "agent": error["agent_id"],
            "iteration": error["iteration_number"],
            "attempt": error["attempt_number"],
            "was_fixed": error["was_fixed"],
            "parameters_used": list(params.keys()),
            "error_msgs": error["errors"][:3],  # First 3 error messages
        }

        # Extract tree structure info if present
        if "payment_tree" in policy:
            tree = policy["payment_tree"]
            pattern_info["tree_type"] = tree.get("type", "unknown")
            if tree.get("type") == "condition":
                cond = tree.get("condition", {})
                pattern_info["condition_op"] = cond.get("op", "unknown")
                # Check for common issues
                left = cond.get("left", {})
                if "field" in left:
                    pattern_info["uses_field"] = left["field"]
                elif "param" in left:
                    pattern_info["uses_param"] = left["param"]

        patterns[category].append(pattern_info)

    return dict(patterns)


def print_summary(analysis: dict[str, Any], detailed: bool = False) -> None:
    """Print analysis summary to console."""
    print("\n" + "=" * 60)
    print("VALIDATION ERROR ANALYSIS")
    print("=" * 60)

    if analysis.get("total_errors", 0) == 0:
        print("\nNo validation errors found in the database(s).")
        print("This could mean:")
        print("  - Experiments haven't been run yet")
        print("  - The database predates the validation_errors table")
        print("  - All policies were valid (unlikely)")
        return

    print(f"\n## Summary")
    print(f"Total errors logged: {analysis['total_errors']}")
    print(f"Initial generation errors: {analysis['initial_errors']}")
    print(f"Successfully fixed: {analysis['fixed_count']} ({analysis['fix_rate']:.1f}%)")
    print(f"Average fix attempts: {analysis['avg_fix_attempts']:.1f}")

    print(f"\n## Errors by Category")
    for category, count in analysis["by_category"].items():
        pct = count / analysis["total_errors"] * 100
        bar = "#" * int(pct / 2)
        print(f"  {category:20s} {count:4d} ({pct:5.1f}%) {bar}")

    print(f"\n## Errors by Agent")
    for agent, count in analysis["by_agent"].items():
        print(f"  {agent}: {count}")

    print(f"\n## Top Error Messages")
    for msg, count in list(analysis["top_error_messages"].items())[:10]:
        # Truncate long messages
        display_msg = msg[:60] + "..." if len(msg) > 60 else msg
        print(f"  {count:3d}x {display_msg}")

    if detailed and "by_experiment" in analysis:
        print(f"\n## By Experiment")
        for exp_id, stats in analysis["by_experiment"].items():
            print(f"\n  {exp_id[:40]}...")
            print(f"    Total errors: {stats['total_errors']}")
            print(f"    Initial errors: {stats['initial_errors']}")
            print(f"    Fixed: {stats['fixed']} ({stats['fix_rate']:.1f}%)")


def export_to_json(errors: list[dict], analysis: dict, output_path: str) -> None:
    """Export errors and analysis to JSON file."""
    export_data = {
        "analysis": analysis,
        "errors": errors,
    }

    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"\nExported to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze validation errors from Castro experiments"
    )
    parser.add_argument(
        "databases",
        nargs="+",
        help="Path(s) to experiment database file(s)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed per-experiment breakdown"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export errors and analysis to JSON file"
    )
    parser.add_argument(
        "--patterns",
        action="store_true",
        help="Extract and show common error patterns"
    )

    args = parser.parse_args()

    # Collect errors from all databases
    all_errors = []
    for db_path in args.databases:
        if not Path(db_path).exists():
            print(f"Warning: {db_path} not found, skipping")
            continue

        try:
            conn = connect_db(db_path)
            errors = get_validation_errors(conn)
            all_errors.extend(errors)
            conn.close()
            print(f"Loaded {len(errors)} errors from {db_path}")
        except Exception as e:
            print(f"Warning: Could not read {db_path}: {e}")

    # Analyze
    analysis = analyze_errors(all_errors)

    # Print summary
    print_summary(analysis, detailed=args.detailed)

    # Show patterns if requested
    if args.patterns and all_errors:
        patterns = extract_common_patterns(all_errors)
        print("\n## Common Error Patterns")
        for category, examples in patterns.items():
            print(f"\n### {category} ({len(examples)} occurrences)")
            # Show first 3 examples
            for ex in examples[:3]:
                print(f"  - {ex['agent']} iter {ex['iteration']}: {ex.get('error_msgs', ['?'])[:1]}")
                if "uses_param" in ex:
                    print(f"    Used param: {ex['uses_param']}")
                if "uses_field" in ex:
                    print(f"    Used field: {ex['uses_field']}")

    # Export if requested
    if args.export:
        export_to_json(all_errors, analysis, args.export)


if __name__ == "__main__":
    main()
