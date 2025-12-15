# SimCash Paper - Handover Prompt

## Context

We are writing a paper to demonstrate how SimCash can reproduce the three experiments from Castro et al. (2025) on reinforcement learning for payment system policy optimization.

**Your task**: Write the SimCash paper using **Castro-compliant configuration**, with a particular focus on explaining:
1. **How the LLM-based policy optimization works** (what the LLM sees, what it returns)
2. **The bootstrap evaluation methodology** (3-agent sandbox design and justification)
3. **How our approach differs from Castro et al.** (LLM vs neural network RL)

---

## 🔴 CRITICAL: Use Castro-Compliant Configuration

SimCash has two liquidity mechanisms:

| Mechanism | Effect | Use Case |
|-----------|--------|----------|
| `posted_collateral` + `max_collateral_capacity` | Provides credit headroom (overdraft) | General payment systems |
| `liquidity_pool` + `liquidity_allocation_fraction` | Provides direct balance | **Castro replication** |

**For Castro replication, you MUST use `liquidity_pool` mode.** This matches Castro's model where:
- Collateral provides direct balance (not credit)
- Hard liquidity constraint: `P_t × x_t ≤ ℓ_{t-1}`
- No intraday overdraft

---

## 🟢 Configuration Pattern

All experiment configs should use this pattern:

```yaml
agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0                      # No credit
    liquidity_pool: 100000                # Castro's B
    # liquidity_allocation_fraction controlled by policy optimization

cost_rates:
  liquidity_cost_per_tick_bps: 500        # r_c
  collateral_cost_per_tick_bps: 0         # Disable collateral mode
  overdraft_bps_per_tick: 0               # No overdraft
```

See the experiment configuration files in `experiments/castro/configs/` for complete experiment-specific configurations.

---

## Your Assignment

### Phase 1: Setup & Verification

- [ ] Review Castro et al. paper: `experiments/castro/papers/castro_et_al.md`
- [ ] Review evaluation methodology: `docs/reference/ai_cash_mgmt/evaluation-methodology.md`
- [ ] Review optimizer prompt architecture: `docs/reference/ai_cash_mgmt/optimizer-prompt.md`
- [ ] Update experiment configs to use `liquidity_pool` pattern:
  - `experiments/castro/configs/exp1_2period.yaml`
  - `experiments/castro/configs/exp2_12period.yaml`
  - `experiments/castro/configs/exp3_joint.yaml`
- [ ] Verify experiment runner supports `liquidity_allocation_fraction` optimization
- [ ] Run sanity check (1 iteration of exp1)

### Phase 2: Experiment Execution

Run experiments using the CLI with verbose output:

```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml
```

**NEVER change the LLM model!** Always use `openai:gpt-5.2` as specified.

- [ ] Run exp1 (2-period deterministic)
- [ ] Run exp2 (12-period stochastic)
- [ ] Run exp3 (3-period joint optimization)
- [ ] Document any errors or unexpected behavior

### Phase 3: Results Analysis & Artifact Generation

For each experiment:
- [ ] Record final policy values
- [ ] Compare to Castro et al. theoretical predictions
- [ ] Document bootstrap statistics (mean, std, CI)
- [ ] Analyze paired delta distributions

