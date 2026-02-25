# Prompt Improvement Recommendations for Liquidity Crunch Strategy Discovery

**Author:** Nash  
**Date:** 2026-02-25  
**Revised:** 2026-02-25 (incorporating Dennis's feedback)  
**Status:** Revised — for review by Stefan  
**Context:** Analysis of why LLM agents fail to discover effective strategies under liquidity crunch conditions, with concrete recommendations for prompt improvements.

---

## Executive Summary

The SimCash optimization prompts are highly effective at enabling LLMs to tune parameters within a fixed strategy template. However, they systematically fail to guide LLMs toward discovering multi-lever strategic compositions — particularly strategies that exploit the **bank tree → payment tree** interaction, which is where sophisticated liquidity management lives.

This report identifies **seven specific gaps** in the current prompt pipeline and proposes targeted fixes. The central theme: the prompts lack quantitative context about the **RTGS settlement balance** — the actual mechanism that determines whether payments clear. Without seeing balance trajectories, liquidity utilization ratios, and the temporal dynamics of inflows vs outflows, LLMs cannot reason about *when* and *why* liquidity crunches occur.

---

## How SimCash Settlement Works (For Context)

In SimCash, payments settle via the RTGS mechanism: a payment clears **if and only if** the sending bank's settlement account balance (plus any available credit) is sufficient to cover the payment amount at the moment of settlement. There is no forced overnight lending — unsettled payments remain unsettled and incur end-of-day penalties.

The **RTGS balance** is therefore the critical state variable:
- **Balance > payment amount** → payment settles immediately
- **Balance < payment amount** → payment queues, accruing delay costs
- **Balance trajectory over the day** determines which payments settle, when, and at what cost

The balance evolves as:
```
balance(t) = balance(t-1) - outflows_settled(t) + inflows_settled(t-1)
                                                    ↑ deferred crediting!
```

**Deferred crediting** means incoming payments received at tick T only become available at tick T+1. This is the key mechanism that creates liquidity crunches: you cannot count on expected inflows to fund same-tick outflows.

The agent's primary strategic lever is `initial_liquidity_fraction` — what fraction of the liquidity pool to commit to the RTGS settlement account at day start. Too much = wasted capital (liquidity opportunity cost). Too little = payments queue and miss deadlines.

---

## Current Prompt Architecture

The prompt pipeline consists of:

1. **System prompt** (`system_prompt_builder.py`): Expert role, domain context (RTGS, queuing, LSM), cost structure, policy tree syntax, allowed fields/actions/parameters, common errors, validation checklist
2. **User prompt** (`single_agent_context.py`): Current policy + parameters, simulation trace (one representative seed), cost breakdown (best/worst/average), full iteration history with rejected policies, parameter trajectories, optimization guidance, instructions

The system prompt explains *mechanics* well. The user prompt provides *data* well. Neither explains the *strategic implications* of the RTGS balance or how trees compose to manage it.

---

## Gap Analysis

### Gap 1: No Quantitative RTGS Balance Context

**Problem:** The LLM never sees how its committed liquidity relates to expected payment demand. It sees `initial_liquidity_fraction: 0.45` and cost numbers, but not:
- How much liquidity was actually committed in absolute terms
- What the expected daily payment volume is
- What fraction of committed liquidity was actually used
- Whether the balance ever hit zero (the crunch moment)

Without this, the LLM tunes `initial_liquidity_fraction` by trial and error rather than by reasoning about the demand/supply ratio.

**Impact:** In the exp2 Castro scenario, the liquidity pool is $1,000,000 and expected daily demand is ~$240,000 (rate=2.0/tick × mean=$10,000 × 12 ticks). The optimal fraction is ~20-40% (per Figure 6 of the paper). But the LLM doesn't know these numbers — it can't reason "I need ~$240k of committed liquidity, so fraction should be ~0.24."

**Recommendation:** Add a "Liquidity Context" section to the user prompt:

```
### RTGS Balance Context
- Liquidity pool: $1,000,000 (this is the maximum you can commit)
- Committed liquidity: $450,000 (45.0% of pool)
- Expected daily payment demand: ~$240,000
- Demand/committed ratio: 53% (you committed roughly 1.9× expected demand)
- Peak balance usage: 78% of committed amount (at tick 7)
- Minimum balance reached: $98,000 at tick 7
- Ticks where balance < 20% of committed: ticks 6-8
```

**Implementation:** This data is available from the simulation run. The balance trajectory is tracked by the engine. Expected demand can be computed from the arrival config (rate × mean × ticks). The `EvalContext` already exposes `balance`, `available_liquidity`, and related fields.

---

### Gap 2: No RTGS Balance Trajectory

**Problem:** The simulation trace shows individual events (arrivals, settlements, queue operations) but the LLM must mentally reconstruct the balance trajectory. In a crunch, the narrative arc — "balance was fine until tick 5, then three large outflows hit with no inflows, and by tick 7 everything was queued" — is the key insight. But it's buried in dozens of individual events.

**Impact:** The LLM sees `✅ RTGS Settled: BANK_A → BANK_B | $150.00` and `📋 Queued TX abc123... (insufficient liquidity)` as independent events. It doesn't see that the queuing at tick 7 was *caused* by the aggressive releasing at ticks 3-5 combined with deferred crediting delaying inflows.

**Recommendation:** Add a condensed RTGS balance trajectory to the simulation trace:

```
### RTGS Balance Trajectory (Seed #42)
Tick | Balance    | Avail Liq  | Outflows  | Inflows   | Queued | Notes
-----|------------|------------|-----------|-----------|--------|------
  0  | $450,000   | $650,000   | $0        | $0        | 0      | Posted 45% of pool
  1  | $380,000   | $580,000   | $70,000   | $0        | 0      | Deferred: no inflows yet
  2  | $295,000   | $495,000   | $120,000  | $35,000   | 0      | 
  3  | $245,000   | $445,000   | $85,000   | $35,000   | 0      | 
  4  | $178,000   | $378,000   | $112,000  | $45,000   | 0      | 
  5  | $120,000   | $320,000   | $98,000   | $40,000   | 1      | First queued payment
  6  | $85,000    | $285,000   | $65,000   | $30,000   | 2      | ⚠️ Low balance
  7  | $98,000    | $298,000   | $22,000   | $35,000   | 4      | ⚠️ CRUNCH: 4 payments queued
  8  | $165,000   | $365,000   | $18,000   | $85,000   | 2      | Large incoming cleared queue
  ...
```

**Critical: Include Available Liquidity (Dennis).** The `Avail Liq` column shows `balance + remaining credit headroom` — this is what `can_pay()` actually checks when deciding whether a payment can settle. A bank might show balance=$85k but with $200k of unsecured_cap, it can still settle a $250k payment. Without seeing available liquidity, the LLM might think the situation is worse (or better) than it actually is. Both `balance` and `available_liquidity` are already exposed via FFI — it's one extra column.

**Implementation:** The engine tracks balance changes via `CostAccrual` and settlement events. A post-processing step could summarize per-tick balance, available liquidity, aggregate outflows/inflows, and count queued payments. This would be a new function in `event_filter.py` or a new module.

---

### Gap 3: Deferred Crediting Not Strategically Emphasized

**Problem:** The domain context section mentions RTGS mechanics and queuing but says nothing about deferred crediting. The Castro section mentions it once ("inflows available NEXT period only") buried in a formula block. The LLM doesn't internalize that **the RTGS balance cannot be replenished within the same tick** — the most important constraint in a crunch.

**Impact:** LLMs may generate policies that release payments aggressively "because incoming payments are expected." But with deferred crediting, those inflows won't be available until next tick. The result: unnecessary queuing and deadline penalties.

**Recommendation:** Add a prominent callout in the domain explanation:

```
### ⚠️ DEFERRED CREDITING (Critical for RTGS Balance Management)
Incoming payments that settle at tick T do NOT increase your RTGS balance until tick T+1.

This means:
- You CANNOT release a payment "because an incoming is about to arrive"
- Your RTGS balance at tick T is determined by: opening balance - cumulative outflows + inflows from ticks 0..T-1
- In tight liquidity, hold payments until incoming funds are CONFIRMED (settled in a previous tick)
- The balance field reflects your CURRENT available RTGS balance — plan releases against THIS number

Strategy implication: In a liquidity crunch, the one-tick delay between receiving and using incoming funds
creates a "liquidity gap" that causes cascading queuing. Your policy must account for this gap.
```

**Implementation:** Modify `_build_domain_explanation_base()` in `system_prompt_builder.py`. The `deferred_crediting` flag is already available in the scenario config.

---

### Gap 4: Optimization Guidance Doesn't Diagnose the Crunch Tradeoff

**Problem:** The current `_build_optimization_guidance()` method checks if individual cost categories exceed 40% and gives independent advice: "HIGH DELAY COSTS → release earlier" or "HIGH LIQUIDITY OPPORTUNITY COST → lower fraction." But in a crunch, these are *opposing forces* — the classic tradeoff. The LLM needs to understand it's in a tension, not that two independent things are wrong.

More fundamentally: the guidance never explains that the **RTGS balance is the bottleneck**. It talks about costs but not about the mechanism that generates them.

**Impact:** The LLM oscillates: it lowers the fraction (reducing opportunity cost), then sees delay costs spike, raises the fraction, sees opportunity costs spike again. It never converges because it's treating symptoms rather than the underlying balance dynamics.

**Recommendation:** Detect the crunch tradeoff pattern and provide integrated guidance:

```python
# In _build_optimization_guidance():
if delay_pct > 20 and liquidity_opp_pct > 20:
    guidance.append(
        "⚡ **RTGS BALANCE TRADEOFF DETECTED**\n"
        "   You're paying significant costs in both liquidity opportunity (idle capital) "
        "and delays (queued payments). This is the classic liquidity crunch tradeoff.\n\n"
        "   The root cause is your RTGS settlement balance: committing too much means "
        "paying for idle liquidity; committing too little means payments can't settle "
        "when your balance runs low.\n\n"
        "   **Don't just adjust initial_liquidity_fraction.** Instead:\n"
        "   - Use the payment tree to CONDITION releases on your current balance\n"
        "     (e.g., only release when balance > amount + safety buffer)\n"
        "   - Use the bank tree to set per-tick release budgets that pace outflows\n"
        "   - Consider the balance trajectory: hold payments in early ticks when\n"
        "     inflows haven't arrived yet (deferred crediting), release more aggressively\n"
        "     later when incoming payments have replenished your balance"
    )
```

---

### Gap 5: Bank Tree Composition Not Explained

**Problem:** The system prompt describes each tree type independently:
- "bank_tree: Bank-level decisions (once per tick)"
- "payment_tree: Decides what to do with each transaction"

It never explains how they *compose*. The bank tree can use `SetReleaseBudget` to set a per-tick spending cap that the payment tree reads via `release_budget_remaining`. This is the primary mechanism for sophisticated intraday liquidity management — pacing outflows to match RTGS balance dynamics.

**Impact:** As Stefan observed, LLMs treat the bank tree as irrelevant. They optimize the payment tree (per-transaction triage) and `initial_liquidity_fraction` (a single number). The bank tree → payment tree composition that would enable release budgeting, counterparty-targeted strategies, and state-based mode switching goes undiscovered.

**Recommendation:** Implement as a **configurable prompt block** (not a default). This gap is an experimental variable for the paper, not a bug to fix.

The key distinction (Dennis): **teach the tool, not the solution.** Instead of giving specific patterns ("Set budget to 50% of balance"), describe the capability:

```
### Tree Interaction Capabilities

The bank tree and payment tree interact through shared state:

- The bank tree's `SetReleaseBudget` action sets a per-tick spending limit.
  The payment tree can read `release_budget_remaining` to check how much budget
  remains for the current tick. This enables the bank tree to pace outflows
  based on the current RTGS balance.

- The bank tree's `SetStateRegister` action stores values in `bank_state_*` fields
  that the payment tree can read. This allows tick-level context to influence
  per-transaction decisions.

- The bank tree evaluates ONCE per tick (before any transactions). The payment tree
  evaluates for EACH pending transaction. This means bank-level decisions set the
  context that per-transaction decisions operate within.
```

Note: this describes *what the tools do*, not *how to use them strategically*. The LLM must discover the strategy.

**Experimental Design (Dennis):** Run experiments in two configurations:
1. **Baseline:** Gaps 1-3 implemented (balance context, trajectory, deferred crediting). Gap 5 OFF.
2. **Enhanced:** Gaps 1-3 + Gap 5 (tree composition capabilities described).

Three possible outcomes, all publishable:
- LLM discovers bank tree strategies with just balance context → emergent strategic reasoning
- LLM discovers them only with Gap 5 → LLMs need capability hints for structural search
- LLM doesn't discover them even with Gap 5 → LLMs are parameter optimizers, not strategy architects (confirms Stefan's observation)

