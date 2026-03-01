# Discussion

## What We Observed

This campaign produced three broad patterns:

1. **LLM optimization reduced costs in single-day scenarios.** Across simple scenarios (2–4 banks, 1 day, 10 optimization rounds), Flash achieved 55–86% cost reduction while maintaining settlement rates above 95%. Pro performed comparably in some scenarios and worse in others. GLM generally underperformed both Gemini models.

2. **LLM optimization increased costs and reduced settlement in multi-day scenarios.** In the three multi-day scenarios (25 days, between-day optimization), both Flash and Pro produced higher total costs (+13–23%) and lower settlement rates than the unoptimized FIFO baseline. The damage was not immediate — Day 1 performance was often comparable to or better than baseline — but accumulated over subsequent days as agents progressively reduced liquidity commitments.

3. **Flash generally outperformed Pro on system-wide metrics.** In 5 of 6 comparable scenarios, Flash produced lower total system costs than Pro. The exception was 4b_8t, where Pro achieved -69.0% cost reduction vs. Flash's -55.5%.

These are the observations. The question is what to make of them.

## Confounds and Limitations

The most important thing to say about this campaign is what it **cannot** tell us. The simple and multi-day scenarios differ in at least eight dimensions simultaneously:

| Factor | Simple Scenarios | Multi-Day Scenarios |
|--------|-----------------|---------------------|
| Days | 1 | 25 |
| Optimization | 10 rounds, same day | 1 round, between-day |
| Bank homogeneity | Symmetric | Heterogeneous (big/mid/small) |
| LSM | Off | Bilateral + cycles |
| Liquidity pools | 1M each | 160K–800K varying |
| Cost structure | 100K EOD penalty | 4–5K EOD penalty |
| Scenario events | None | Shocks, crisis phases |
| Baseline SR | 100% | 59–77% |

Notably, the Periodic Shocks scenario has **4 banks** — the same count as 4b_8t, where LLM optimization works well. This directly undermines any claim that bank count alone explains the performance difference. The multi-day scenarios are harder for LLM optimization, but we cannot say *why* from this data. It could be the temporal dynamics, the constrained baselines, the heterogeneous banks, the LSM interactions, or any combination.

Previous versions of this paper proposed a "complexity threshold at ~4–5 banks." We retract that framing. The data does not support attributing the multi-day failures to bank count specifically.

### Additional Limitations

- **No agent communication**: Real banks communicate, negotiate, and have reputations. Our agents are isolated optimizers.
- **Three models from two providers**: We tested only Gemini and GLM. Results may not generalize to GPT-4o, Claude, Llama, or other architectures.
- **Three runs per condition**: With n=3, we cannot reliably distinguish systematic model differences from stochastic variation.
- **GLM exclusion on multi-day scenarios**: A pre-bugfix data integrity issue required excluding GLM results for multi-day scenarios.
- **Deterministic simulation**: SimCash uses a fixed seed (42); all variance comes from LLM stochasticity.
- **Cost-only optimization**: The `is_better_than()` function compares cost only. A candidate that settles fewer payments at lower cost will be preferred. This is a design choice that affects agent behavior.

## The Ratchet Effect

The most mechanistically clear observation from the campaign is the **liquidity ratchet** in multi-day scenarios. The between-day optimization structure works as follows: after each simulated day, the LLM reviews the day's costs and proposes a new policy for the next day. Since reducing the initial liquidity fraction reduces the bank's own holding costs (at least on that day), agents consistently ratchet fractions downward.

A concrete example from Lehman Month (BANK_GAMMA):

| Day | Liquidity Fraction |
|-----|--------------------|
| 1 | 0.50 |
| 2 | 0.25 |
| 3 | 0.125 |
| 5 | 0.016 |
| 10 | 0.0005 |
| 15 | 0.0 |

By mid-simulation, multiple banks are committing zero liquidity. The system depends entirely on recycled incoming payments to fund outgoing ones — a fragile state that produces settlement failures and delayed-payment penalties exceeding the liquidity savings.

This ratchet is observable and mechanistic. It does not require invoking game-theoretic concepts: each agent independently discovers that lower fractions reduce its own costs on the current day, without visibility into the cumulative system-wide effect. The between-day optimization structure (1 round, no re-evaluation) means each step downward is locked in before its consequences propagate.

Whether this ratchet is specific to between-day optimization (vs. the 10-round within-day optimization used in simple scenarios) or to the multi-day temporal structure is an open question. Test A in Future Research below would address this.

## Strategy Poverty

Examining the policy trees produced by all three models across all experiments reveals a striking pattern: **LLMs are parameter tuners, not strategy architects**.

