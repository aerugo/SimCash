# SimCash Paper v5 - Handover Prompt

## Context

We are writing a paper to demonstrate how SimCash can reproduce the three experiments from Castro et al. (2025) on reinforcement learning for payment system policy optimization.

**Your task**: Re-run all experiments in three passes, then use the **paper_generator** to automatically generate charts, tables, and the complete LaTeX paper from the experiment databases.

---

## Key Change from v4: Automated Paper Generation

**v5 uses a programmatic paper generation system** located at:

```
docs/papers/simcash-paper/paper_generator/
```

This eliminates manual work that was required in v4:
- ✅ **Charts**: Automatically generated from database queries
- ✅ **Tables**: Automatically generated with correct values
- ✅ **Results text**: Data-driven, no manual transcription
- ✅ **Confidence intervals**: Computed and formatted automatically
- ✅ **LaTeX compilation**: Single command generates PDF

**What you DO manually**:
- Run the 3 passes of experiments
- Update `config.yaml` with new run_ids
- Analyze the generated paper and update section **source code** (NOT output!)
- Regenerate and verify

---

## Project Architecture

```
docs/papers/simcash-paper/paper_generator/
├── config.yaml              # ← REQUIRED: Maps passes to run_ids
├── configs/                 # Experiment configuration files
│   ├── exp1.yaml           # Exp1 experiment config
│   ├── exp1_2period.yaml   # Exp1 scenario config
│   ├── exp2.yaml           # Exp2 experiment config
│   ├── exp2_12period.yaml  # Exp2 scenario config
│   ├── exp3.yaml           # Exp3 experiment config
│   └── exp3_joint.yaml     # Exp3 scenario config
├── data/                    # Experiment databases (after running experiments)
│   ├── exp1.db             # All exp1 passes stored here
│   ├── exp2.db             # All exp2 passes stored here
│   └── exp3.db             # All exp3 passes stored here
├── output/                  # Generated output (READ ONLY)
│   ├── paper.tex           # ← READ THIS to see actual paper
│   ├── paper.pdf           # Compiled PDF
│   └── charts/             # Generated PNG charts
├── src/                     # Source code (EDIT THIS to change paper)
│   ├── sections/           # Section generators
│   │   ├── abstract.py
│   │   ├── introduction.py
│   │   ├── methods.py
│   │   ├── results.py      # ← Main results analysis
│   │   ├── discussion.py   # ← Interpretation of results
│   │   └── conclusion.py
│   ├── latex/              # LaTeX formatting helpers
│   └── charts/             # Chart generation code
└── generate_paper.sh       # Quick-start script
```

---

## Your Assignment

### Phase 1: Run Experiments (Three Passes)

Run each experiment THREE times to assess reproducibility. All passes for an experiment go into the same database file.

**NEVER change the LLM model!** Always use `openai:gpt-5.2` as specified in the configs.

```bash
cd api

# Pass 1
.venv/bin/payment-sim experiment run --verbose \
  ../docs/papers/simcash-paper/paper_generator/configs/exp1.yaml \
  --db ../docs/papers/simcash-paper/paper_generator/data/exp1.db \
  2>&1 | tee ../docs/papers/simcash-paper/paper_generator/logs/pass1_exp1.log

.venv/bin/payment-sim experiment run --verbose \
  ../docs/papers/simcash-paper/paper_generator/configs/exp2.yaml \
  --db ../docs/papers/simcash-paper/paper_generator/data/exp2.db \
  2>&1 | tee ../docs/papers/simcash-paper/paper_generator/logs/pass1_exp2.log

.venv/bin/payment-sim experiment run --verbose \
  ../docs/papers/simcash-paper/paper_generator/configs/exp3.yaml \
  --db ../docs/papers/simcash-paper/paper_generator/data/exp3.db \
  2>&1 | tee ../docs/papers/simcash-paper/paper_generator/logs/pass1_exp3.log

# Pass 2 - same commands, results accumulate in same DBs

# Pass 3 - same commands, results accumulate in same DBs
```