**Implementation:** Add as a toggleable prompt block in `_build_policy_architecture()` in `system_prompt_builder.py`, controlled by experiment config. The prompt block infrastructure from the refactor already supports this.

---

### Gap 6: No Worst-Case Analysis for Stochastic Scenarios

**Problem:** The LLM sees one representative simulation trace. In stochastic scenarios (like exp2 with Poisson arrivals), variance is the whole story. The best seed might have lucky inflow timing; the worst seed might be a disaster with drought periods that cause cascading failures.

The cost breakdown shows best/worst/average costs, but without a *trace* from the worst case, the LLM can't learn what went wrong or design policies that are robust to unlucky draws.

**Impact:** The LLM optimizes for the sample it sees. If the representative seed has relatively even inflow/outflow timing, the LLM won't discover that its policy fails catastrophically when 3-4 ticks pass with no incoming payments (a plausible Poisson outcome).

**Recommendation:** Add a condensed worst-case summary:

```
### Worst-Case Seed Analysis (Seed #99, Cost: $180,000)

Critical failure points:
1. Ticks 3-6: No incoming payments (Poisson drought)
   → RTGS balance dropped from $245,000 to $12,000
   → 6 payments queued simultaneously
2. Tick 7: 3 payments passed deadline → $150,000 in penalties
3. Tick 11: 1 payment still unsettled at EOD → $100,000 EOD penalty

Lesson: Policy must survive 3-4 tick drought periods with no inflows.
Consider: Higher initial_liquidity_fraction OR conditional holding when
balance drops below a safety threshold.
```

