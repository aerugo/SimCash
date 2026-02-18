# UX Review: SimCash Platform — Bank of Canada Researcher Persona

**Date:** 2026-02-18
**Persona:** Dr. Sarah Chen, Senior Researcher, Payments and Settlements Department, Bank of Canada
**Goal:** Evaluate whether a payments systems researcher could use SimCash to design and run experiments on RTGS liquidity coordination, build custom scenarios modeling Canadian interbank payments, and interpret the results with confidence.
**Method:** Full walkthrough of all platform sections, building a custom 5-bank Canadian LVTS scenario, running experiments with starting policies, and assessing the complete research workflow.

---

## Executive Summary

SimCash is an impressive research tool with a genuinely novel approach — using LLM agents to explore RTGS coordination games. The core simulation engine produces plausible results, and the multi-day policy optimization loop is convincing. However, the platform currently assumes significant prior knowledge of both RTGS systems and the SimCash engine specifically. A researcher would need 30-60 minutes of exploration before feeling confident enough to design experiments. Key gaps: insufficient onboarding, opaque terminology, and several schema mismatches between what the UI suggests and what the engine actually accepts.

**Overall rating: 7/10 for a technical researcher, 4/10 for a general audience.**

---

## 1. First Impressions — Landing Page (Setup Tab)