**After each experiment run**, note the run_id printed in the output (format: `exp1-YYYYMMDD-HHMMSS-XXXXXX`).

---

### Phase 2: Update config.yaml

After all experiments complete, update `config.yaml` with the new run_ids:

```yaml
# docs/papers/simcash-paper/paper_generator/config.yaml

databases:
  exp1: data/exp1.db
  exp2: data/exp2.db
  exp3: data/exp3.db

experiments:
  exp1:
    name: "2-Period Deterministic Nash Equilibrium"
    passes:
      1: "exp1-YYYYMMDD-HHMMSS-XXXXXX"  # Replace with actual run_id from Pass 1
      2: "exp1-YYYYMMDD-HHMMSS-XXXXXX"  # Replace with actual run_id from Pass 2
      3: "exp1-YYYYMMDD-HHMMSS-XXXXXX"  # Replace with actual run_id from Pass 3

  exp2:
    name: "12-Period Stochastic LVTS-Style"
    passes:
      1: "exp2-YYYYMMDD-HHMMSS-XXXXXX"
      2: "exp2-YYYYMMDD-HHMMSS-XXXXXX"
      3: "exp2-YYYYMMDD-HHMMSS-XXXXXX"

  exp3:
    name: "3-Period Symmetric Joint Liquidity"
    passes:
      1: "exp3-YYYYMMDD-HHMMSS-XXXXXX"
      2: "exp3-YYYYMMDD-HHMMSS-XXXXXX"
      3: "exp3-YYYYMMDD-HHMMSS-XXXXXX"

output:
  paper_filename: paper.tex
  charts_dir: charts
```

**To find run_ids** if you forgot to note them:

```bash
cd api
.venv/bin/payment-sim experiment results \
  --db ../docs/papers/simcash-paper/paper_generator/data/exp1.db
```

---

### Phase 3: Generate the Paper

```bash
cd docs/papers/simcash-paper/paper_generator

# Option 1: Use the helper script (recommended)
./generate_paper.sh

# Option 2: Run directly with uv
uv run python -m src.cli --config config.yaml --output-dir output/

# Option 3: Generate .tex only (faster, no PDF compilation)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf
```

This generates:
- `output/paper.tex` - Complete LaTeX document
- `output/paper.pdf` - Compiled PDF (if pdflatex available)
- `output/charts/*.png` - All convergence charts

---

### Phase 4: Analyze Results and Update Paper

**CRITICAL WORKFLOW**: Read output → Edit source → Regenerate

#### Step 1: Read the Generated Paper

```bash
# Read the compiled paper to see actual values
cat docs/papers/simcash-paper/paper_generator/output/paper.tex
```

Look at:
- Tables with experiment results
- Charts showing convergence
- Current narrative text
- Whether results match Castro predictions

#### Step 2: Edit Source Code (NOT output/paper.tex!)

If the narrative needs updating to discuss results, edit the **source files**:

| What to Change | File to Edit |
|----------------|--------------|
| Abstract summary | `src/sections/abstract.py` |
| Results discussion | `src/sections/results.py` |
| Analysis/interpretation | `src/sections/discussion.py` |
| Conclusion | `src/sections/conclusion.py` |
| Table formatting | `src/latex/tables.py` |
| Chart styling | `src/charts/generators.py` |

**NEVER edit `output/paper.tex` directly** - it gets overwritten on every generation!

#### Step 3: Regenerate and Verify

```bash
cd docs/papers/simcash-paper/paper_generator
./generate_paper.sh
```

Then read `output/paper.tex` again to verify your changes appear correctly.

---

### Phase 5: Final Verification Checklist

Before finalizing, verify:

1. **Results match Castro predictions**:
   | Experiment | Castro Prediction | Check |
   |------------|-------------------|-------|
   | Exp1 | A=0%, B=20% (asymmetric equilibrium) | |
   | Exp2 | Both 10-30% (stochastic case) | |
   | Exp3 | Both ~25% (symmetric equilibrium) | |

