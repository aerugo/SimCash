# SimCash Paper Research Plan

## Objective

Write a draft paper demonstrating how SimCash (an LLM-based payment system simulator) reproduces the three key experiments from Castro et al. (2025) "Estimating Policy Functions in Payment Systems Using Reinforcement Learning".

## Background

Castro et al. (2025) used reinforcement learning (RL) to approximate policy functions for banks in high-value payment systems. Their key experiments were:

1. **Experiment 1**: 2-Period Deterministic Nash Equilibrium
   - Analytical solution exists
   - Expected: Bank A posts 0%, Bank B posts ~20%

2. **Experiment 2**: 12-Period Stochastic LVTS-Style
   - Realistic scenario with stochastic arrivals
   - Both agents learn to reduce initial liquidity
   - Agent with lower demand converges to lower liquidity

3. **Experiment 3**: Three-Period Dummy Example (Joint Learning)
   - Symmetric payments: P^A = P^B = [0.2, 0.2, 0]
   - Expected: ~25% initial liquidity when r_c < r_d

## Research Questions

1. Can LLM-based optimization replicate RL-discovered equilibria?
2. How does LLM convergence compare to RL training (iterations vs episodes)?
3. What advantages does LLM optimization offer over RL (interpretability, convergence speed)?

## Methodology

### Phase 1: Experiment Setup & Validation (Current)
- [x] Read and understand Castro et al. paper
- [x] Review previous alignment work (exp2_work_notes, exp3_work_notes)
- [x] Understand SimCash architecture and cost model
- [ ] Run all three experiments
- [ ] Verify convergence and results

### Phase 2: Data Collection & Analysis
- [ ] Collect iteration-by-iteration policy changes
- [ ] Extract cost trajectories for each experiment
- [ ] Compare final policies to paper predictions
- [ ] Use replay --audit to understand LLM reasoning

### Phase 3: Paper Writing
- [ ] Draft introduction and motivation
- [ ] Document methodology (SimCash architecture)
- [ ] Present results with tables and charts
- [ ] Discuss comparison to Castro et al.
- [ ] Conclude with implications

## Experiment Configuration Summary

| Experiment | Periods | Mode | Expected Outcome |
|------------|---------|------|------------------|
| exp1 | 2 | deterministic | A: 0%, B: 20% |
| exp2 | 12 | bootstrap (10 samples) | Both reduce from 50%, A < B |
| exp3 | 3 | deterministic | Both ~25% |

## Key SimCash Concepts for Paper

### Architecture
- Rust simulation core + Python orchestration layer
- LLM (OpenAI gpt-5.2) for policy optimization
- Bootstrap paired evaluation for policy acceptance

### Cost Model (Castro-aligned)
- r_c: collateral cost (initial liquidity)
- r_d: delay cost (per tick)
- r_b: end-of-day borrowing cost
- Required: r_c < r_d < r_b

### Policy Representation
- JSON decision trees
- `initial_liquidity_fraction` parameter (0.0 to 1.0)
- Payment timing decisions (Release/Hold)

## Expected Deliverables

1. **Lab Notes**: Detailed experiment logs in `lab-notes.md`
2. **Results Data**: JSON/CSV exports from experiment databases
3. **Visualizations**: Charts showing convergence trajectories
4. **Draft Paper**: Complete draft for collaborator review

## Timeline (Phases, not dates)

1. **Phase 1**: Run experiments, validate results
2. **Phase 2**: Extract data, create visualizations
3. **Phase 3**: Write draft paper sections
4. **Phase 4**: Review and refine

## Notes

- All experiments use OpenAI gpt-5.2 with reasoning_effort=high
- Bootstrap evaluation uses 10 samples for stochastic scenarios
- Deterministic mode for fixed-schedule experiments
