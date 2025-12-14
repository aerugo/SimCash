# Phase 4: CLI Command

## Overview

Add `policy-evolution` command to the experiment CLI app.

**Status**: In Progress
**Start Date**: 2025-12-14

---

## Goals

1. Add `policy-evolution` subcommand to experiment_app
2. Implement all CLI options (--agent, --start, --end, --llm)
3. Output JSON to stdout
4. Handle errors gracefully with exit codes

---

## CLI Specification

```bash
payment-sim experiment policy-evolution <run_id> [OPTIONS]

Arguments:
  run_id          Run ID to analyze (e.g., exp1-20251209-143022-a1b2c3)

Options:
  --db, -d PATH          Path to database file [default: results/experiments.db]
  --agent, -a TEXT       Filter by agent ID
  --start INTEGER        Start iteration (1-indexed, inclusive)
  --end INTEGER          End iteration (1-indexed, inclusive)
  --llm                  Include LLM prompts and responses
  --compact              Output compact JSON (no indentation)
```

---

## TDD Steps

### Step 4.1: Create Test File (RED)

Create `api/tests/experiments/cli/test_policy_evolution_command.py`

**Test Cases**:
1. `test_command_outputs_json` - Basic JSON output
2. `test_command_filters_by_agent` - --agent flag
3. `test_command_filters_by_iteration_range` - --start/--end
4. `test_command_includes_llm_with_flag` - --llm flag
5. `test_command_excludes_llm_by_default` - Default behavior
6. `test_command_handles_invalid_run_id` - Error exit code
7. `test_command_handles_missing_database` - Error exit code
8. `test_command_compact_output` - --compact flag

### Step 4.2: Add Command (GREEN)

Modify `api/payment_simulator/experiments/cli/commands.py`

### Step 4.3: Refactor

- Ensure consistent error handling
- Verify JSON output format
- Check exit codes

---

## Error Handling

| Error | Exit Code | Message |
|-------|-----------|---------|
| Database not found | 1 | "Database not found: {path}" |
| Run ID not found | 1 | "Run not found: {run_id}" |
| Invalid iteration range | 1 | "--start must be <= --end" |

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Help text is clear
- [ ] JSON output is correct
