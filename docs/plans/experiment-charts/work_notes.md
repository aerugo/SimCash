# Experiment Charts - Work Notes

**Project**: Add `payment-sim experiment chart` command for visualizing experiment runs
**Started**: 2025-12-15
**Branch**: claude/add-experiment-charts-rrvMK

---

## Session Log

### 2025-12-15 - Initial Planning

**Context Review Completed**:
- Read `docs/plans/CLAUDE.md` - understood planning template structure
- Read `docs/papers/simcash-paper/v3/draft-paper.md` - understood experiment output and what charts need to show
- Read `docs/reference/cli/commands/experiment.md` - understood existing CLI structure
- Read `api/payment_simulator/experiments/persistence/repository.py` - understood database schema
- Read `api/payment_simulator/experiments/cli/commands.py` - understood CLI command patterns
- Read `api/payment_simulator/experiments/analysis/evolution_service.py` - understood data extraction patterns
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants

**Applicable Invariants**:
- INV-1: Costs stored as integer cents, need to convert to dollars for display
- INV-5: Using same data source (experiment_iterations) as replay ensures consistency

**Key Insights**:
- Database stores `costs_per_agent`, `accepted_changes`, and `policies` per iteration
- For deterministic: total system cost is sum of agent costs
- For bootstrap: mean(delta) cost from paired comparison
- Need to distinguish "accepted" policies (convergence path) vs "all" policies (exploration)
- matplotlib already in dependencies - can use for rendering
- PolicyEvolutionService provides good pattern for data extraction service

**Completed**:
- [x] Research existing codebase structure
- [x] Create development plan
- [x] Create work notes

---

### 2025-12-15 - Implementation

**Completed**:
- [x] Created `charting.py` with `ExperimentChartService` and `render_convergence_chart`
- [x] Created 17 unit tests covering data extraction and rendering
- [x] Added `chart` command to CLI with all options
- [x] Updated documentation in `experiment.md`
- [x] All tests passing (63 analysis tests)
- [x] Type check and lint pass

**Implementation Notes**:
- Used `ChartDataPoint` and `ChartData` dataclasses for clean data structures
- Dual-line visualization: accepted (blue, prominent) vs all (gray, dashed)
- Parameter annotations show values above accepted data points
- Costs converted from cents to dollars (INV-1 compliance)
- Error handling: `--parameter` requires `--agent` flag

---

## Key Decisions

### Decision 1: Use matplotlib for rendering
**Rationale**: Already a dependency, produces high-quality plots suitable for publication/research, well-documented.

### Decision 2: Dual-line visualization
**Rationale**: Showing both accepted (convergent) and all (exploratory) policies helps visualize how optimization explored the space before converging.

### Decision 3: Separate service layer
**Rationale**: Following existing pattern (PolicyEvolutionService), keeps CLI thin and logic testable.

---

## Files to Create/Modify

### To Create
- `api/payment_simulator/experiments/analysis/charting.py` - Chart service
- `api/tests/experiments/analysis/test_charting.py` - Unit tests

### To Modify
- `api/payment_simulator/experiments/cli/commands.py` - Add chart command
- `api/payment_simulator/experiments/analysis/__init__.py` - Export new service
- `docs/reference/cli/commands/experiment.md` - Document new command
