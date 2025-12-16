# SimCash Paper v4 - Handover Prompt

## Context

We are writing a paper to demonstrate how SimCash can reproduce the three experiments from Castro et al. (2025) on reinforcement learning for payment system policy optimization.

**Your task**: Re-run all experiments in three passes using the new project architecture, generate charts, and update the paper with fresh results.

---

## Project Architecture (Updated)

All paper-related files are now consolidated in:

```
docs/papers/simcash-paper/
├── v1/                          # Historical - first attempt
├── v2/                          # Historical - second attempt
├── v3/                          # Current working version
│   ├── configs/                 # Experiment configuration files
│   │   ├── exp1.yaml           # Exp1 experiment config
│   │   ├── exp1_2period.yaml   # Exp1 scenario config
│   │   ├── exp2.yaml           # Exp2 experiment config
│   │   ├── exp2_12period.yaml  # Exp2 scenario config
│   │   ├── exp3.yaml           # Exp3 experiment config
│   │   └── exp3_joint.yaml     # Exp3 scenario config
│   ├── logs/                    # Console output logs
│   │   ├── exp1_run.log
│   │   ├── exp2_run.log
│   │   └── exp3_run.log
│   ├── pass_1/                  # First experiment pass
│   │   └── appendices/
│   │       ├── charts/          # Generated convergence charts
│   │       └── *.json           # Policy evolution exports
│   ├── pass_2/                  # Second experiment pass (reference)
│   │   └── appendices/
│   │       ├── charts/
│   │       └── *.json
│   ├── pass_3/                  # Third experiment pass
│   │   └── appendices/
│   │       ├── charts/
│   │       └── *.json
│   ├── lab-notes.md             # Detailed experiment logs
│   └── draft-paper.md           # The paper document
└── v4/                          # YOUR WORKING DIRECTORY
    ├── configs/                 # Copy configs here
    ├── logs/
    ├── pass_1/appendices/charts/
    ├── pass_2/appendices/charts/
    ├── pass_3/appendices/charts/
    ├── lab-notes.md
    └── draft-paper.md
```

### Key Changes from v3

1. **Consolidated location**: Everything in `docs/papers/simcash-paper/`
2. **Pass separation**: Results from each pass stored in separate directories
3. **Chart generation**: Use CLI `experiment chart` command instead of manual matplotlib
4. **Database per pass**: Each pass stores its database separately

---

## Your Assignment

### Phase 1: Setup

1. **Create v4 directory structure**:
   ```bash
   mkdir -p docs/papers/simcash-paper/v4/{configs,logs}
   mkdir -p docs/papers/simcash-paper/v4/pass_{1,2,3}/appendices/charts
   ```

2. **Copy configs from v3**:
   ```bash
   cp docs/papers/simcash-paper/v3/configs/*.yaml docs/papers/simcash-paper/v4/configs/
   ```

3. **Update config database paths** (in each `exp*.yaml`):
   ```yaml
   output:
     directory: docs/papers/simcash-paper/v4/pass_1  # Change per pass
     database: experiments.db
     verbose: true
   ```

4. **Verify CLI is working**:
   ```bash
   cd api
   .venv/bin/payment-sim experiment --help
   ```

---

### Phase 2: Experiment Execution (Three Passes)

Run each experiment THREE times to assess reproducibility. Each pass uses the same configs but stores results in separate directories.

**NEVER change the LLM model!** Always use `openai:gpt-5.2` as specified in the configs.

#### Pass 1

```bash
cd api

# Update configs to use pass_1 directory first, then run:
.venv/bin/payment-sim experiment run --verbose \
  ../docs/papers/simcash-paper/v4/configs/exp1.yaml \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  2>&1 | tee ../docs/papers/simcash-paper/v4/logs/pass1_exp1.log

.venv/bin/payment-sim experiment run --verbose \
  ../docs/papers/simcash-paper/v4/configs/exp2.yaml \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  2>&1 | tee ../docs/papers/simcash-paper/v4/logs/pass1_exp2.log

.venv/bin/payment-sim experiment run --verbose \
  ../docs/papers/simcash-paper/v4/configs/exp3.yaml \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  2>&1 | tee ../docs/papers/simcash-paper/v4/logs/pass1_exp3.log
```

