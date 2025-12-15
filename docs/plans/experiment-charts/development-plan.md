# Experiment Charts - Development Plan

**Status**: In Progress
**Created**: 2025-12-15
**Branch**: claude/add-experiment-charts-rrvMK

## Summary

Add a `payment-sim experiment chart` command that produces visualizations of experiment runs, showing cost convergence over iterations with support for accepted-only vs all-policies comparison, agent filtering, and parameter value overlay.

## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All costs read from database are integer cents, display in dollars for human readability on charts
- **INV-5**: Replay Identity - Chart data comes from the same `experiment_iterations` table used by replay, ensuring consistency

## Current State Analysis

The experiment framework has:
- `ExperimentRepository` with `experiment_iterations` table storing `costs_per_agent`, `accepted_changes`, and `policies` per iteration
- `PolicyEvolutionService` for extracting policy data across iterations
- Existing commands: `run`, `replay`, `results`, `policy-evolution`, `validate`, `info`, `list`, `template`
- matplotlib already in dependencies

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/experiments/cli/commands.py` | Has experiment subcommands | Add `chart` command |
| `api/payment_simulator/experiments/analysis/__init__.py` | Exports evolution service | Export new charting service |
| NEW: `api/payment_simulator/experiments/analysis/charting.py` | N/A | Chart data extraction and rendering |
| NEW: `api/tests/experiments/analysis/test_charting.py` | N/A | Unit tests for charting logic |
| `docs/reference/cli/commands/experiment.md` | Documents experiment commands | Add `chart` command documentation |

## Solution Design

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  CLI: experiment chart                   │
│  --db, run_id, --agent, --parameter, --output           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ExperimentChartService                      │
│  - extract_chart_data(run_id, agent_filter)             │
│  - render_convergence_chart(data, output_path)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ExperimentRepository                        │
│  - load_experiment(run_id)                              │
│  - get_iterations(run_id)                               │
└─────────────────────────────────────────────────────────┘
```

### Chart Specification

**Primary Chart: Cost Convergence**

```
                Cost Convergence - exp1-20251215-084901-866d63
    Cost ($)
      │
  80  ┤                    ·
      │                 ·     ·
  60  ┤              ·  ┌───────────────── All Policies (subtle)
      │           ·     │
  40  ┤    ●────●───●───●───●───●───● ◄── Accepted Policies (prominent)
      │ ·     ·    ·
  20  ┤
      │
   0  ┼────┬────┬────┬────┬────┬────┬────
          1    2    3    4    5    6    7
                    Iteration
```

**Visual Design**:
- Primary line (accepted): Bold, saturated color (e.g., `#2563eb` blue)
- Secondary line (all): Thin, muted color (e.g., `#94a3b8` gray), dashed
- For bootstrap mode: Add shaded uncertainty band around accepted line
- Clean, minimal style with subtle gridlines
- Clear axis labels with units

**With `--parameter` flag**:
```
    Cost ($)                                    Parameter: initial_liquidity_fraction
      │
  40  ┤    ●────●───●───●───●───●───●          0.50 ─●
      │    │    │   │   │   │   │   │               │
      │   0.50 0.40 │ 0.30 │ 0.20 │ 0.20      0.25 ─┤    ●───●───●───●
      │            0.35   0.25   0.20               │
      ┼────┬────┬────┬────┬────┬────┬────          └────┬────┬────┬────
          1    2    3    4    5    6    7                1    2    3    4
```
Parameter values shown as annotations at each data point.

### Key Design Decisions

1. **Separate service from CLI**: Chart logic in `charting.py`, CLI just wires inputs
2. **Support both deterministic and bootstrap modes**: For deterministic, sum agent costs; for bootstrap, use mean(delta) if available from events
3. **matplotlib for rendering**: Already a dependency, produces publication-quality plots
4. **Save to file by default**: `--output` flag with auto-generated name if not specified
5. **Dual-line visualization**: Accepted policies (prominent) vs all policies (subtle) shows exploration vs convergence

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Chart data extraction | Data structures and repository queries | 6 tests |
| 2 | Chart rendering | matplotlib output generation | 4 tests |
| 3 | CLI integration | Command wiring and options | 3 tests |
| 4 | Documentation | Update CLI docs | N/A |

## Phase 1: Chart Data Extraction

**Goal**: Extract chart-ready data from experiment database

### Deliverables
1. `ChartDataPoint` dataclass
2. `ChartData` dataclass
3. `ExperimentChartService.extract_chart_data()` method

### TDD Approach
1. Write failing tests for data extraction
2. Implement `ExperimentChartService` to pass tests
3. Refactor for clarity

### Success Criteria
- [ ] Extract iteration costs for all agents
- [ ] Separate accepted vs all policies
- [ ] Handle agent filtering with `--agent`
- [ ] Extract parameter values for `--parameter`
- [ ] Costs converted from cents to dollars for display

## Phase 2: Chart Rendering

**Goal**: Generate matplotlib charts with proper styling

### Deliverables
1. `render_convergence_chart()` function
2. Style configuration for pleasant appearance
3. Support for parameter annotation overlay

### TDD Approach
1. Write tests that verify chart generation (file created, dimensions)
2. Implement rendering with matplotlib
3. Refine styling

### Success Criteria
- [ ] Chart saved to specified path
- [ ] Dual-line visualization (accepted + all)
- [ ] Bootstrap uncertainty band when applicable
- [ ] Parameter annotations when `--parameter` used
- [ ] Clean, publication-quality styling

## Phase 3: CLI Integration

**Goal**: Wire chart command into experiment subcommand

### Deliverables
1. `chart` subcommand in experiment_app
2. Options: `--db`, `--agent`, `--parameter`, `--output`
3. Error handling and validation

### TDD Approach
1. Test CLI argument parsing
2. Test error cases (invalid run_id, missing db)
3. Integration test with real output

### Success Criteria
- [ ] `payment-sim experiment chart <run-id>` works
- [ ] `--agent` filters to single agent
- [ ] `--parameter` requires `--agent` flag
- [ ] `--output` controls output path
- [ ] Helpful error messages

## Phase 4: Documentation

**Goal**: Update CLI reference documentation

### Deliverables
1. Add `chart` command to `docs/reference/cli/commands/experiment.md`

### Success Criteria
- [ ] Synopsis with all options
- [ ] Description with examples
- [ ] Output examples showing chart appearance

## Testing Strategy

### Unit Tests
- Data extraction from mock repository
- Parameter extraction from policy dicts
- Cost aggregation (sum for deterministic, mean for bootstrap)

### Integration Tests
- End-to-end: create experiment, run chart, verify output file exists
- Chart with --agent filtering
- Chart with --parameter annotation

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/cli/commands/experiment.md` - Add chart command section
- [ ] Update CLI index if needed

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
| Phase 3 | Pending | |
| Phase 4 | Pending | |