2. **Cross-pass reproducibility**: Results consistent across all 3 passes

3. **Narrative consistency**: Text in abstract, results, and discussion matches the actual data shown in tables and charts

4. **Charts are readable**: Convergence patterns visible, axes labeled correctly

---

## CLI Reference

### Run Experiments

```bash
# Run with verbose output
payment-sim experiment run --verbose <config.yaml>

# Override database path
payment-sim experiment run --verbose <config.yaml> --db <path/to/db>
```

### List Results

```bash
# List all experiment runs in a database
payment-sim experiment results --db <path/to/db>

# Filter by experiment name
payment-sim experiment results --db <path/to/db> --experiment exp1
```

### Generate Paper

```bash
cd docs/papers/simcash-paper/paper_generator

# Full generation (charts + PDF)
uv run python -m src.cli --config config.yaml --output-dir output/

# Skip chart regeneration (faster if charts unchanged)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-charts

# Skip PDF compilation (LaTeX only)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf
```

---

## Expected Outcomes

With Castro-compliant configuration, results should match Castro's theoretical predictions:

| Experiment | Castro Prediction | Notes |
|------------|-------------------|-------|
| **Exp1** | A=0%, B=20% | Asymmetric equilibrium (free-rider emerges) |
| **Exp2** | Both 10-30% | Stochastic case with uncertainty |
| **Exp3** | Both ~25% | Symmetric equilibrium |

---

## Key Files Reference

### Paper Generator Documentation
- `docs/papers/simcash-paper/paper_generator/README.md` - Setup and usage
- `docs/papers/simcash-paper/paper_generator/CLAUDE.md` - AI workflow guide

### Castro Reference
- `experiments/castro/papers/castro_et_al.md` - Castro's theoretical predictions

### Evaluation Methodology
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Bootstrap evaluation
- `docs/reference/ai_cash_mgmt/optimizer-prompt.md` - LLM prompt architecture

---

## Troubleshooting

### "Config validation failed: run_id not found"

The run_id in `config.yaml` doesn't exist in the database. Check:
```bash
payment-sim experiment results --db data/exp1.db
```

### "pdflatex not found"

Install LaTeX or skip PDF compilation:
```bash
# Skip PDF (generate .tex only)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf
```

### Charts not updating

Force chart regeneration by NOT using `--skip-charts`:
```bash
uv run python -m src.cli --config config.yaml --output-dir output/
```

### Paper text doesn't match data

You may have edited `output/paper.tex` directly. Edits must go in `src/sections/*.py`. Regenerate to apply.

---

## Checklist

### Experiment Execution
- [ ] Pass 1: exp1, exp2, exp3 completed
- [ ] Pass 2: exp1, exp2, exp3 completed
- [ ] Pass 3: exp1, exp2, exp3 completed
- [ ] All run_ids noted/recorded

### Configuration
- [ ] `config.yaml` updated with all 9 run_ids (3 experiments × 3 passes)
- [ ] Config validation passes (no errors on generation)

### Paper Generation
- [ ] Paper generated successfully
- [ ] Charts generated in `output/charts/`
- [ ] PDF compiled (or LaTeX reviewed if no pdflatex)

### Analysis
- [ ] Read `output/paper.tex` to understand current state
- [ ] Results match Castro predictions (within tolerance)
- [ ] Narrative in abstract/results/discussion matches data
- [ ] Cross-pass reproducibility confirmed

### Final Edits (if needed)
- [ ] Edits made in `src/sections/*.py` (NOT output/paper.tex)
- [ ] Paper regenerated after edits
- [ ] Final paper.tex reviewed for consistency

---

## Output Location

All work goes in: `docs/papers/simcash-paper/paper_generator/`

- Databases: `data/*.db`
- Generated paper: `output/paper.tex`, `output/paper.pdf`
- Generated charts: `output/charts/`

---

*Last updated: 2025-12-18 (v5 with paper_generator workflow)*
