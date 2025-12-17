# Programmatic Paper Generation - Work Notes

**Project**: SimCash paper v5 - Programmatic LaTeX generation
**Started**: 2025-12-17
**Branch**: `claude/tree-experiments-charts-hxsAh`

---

## Session Log

### 2025-12-17 - Initial Planning

**Context Review Completed**:
- Read `.claude/agents/python-stylist.md` - identified Protocol pattern, TypedDict usage, composition over inheritance
- Read `docs/plans/CLAUDE.md` - understood plan structure requirements
- Analyzed v4 paper issues - identified Exp2 cost table duplication bug

**Applicable Patterns**:
- Protocol-based DataProvider for testable data access
- TypedDicts for query result shapes
- Composition for section ordering

**Key Insights**:
- Exp2 Appendix C bug: script likely used wrong column or aggregated incorrectly
- All paper values must flow from single database queries
- Chart generation can reuse existing CLI tools

**Completed**:
- [x] Created v5 directory structure
- [x] Copied databases from `api/results/` to `v5/data/`
- [x] Copied config files from v4 to `v5/configs/`
- [x] Created development plan

**Next Steps**:
1. Create Phase 1 detailed plan
2. Define DataProvider protocol and TypedDicts
3. Implement DatabaseDataProvider
4. Write tests verifying query accuracy

---

## Phase Progress

### Phase 1: Data Provider
**Status**: Complete
**Started**: 2025-12-17
**Completed**: 2025-12-17

#### Results
- Created `src/data_provider.py` with TypedDicts and DatabaseDataProvider
- 29 tests passing including Exp2 bug fix verification
- mypy and ruff pass with no issues

#### Key Findings
- Exp2 agents correctly return DIFFERENT costs (bug fix verified)
- Database values differ from v4 paper (may need to regenerate experiments or paper was reporting incorrectly)

---

## Key Decisions

### Decision 1: Raw LaTeX over pylatex
**Rationale**: Maximum control over output, easier debugging, fewer dependencies. LaTeX is already a well-defined DSL; wrapping it in Python objects adds complexity without benefit.

### Decision 2: Sections as functions, not classes
**Rationale**: Simpler composition—just call functions in order. No need for inheritance hierarchy. Functions are easier to test and reorder.

### Decision 3: DataProvider as Protocol
**Rationale**: Enables testing with mock data, swapping implementations (e.g., from DB to cached results), and clear interface documentation.

### Decision 4: Charts via CLI subprocess
**Rationale**: Reuse existing chart generation code in `payment-sim`. Avoid duplicating matplotlib logic. CLI already handles all edge cases.

---

## Issues Encountered

*None yet*

---

## Files Modified

### Created
- `docs/plans/simcash-paper/development-plan.md` - Main development plan
- `docs/plans/simcash-paper/work_notes.md` - This file
- `docs/papers/simcash-paper/v5/` - Output directory structure
- `docs/papers/simcash-paper/v5/data/` - Experiment databases
- `docs/papers/simcash-paper/v5/configs/` - Experiment configs

### Modified
*None yet*

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] Add INV-N: Paper Generation Identity (values must come from queries)

### Other Documentation
- [ ] `docs/papers/simcash-paper/README.md` - Add v5 build instructions
