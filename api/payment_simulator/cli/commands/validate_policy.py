"""CLI command for validating policy tree JSON files.

This command validates policy files in three stages:
1. JSON syntax validation
2. Schema validation (required fields)
3. Semantic validation (field references, parameters, division safety, etc.)

Optionally runs functional tests against a test scenario.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Annotated

from payment_simulator.backends import validate_policy as rust_validate_policy


class OutputFormat(str, Enum):
    """Output format options."""
    text = "text"
    json = "json"


console = Console()


def validate_policy(
    policy_file: Annotated[
        Path,
        typer.Argument(help="Path to the policy JSON file to validate"),
    ],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.text,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed validation output"),
    ] = False,
    functional_tests: Annotated[
        bool,
        typer.Option("--functional-tests", help="Run functional tests against the policy"),
    ] = False,
    scenario: Annotated[
        Optional[Path],
        typer.Option("--scenario", "-s", help="Custom scenario config for functional tests"),
    ] = None,
):
    """Validate a policy tree JSON file.

    Performs comprehensive validation including:

    - JSON syntax validation
    - Schema validation (required fields)
    - Semantic validation:
      - Node ID uniqueness
      - Tree depth limits (max 100)
      - Field reference validity
      - Parameter reference validity
      - Division-by-zero safety
      - Action reachability

    Examples:

        # Basic validation
        payment-sim validate-policy policies/fifo.json

        # JSON output for programmatic use
        payment-sim validate-policy policies/custom.json --format json

        # Verbose output with details
        payment-sim validate-policy policies/complex.json --verbose

        # Run functional tests
        payment-sim validate-policy policies/smart.json --functional-tests
    """
    # Check file exists
    if not policy_file.exists():
        _output_error(
            format,
            f"Policy file not found: {policy_file}",
            "FileNotFound"
        )
        raise typer.Exit(code=1)

    # Read file content
    try:
        policy_content = policy_file.read_text()
    except Exception as e:
        _output_error(
            format,
            f"Failed to read file: {e}",
            "ReadError"
        )
        raise typer.Exit(code=1)

    # Handle empty file
    if not policy_content.strip():
        _output_error(
            format,
            "Policy file is empty",
            "EmptyFile"
        )
        raise typer.Exit(code=1)

    # Call Rust validation
    result_json = rust_validate_policy(policy_content)
    result = json.loads(result_json)

    # Run functional tests if requested
    functional_test_result = None
    if functional_tests:
        functional_test_result = _run_functional_tests(
            policy_file, policy_content, result, scenario, verbose
        )

    # Output results
    if format == OutputFormat.json:
        _output_json(result, functional_test_result)
    else:
        _output_text(result, policy_file, verbose, functional_test_result)

    # Exit with appropriate code
    if not result.get("valid", False):
        raise typer.Exit(code=1)
    if functional_test_result and not functional_test_result.get("passed", True):
        raise typer.Exit(code=1)


def _output_error(format: OutputFormat, message: str, error_type: str):
    """Output an error message."""
    if format == OutputFormat.json:
        output = {
            "valid": False,
            "errors": [{"type": error_type, "message": message}]
        }
        console.print(json.dumps(output, indent=2))
    else:
        console.print(f"[red]Error:[/red] {message}")


def _output_json(result: dict, functional_test_result: Optional[dict] = None):
    """Output validation results as JSON."""
    if functional_test_result:
        result["functional_tests"] = functional_test_result
    console.print(json.dumps(result, indent=2))


def _output_text(
    result: dict,
    policy_file: Path,
    verbose: bool,
    functional_test_result: Optional[dict] = None
):
    """Output validation results as human-readable text."""
    if result.get("valid"):
        console.print(Panel(
            f"[green]Policy validation passed[/green]\n\n"
            f"[bold]File:[/bold] {policy_file}\n"
            f"[bold]Policy ID:[/bold] {result.get('policy_id', 'N/A')}\n"
            f"[bold]Version:[/bold] {result.get('version', 'N/A')}",
            title="Validation Result",
            border_style="green",
        ))

        if verbose:
            _show_policy_details(result)

        if functional_test_result:
            _show_functional_test_results(functional_test_result)
    else:
        errors = result.get("errors", [])
        error_table = Table(title="Validation Errors", show_header=True)
        error_table.add_column("Type", style="red")
        error_table.add_column("Message")

        for error in errors:
            error_table.add_row(
                error.get("type", "Unknown"),
                error.get("message", "No message")
            )

        console.print(error_table)
        console.print(f"\n[red]Policy validation failed with {len(errors)} error(s)[/red]")


def _show_policy_details(result: dict):
    """Show detailed policy information."""
    trees = result.get("trees", {})

    table = Table(title="Policy Trees", show_header=True)
    table.add_column("Tree Type")
    table.add_column("Present")

    tree_types = [
        ("payment_tree", trees.get("has_payment_tree", False)),
        ("bank_tree", trees.get("has_bank_tree", False)),
        ("strategic_collateral_tree", trees.get("has_strategic_collateral_tree", False)),
        ("end_of_tick_collateral_tree", trees.get("has_end_of_tick_collateral_tree", False)),
    ]

    for tree_name, present in tree_types:
        status = "[green]Yes[/green]" if present else "[dim]No[/dim]"
        table.add_row(tree_name, status)

    console.print(table)

    # Show parameters
    params = trees.get("parameters", [])
    if params:
        console.print(f"\n[bold]Parameters ({len(params)}):[/bold] {', '.join(params)}")
    else:
        console.print("\n[dim]No parameters defined[/dim]")

    # Show description
    if description := result.get("description"):
        console.print(f"\n[bold]Description:[/bold] {description}")


def _run_functional_tests(
    policy_file: Path,
    policy_content: str,
    validation_result: dict,
    scenario: Optional[Path],
    verbose: bool,
) -> dict:
    """Run functional tests against the policy.

    Tests include:
    1. Policy can be loaded by the orchestrator
    2. Policy executes without errors on sample transactions
    3. Policy produces valid decisions
    """
    from payment_simulator._core import Orchestrator

    tests_run = 0
    tests_passed = 0
    test_results = []

    # Test 1: Policy can be loaded
    tests_run += 1
    try:
        # Read policy content and create config
        # The orchestrator expects: {"type": "FromJson", "json": "...policy content..."}
        ffi_config = {
            "ticks_per_day": 10,
            "num_days": 1,
            "rng_seed": 12345,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "FromJson", "json": policy_content},
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 1_000_000,
                    "unsecured_cap": 500_000,
                    "policy": {"type": "FromJson", "json": policy_content},
                },
            ],
        }

        # Try to create orchestrator
        orch = Orchestrator.new(ffi_config)
        tests_passed += 1
        test_results.append({
            "name": "load_policy",
            "passed": True,
            "message": "Policy loaded successfully by orchestrator"
        })
    except Exception as e:
        test_results.append({
            "name": "load_policy",
            "passed": False,
            "message": f"Failed to load policy: {str(e)}"
        })
        # If we can't load, skip other tests
        return {
            "passed": False,
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "results": test_results,
        }

    # Test 2: Policy executes without errors
    tests_run += 1
    try:
        # Submit a transaction and run a few ticks
        orch.submit_transaction(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            priority=5,
            deadline_tick=50,
            divisible=False,
        )

        # Run 5 ticks
        for _ in range(5):
            orch.tick()

        tests_passed += 1
        test_results.append({
            "name": "execute_policy",
            "passed": True,
            "message": "Policy executed for 5 ticks without errors"
        })
    except Exception as e:
        test_results.append({
            "name": "execute_policy",
            "passed": False,
            "message": f"Policy execution failed: {str(e)}"
        })

    # Test 3: Policy produces valid state
    tests_run += 1
    try:
        # Check that we can query agent and queue state
        agent_ids = orch.get_agent_ids()
        assert len(agent_ids) == 2, "Expected 2 agents"

        # Query system metrics
        metrics = orch.get_system_metrics()
        assert metrics is not None, "System metrics should be available"

        # Query queue states
        queue1_a = orch.get_queue1_size("BANK_A")
        queue2_size = orch.get_queue2_size()

        tests_passed += 1
        test_results.append({
            "name": "valid_state",
            "passed": True,
            "message": "Policy produces valid simulation state"
        })
    except Exception as e:
        test_results.append({
            "name": "valid_state",
            "passed": False,
            "message": f"State validation failed: {str(e)}"
        })

    all_passed = tests_passed == tests_run
    return {
        "passed": all_passed,
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "results": test_results,
    }


def _show_functional_test_results(result: dict):
    """Display functional test results."""
    table = Table(title="Functional Tests", show_header=True)
    table.add_column("Test")
    table.add_column("Status")
    table.add_column("Message")

    for test in result.get("results", []):
        status = "[green]PASS[/green]" if test["passed"] else "[red]FAIL[/red]"
        table.add_row(test["name"], status, test["message"])

    console.print(table)

    passed = result.get("tests_passed", 0)
    total = result.get("tests_run", 0)
    if result.get("passed"):
        console.print(f"\n[green]All functional tests passed ({passed}/{total})[/green]")
    else:
        console.print(f"\n[red]Functional tests failed ({passed}/{total} passed)[/red]")
