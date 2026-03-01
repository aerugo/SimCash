# LLM Optimization in Simulated RTGS Systems: An Exploratory Campaign

*Stefan Hommes & Hugi Aegisberg — Q1 2026*

---

## Motivation

Real-time gross settlement (RTGS) systems are the backbone of modern financial infrastructure. Systems like Lynx (Canada), Fedwire (United States), and TARGET2 (Euro area) process trillions of dollars in interbank payments daily, settling each transaction individually and in real time. The core operational challenge is **intraday liquidity management**: banks must decide how much cash to commit to the settlement process at the start of each day, and how to prioritize payments as the day unfolds.

This is a strategic problem. A bank that commits too little liquidity saves on holding costs but risks delaying its own payments — and starving counterparties of the incoming liquidity they need. A bank that commits too much pays unnecessarily for idle balances. The socially optimal outcome requires coordination: all participants contributing sufficient liquidity to keep the system flowing. But each individual bank has an incentive to hold back and free-ride on others' contributions. Most RTGS systems include **throughput guidelines** — soft or hard requirements that banks settle a minimum fraction of their payments by certain times of day — precisely because individual incentives do not align with system-wide efficiency.

### The AI Proposition

Recent work has explored whether artificial intelligence can assist with intraday liquidity management. A Bank of Canada Staff Working Paper (SWP 2025-35, jointly published as BIS Working Paper 1310) tested whether ChatGPT's reasoning model could perform high-level cash management in a simulated wholesale payment system. The results were striking: even without domain-specific training, the AI agent closely replicated prudential cash-management practices, maintaining precautionary liquidity buffers and dynamically prioritizing payments under tight constraints.

That study examined a **single** AI agent managing the system's liquidity. A natural follow-up question is what happens when **every** bank has its own AI agent — moving from single-agent optimization to multi-agent strategic interaction. Korinek (2025) provides a useful framework for understanding these AI agent capabilities, distinguishing between traditional LLMs (System 1 pattern recognition), reasoning models (System 2 deliberation), and agentic systems (autonomous tool-using agents operating in ReAct loops).

### This Paper

We report results from an **exploratory campaign** of 132 experiments using SimCash, an open-source RTGS simulation platform. We tested three large language models across 10 scenarios spanning different network sizes, stress conditions, and temporal dynamics. The goal was not to prove specific hypotheses but to **map the landscape**: under what conditions does LLM optimization help, where does it fail, and what patterns emerge that warrant further investigation?

The campaign produced several observations worth reporting. LLM optimization substantially reduced costs in single-day scenarios with 2–4 banks. In multi-day scenarios, LLM optimization produced higher costs and lower settlement rates than the unoptimized baseline. However, the simple and multi-day scenarios differ in at least eight dimensions simultaneously — number of days, optimization method, bank heterogeneity, LSM configuration, cost structure, liquidity pools, scenario events, and baseline difficulty — making it impossible to attribute the performance difference to any single factor. We document these confounds explicitly and propose controlled follow-up experiments to disentangle them.

We also observed that prompt engineering with explicit constraints improved LLM behavior on a simple scenario (Castro Exp2, 2 banks), and that the less capable model (Gemini 2.5 Flash) generally produced better system-wide outcomes than the more capable one (Gemini 2.5 Pro), though we refrain from claiming a causal mechanism for this pattern.

## Experimental Platform

### SimCash

SimCash is an open-source RTGS simulation platform (Aegisberg, 2025) that models interbank payment networks with configurable numbers of banks, payment types, liquidity conditions, and multi-day dynamics. The simulation engine (Rust) processes payments deterministically given a fixed seed, while a Python orchestration layer manages iterative policy optimization.

Each bank operates according to a **policy** consisting of:
- An **initial liquidity fraction** — how much of the bank's available funds to commit at the start of each day
- A **payment decision tree** — rules for when to release, delay, hold, or split individual payments based on contextual variables (queue depth, available balance, time remaining, payment urgency)
- A **bank-level decision tree** — rules for system-wide actions (requesting additional liquidity, adjusting reserves)