Repeat for Pass 2 and Pass 3, changing paths accordingly.

---

### Phase 3: Chart Generation

After each pass, generate convergence charts using the CLI:

```bash
cd api

# Get run IDs from the database
.venv/bin/payment-sim experiment results \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db

# Generate charts for each experiment
# Example for exp1 (replace <run-id> with actual run ID):

# Total system cost chart
.venv/bin/payment-sim experiment chart <exp1-run-id> \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  --output ../docs/papers/simcash-paper/v4/pass_1/appendices/charts/exp1_total_cost.png

# Agent-specific charts with parameter annotations
.venv/bin/payment-sim experiment chart <exp1-run-id> \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  --agent BANK_A \
  --parameter initial_liquidity_fraction \
  --output ../docs/papers/simcash-paper/v4/pass_1/appendices/charts/exp1_bank_a_cost.png

.venv/bin/payment-sim experiment chart <exp1-run-id> \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  --agent BANK_B \
  --parameter initial_liquidity_fraction \
  --output ../docs/papers/simcash-paper/v4/pass_1/appendices/charts/exp1_bank_b_cost.png
```

Repeat for exp2, exp3, and for all three passes.

#### Chart Naming Convention

For each experiment and pass, generate THREE charts:
- `exp{N}_total_cost.png` - System total cost convergence
- `exp{N}_bank_a_cost.png` - BANK_A cost with parameter trajectory
- `exp{N}_bank_b_cost.png` - BANK_B cost with parameter trajectory

This gives 9 charts per pass, 27 charts total.

---

### Phase 4: Policy Evolution Export

Export policy evolution JSON for paper appendices:

```bash
cd api

# Export with LLM prompts/responses included
.venv/bin/payment-sim experiment policy-evolution <exp1-run-id> \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  --llm > ../docs/papers/simcash-paper/v4/pass_1/appendices/exp1_policy_evolution.json

# Export for specific agent only
.venv/bin/payment-sim experiment policy-evolution <exp1-run-id> \
  --db ../docs/papers/simcash-paper/v4/pass_1/experiments.db \
  --agent BANK_A \
  --llm > ../docs/papers/simcash-paper/v4/pass_1/appendices/exp1_bank_a_evolution.json
```

---

### Phase 5: Paper Writing

Write the paper in `docs/papers/simcash-paper/v4/draft-paper.md`.

**Required sections** (see v3 handover for detailed requirements):
1. Abstract
2. Introduction
3. LLM Policy Optimization Methodology
4. Bootstrap Evaluation & 3-Agent Sandbox
5. Comparison to Castro et al.
6. Results with confidence intervals
7. Discussion and conclusion
8. Appendices (policy evolution, supplementary charts)

**Chart references in paper**:

Use relative paths from the paper location:

```markdown
**Figure 1: Experiment 1 Convergence (Pass 2)**

![Exp1 Total Cost](pass_2/appendices/charts/exp1_total_cost.png)
*Figure 1a: System total cost convergence*

![Exp1 Bank A Cost](pass_2/appendices/charts/exp1_bank_a_cost.png)
*Figure 1b: BANK_A cost with initial_liquidity_fraction trajectory*
```

**Appendix for all charts**:

Include a section listing all charts across all passes:

```markdown
## Appendix B: Complete Chart Collection

### Pass 1
- `pass_1/appendices/charts/exp1_total_cost.png`
- `pass_1/appendices/charts/exp1_bank_a_cost.png`
- ...

### Pass 2 (Reference)
- `pass_2/appendices/charts/exp1_total_cost.png`
- ...

### Pass 3
- `pass_3/appendices/charts/exp1_total_cost.png`
- ...
```