**Implementation:** The bootstrap evaluation already runs multiple seeds. Extract critical moments (balance minimums, deadline breaches, EOD penalties) from the worst seed and format as a condensed narrative. This could be done in the `_build_cost_breakdown_section` or a new section.

---

### Gap 7: No Reference Cost Bounds

**Problem:** The LLM has no anchor for what cost levels are achievable. Is $50,000 good or terrible? Without a reference, it can't calibrate how aggressively to optimize.

**Impact:** The LLM may stop optimizing prematurely ("costs are declining, this seems fine") or make overly aggressive changes ("costs are still high, I need a completely different approach") without knowing where the theoretical optimum lies.

**Recommendation:** Provide cost reference points when computable:

```
### Cost Reference Points
- Liquidity cost floor: $83/tick × 12 ticks × optimal_fraction × pool = ~$X
  (minimum cost if all payments settled instantly)
- FIFO baseline: ~$Y (releasing all payments immediately with fraction=1.0)
- Current policy: $Z
- Theoretical minimum depends on payment draw — stochastic lower bound is not zero
```

**Implementation:** The FIFO baseline could be computed from a single simulation run with a trivial policy. The liquidity cost floor is computable from the cost rates and pool size. These could be precomputed and injected into the prompt.

---

## Priority Matrix

