# Castro Experiment Handover Note

**Date**: 2025-12-03
**Prepared by**: Claude (AI Research Assistant)
**Status**: Ready for LLM optimization experiments

---

## Summary

The Castro et al. (2025) replication experiments have been restructured to align with the paper's payment system model. Two critical features (`deferred_crediting` and `deadline_cap_at_eod`) were implemented in SimCash and the experiment configurations have been updated to use them.

**Previous experiments have been archived** because they used immediate crediting and multi-day deadlines, which created fundamentally different equilibrium dynamics than Castro's model.

---

## Research Context

### The Castro Paper (2025)

Castro et al. demonstrated that reinforcement learning (RL) can discover near-optimal policies for banks in high-value payment systems (HVPS). Banks face a **liquidity-delay tradeoff**:

- **Post more collateral** → Higher opportunity cost, but payments settle immediately
- **Post less collateral** → Lower cost, but payments may be delayed or fail at EOD

The paper shows that in a **2-period game** with known payments, there exists a **Nash equilibrium** where banks optimally balance these costs.

### Our Research Hypothesis

**Primary Hypothesis**: Large Language Models (LLMs) can discover near-optimal payment system policies through iterative refinement, with:
1. **Greater sample efficiency** than RL (~10 iterations vs ~100 episodes)
2. **Interpretable policies** (decision trees vs opaque neural networks)
3. **Novel policy mechanisms** through explicit reasoning

**Secondary Hypotheses**:
- H1: LLM will discover the asymmetric Nash equilibrium in the 2-period scenario
- H2: LLM will achieve comparable cost reduction to RL in the 12-period scenario
- H3: LLM can jointly optimize liquidity AND payment timing (3-period scenario)

### Why This Matters

1. **Regulatory Compliance**: Interpretable policies can be audited by regulators
2. **Sample Efficiency**: Fewer simulations needed = lower computational cost
3. **Novel Mechanisms**: LLMs may discover policy features that RL misses
4. **Central Bank Design**: Insights for designing payment system rules

---

## Experiment Protocol

### Pre-Experiment Checklist

Before running ANY experiment, verify the following:

#### Environment Setup
- [ ] Python environment activated: `cd experiments/castro && source .venv/bin/activate`
- [ ] Dependencies installed: `uv sync --extra dev`
- [ ] Payment-simulator built: The above command builds the Rust backend

#### API Configuration
- [ ] OpenAI API key set: `export OPENAI_API_KEY="your-key-here"`
- [ ] Verify API access: Run a simple API test to confirm connectivity
- [ ] Check API quota: Ensure sufficient tokens for experiment (~500k tokens per full run)

#### Configuration Validation
- [ ] Verify `deferred_crediting: true` in config file
- [ ] Verify `deadline_cap_at_eod: true` in config file
- [ ] Verify cost rates match Castro paper (see Cost Parameters section below)
- [ ] Verify `max_collateral_capacity` is set appropriately

#### Baseline Verification
- [ ] Run seed policy once to verify config works
- [ ] Check that 100% settlement is achievable (or document why not)
- [ ] Record baseline costs in lab notes

---

## Experiment 1: Two-Period Nash Equilibrium Validation

### Scientific Objective

Validate that the LLM can discover the **asymmetric Nash equilibrium** predicted by Castro et al. for a deterministic 2-period payment game.

### Theoretical Background

In the 2-period game with payment profile:
- **Bank A**: P^A = [0, $150] (no period-1 outgoing, $150 in period 2)
- **Bank B**: P^B = [$150, $50] ($150 in period 1, $50 in period 2)