---

## CLI Reference

### Run Experiments

```bash
# Run with verbose output
payment-sim experiment run --verbose <config.yaml>

# Override database path
payment-sim experiment run --verbose <config.yaml> --db <path/to/db>

# Override LLM model (NOT RECOMMENDED for paper)
payment-sim experiment run --verbose <config.yaml> --model openai:gpt-4o
```

### List Results

```bash
# List all experiment runs in a database
payment-sim experiment results --db <path/to/db>

# Filter by experiment name
payment-sim experiment results --db <path/to/db> --experiment exp1
```

### Generate Charts

```bash
# System total cost chart
payment-sim experiment chart <run-id> --db <path/to/db> --output <output.png>

# Agent-specific with parameter annotations
payment-sim experiment chart <run-id> \
  --db <path/to/db> \
  --agent BANK_A \
  --parameter initial_liquidity_fraction \
  --output <output.png>

# Supported output formats: .png, .pdf, .svg
```

### Export Policy Evolution

```bash
# Full evolution with LLM prompts
payment-sim experiment policy-evolution <run-id> --db <path/to/db> --llm

# Specific agent
payment-sim experiment policy-evolution <run-id> --db <path/to/db> --agent BANK_A

# Iteration range
payment-sim experiment policy-evolution <run-id> --db <path/to/db> --start 1 --end 10
```

### Replay/Audit

```bash
# Standard replay
payment-sim experiment replay <run-id> --db <path/to/db>

# Audit trail for specific iterations
payment-sim experiment replay <run-id> --db <path/to/db> --audit --start 3 --end 5
```

---

## Expected Outcomes

With Castro-compliant configuration, results should match Castro's theoretical predictions:

| Experiment | Castro Prediction | Notes |
|------------|-------------------|-------|
| **Exp1** | A=0%, B=20% | Asymmetric equilibrium |
| **Exp2** | Both 10-30% | Stochastic case |
| **Exp3** | Both ~25% | Symmetric equilibrium |

---

## Key Files Reference

### Must Read
- `experiments/castro/papers/castro_et_al.md` - Castro's theoretical predictions
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Bootstrap evaluation & 3-agent sandbox
- `docs/reference/ai_cash_mgmt/optimizer-prompt.md` - LLM prompt architecture
- `docs/reference/cli/commands/experiment.md` - CLI commands reference

### Configuration Templates
- `docs/papers/simcash-paper/v3/configs/` - Working experiment configs to copy

### Previous Results (for reference)
- `docs/papers/simcash-paper/v3/draft-paper.md` - v3 paper for structure reference
- `docs/papers/simcash-paper/v3/lab-notes.md` - v3 experiment logs

---

## Checklist

### Setup
- [ ] v4 directory structure created
- [ ] Configs copied and database paths updated
- [ ] CLI working (`payment-sim experiment --help`)

### Experiment Execution
- [ ] Pass 1: exp1, exp2, exp3 completed
- [ ] Pass 2: exp1, exp2, exp3 completed
- [ ] Pass 3: exp1, exp2, exp3 completed
- [ ] All logs saved to `logs/` directory

### Chart Generation
- [ ] Pass 1: 9 charts generated (3 experiments x 3 chart types)
- [ ] Pass 2: 9 charts generated
- [ ] Pass 3: 9 charts generated
- [ ] Charts use correct naming convention

### Policy Evolution Export
- [ ] Pass 1: 3 JSON files exported
- [ ] Pass 2: 3 JSON files exported
- [ ] Pass 3: 3 JSON files exported

### Paper Writing
- [ ] Results match Castro predictions (within tolerance)
- [ ] All required sections complete
- [ ] Charts embedded with correct paths
- [ ] Appendix includes all chart locations
- [ ] Cross-pass reproducibility documented

---

## Output Location

All work goes in: `docs/papers/simcash-paper/v4/`

---

*Last updated: 2025-12-16*
