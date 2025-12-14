# Policy Evolution Tracking - Documentation Draft

## Summary

Added a new CLI command `payment-sim experiment policy-evolution` that extracts and displays how policies evolved across experiment iterations. The output is JSON, making it suitable for piping to tools like `jq` for further analysis.

## New Command

```bash
payment-sim experiment policy-evolution <run-id> [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--db, -d` | Path to database file (default: `results/experiments.db`) |
| `--agent, -a` | Filter by agent ID |
| `--start` | Start iteration (1-indexed, inclusive) |
| `--end` | End iteration (1-indexed, inclusive) |
| `--llm` | Include LLM prompts and responses |
| `--compact` | Output compact JSON (no indentation) |

### Output Format

```json
{
  "BANK_A": {
    "iteration_1": {
      "policy": {...},
      "diff": "",
      "cost": 10000,
      "accepted": true
    },
    "iteration_2": {
      "policy": {...},
      "diff": "Changed: parameters.urgency_threshold (5 -> 7)",
      "cost": 9000,
      "accepted": true
    }
  }
}
```

## New Module: `payment_simulator.experiments.analysis`

### Components

1. **policy_diff.py**: Computes human-readable diffs between policy dictionaries
   - `compute_policy_diff(old_policy, new_policy)` -> str
   - `extract_parameter_changes(old_policy, new_policy)` -> dict

2. **evolution_model.py**: Immutable dataclasses for evolution output
   - `LLMInteractionData`: LLM prompts and response
   - `IterationEvolution`: Single iteration's policy state
   - `AgentEvolution`: Agent's complete evolution history
   - `build_evolution_output()`: Convert to JSON dict

3. **evolution_service.py**: Service layer for data extraction
   - `PolicyEvolutionService`: Orchestrates repository queries, diff calculation, and model building

## Key Decisions

### Iteration Indexing
- **Database**: 0-indexed (internal standard)
- **Output**: 1-indexed (user-facing)
- Keys are `"iteration_1"`, `"iteration_2"`, etc.

### Costs (INV-1 Compliance)
- All costs are integer cents
- Never use floats for money

### LLM Data
- Only included when `--llm` flag is present
- Includes: system_prompt, user_prompt, raw_response

## Documentation Updates

1. Updated `docs/reference/cli/commands/experiment.md`:
   - Added `policy-evolution` to command table
   - Added full command documentation section

## Test Coverage

- 67 tests total
- Policy diff: 16 tests
- Evolution model: 15 tests
- Evolution service: 15 tests
- CLI command: 12 tests
- Integration: 9 tests
