# Paper Reproduction Failure Analysis

**Date:** 2026-02-21  
**Author:** Nash  
**For:** Dennis (review & investigation)  
**Status:** Needs investigation

## What Happened

I ran all three paper experiments (exp1, exp2, exp3) on the deployed web platform with 50 eval samples and 25 rounds each, using the exact YAML configs from `experiments/castro/configs/`. All three converged to `initial_liquidity_fraction = 1.0` and stayed there for all 25 rounds. This is wrong — the paper shows convergence to much lower fractions.

### Paper Results (from `docs/papers/simcash-paper/paper_generator/data/`)

**Exp 2** (12-Period Stochastic): Started at 0.5, converged to ~0.08 (BANK_A) / ~0.06 (BANK_B) over 33 iterations. Clear downward trajectory with acceptance/rejection decisions.

### Web Platform Results

**All three experiments**: Started at 1.0, stayed at 1.0 for all 25 rounds. Zero exploration.

| Experiment | Game ID | Expected | Got |
|-----------|---------|----------|-----|
| Exp 1 (2-Period Nash) | `6123c7ab` | A=0%, B=20% | Both 100% |
| Exp 2 (12-Period Stochastic) | `ca391260` | Both ~6-8% | Both 100% |
| Exp 3 (3-Period Joint) | `e3d99b1a` | Symmetric low | Both 100% |

## Root Causes

### 1. Starting Fraction: 1.0 vs 0.5

The web platform's `DEFAULT_POLICY` in `game.py:26` sets `initial_liquidity_fraction: 1.0`. The paper's experiment runner starts at 0.5 (see `exp2` iteration 0 in the DB).

At fraction=1.0, all payments settle immediately. The LLM sees:
- Liquidity cost: ~$10k (the only cost)
- Delay penalties: $0
- EOD penalties: $0
- Deadline penalties: $0

The LLM has **no information** about what happens at lower fractions. It only knows that reducing fraction *might* cause $100,000 penalties per unsettled transaction. Rationally, it stays at 1.0.

At fraction=0.5 (paper's starting point), the LLM sees a mix of costs — some payments settle, some don't, and it can reason about the tradeoff. It has gradient information.

### 2. No Policy Acceptance/Rejection Mechanism

The paper's `OptimizationLoop` (in `api/payment_simulator/experiments/runner/optimization.py`) has a sophisticated acceptance mechanism:
- **Paired bootstrap comparison**: Run proposed policy on same seeds as current best, compare costs
- **Statistical significance**: Require 95% CI to not cross zero
- **Variance check**: Reject if coefficient of variation > 0.5
- **Rollback**: If rejected, keep the current best policy

The web platform's `streaming_optimizer.py` just takes whatever the LLM outputs and applies it. No comparison, no rejection, no rollback. This means:
- Bad policies get applied and compound errors
- The LLM has no "safety net" that would encourage exploration
- There's no concept of "current best" that the LLM is trying to beat

### 3. Prompt Differences (Likely)

The web platform's `_build_optimization_prompt()` in `streaming_optimizer.py` constructs the prompt differently from the paper's `PolicyOptimizer.build_single_agent_context()` path in the experiment runner. I suspect there are differences in:
- How iteration history is presented (acceptance status, rejected policies)
- Whether the prompt mentions the acceptance mechanism
- How cost breakdowns are structured
- Whether `prompt_customization` from the experiment config is included

I didn't properly trace the full prompt path in the experiment runner before building the web version. This is the core mistake.

## What Dennis Should Investigate

1. **Starting policy in the experiment runner**: How is the initial fraction=0.5 set? Is it in the experiment config, hardcoded, or derived from the scenario?

2. **Full prompt construction path**: Trace the experiment runner's prompt from `OptimizationLoop` through `PolicyOptimizer` → `build_single_agent_context()` → `SystemPromptBuilder`. Compare with the web's `_build_optimization_prompt()`. Document every difference.

3. **Acceptance mechanism**: How exactly does paired bootstrap comparison work? The web platform needs this. Key questions:
   - How are seeds managed for paired comparison?
   - What happens on rejection — does the LLM see that its proposal was rejected?
   - Does the experiment runner's prompt include rejected policy history?

4. **Experiment config fields**: The paper configs (`docs/papers/simcash-paper/paper_generator/configs/exp2.yaml`) have fields the web platform ignores:
   - `evaluation.mode: bootstrap` / `deterministic-temporal`
   - `evaluation.acceptance.require_statistical_significance`
   - `evaluation.acceptance.max_coefficient_of_variation`
   - `convergence.stability_threshold` / `stability_window`
   - `prompt_customization.all` (experiment-specific guidance text)
   - `policy_constraints` (allowed fields/actions)
   
   Which of these are critical for reproduction?

5. **Model difference**: Paper used `openai:gpt-5.2` with `reasoning_effort: "high"`. Web used `google-vertex:glm-4.7-maas`. Could the model difference alone explain the behavior? (I doubt it — the structural issues above are more fundamental.)

## Lessons Learned

1. **Don't assume same YAML = same behavior.** The YAML configs define the *scenario*, but the experiment runner adds critical orchestration logic (starting policy, acceptance mechanism, prompt construction) that the web platform didn't replicate.

2. **Check the paper's actual code path before building a reproduction.** I should have traced `payment-sim experiment run exp2.yaml` end-to-end and documented every step before building the web equivalent.

3. **Starting conditions matter enormously for LLM optimization.** At fraction=1.0, the LLM is at a local optimum with zero gradient information about penalties. At 0.5, it's in a region with rich cost signals. This is analogous to weight initialization in neural networks — start in the wrong place and you never converge.

## Files to Compare

| Component | Experiment Runner | Web Platform |
|-----------|------------------|--------------|
| Main loop | `experiments/runner/optimization.py` `OptimizationLoop` | `web/backend/app/game.py` `Game.optimize_policies()` |
| Prompt builder | `ai_cash_mgmt/optimization/policy_optimizer.py` | `web/backend/app/streaming_optimizer.py` `_build_optimization_prompt()` |
| System prompt | `ai_cash_mgmt/prompts/system_prompt_builder.py` | Same (reused) |
| User context | `ai_cash_mgmt/prompts/single_agent_context.py` | Same (reused) |
| LLM client | `experiments/runner/llm_client.py` | `streaming_optimizer.py` (pydantic-ai direct) |
| Acceptance | `experiments/runner/optimization.py` `_is_improvement()` | **MISSING** |
| Bootstrap eval | `experiments/runner/bootstrap_support.py` | `game.py` `run_day()` multi-seed averaging |
| Starting policy | Experiment config / runner default | `game.py:26` `DEFAULT_POLICY` (frac=1.0) |
| Experiment config | Full YAML with eval/convergence/prompt sections | Only scenario YAML (eval/convergence ignored) |