Of the 11 available policy actions (Release, Delay, Hold, Split, RequestLiquidity, NoAction, plus conditional branches based on queue depth, balance, urgency, time), models consistently used only 5. The bank-level decision tree was universally set to NoAction — no model ever learned to request additional liquidity or adjust reserves during the day.

The primary lever every model discovered was the **initial liquidity fraction**. Models tuned this parameter aggressively (Flash tended toward moderate values of 0.05–0.25; GLM and Pro pushed toward 0.00–0.05) but rarely constructed meaningful conditional logic in the payment decision tree.

This is an observable fact about the current system, not a claim about LLM capability in general. It may reflect limitations of the bootstrap evaluation framework (which compares aggregate cost, not strategy components), the prompt design, the action space presentation, or intrinsic model limitations. We note it as a pattern warranting investigation.

## Prompt Engineering on Castro Exp2

The v0.2 prompt variants tested four conditions on the Castro Exp2 scenario (2 banks, 1 day, 10 rounds):

- **C1 (information)**: Telling the LLM about settlement rates. Minimal effect on behavior.
- **C2 (settlement floor)**: Imposing a minimum 80% settlement requirement. Flash achieved 100% settlement while maintaining cost reduction.
- **C3 (strategy guidance)**: Describing available policy tools. Flash achieved 100% settlement.
- **C4 (full composition)**: Combining all interventions. Flash achieved 100% settlement with the lowest cost.

The pattern: **constraints shaped behavior more effectively than information alone**. This is consistent with how real RTGS systems operate — throughput guidelines and penalty structures are binding constraints, not informational advisories.

We scope this finding strictly to Castro Exp2. We did not systematically test v0.2 prompts across all scenarios, so we cannot say whether the same pattern holds in multi-day or larger-network settings.

## Future Research

The most important next step is **controlled experimentation**. The current campaign was exploratory — it surveyed a landscape but confounded multiple variables. Disentangling the factors that drive multi-day performance degradation requires factorial designs where one variable changes at a time.

### Proposed Factorial Experiments

**Test A: Isolate multi-day dynamics.**
Run 4b_8t (where LLM optimization works) extended to 25 days with between-day optimization. If performance degrades, the temporal/optimization structure — not bank count or scenario complexity — is the driver.

**Test B: Isolate baseline constraint.**
Run 4b_8t with reduced liquidity pools (160K–800K instead of 1M each), keeping everything else identical. If performance degrades, tight baselines interact badly with LLM optimization.

**Test C: Isolate bank asymmetry.**
Run 4b_8t with heterogeneous banks (big/mid/small instead of symmetric), keeping 1 day and 10 rounds. If performance degrades, heterogeneity is a factor.

**Test D: Multi-day + constrained interaction.**
Combine Tests A and B: 4b_8t extended to 25 days with reduced liquidity pools. This tests whether the interaction between temporal dynamics and liquidity constraints is the key driver.

**Test E: Isolate bank count.**
Run a scenario identical to 4b_8t in every respect — 1 day, 10 rounds, symmetric banks, no LSM, 1M pools, 100K EOD penalty — but with 6 banks instead of 4. This is the only clean test of whether bank count matters.

### Other Directions

- **Multi-objective optimization**: Replace the cost-only `is_better_than()` with Pareto-frontier evaluation incorporating settlement rate. The current cost-only objective may be driving the liquidity ratchet.

- **Agent communication**: Allow agents to observe or signal each other's liquidity commitments. This transforms the optimization problem from independent to interactive and may enable cooperative equilibria.

- **Broader model testing**: Test GPT-4o, Claude, Llama, Qwen, and other architectures to determine whether the observed patterns are model-specific or general properties of LLM-based optimization.

- **Real-world calibration**: Validate scenario parameters against actual Lynx transaction data and test whether results shift with realistic payment distributions.

- **Dynamic scenarios**: Introduce time-varying participation, stochastic payment generation, and adaptive opponent modeling.

## Conclusion

SimCash provides an open-source platform for studying how LLM agents interact with RTGS payment systems. This campaign of 132 experiments across 3 models and 10 scenarios generated several patterns worth investigating further: strong cost reduction in single-day scenarios, performance degradation in multi-day scenarios, an observable liquidity ratchet mechanism, and a consistent (if unexplained) advantage of Flash over Pro.

What the campaign did not produce is clean causal evidence. The scenarios that worked differ from those that failed in too many dimensions to attribute the difference to any single factor. The proposed factorial experiments would address this directly.

The data is publicly available through the SimCash experiment viewer. We invite researchers to examine the results, challenge our observations, and extend the platform with new scenarios and optimization approaches.