### What Works
- **Four wayfinding cards** (Explore Scenarios, Policy Library, Build Your Own, Documentation) provide clear entry points for different research goals
- **Scenario cards** with metadata badges (ticks, banks, cost parameters) give quick comparisons
- **Cost parameter tooltips** (💰 83 bps, ⏱ 0.2/¢/tick, ⚠️ $500) explain what each number means on hover — excellent for learning
- **Dark mode** is comfortable for extended research sessions

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F1.1 | **Title is generic** | P2 | "Payment System Simulator" doesn't convey the AI coordination game angle. Consider: "SimCash — AI Agents Learn to Play the Liquidity Game" |
| F1.2 | **"How It Works" collapsed by default** | P1 | This is critical context for first-time users. A researcher landing here needs to immediately understand: What is this? What's the game? What will I see? It should be expanded on first visit. |
| F1.3 | **Subtitle is vague** | P2 | "Watch AI agents make real-time decisions about liquidity allocation and payment timing" — *real-time* is misleading (it's simulated). Suggest: "Watch AI agents learn to optimize liquidity strategies in a simulated RTGS system" |
| F1.4 | **No research context** | P1 | No mention of the BIS paper, the coordination game framework, or why this matters. A researcher needs to see academic credibility immediately. Consider a "Based on BIS Working Paper 1310" badge. |
| F1.5 | **"Mock Mode (no API costs)"** is confusing | P1 | What's the difference? Is mock mode fake? Does it produce valid results? The label implies the non-mock mode costs money — alarming for a researcher exploring the tool. Rename to "Simulated AI" vs "LLM-Powered AI" with clear explanations. |
| F1.6 | **"Policy Complexity: Full power"** is jargon | P2 | What does "Full — all actions, fields, parameters" mean? A researcher needs to understand what constraint levels mean for experimental validity. Add a "What's this?" link. |
| F1.7 | **No suggested first experiment** | P1 | A "Quick Start" button or guided first run would dramatically reduce time-to-insight. "Run your first experiment in 30 seconds" → select 2 Banks, 12 Ticks → auto-run 5 days → show results. |

---

## 2. Scenario Library

### What Works
- **18 scenarios** with consistent metadata cards
- **Category filters** (Crisis & Stress, Paper Experiments, LSM Exploration, Custom) map to research interests
- **Difficulty badges** (beginner/intermediate/advanced) help self-select
- **Feature tags** (crisis, lsm, multi-day, stochastic, priority) enable filtering by research question

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F2.1 | **Descriptions are developer-focused** | P2 | "Castro Experiment 2 baseline. Stochastic arrivals over 12 periods." — a researcher needs: "Replicates the baseline experiment from Castro et al. (2025) Section 4.2. Tests whether AI agents converge to the same ~8% liquidity fraction found in the BIS paper." |
| F2.2 | **No "Run this scenario" button** | P1 | Clicking a scenario card shows details but doesn't offer a direct path to launching it. Researcher has to mentally note the scenario, go back to Setup, find it in the list, and configure settings. |
| F2.3 | **No scenario comparison view** | P2 | Can't see two scenarios side-by-side. For research, comparing parameter variations is essential. |
| F2.4 | **Advanced scenarios (25-day) have caveats not shown** | P2 | The TARGET2 25-day scenarios run all 2500 ticks in one game-day, which may surprise researchers expecting day-by-day progression. |
| F2.5 | **No search** | P2 | With 18 scenarios it's manageable, but text search would help find specific configurations. |

---

## 3. Policy Library

### What Works
- **29 policies** covering the full spectrum from simple FIFO to complex adaptive strategies
- **Complexity badges** (simple/moderate/complex) with node counts
- **Action tags** (Hold, Release, PostCollateral, Split, etc.) show at a glance what each policy does
- Good variety — aggressive, conservative, deadline-aware, liquidity-splitting strategies

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F3.1 | **No visual decision tree** | P1 | Policies are the core research object, but there's no visual representation. Clicking a policy should show a tree diagram (boxes and arrows), not just a JSON dump. This is the #1 most impactful missing feature. |
| F3.2 | **No "What does this policy do?" plain-English summary** | P1 | "Balanced Cost Optimizer V1" → what tradeoffs does it make? When does it hold vs release? A natural-language summary would make policies accessible to non-engineers. |
| F3.3 | **No policy comparison** | P2 | Can't select two policies and see differences highlighted. Essential for research. |
| F3.4 | **fraction not prominently displayed** | P2 | The `initial_liquidity_fraction` is arguably the most important parameter, but it's buried in the JSON. Show it prominently on each card. |

---

## 4. Create Tab — Scenario Editor

### What Works
- **Form + YAML dual mode** is excellent — structured editing for beginners, raw YAML for power users
- **Live validation** with clear error messages
- **Validation summary** (agents, ticks, cost parameters, features) gives immediate feedback
- **Event Timeline Builder** with visual timeline is innovative — placing events on a tick axis is intuitive
- **Agent management** (add/remove, counterparty weights, arrival config) covers all parameters
- **Template dropdown** for starting from existing scenarios
- **Game Settings panel** integrated with starting policies — can configure and launch from one place

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F4.1 | **Form → YAML `deadline_range` indentation bug** | P0 | When the Form generates YAML, `deadline_range` is placed at the agent level instead of inside `arrival_config`. This causes validation failure. Researcher builds a scenario in Form mode, switches to YAML to fine-tune, and gets mysterious errors. |
| F4.2 | **No field labels for agent parameters** | P1 | In the Agent section, numeric inputs have no visible labels. What's "3" and "8"? Those are deadline_range min/max, but the Form doesn't say so. Every field needs a label. |
| F4.3 | **Cost parameter display bug** | P1 | Validation summary shows EOD Penalty as "$1,500" when the actual value is 150,000 cents ($1,500.00). The display divides by 100 without explaining the unit. All monetary values should consistently show as dollars with a "$" prefix. |
| F4.4 | **No "What does this field mean?" tooltips** | P1 | Cost Rates section: What's "Liquidity Cost (bps/tick)"? New users need hover tooltips explaining each parameter in plain English with economic interpretation. |
| F4.5 | **LSM Config options are engineer-focused** | P2 | "Enable", "Bilateral", "Cycles" checkboxes — but what do bilateral offsetting and cycle detection mean? No explanation provided. |
| F4.6 | **Event builder field names don't match user expectations** | P1 | A researcher would write `sender`/`receiver` but the engine needs `from_agent`/`to_agent`. The Form handles this, but switching to YAML is a trap. Need better error messages: "Did you mean `from_agent`?" |
| F4.7 | **Event schedule type `OneTime` not discoverable** | P1 | In YAML mode, a researcher would write `type: fixed_tick` but the engine needs `type: OneTime`. The Form handles this, but hand-editing YAML requires knowing the exact schema. |
| F4.8 | **No "duplicate agent" button** | P2 | When building a 5-bank scenario, you have to configure each agent from scratch. A "Duplicate" button would save time and reduce errors. |
| F4.9 | **Counterparty weights must be manually balanced** | P2 | When adding a 3rd agent, all existing agents' counterparty weights need updating. The Form doesn't auto-adjust or warn about weights not summing to 1.0. |
| F4.10 | **No scenario save without launch** | P2 | "Save & Launch" is the only save option. Sometimes you want to save a scenario for later without running it immediately. |

---

## 5. Create Tab — Policy Editor

### What Works
- **JSON editor** with template and library dropdowns
- **Validate, Save, and Test Policy** buttons
- **"Load from library"** dropdown loads existing policies for modification

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F5.1 | **No visual tree builder** | P1 | Editing raw JSON decision trees is error-prone and opaque. A drag-and-drop visual builder (condition nodes → action nodes) would make policy design accessible to researchers who aren't software engineers. |
| F5.2 | **"Test Policy" button has no explanation** | P2 | What does testing a policy do? Does it run a simulation? Against what scenario? The button exists but offers no context. |
| F5.3 | **No policy documentation in editor** | P1 | When building a policy tree, what actions are available? What conditions can you use? What fields are valid? Need a reference panel or autocomplete. |
| F5.4 | **Template dropdown lacks descriptions** | P2 | Template names like "Conditional Hold/Release" don't explain what they demonstrate. |

---

## 6. Game View — Running Experiments

### What Works
- **Game Complete banner** with key metrics (Day 1 cost, Final cost, Cost Reduction %, Final Fractions) — immediate summary
- **Liquidity Fraction Evolution chart** — the most important visualization, shows convergence clearly
- **Cost Evolution chart** — validates that lower fractions actually reduce costs
- **Day Timeline** with numbered buttons — easy to navigate between days
- **Per-agent cost breakdown** (Liquidity, Delay, Penalty, Total) on each day
- **Balance chart** showing intraday liquidity dynamics
- **Policy History** with full trajectory — shows the learning path
- **Day Events summary** with event type counts
- **Auto-run** completes quickly (~15 seconds for 10 days of 3-bank scenario in mock mode)

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F6.1 | **No explanation of what happened** | P1 | After a game completes, there's no narrative summary. "Banks converged to ~12% liquidity fraction, reducing system costs by 87%. The symmetric scenario produced near-identical strategies across all banks, consistent with Nash equilibrium predictions." This is what a researcher needs. |
| F6.2 | **Cost Reduction arrow direction misleading** | P1 | Shows "↓ 87.4%" in green — the arrow suggests decrease, which is good, but the color coding could be clearer. Some researchers might read "↓" as "bad" (costs went down = less business activity?). |
| F6.3 | **No settlement rate metric** | P1 | How many payments settled on time vs. missed deadline? This is THE key metric for a payments researcher. Settlement rate should be prominently displayed alongside cost. |
| F6.4 | **Policy History only shows fraction** | P2 | The full policy includes a decision tree, but only `initial_liquidity_fraction` is shown. If agents are building complex trees (Hold when low balance, Release when flush), that's invisible. |
| F6.5 | **"Latest Reasoning" section is empty in mock mode** | P1 | This is the most interesting part for a researcher — seeing HOW the AI thinks about the tradeoffs. In mock mode, it's blank. Even mock mode should show simulated reasoning to demonstrate the concept. |
| F6.6 | **No data export** | P1 | Can't export results as CSV, JSON, or PDF. A researcher needs to take this data into their own analysis pipeline (R, Python, Stata). |
| F6.7 | **No "re-run with different seed" button** | P2 | Statistical validity requires multiple runs. Currently have to go back to Setup, change nothing, and re-run. |
| F6.8 | **Day 10 events show "16 DeferredCreditApplied"** | P2 | Great that events are counted, but what does DeferredCreditApplied mean? Event type names are engine jargon. Need plain-English labels. |
| F6.9 | **No comparison to baseline** | P1 | "Cost reduced by 87%" compared to what? Day 1? FIFO policy? Theoretical optimum? A researcher needs a clear baseline: "vs. FIFO baseline: X%, vs. theoretical optimum: Y%". |

---

## 7. Documentation

### What Works
- **Well-structured sidebar** with Guides, Advanced Topics, Blog Posts, Reference
- **Overview page** clearly explains the coordination game problem
- **Key Insight callout** about stability vs optimality is genuinely interesting
- **Academic context** (BIS Working Paper, Korinek 2025) establishes credibility
- **Blog posts** provide accessible narrative entries

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F7.1 | **Says "powered by GPT-5.2"** | P0 | Outdated — now uses Gemini. Must be corrected; academic credibility depends on accuracy. |
| F7.2 | **No quick-start guide** | P1 | First page should be "Run your first experiment in 5 minutes" with screenshots. Currently jumps straight into theory. |
| F7.3 | **No YAML/JSON schema reference** | P1 | Researchers building custom scenarios in YAML need a field-by-field reference with valid values, types, and examples. Currently have to guess and rely on validation errors. |
| F7.4 | **Hardcoded in TSX** | P2 | Docs are embedded in React components, making them hard to update and impossible to search. Should be Markdown files served by the backend. |
| F7.5 | **No API documentation** | P2 | Researchers who want to script experiments (run 100 scenarios with varying parameters) need API docs. The backend has FastAPI /docs, but it's not linked. |

---

## 8. Starting Policies — The Feature That Bridges Theory and Practice

### What Works
- **Per-agent policy selection** with dropdowns showing all 29 library policies
- **Fraction slider** (0.00-1.00) for fine-tuning liquidity commitment
- **Auto-fill from library** — selecting "Aggressive Market Maker" auto-sets fraction to 0.35
- **"Apply to all" bulk selector** for symmetric experiments
- **Dynamic banner** in Game View showing actual starting fractions (BANK_A=0.35, BANK_B=1.00, BANK_C=0.70)

### Issues

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| F8.1 | **No explanation of what starting policies DO** | P1 | A researcher needs to understand: "Starting policies set each agent's initial strategy for Day 1. The AI optimizer will then try to improve upon these. Different starting points may lead to different equilibria." |
| F8.2 | **Policy names in dropdown are not descriptive enough** | P2 | "Aggressive Market Maker V1 (frac=0.35)" — what makes it aggressive? A one-line behavioral summary would help: "Releases payments immediately, commits minimal liquidity" |
| F8.3 | **No visual preview of selected policy** | P2 | After selecting a policy from the dropdown, can't see what it does without going to the Policy Library tab. |

---

## 9. Onboarding & Learning Curve

### Current State
1. **No guided onboarding** — researcher lands on the page and must self-discover
2. **No progressive disclosure** — all options visible at once (scenario list + game settings + starting policies + mock mode)
3. **No contextual help** — no "?" icons, no inline explanations
4. **Error messages are engine-level** — "Field required [type=missing, input_value=...]" instead of "The 'deadline_range' field must be inside 'arrival_config', not at the agent level"

### Recommended Onboarding Flow
1. **First visit**: Show expanded "How It Works" with a "Try It Now" button that auto-selects "2 Banks, 12 Ticks" and launches a 5-day mock game
2. **During first game**: Annotated UI — callout bubbles explaining each section ("This shows how much liquidity each bank committed", "Watch the costs decrease as agents learn")
3. **After first game**: Prompt to explore — "Want to try a more complex scenario? Check the Scenario Library" / "Want to build your own? Use the Scenario Editor"
4. **Progressive complexity**: Default to "Simple" policy complexity for first-time users, show "Unlock Full Power" after completing a game

---

## 10. End-to-End Experiment: Canadian LVTS Stress Test

### What I Tried
Built a 5-bank scenario modeling Canada's Large Value Transfer System:
- **RBC** ($8M pool, 3.5 payments/tick) — dominant player
- **TD** ($7M pool, 3.0 payments/tick) — second largest
- **BMO** ($5M pool, 2.5 payments/tick) — mid-tier
- **SCOTIA** ($5M pool, 2.5 payments/tick) — mid-tier
- **NATIONAL** ($2M pool, 1.5 payments/tick) — smallest player
- LSM enabled, high penalties, 2 stress events (rate spike + forced transfer)
- Asymmetric starting policies: RBC=Aggressive(0.35), TD=Balanced(0.50), BMO/SCOTIA=Cautious(0.70), NATIONAL=Conservative(0.80)

### What Happened
- Game ran 10 days (mock mode), **74% cost reduction**
- Smaller banks (BMO 0.104, SCOTIA 0.090) optimized more aggressively than larger banks (RBC 0.197) — economically plausible
- All banks converged to low fractions with zero penalties by Day 10

### Friction Points
1. Had to write YAML by hand because the Form has bugs (deadline_range indentation, LSM field names)
2. `sender`/`receiver` → `from_agent`/`to_agent` and `fixed_tick` → `OneTime` — three tries to get validation passing
3. Starting policies didn't pass through Save & Launch from the Create tab (fixed during this session)
4. No way to name the game or add notes for later reference

---

## 11. Priority Recommendations

### Must Fix (P0)
1. **Fix docs "GPT-5.2" reference** — factual error undermining credibility
2. **Fix Form→YAML deadline_range bug** — breaks the primary scenario creation workflow

### Should Fix (P1) — High Impact
3. **Add quick-start guided first experiment** — reduce time-to-insight from 30 min to 2 min
4. **Add settlement rate metric** to Game View — THE metric a payments researcher cares about
5. **Add plain-English game summary** after completion — narrative interpretation of results
6. **Add YAML/JSON schema reference** to Docs — field-by-field with examples
7. **Add data export** (CSV/JSON) — enable downstream analysis
8. **Visual decision tree renderer** for policies — make the core research object visible
9. **"Run this scenario" button** on Scenario Library cards — reduce clicks to start experimenting
10. **Explain mock mode vs LLM mode** clearly — researchers need to know what's real
11. **Add field labels to Form agent parameters** — currently unlabeled number inputs

### Nice to Have (P2) — Polish
12. Policy comparison view
13. Duplicate agent button in Form
14. Scenario search
15. Event type plain-English labels
16. Re-run with different seed button
17. Policy behavioral summaries in dropdowns

---

## 12. Competitive Assessment

### Strengths vs Existing Tools
- **Unique**: No other tool combines RTGS simulation + LLM policy optimization + interactive web sandbox
- **Engine quality**: Rust-based simulation is fast, deterministic, and produces plausible results
- **Research validity**: Based on published BIS methodology, not just a toy demo
- **Multi-agent dynamics**: Watching independent agents converge (or fail to) is genuinely novel

### Risks
- **Schema complexity**: The gap between what a researcher expects and what the engine accepts is the #1 adoption barrier
- **Mock mode ambiguity**: If researchers can't tell what's "real" vs "simulated", results lose credibility
- **No batch experiments**: Academic research requires parameter sweeps (100 runs × 10 seeds). Currently must run one-at-a-time through the UI.

---

## Appendix: Test Environment
- **URL**: http://localhost:5173 (local development)
- **Backend**: SimCash FastAPI on port 8642
- **Mode**: SIMCASH_AUTH_DISABLED=true, SIMCASH_STORAGE=local
- **LLM**: Mock mode (no real LLM calls)
- **Browser**: Chromium via OpenClaw browser automation