**Generate Policy Evolution JSON Appendices** (see [Policy Evolution Export](#policy-evolution-export) below):
- [ ] Export policy evolution for each experiment as JSON
- [ ] Save to `docs/plans/simcash-paper/appendices/` for paper attachment

**Audit LLM Interactions** (see [Auditing LLM Prompts](#auditing-llm-prompts) below):
- [ ] Replay at least one iteration with `--audit` to capture full LLM prompt/response
- [ ] Include representative examples in the paper's methodology section

### Phase 4: Paper Writing

Write documentation in `docs/plans/simcash-paper/`:

1. **`research-plan.md`** - Your phased approach
2. **`lab-notes.md`** - Detailed experiment logs
3. **`draft-paper.md`** - Complete paper including all sections below

**Required Paper Sections** (see [Paper Structure Requirements](#paper-structure-requirements)):

- Abstract
- Introduction
- **LLM Policy Optimization Methodology** ⭐ NEW - Detailed explanation
- **Bootstrap Evaluation & 3-Agent Sandbox** ⭐ NEW - With justification
- **Comparison to Castro et al.** ⭐ NEW - Differences in approach
- Results with confidence intervals
- Discussion and conclusion
- **Appendices**: Policy evolution JSON files

### Phase 5: Figures & Tables

- [ ] Policy evolution diagrams
- [ ] Cost over iterations with confidence intervals
- [ ] Final policy comparison table vs Castro predictions
- [ ] LLM prompt structure diagram (showing the 7 sections)
- [ ] 3-agent sandbox architecture diagram

---

## 🔵 Policy Evolution Export

After running each experiment, export the policy evolution as JSON for paper appendices:

```bash
cd api

# Export full policy evolution with LLM prompts/responses
.venv/bin/payment-sim experiment policy-evolution <run-id> --llm > ../docs/plans/simcash-paper/appendices/exp1_policy_evolution.json

# Filter by agent
.venv/bin/payment-sim experiment policy-evolution <run-id> --agent BANK_A --llm > ../docs/plans/simcash-paper/appendices/exp1_bank_a_evolution.json

# Filter by iteration range
.venv/bin/payment-sim experiment policy-evolution <run-id> --start 1 --end 10 --llm > ../docs/plans/simcash-paper/appendices/exp1_iterations_1_10.json
```

**Output format** (per agent, per iteration):
```json
{
  "BANK_A": {
    "iteration_1": {
      "policy": { ... },
      "diff": "",
      "cost": 10000,
      "accepted": true,
      "llm": {
        "system_prompt": "You are an expert...",
        "user_prompt": "Current policy: {...}\nGenerate...",
        "raw_response": "{\"policy\": {...}}"
      }
    }
  }
}
```

Use these JSON files as **supplementary material/appendices** for the paper, allowing readers to see the complete optimization trajectory.

---

## 🔵 Auditing LLM Prompts

To understand exactly what the LLM sees and returns, use the audit feature:

```bash
cd api

# Show full audit trail for all iterations
.venv/bin/payment-sim experiment replay <run-id> --audit

# Focus on a specific iteration (e.g., iteration 3)
.venv/bin/payment-sim experiment replay <run-id> --audit --start 3 --end 3

# Show audit for iterations 2-5
.venv/bin/payment-sim experiment replay <run-id> --audit --start 2 --end 5
```

**Audit output includes** for each agent at each iteration:
- **Model metadata**: Model name, token counts (prompt/completion), latency
- **System prompt**: The complete system prompt sent to the LLM
- **User prompt**: The full context prompt (~50k tokens) with all 7 sections
- **Raw response**: The complete LLM response before parsing
- **Validation results**: Whether the policy was successfully parsed

**Use this to**:
1. Capture a representative LLM prompt for the paper's methodology section
2. Show what information the LLM receives (cost breakdown, simulation outputs, history)
3. Demonstrate the structured nature of the optimization process

---

## 🔵 Paper Structure Requirements

### Section: LLM Policy Optimization Methodology

**This section MUST explain in detail:**

1. **The Optimization Loop**:
   - LLM generates candidate policy → Policy evaluated via simulation → Accept/reject based on cost comparison → LLM sees results and generates improved policy

2. **What the LLM Receives** (the 7-section prompt structure from `docs/reference/ai_cash_mgmt/optimizer-prompt.md`):
   - **Section 1 - Header**: Agent ID, iteration number, table of contents
   - **Section 2 - Current State**: Performance metrics, current policy parameters
   - **Section 3 - Cost Analysis**: Cost breakdown by type (delay, overdraft, etc.) with rates
   - **Section 4 - Optimization Guidance**: Actionable recommendations based on cost patterns
   - **Section 5 - Simulation Output**: Tick-by-tick event traces from best and worst bootstrap samples
   - **Section 6 - Iteration History**: Full history with acceptance status and policy changes
   - **Section 7 - Parameter Trajectories**: How each parameter evolved across iterations
   - **Section 8 - Final Instructions**: Output requirements and warnings about rejected policies

3. **What the LLM Returns**:
   - A complete policy JSON with parameters (e.g., `initial_liquidity_fraction`)
   - Decision trees for payment timing
   - Must conform to policy constraints defined in experiment config

4. **Validation and Retry**:
   - Responses are validated against the constraint schema
   - Invalid policies trigger retry with error feedback
   - Up to `max_retries` attempts per iteration

**Include a representative prompt excerpt** from the audit output to show readers the level of detail provided to the LLM.

### Section: Bootstrap Evaluation & 3-Agent Sandbox

**This section MUST explain the evaluation methodology for exp2 (and exp3):**

1. **The Problem**: How do we evaluate whether a candidate policy is better than the current policy when costs are highly variable due to stochastic transaction arrivals?

2. **Solution: Paired Comparison Bootstrap**:
   - Generate N bootstrap samples from historical transaction data
   - Run **both** policies on the **same** N samples
   - Compute delta = cost(current) - cost(candidate) for each sample
   - Accept new policy if mean(delta) > 0
   - **Why paired comparison**: Eliminates sample-to-sample variance, making true policy differences detectable

3. **The 3-Agent Sandbox Architecture** (CRITICAL - explain and justify):

   ```
   SOURCE → AGENT → SINK
     ↓                 ↑
     └─────liquidity───┘
   ```

   - **SOURCE**: Infinite liquidity, sends "incoming settlements" to AGENT at historically-observed times
   - **AGENT**: Target agent with test policy being evaluated
   - **SINK**: Infinite capacity, receives AGENT's outgoing transactions

4. **Justification for the 3-Agent Sandbox** (from `docs/reference/ai_cash_mgmt/evaluation-methodology.md`):

   **The Information Set Argument**:
   - In a real payment system, agents **cannot observe** other agents' internal states (policies, queues, liquidity)
   - From any agent's perspective, they only see: their own policy, when their payments settle, when liquidity arrives
   - **Settlement timing is a sufficient statistic** for the liquidity environment
   - The sandbox preserves this by encoding market conditions in the `settlement_offset` of historical transactions

   **When the Approximation is Valid**:
   - Agent is "small" (doesn't materially affect system liquidity)
   - Policy decisions are local (about releasing own transactions)
   - No strategic counterparty response
   - Diverse counterparty set

   **Known Limitations**:
   - No bilateral feedback loop (releasing payment to B doesn't immediately give B liquidity to send back)
   - No multilateral LSM cycles (sandbox only supports bilateral offsets)
   - Settlement timing fixed to historical values

5. **Statistical Recommendations**:
   - Sample sizes: 10-20 for quick iteration, 50-100 for production, 200+ for research
   - Confidence intervals computed from bootstrap sample deltas

### Section: Comparison to Castro et al.

**This section MUST explain how SimCash differs from Castro's approach:**

| Aspect | Castro et al. (2025) | SimCash |
|--------|---------------------|---------|
| **Learning Algorithm** | REINFORCE (policy gradient RL) | LLM-based prompt optimization |
| **Policy Representation** | Neural network weights | Explicit JSON decision trees |
| **Training Process** | Episodes × gradient updates | Iteration × LLM call × accept/reject |
| **Exploration** | Softmax action probabilities | LLM's inherent variability + structured prompts |
| **State Representation** | Vector input to neural net | Structured text with simulation traces |
| **Interpretability** | Black-box neural network | Transparent decision rules |
| **Knowledge** | Learns from scratch | LLM has prior knowledge about optimization |

**Key Differences to Discuss**:

1. **Continuous vs Discrete Actions**: Castro uses 21-point discretization of [0,1] for liquidity fraction. SimCash policies can specify any value.

2. **Training Dynamics**:
   - Castro: Hundreds of episodes with gradient updates, policies evolve smoothly
   - SimCash: ~25 iterations, each producing a complete new policy, accept/reject mechanism

3. **Multi-Agent Interaction**:
   - Castro: Two agents train simultaneously, affecting each other's environment
   - SimCash: Agents optimized sequentially within each iteration (or in alternating fashion)

4. **Environment Stationarity**:
   - Castro: Non-stationary due to both agents learning
   - SimCash: Bootstrap evaluation uses fixed historical samples

5. **Payment Demand**:
   - Castro: 380 days of real LVTS data, random sampling per episode
   - SimCash: Configurable arrival patterns, bootstrap resampling

6. **Costs**:
   - Castro: r_c=0.1, r_d=0.2, r_b=0.4 (normalized)
   - SimCash: Basis points per tick, configurable

**Despite these differences**, both approaches should converge to similar equilibrium policies because:
- The underlying optimization problem is the same (minimize cost)
- The cost structure creates the same incentives
- Castro's theoretical analysis provides ground truth for simple cases

---

## Expected Outcomes

With Castro-compliant configuration, results should match Castro's theoretical predictions:

| Experiment | Castro Prediction | Notes |
|------------|-------------------|-------|
| **Exp1** | A=0%, B=20% | Asymmetric equilibrium |
| **Exp2** | Both 10-30% | Stochastic case |
| **Exp3** | Both ~25% | Symmetric equilibrium |

---

## Key Files

### Must Read
- `experiments/castro/papers/castro_et_al.md` - Castro's theoretical predictions
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Bootstrap evaluation & 3-agent sandbox justification
- `docs/reference/ai_cash_mgmt/optimizer-prompt.md` - LLM prompt architecture (7 sections)
- `docs/reference/cli/commands/experiment.md` - CLI commands including `policy-evolution` and `replay --audit`
- `docs/reference/scenario/agents.md` - `liquidity_pool` documentation
- `docs/reference/scenario/cost-rates.md` - `liquidity_cost_per_tick_bps` documentation

### Experiment Configs
- `experiments/castro/configs/exp1_2period.yaml`
- `experiments/castro/configs/exp2_12period.yaml`
- `experiments/castro/configs/exp3_joint.yaml`

---

## CLI Reference

```bash
# Run experiment
.venv/bin/payment-sim experiment run --verbose <config.yaml>

# List experiments
.venv/bin/payment-sim experiment list

# List completed experiment runs (to find run IDs)
.venv/bin/payment-sim experiment results

# Replay experiment (standard output)
.venv/bin/payment-sim experiment replay <run-id>

# Replay with audit trail (LLM prompts/responses)
.venv/bin/payment-sim experiment replay <run-id> --audit --start N --end N

# Export policy evolution as JSON (for paper appendices)
.venv/bin/payment-sim experiment policy-evolution <run-id> --llm > policy_evolution.json

# Export specific agent's evolution
.venv/bin/payment-sim experiment policy-evolution <run-id> --agent BANK_A --llm

# Export specific iteration range
.venv/bin/payment-sim experiment policy-evolution <run-id> --start 1 --end 10 --llm
```

---

## Output Location

All work goes in: `docs/plans/simcash-paper/`

Create subdirectory for appendices: `docs/plans/simcash-paper/appendices/`

---

## Checklist

Before starting:
- [ ] Configs updated to use `liquidity_pool` pattern
- [ ] Experiment runner verified to support `liquidity_allocation_fraction`
- [ ] Sanity check passed
- [ ] Reviewed optimizer-prompt.md to understand LLM prompt structure
- [ ] Reviewed evaluation-methodology.md to understand bootstrap/sandbox

During experiments:
- [ ] Capture all verbose output
- [ ] Document iteration-by-iteration progress in lab notes

After experiments:
- [ ] Results compared to Castro predictions
- [ ] Policy evolution JSON exported for each experiment
- [ ] At least one iteration audited with `--audit` flag
- [ ] Representative LLM prompt captured for paper
- [ ] Draft paper complete with all required sections:
  - [ ] LLM Policy Optimization Methodology section
  - [ ] Bootstrap Evaluation & 3-Agent Sandbox section
  - [ ] Comparison to Castro et al. section
- [ ] Figures and tables included
- [ ] Appendices with policy evolution JSON attached
