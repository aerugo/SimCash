# Phase 6: CLI/Query Support

**Status**: Pending
**Started**:

---

## Objective

Enable querying and displaying reasoning summaries from experiments. Add support in the audit output and optionally a dedicated CLI command.

---

## Invariants Enforced in This Phase

- None directly - this is read-only query functionality

---

## TDD Steps

### Step 6.1: Update Audit Display

Modify `api/payment_simulator/experiments/runner/audit.py` to include reasoning in the audit output.

**Test Cases**:
1. `test_audit_output_includes_reasoning` - Reasoning displayed in audit
2. `test_audit_output_handles_none_reasoning` - Works when no reasoning

```python
"""Tests for reasoning in audit output."""

from __future__ import annotations

from datetime import datetime
from io import StringIO
import pytest

from payment_simulator.ai_cash_mgmt.persistence.models import LLMInteractionRecord
from payment_simulator.experiments.runner.audit import display_audit_output


class TestAuditReasoningDisplay:
    """Tests for reasoning display in audit output."""

    def test_audit_output_includes_reasoning(self, capsys) -> None:
        """Verify reasoning is displayed in audit output."""
        interactions = [
            LLMInteractionRecord(
                interaction_id="int-001",
                game_id="game-001",
                agent_id="BANK_A",
                iteration_number=1,
                system_prompt="system",
                user_prompt="prompt",
                raw_response="response",
                parsed_policy_json='{"policy": "test"}',
                parsing_error=None,
                llm_reasoning="I considered options A and B...",
                request_timestamp=datetime.now(),
                response_timestamp=datetime.now(),
            )
        ]

        display_audit_output(interactions)

        captured = capsys.readouterr()
        assert "I considered options A and B..." in captured.out

    def test_audit_output_handles_none_reasoning(self, capsys) -> None:
        """Verify audit works when reasoning is None."""
        interactions = [
            LLMInteractionRecord(
                interaction_id="int-001",
                game_id="game-001",
                agent_id="BANK_A",
                iteration_number=1,
                system_prompt="system",
                user_prompt="prompt",
                raw_response="response",
                parsed_policy_json=None,
                parsing_error=None,
                llm_reasoning=None,
                request_timestamp=datetime.now(),
                response_timestamp=datetime.now(),
            )
        ]

        # Should not raise
        display_audit_output(interactions)

        captured = capsys.readouterr()
        # Should indicate no reasoning available or just skip
        assert "Reasoning:" not in captured.out or "N/A" in captured.out
```

### Step 6.2: Optional - Add Reasoning Query Command

Create a command to query reasoning for specific iterations:

```bash
# Usage
payment-sim query-reasoning --game-id <id> --agent <agent> --iteration <n>
```

**Implementation** (optional, can be deferred):

```python
"""Query reasoning command."""

from typing import Annotated
from pathlib import Path

import typer
from rich.console import Console

from payment_simulator.ai_cash_mgmt.persistence.repository import GameRepository


def query_reasoning(
    database: Annotated[Path, typer.Argument(help="Path to database")],
    game_id: Annotated[str, typer.Option("--game-id", "-g", help="Game ID")],
    agent: Annotated[str, typer.Option("--agent", "-a", help="Agent ID")],
    iteration: Annotated[int, typer.Option("--iteration", "-i", help="Iteration number")],
) -> None:
    """Query LLM reasoning for a specific iteration."""
    console = Console()

    repo = GameRepository(database)
    interaction = repo.get_llm_interaction(game_id, agent, iteration)

    if interaction is None:
        console.print(f"[red]No interaction found for {game_id}/{agent}/iter{iteration}[/red]")
        raise typer.Exit(1)

    if interaction.llm_reasoning is None:
        console.print("[yellow]No reasoning captured for this interaction[/yellow]")
    else:
        console.print("\n[bold cyan]LLM Reasoning Summary[/bold cyan]\n")
        console.print(interaction.llm_reasoning)
```

---

## Implementation Details

### Audit Display Update

In `display_audit_output()`, add a section for reasoning:

```python
def display_audit_output(interactions: list[LLMInteractionRecord]) -> None:
    """Display audit trail with reasoning."""
    console = Console()

    for interaction in interactions:
        console.print(f"\n[bold]Iteration {interaction.iteration_number}[/bold]")
        console.print(f"Agent: {interaction.agent_id}")

        # ... existing output ...

        # Add reasoning section
        if interaction.llm_reasoning:
            console.print("\n[bold cyan]Reasoning:[/bold cyan]")
            console.print(interaction.llm_reasoning)
        else:
            console.print("\n[dim]No reasoning captured[/dim]")
```

### Rich Formatting for Long Reasoning

For long reasoning text, use a Panel or collapsible section:

```python
from rich.panel import Panel
from rich.markdown import Markdown

if interaction.llm_reasoning:
    # Truncate if very long, with option to expand
    reasoning_text = interaction.llm_reasoning
    if len(reasoning_text) > 1000:
        reasoning_text = reasoning_text[:1000] + "... [truncated]"

    console.print(Panel(
        Markdown(reasoning_text),
        title="LLM Reasoning",
        border_style="cyan",
    ))
```

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/runner/audit.py` | MODIFY |
| `api/tests/experiments/test_audit_reasoning.py` | CREATE |
| `api/payment_simulator/cli/commands/query.py` | CREATE (optional) |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/experiments/test_audit_reasoning.py -v

# Manual test with real experiment
payment-sim optimize --config test.yaml --verbose --audit
# Should show reasoning in audit output

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/runner/audit.py
```

---

## Completion Criteria

- [ ] Reasoning displayed in audit output
- [ ] Handles None reasoning gracefully
- [ ] Long reasoning formatted nicely
- [ ] (Optional) Query command works
- [ ] All tests pass
