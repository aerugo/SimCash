# Plan: Update Paper After Exp2 Reruns and Convergence Criteria Changes

## Context

Since the last paper update, several significant changes have been made:

1. **New Bootstrap Convergence Criteria** (commit 9608527): Bootstrap mode now uses `BootstrapConvergenceDetector` with three criteria that ALL must be satisfied:
   - **CV Criterion**: Coefficient of variation < 3% (stability)
   - **Trend Criterion**: Mann-Kendall test p > 0.05 (no significant trend)
   - **Regret Criterion**: Current cost within 10% of best observed

2. **New Exp2 Data** (commit 1769400): All exp2 runs have been replaced with fresh runs using the new convergence criteria.

3. **Chart Style Changes** (commits 98b6d8e, 784d95f): Bootstrap variance charts now use GP-style visualization:
   - Blue mean prediction line with straight lines (not interpolated)
   - Shaded 95% confidence interval band (light blue)
   - Red scatter points for observed data

4. **Bootstrap Appendix Removed** (commit bae66ab): The Bootstrap Evaluation Statistics appendix (Section E) was removed from the paper generator.

---

## Current Issues Identified

### 1. Stale paper.tex Output
The `output/paper.tex` file still contains:
- Bootstrap Evaluation Statistics appendix section (should be removed)
- References to `ci_width.png`, `variance_evolution.png`, `sample_distribution.png` charts

### 2. Methods Section Outdated
`src/sections/methods.py` line 83-84 describes the old convergence criterion:
```
\item \textbf{Convergence criterion}: Cost improvement plateau with coefficient of variation below 5\%
```
Should be updated to describe the new three-criteria approach.

### 3. Empty Variance Charts
- `exp2_pass1_variance_evolution.png` - appears empty
- `exp2_pass3_variance_evolution.png` - appears empty

These may have insufficient data or the chart generator isn't finding the right data.

### 4. Config Run ID Mapping
The `config.yaml` shows all experiments using identical run_ids from exp3 database - need to verify this is intentional or update with correct exp2 run_ids.

---

## Update Tasks

### Task 1: Update Methods Section - Convergence Criteria

**File**: `src/sections/methods.py`

**Changes needed**:
- Update Bootstrap Mode section (lines 74-84) to describe the new three-criteria convergence:
  - CV criterion (< 3%)
  - Mann-Kendall trend criterion (p > 0.05)
  - Regret criterion (< 10% from best)

**Before**:
```latex
\item \textbf{Convergence criterion}: Cost improvement plateau with coefficient of variation below 5\%
```

**After** (proposed):
```latex
\item \textbf{Convergence criterion}: Three criteria must ALL be satisfied:
    \begin{enumerate}
        \item CV below 3\% over last 5 iterations (stability)
        \item Mann-Kendall p-value $>$ 0.05 (no significant trend)
        \item Regret below 10\% (current cost within 10\% of best observed)
    \end{enumerate}
```

### Task 2: Regenerate Paper

Run the paper generator to:
1. Remove stale Bootstrap Evaluation Statistics appendix
2. Update all data-driven values from new exp2 results
3. Regenerate all charts with current data

**Command**:
```bash
cd docs/papers/simcash-paper/paper_generator
python -m src.cli build --config config.yaml
```

### Task 3: Verify Exp2 Results Data

Query the exp2 database to extract key metrics for the paper:
- Convergence iterations for each pass
- Final costs and liquidity fractions
- Bootstrap statistics (mean, std dev, CI)

These should reflect the new convergence criteria behavior.

### Task 4: Review Chart Output

After regeneration, review:
1. Combined convergence charts show expected learning curves
2. Variance charts (if still generated) have data or remove references
3. Bootstrap variance charts use GP-style (blue line, red dots, shaded CI)

### Task 5: Update Results Section (if needed)

Based on new exp2 data, may need to update:
- Convergence iteration counts
- Cost values in text
- Interpretation of results

---

## Verification Steps

1. **Compile paper.pdf**: Run `pdflatex paper.tex` and verify no missing figure errors
2. **Spot-check values**: Verify a few data-driven values in paper match database
3. **Visual review**: Check convergence charts show expected behavior
4. **Diff review**: Compare new paper.tex with previous version for unexpected changes

---

## Timeline Estimate

- Task 1: Update methods.py convergence description - straightforward edit
- Task 2: Regenerate paper - run build command
- Task 3: Verify exp2 data - query database, review output
- Task 4: Review charts - visual inspection
- Task 5: Update results section - may require iteration

---

## Notes

- The config.yaml run_id mapping issue should be investigated - all experiments showing same run_ids from exp3 database is suspicious
- If variance_evolution charts remain empty, consider removing references from paper or investigating data source