The Nash equilibrium under **deferred crediting** is:
- **Bank A**: ℓ₀ = $0 (post no collateral; wait for B's payment to fund outgoing)
- **Bank B**: ℓ₀ = $200 (post enough to cover both periods)

**Why asymmetric?** Bank B must pay $150 in period 1. With deferred crediting, Bank A cannot use this payment until period 2 - but that's exactly when A needs it. So A can free-ride on B's liquidity.

### Cost Parameters (Castro Standard)

| Parameter | Value | Derivation |
|-----------|-------|------------|
| Collateral cost (r_c) | 500 bps/tick | 10%/day ÷ 2 ticks = 5%/tick |
| Delay cost (r_d) | 0.001/cent/tick | 20%/day ÷ 2 ticks |
| Overdraft cost (r_b) | 2000 bps/tick | 40%/day ÷ 2 ticks = 20%/tick |

### Protocol

#### Step 1: Baseline Run
```bash
cd experiments/castro
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp1 \
    --max-iter 1 \
    --output results/exp1_baseline.db
```

**Record in lab notes**:
- Baseline cost (Bank A, Bank B, Total)
- Settlement rate (should be 100%)
- Seed policy parameters used

#### Step 2: Full Optimization Run
```bash
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp1 \
    --max-iter 20 \
    --output results/exp1_full.db
```

**During run, monitor for**:
- Cost reduction trend (should decrease monotonically)
- Convergence (< 1% improvement for 3 consecutive iterations)
- LLM reasoning quality (coherent explanations of changes)

#### Step 3: Validation Checks

After completion, verify the following:

**Quantitative Validation**:
- [ ] Total cost reduced by > 80% from baseline
- [ ] Settlement rate = 100%
- [ ] Convergence achieved (not hitting max iterations)

**Qualitative Validation (Nash Equilibrium)**:
- [ ] Bank A's initial_liquidity_fraction → 0 (or near-zero)
- [ ] Bank B's initial_liquidity_fraction ≈ 0.2 (20% of capacity = $200)
- [ ] Equilibrium is **asymmetric** (A ≠ B policies)

**If symmetric equilibrium found instead**:
This suggests deferred crediting may not be working correctly. Verify:
1. Check for `DeferredCreditsApplied` events in verbose output
2. Confirm Bank A cannot use B's payment in same tick it's received

#### Step 4: Documentation
- Export final policies to `results/exp1_final_policies.json`
- Update `LAB_NOTES.md` with:
  - Iterations to convergence
  - Final costs (per-bank and total)
  - Whether asymmetric equilibrium was discovered
  - Any unexpected behaviors or observations

### Success Criteria

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Cost reduction | > 80% | Seed policy is deliberately suboptimal |
| Settlement rate | = 100% | Deterministic scenario must settle all |
| Asymmetric equilibrium | A ≈ 0, B ≈ 0.2 | Castro's analytical prediction |
| Convergence | < 15 iterations | LLM sample efficiency hypothesis |

---

## Experiment 2: Twelve-Period Stochastic Environment

### Scientific Objective

Test whether the LLM can handle **stochastic payment arrivals** with realistic LVTS-style profiles.

### Theoretical Background

Real payment systems have:
- **Stochastic arrivals**: Payments arrive randomly throughout the day
- **Volume patterns**: Peak periods (morning, end-of-day) and quiet periods
- **Asymmetric profiles**: Banks have different payment patterns

Castro et al. showed RL converges in ~50-100 episodes for this scenario. We hypothesize LLM can match this with ~20-30 iterations.

### Key Differences from Experiment 1

| Aspect | Exp 1 | Exp 2 |
|--------|-------|-------|
| Periods | 2 | 12 |
| Arrivals | Deterministic | Stochastic (Poisson) |
| Profile | Fixed | LVTS-style distribution |
| Solution | Analytical | Numerical only |

### Protocol

#### Step 1: Multi-Seed Baseline
```bash
cd experiments/castro
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp2 \
    --max-iter 1 \
    --seeds 10 \
    --output results/exp2_baseline.db
```

**Record in lab notes**:
- Mean cost ± standard deviation across seeds
- Settlement rate (may be < 100%)
- Per-seed breakdown (identifies high-variance scenarios)

#### Step 2: Full Optimization Run
```bash
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp2 \
    --max-iter 30 \
    --seeds 10 \
    --output results/exp2_full.db
```

**Critical Monitoring**:
- **Variance tracking**: High std dev may indicate overfitting to specific seeds
- **Settlement rate**: Must maintain > 95% settlement
- **Cost stability**: Watch for oscillation (sign of unstable policy)

#### Step 3: Variance Analysis

After completion, analyze:

```sql
-- Query experiment database for per-seed variance
SELECT iteration_number,
       AVG(total_cost) as mean_cost,
       STDDEV(total_cost) as std_cost,
       MIN(total_cost) as min_cost,
       MAX(total_cost) as max_cost
FROM simulation_runs
GROUP BY iteration_number
ORDER BY iteration_number;
```

**Key Questions**:
- Does variance decrease with iteration? (desirable)
- Are there outlier seeds with very high costs? (may need investigation)
- Is the LLM optimizing for mean or worst-case?

#### Step 4: Comparison to RL

Document comparison to Castro's RL results:

| Metric | Castro RL | Our LLM | Notes |
|--------|-----------|---------|-------|
| Iterations to converge | 50-100 | ? | Sample efficiency |
| Final cost (normalized) | X | ? | Quality of solution |
| Settlement rate | ~100% | ? | Must maintain |
| Variance | ? | ? | Stability |

### Success Criteria

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Cost reduction | > 30% | Stochastic is harder than deterministic |
| Settlement rate | > 95% | Allow some EOD failures |
| Convergence | < 30 iterations | Match or beat RL |
| Variance reduction | Decreasing std | Indicates robust policy |

### Known Challenges

From previous experiments, Experiment 2 is the **most difficult**:

1. **High variance**: Stochastic arrivals create seed-dependent outcomes
2. **EOD cliff**: Binary settle/fail creates discontinuous cost landscape
3. **Policy expressiveness**: DSL may lack needed constructs (e.g., forecasting)

**If cost increases during optimization**:
- This indicates the LLM is struggling with variance-mean tradeoffs
- Consider: Present variance information explicitly to LLM
- Consider: Use mean-variance objective instead of pure mean

---

## Experiment 3: Joint Learning (Liquidity + Timing)

### Scientific Objective

Test whether the LLM can **jointly optimize** both:
1. Initial liquidity allocation (how much to post)
2. Payment timing (when to release vs hold)

### Theoretical Background

Castro et al. (Section 7) showed that in a 3-period scenario with symmetric payments, agents can learn to:
- Delay payments strategically to recycle liquidity
- Post minimal initial collateral when payment flows offset

The **theoretical optimum** for symmetric flows is near-zero cost: both banks can settle using each other's payments with minimal additional liquidity.

### Payment Profile

For both banks:
```
P = [$200, $200, $0]
```

Period 1: Both banks owe $200 to each other
Period 2: Both banks owe $200 to each other
Period 3: No payments (settlement period)

With symmetric flows, payments naturally offset → minimal liquidity needed.

### Protocol

#### Step 1: Baseline with Default Timing
```bash
cd experiments/castro
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp3 \
    --max-iter 1 \
    --output results/exp3_baseline.db
```

**Record**:
- Baseline cost (should be moderate due to unnecessary collateral)
- Payment timing pattern (default policy likely releases immediately)

#### Step 2: Full Joint Optimization
```bash
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp3 \
    --max-iter 25 \
    --output results/exp3_full.db
```

**Monitor for**:
- **Cost approaching zero**: Theoretical optimum for symmetric flows
- **Payment timing changes**: LLM should learn to hold → release strategically
- **Collateral reduction**: Initial liquidity fraction should decrease

#### Step 3: Mechanism Analysis

After completion, analyze the **discovered mechanisms**:

**Liquidity Strategy**:
- What initial_liquidity_fraction was learned?
- Is it near-zero (optimal for symmetric flows)?

**Timing Strategy**:
- Does the policy hold payments strategically?
- Is there a "wait for incoming" pattern?
- Any novel mechanisms (partial release, time-varying buffers)?

#### Step 4: Document Novel Discoveries

The LLM may invent policy features not in the seed policy. Look for:

| Mechanism | Description | Rationale |
|-----------|-------------|-----------|
| Time-varying buffer | Different thresholds early vs late in day | Adapt to time-of-day liquidity patterns |
| Partial release | Accept partially-funded payments | Reduce delay costs near deadline |
| Counterparty awareness | Different logic per counterparty | Exploit payment flow asymmetries |

### Success Criteria

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Cost reduction | > 95% | Symmetric flows = near-zero optimal |
| Settlement rate | = 100% | Must settle all |
| Near-zero liquidity | fraction < 0.05 | Relies on payment recycling |
| Novel mechanisms | ≥ 1 discovered | LLM creativity hypothesis |

---

## Data Collection Protocol

### Per-Iteration Data

For each optimization iteration, record:

```json
{
  "iteration": 1,
  "timestamp": "2025-12-03T10:00:00Z",
  "policy_hash": "sha256:...",
  "seeds_used": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "results": {
    "mean_cost": 1080.00,
    "std_cost": 0.00,
    "min_cost": 1080.00,
    "max_cost": 1080.00,
    "settlement_rate": 1.0,
    "per_bank": {
      "BANK_A": {"cost": 540.00, "settlement_rate": 1.0},
      "BANK_B": {"cost": 540.00, "settlement_rate": 1.0}
    }
  },
  "llm_reasoning": "Bank A is posting too much collateral...",
  "policy_changes": ["Reduced initial_liquidity_fraction from 0.5 to 0.25"]
}
```

### Per-Experiment Summary

At experiment completion, produce:

1. **Cost Progression Chart**: X=iteration, Y=mean cost (with error bars)
2. **Policy Evolution Table**: Key parameters at each iteration
3. **Final Policy Export**: Complete JSON policy files
4. **LLM Interaction Log**: All prompts and responses

### Database Schema

All data persisted to DuckDB for reproducibility:

```sql
-- Experiment-level config
experiment_config(experiment_id, name, config_yaml, created_at)

-- Per-iteration policies WITH CHANGE TRACKING
policy_iterations(
    iteration_id,
    experiment_id,
    iteration_number,
    agent_id,
    policy_json,              -- Full policy JSON
    policy_hash,              -- SHA256 for quick comparison
    parameters,               -- Extracted key parameters
    changes_from_previous,    -- Structured diff (added/removed/modified)
    change_summary,           -- Human-readable (e.g., "initial_liquidity_fraction: 0.5 → 0.25 (↓50%)")
    created_by                -- 'init', 'llm', 'manual'
)

-- Per-run simulation results
simulation_runs(run_id, iteration_id, seed, bank_a_cost, bank_b_cost, total_cost, settlement_rate)

-- LLM interactions
llm_interactions(interaction_id, iteration_id, prompt, response, model, tokens_used)
```

### Analyzing Policy Changes

Query the policy evolution to understand how the LLM refined its strategy:

```python
from scripts.reproducible_experiment import ExperimentDatabase

db = ExperimentDatabase("results/exp1_full.db")

# Get full evolution with change tracking
evolution = db.get_policy_evolution(experiment_id)
for entry in evolution:
    print(f"Iteration {entry['iteration_number']} ({entry['agent_id']}):")
    print(f"  Changes: {entry['change_summary']}")

# Get only significant changes (filter out no-ops)
significant = db.get_significant_changes(experiment_id)
for entry in significant:
    changes = entry['changes_from_previous']
    print(f"Iteration {entry['iteration_number']}: {len(changes.get('modified', {}))} params changed")
```

**Example change_summary output**:
```
Iteration 1: Initial policy (no previous version)
Iteration 2: parameters.initial_liquidity_fraction: 0.5 → 0.25 (↓50.0%)
Iteration 3: parameters.initial_liquidity_fraction: 0.25 → 0.1 (↓60.0%); parameters.urgency_threshold: 3 → 2 (↓33.3%)
```

**Structured diff format** (`changes_from_previous`):
```json
{
  "added": {},
  "removed": {},
  "modified": {
    "parameters.initial_liquidity_fraction": {"old": 0.5, "new": 0.25}
  },
  "unchanged_count": 15
}
```

---

## Analysis Protocol

### After Each Experiment

1. **Export Results**
```bash
.venv/bin/python -c "
import duckdb
conn = duckdb.connect('results/exp1_full.db')
print(conn.execute('SELECT * FROM iteration_metrics').fetchdf())
"
```

2. **Generate Visualization**
```python
import matplotlib.pyplot as plt
# Plot cost progression
# Plot policy parameter evolution
# Plot settlement rate
```

3. **Update Lab Notes**
- Record key findings
- Note any anomalies
- Document hypotheses for next experiment

### Cross-Experiment Analysis

After all experiments complete:

1. **Compare to Castro RL**
   - Sample efficiency (iterations to converge)
   - Solution quality (final cost)
   - Policy interpretability

2. **Document Novel Mechanisms**
   - What did LLM invent that RL didn't?
   - Are these mechanisms generalizable?

3. **Update Research Paper**
   - Fill in results tables
   - Add cost progression figures
   - Document qualitative findings

---

## Troubleshooting

### "max_collateral_capacity ignored" Issue
**Status**: ✅ RESOLVED (2025-12-01)

This issue has been fixed. The `max_collateral_capacity` config field is now properly read from YAML configuration. If not specified, the 10x heuristic (`unsecured_cap × 10`) is used as a fallback.

See `docs/bugs/max_collateral_capacity_ignored.md` for full details on the fix.

### Verifying Deferred Crediting Works

Run with verbose output and check for `DeferredCreditsApplied` events:

```bash
payment-sim run --config configs/castro_2period_aligned.yaml --verbose 2>&1 | grep -i deferred
```

If Bank A can use Bank B's payment within the same tick, deferred crediting is NOT working.

**Expected behavior**: Credits should only appear in the tick AFTER payment is received.

### LLM Generates Invalid JSON

The experiment scripts have retry logic, but if failures persist:

1. Check LLM reasoning for confusion about DSL syntax
2. Simplify the policy DSL in prompt
3. Provide more examples of valid JSON

### Cost Not Decreasing

If costs plateau or increase:

1. **Check settlement rate**: May be sacrificing settlement for lower cost
2. **Check variance**: High std dev may cause mean to fluctuate
3. **Review LLM reasoning**: May be stuck in local optimum
4. **Try temperature adjustment**: If model supports it

### API Rate Limits

OpenAI has rate limits. If hitting them:

1. Add delays between iterations: `--delay 30` (30 seconds)
2. Use smaller batch sizes
3. Consider caching LLM responses for reruns

---

## Policy Validation Protocol

### Overview

LLM-generated policies are validated using the SimCash `validate-policy` CLI before being used in simulations. This ensures policies conform to the DSL schema and scenario feature toggles.

### Validation Workflow

```
LLM generates policy
        ↓
    Validate with CLI (validate-policy --scenario config.yaml)
        ↓
    Valid? ───Yes───→ Use policy
        │
        No
        ↓
    Retry count < 5?
        │
       Yes
        ↓
    Create retry prompt with:
      - Original policy
      - Validation errors
      - Schema hints
        ↓
    LLM generates fix
        ↓
    (loop back to validate)
        │
       No (retry limit reached)
        ↓
    Log failure, keep current policy
```

### Components

#### Dynamic Schema Generation

The policy schema is **dynamically generated** from the `policy-schema` CLI command, filtered by the scenario's feature toggles. This ensures the LLM only sees elements that are valid for the specific scenario.

The dynamic prompt includes:

- **Policy structure**: JSON format, required fields
- **Available actions**: Only actions valid for the scenario's enabled features
- **Comparison & logical operators**: From the schema
- **Arithmetic operators**: From the schema
- **Context fields**: Transaction, agent, queue, and time fields
- **Example valid policy**: Complete working example
- **Common mistakes**: To help the LLM avoid validation errors

**Key benefit**: If a scenario disables certain features (e.g., splitting), the corresponding actions won't appear in the prompt, preventing the LLM from generating invalid policies.

#### Static Reference (`prompts/policy_generation_master.md`)

A static reference prompt is also available for documentation and fallback purposes. The dynamic prompt takes precedence when a scenario is configured.

#### Policy Validator (`scripts/policy_validator.py`)

Python module that wraps the CLI:

```python
from policy_validator import PolicyValidator

validator = PolicyValidator(
    simcash_root="/home/user/SimCash",
    scenario_path="experiments/castro/configs/castro_2period_aligned.yaml"
)

result = validator.validate(policy_json)
if result.valid:
    print("Policy is valid!")
else:
    print(f"Errors: {result.error_summary}")
```

#### Integration in Experiment Runner

The `LLMOptimizer` class in `reproducible_experiment.py` automatically:

1. Includes master prompt in all optimization requests
2. Validates generated policies using `PolicyValidator`
3. Retries with LLM up to 5 times on validation failure
4. Logs all validation attempts and errors

### Configuration

The validation retry limit can be configured:

```python
experiment = ReproducibleExperiment(
    experiment_key="exp1",
    db_path="results.db",
    max_validation_retries=5,  # Default: 5
)
```

### Monitoring Validation

During experiment runs, watch for validation messages:

```
  Calling LLM for optimization (with validation)...
  LLM response: 2500 tokens, 3.2s
    BANK_A: Validation passed (attempt 1)
    BANK_B: Validation failed (attempt 1)
      Errors: [InvalidNodeId] Duplicate node_id 'P1_release'...
    BANK_B: Requesting fix from LLM...
    BANK_B: Validation passed (attempt 2)
  Policies validated successfully
```

### Troubleshooting Validation Failures

#### "Max retries reached"

If policies consistently fail validation after 5 retries:

1. **Check master prompt**: Ensure it's up-to-date with current DSL
2. **Review error patterns**: Are errors similar across attempts?
3. **Simplify prompts**: The LLM may be confused by complex requirements
4. **Update examples**: Add examples of correct patterns

#### "CLI not found"

```
RuntimeError: CLI not found at /home/user/SimCash/api/.venv/bin/payment-sim
```

Fix: Rebuild the environment:
```bash
cd /home/user/SimCash/api
uv sync --extra dev
```

#### "Scenario load error"

Check that the scenario path is correct and the YAML is valid:
```bash
payment-sim run --config experiments/castro/configs/castro_2period_aligned.yaml --dry-run
```

### Schema Reference

Get the full policy schema for your scenario:

```bash
cd /home/user/SimCash/api
payment-sim policy-schema --scenario ../experiments/castro/configs/castro_2period_aligned.yaml
```

For JSON format (useful for programmatic use):
```bash
payment-sim policy-schema --scenario ../experiments/castro/configs/castro_2period_aligned.yaml --format json
```

---

## File Locations

```
experiments/castro/
├── HANDOVER.md                 ← You are here
├── CLAUDE.md                   ← Research environment style guide
├── LAB_NOTES.md                ← Detailed research log
├── RESEARCH_PAPER.md           ← Draft paper (needs updating)
├── pyproject.toml              ← UV/pip configuration
│
├── configs/
│   ├── castro_2period_aligned.yaml   ← Experiment 1
│   ├── castro_12period_aligned.yaml  ← Experiment 2
│   └── castro_joint_aligned.yaml     ← Experiment 3
│
├── policies/
│   └── seed_policy.json        ← Starting policy for optimization
│
├── prompts/
│   └── policy_generation_master.md   ← LLM policy generation guide
│
├── scripts/
│   ├── README.md               ← Script documentation
│   ├── optimizer.py            ← Original optimizer
│   ├── optimizer_v2.py         ← Improved version
│   ├── optimizer_v3.py         ← Latest version
│   ├── policy_validator.py     ← Policy validation with retry logic
│   └── reproducible_experiment.py  ← Main experiment runner (with validation)
│
├── results/                    ← Output databases go here
│   ├── exp1_baseline.db
│   ├── exp1_full.db
│   └── ...
│
├── archive/
│   └── pre-castro-alignment/   ← Old experiments (don't use)
│
└── papers/
    └── castro_et_al.md         ← Original paper reference
```

---

## Key References

- **Castro Paper**: `papers/castro_et_al.md` - Full text with equations
- **Feature Documentation**: `docs/reference/scenario/advanced-settings.md`
- **Policy DSL Guide**: `docs/policy_dsl_guide.md`
- **Policy Generation Prompt**: `prompts/policy_generation_master.md` - Master prompt for LLM
- **Lab Notes**: `LAB_NOTES.md` - Detailed experiment history

---

## Questions?

- Check `LAB_NOTES.md` for detailed experiment history
- Original Castro paper is in `papers/castro_et_al.md`
- SimCash documentation in `/docs/reference/`
- Research environment guide in `CLAUDE.md`

Good luck with the experiments!
