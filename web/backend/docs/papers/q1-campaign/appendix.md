# Appendix: Detailed Per-Scenario Data

## Per-Run Results

All experiments were run 3 times (r1, r2, r3) to measure variance. The table below shows all runs.

*Data will be populated from `experiments/2026Q1/paper-data.json` — see `generate_paper_data.py`.*

### 2b_3t (2 banks, 3 types)

| Run | Model | Final Cost | Cumulative SR | Days |
|-----|-------|-----------|---------------|------|
| — | Baseline | 99,900 | 100.0% | 1 |
| r1 | Flash | 13,660 | 96.6% | 10 |
| r1 | Pro | 75,886 | 79.7% | 10 |
| r1 | GLM | 100,909 | 57.1% | 10 |

### 3b_6t (3 banks, 6 types)

| Run | Model | Final Cost | Cumulative SR | Days |
|-----|-------|-----------|---------------|------|
| — | Baseline | 74,700 | 100.0% | 1 |
| r1 | Flash | 18,017 | 99.2% | 10 |
| r1 | Pro | 19,678 | 99.2% | 10 |
| r1 | GLM | 19,631 | 99.2% | 10 |

### 4b_8t (4 banks, 8 types)

| Run | Model | Final Cost | Cumulative SR | Days |
|-----|-------|-----------|---------------|------|
| — | Baseline | 132,800 | 100.0% | 1 |
| r1 | Flash | 59,123 | 99.0% | 10 |
| r1 | Pro | 41,233 | 98.6% | 10 |
| r1 | GLM | 40,178 | 97.9% | 10 |

### Large Network (6+ banks, 25 days)

| Run | Model | Final Cost | Cumulative SR | Days |
|-----|-------|-----------|---------------|------|
| — | Baseline | 182,875,980 | 66.8% | 25 |
| r1 | Flash | 192,578,912 | 63.1% | 25 |
| r1 | Pro | 202,038,573 | 60.9% | 25 |

> GLM excluded for complex scenarios (pre-bugfix data).

### Lehman Month (5+ banks, 25 days)

| Run | Model | Final Cost | Cumulative SR | Days |
|-----|-------|-----------|---------------|------|
| — | Baseline | 199,111,725 | 73.2% | 25 |
| r1 | Flash | 233,402,769 | 66.9% | 25 |
| r1 | Pro | 252,529,888 | 65.6% | 25 |
| r1 | GLM | 246,700,276 | 66.8% | 25 |

## v0.2 Prompt Variants (Castro Exp2)

The castro_exp2 scenario tested 4 prompt engineering variants across all 3 models:

| Variant | Description |
|---------|-------------|
| c1-info | Enhanced information context about the payment system |
| c2-floor | Floor price awareness — minimum cost thresholds |
| c3-guidance | Explicit optimization guidance in the system prompt |
| c4-composition | Compositional strategy building — layered heuristics |

*Full v0.2 variant results to be populated from paper-data.json.*

## Data Processing

Results were extracted using `experiments/2026Q1/generate_paper_data.py`. Raw experiment JSON files are in `experiments/2026Q1/results/`.

### Methodology Notes

- **Cumulative SR** = sum(total_settled) / sum(total_arrivals) across all days
- **Cost delta** = (model_cost - baseline_cost) / baseline_cost × 100%
- **Baselines** run for 1 day (simple) or 25 days (complex) with default policies
- **GLM exclusion**: GLM results for periodic_shocks, large_network, and lehman_month are excluded due to a simulator bug that was present when those experiments ran, compromising the data integrity