The optimization process uses a **bootstrap paired evaluation** framework: a candidate policy is compared to the incumbent across multiple simulation runs, and is adopted only if it produces statistically significant cost improvement.

### Models Tested

| Model | Description | Provider | Reasoning |
|-------|-------------|----------|-----------|
| **Gemini 2.5 Flash** | Mid-tier frontier model | Google (Vertex AI) | Extended thinking (~4k tokens) |
| **Gemini 2.5 Pro** | Top-tier frontier model | Google (Vertex AI) | Extended thinking (~8k tokens) |
| **GLM-4.7** | Open-weight model | Zhipu AI (Vertex AI) | Standard generation |

### Scenarios

We designed 10 scenarios spanning a range of network sizes, stress conditions, and temporal dynamics:

**Simple scenarios (1 simulated day, 10 optimization rounds):**

| Scenario | Banks | Description |
|----------|-------|-------------|
| 2 Banks, 3 Types (`2b_3t`) | 2 | Minimal bilateral network |
| 2 Banks, Stress (`2b_stress`) | 2 | Bilateral under elevated payment pressure |
| 3 Banks, 6 Types (`3b_6t`) | 3 | Trilateral coordination |
| 4 Banks, 8 Types (`4b_8t`) | 4 | Medium network |
| Castro Exp2 (`castro_exp2`) | 2 | Replication of BIS/BoC paper setup |
| Lynx Day (`lynx_day`) | 4 | Calibrated to Bank of Canada's Lynx parameters |
| Liquidity Squeeze (`liquidity_squeeze`) | 2 | Mid-day liquidity drain |

**Multi-day scenarios (25 simulated days, 1 round with between-day optimization):**

| Scenario | Banks | Description |
|----------|-------|-------------|
| Periodic Shocks (`periodic_shocks`) | 4 | Recurring liquidity shocks every few days |
| Large Network (`large_network`) | 5 | Steady-state large interbank network |
| Lehman Month (`lehman_month`) | 6 | Calibrated to September 2008 crisis dynamics |

These two groups differ in multiple dimensions beyond bank count — see Discussion for a full accounting of confounds.

### Experiment Design

Each scenario was run with:
- **1 deterministic baseline** (FIFO policy, 0.5 liquidity fraction, no LLM optimization)
- **3 models × 3 independent runs** to capture variance from LLM stochasticity (the simulation itself is deterministic with seed 42)
- **v0.2 prompt engineering variants** (Castro Exp2 only): four conditions testing whether improved prompts can enhance LLM behavior — information provision (C1), settlement floor constraint (C2), strategy guidance (C3), and full compositional prompts (C4)

### Metrics

**Total system cost** is summed across all banks and all days. For simple scenarios, we report the converged last-day cost after iterative optimization. For multi-day scenarios, we sum per-day costs across all 25 days, as the simulation engine resets cost accumulators each day.

**Cumulative settlement rate** is the fraction of all arrived payments successfully settled across the entire simulation:

$$\text{Cumulative SR} = \frac{\sum_{\text{all days}} \text{total\_settled}}{\sum_{\text{all days}} \text{total\_arrived}}$$

This volume-weighted metric captures the full picture across multi-day runs — a day with 200 transactions weighs more than a day with 50, matching how regulators assess system performance.

### Data Integrity

During the campaign, we discovered and fixed a bug in the Python orchestration layer's cost delta computation (`_compute_cost_deltas()`) that produced incorrect feedback to the LLM optimizer in multi-day scenarios. All 38 affected experiments (multi-day scenarios with LLM optimization run before revision simcash-00168-v29) were quarantined and excluded from analysis. The 132 experiments reported here are all clean post-fix runs or single-day runs unaffected by the bug. Full documentation in `DATA-INTEGRITY.md`.