| # | Gap | Priority | Effort | Impact on Crunch Discovery | Implementation |
|---|-----|----------|--------|---------------------------|----------------|
| 1 | RTGS balance context | 🔴 HIGH | Low | LLM can reason quantitatively about fraction vs demand | Implement now |
| 2 | Balance trajectory | 🔴 HIGH | Medium | LLM sees the crunch moment directly | Implement now |
| 3 | Deferred crediting emphasis | 🔴 HIGH | Low | Prevents naive "wait for inflows" strategies | Implement now |
| 5 | Bank tree composition | 🟡 MED | Low | Enables multi-lever strategy discovery | Configurable prompt block — experimental variable |
| 4 | Crunch tradeoff guidance | 🟡 MED | Low | Better diagnostic messaging for oscillating costs | Implement after Gaps 1-3 |
| 6 | Worst-case analysis | 🟡 MED | Medium | Robustness across stochastic draws | Implement after Gaps 1-3 |
| 7 | Reference cost bounds | 🟢 LOW | Medium | Calibration anchor for optimization | Later |

**Rationale for priority change (Dennis):** Gap 5 moved above Gap 4 because it addresses a structural problem (LLM doesn't know the bank tree is a strategic lever), while Gap 4 is better diagnostic messaging for a problem the LLM already sees. Gap 5 enables a *category of solutions* that currently can't be discovered.

---

## Relationship to Stefan's Observations

Stefan identified three key findings:

1. **Individual cost optimization → free-rider dynamics.** The prompts don't address this because it's a property of the objective function, not the prompts. However, Gap 1 (balance context) would help LLMs understand *why* posting less liquidity is individually rational even as settlement degrades.

2. **Parameter-space vs structural-space exploration.** Gaps 4 and 5 directly address this. The current prompts present optimization as "adjust these numbers." The recommended changes frame it as "compose these levers" — bank tree budgeting + payment tree conditioning + liquidity fraction.

3. **Bank tree as strategic gap.** Gap 5 is the key experimental variable. Rather than simply fixing the prompts, we use the presence/absence of tree composition guidance as an independent variable to measure LLM strategic capability.

### Experimental Design

**Phase 1: Fix information deficits (Gaps 1-3)**
Implement balance context, balance trajectory (with available liquidity column), and deferred crediting emphasis. These are not "hints" — they're data the agent needs to reason about liquidity. Run baseline experiments with these fixes.

**Phase 2: Test structural guidance (Gap 5 as variable)**
Run the same experiments with Gap 5 enabled as a configurable prompt block. Compare bank tree usage, strategy diversity, and cost outcomes.

**Three publishable outcomes:**
- *Emergent composition:* LLMs discover bank tree strategies with just balance context (Gaps 1-3). Finding: given adequate state information, LLMs can perform structural search.
- *Guided composition:* LLMs discover bank tree strategies only with capability descriptions (Gap 5). Finding: LLMs can use tools they're told about but don't discover tools autonomously.
- *No composition:* LLMs don't discover bank tree strategies even with Gap 5. Finding: confirms Stefan's observation — LLMs are parameter optimizers within templates, not strategy architects. This is the strongest result for the paper.

All three outcomes support the paper's contribution. The experimental design makes the prompt improvements serve the research rather than just improve the product.

---

## Implementation Notes

### Files to Modify

1. `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py`
   - Gap 3: Add deferred crediting section to `_build_domain_explanation_base()`
   - Gap 5: Add tree composition section to `_build_policy_architecture()`

2. `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py`
   - Gap 1: New `_build_liquidity_context()` section
   - Gap 2: New `_build_balance_trajectory()` section
   - Gap 4: Enhance `_build_optimization_guidance()` with crunch detection
   - Gap 6: New `_build_worst_case_analysis()` section
   - Gap 7: New `_build_reference_bounds()` section

3. `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py`
   - Add fields to `SingleAgentContext`: `liquidity_pool`, `expected_daily_demand`, `balance_trajectory`, `worst_seed_critical_moments`

4. `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py`
   - New function: `extract_balance_trajectory()` — post-process events into per-tick balance summary

5. Callers (experiment runner, web streaming optimizer)
   - Pass additional context data when building prompts

### Data Availability

All recommended data is either:
- **Already computed** by the engine (balance, queue sizes, settlement events)
- **Derivable** from existing config (pool size, arrival rates, cost rates)
- **Available from bootstrap** (worst seed trace, multi-seed cost distribution)

No engine changes required. This is purely a prompt engineering + context building effort.
