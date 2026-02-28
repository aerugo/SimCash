# The Complexity Threshold: When AI Agents Fail at Payment Coordination

*Stefan Hommes & Hugi Aegisberg — Q1 2026*

---

## Motivation

Real-time gross settlement (RTGS) systems are the backbone of modern financial infrastructure. Systems like Lynx (Canada), Fedwire (United States), and TARGET2 (Euro area) process trillions of dollars in interbank payments daily, settling each transaction individually and in real time. The core operational challenge is **intraday liquidity management**: banks must decide how much cash to commit to the settlement process at the start of each day, and how to prioritize payments as the day unfolds.

This is a strategic problem. A bank that commits too little liquidity saves on holding costs but risks delaying its own payments — and starving counterparties of the incoming liquidity they need. A bank that commits too much pays unnecessarily for idle balances. The socially optimal outcome requires coordination: all participants contributing sufficient liquidity to keep the system flowing. But each individual bank has an incentive to hold back and free-ride on others' contributions.

Central banks have long recognized this tension. Most RTGS systems include **throughput guidelines** — soft or hard requirements that banks settle a minimum fraction of their payments by certain times of day. These guidelines exist precisely because individual incentives do not align with system-wide efficiency. The question of how to manage this tension sits at the intersection of mechanism design and operational policy.

### The AI Proposition

Recent work has explored whether artificial intelligence can assist with intraday liquidity management. Notably, a Bank of Canada Staff Working Paper (SWP 2025-35, jointly published as BIS Working Paper 1310) tested whether ChatGPT's reasoning model could perform high-level cash management in a simulated wholesale payment system. The results were striking: even without domain-specific training, the AI agent closely replicated prudential cash-management practices, maintaining precautionary liquidity buffers and dynamically prioritizing payments under tight constraints.

That study examined a **single** AI agent managing the system's liquidity. The natural next question — and the one this paper addresses — is what happens when you give **every** bank its own AI agent.

This is not merely a scaling question. Moving from one agent to many transforms the problem from optimization to strategic interaction. Each agent now faces not just the payment schedule but the emergent behavior of other agents' strategies. The system becomes a game.

### What We Found

We conducted a systematic experiment campaign using SimCash, an open-source RTGS simulation platform, testing three large language models across 10 scenarios of varying complexity. The campaign spanned 132 clean experiments.

The headline finding is a **complexity threshold**. Below approximately 4 banks, LLM optimization delivers substantial value: 55–86% cost reduction while maintaining near-perfect settlement rates. Above approximately 5 banks, LLM optimization produces **simultaneously** higher costs and lower settlement rates than a simple first-in-first-out (FIFO) baseline with no optimization at all.

This is not a trade-off between cost and settlement — it is pure value destruction. The AI agents, each individually optimizing for their bank's costs, collectively make the system worse on every metric. We characterize this as a **computational tragedy of the commons**: a classic common-pool resource problem instantiated in silico, where intraday liquidity is the shared resource and AI agents are the rational but uncoordinated extractors.

A second unexpected finding concerns model capability. Across complex scenarios, Gemini 2.5 Pro — the more capable model — consistently produces **worse** collective outcomes than Gemini 2.5 Flash. We call this the **smart free-rider effect**: a more capable reasoner is better at identifying opportunities to free-ride on others' liquidity, but this individually rational sophistication is precisely what makes the system worse.

## Related Work

### AI in Payment Systems

The application of AI to payment system operations is an emerging research area. Castro et al. (2023) introduced RTGS simulation environments for testing algorithmic payment strategies. The Bank of Canada/BIS collaboration (Bédard-Pagé et al., 2025) demonstrated single-agent LLM cash management. Korinek (2025) provides a comprehensive framework for understanding AI agent capabilities in economics research, distinguishing between traditional LLMs (System 1 pattern recognition), reasoning models (System 2 deliberation), and agentic systems (autonomous tool-using agents operating in ReAct loops).

Our work extends this literature from single-agent optimization to multi-agent strategic interaction — the setting that actually characterizes real RTGS operations.

### Multi-Agent Coordination Failures

The complexity threshold we document connects to a deep literature on coordination failures in game theory. Hardin's (1968) tragedy of the commons, the prisoner's dilemma, and the public goods provision problem all describe settings where individually rational behavior produces collectively suboptimal outcomes. Our contribution is demonstrating that general-purpose LLM agents, despite having no explicit game-theoretic training, naturally exhibit these failure modes when deployed as competing optimizers in a shared system.

The smart free-rider effect resonates with findings in algorithmic trading, where more sophisticated strategies can destabilize markets (Kirilenko et al., 2017), and in multi-agent reinforcement learning, where capable agents can learn to exploit shared resources more effectively (Leibo et al., 2017).

### Mechanism Design and RTGS

Central banks' use of throughput guidelines, penalty structures, and liquidity savings mechanisms in RTGS systems represents applied mechanism design — the engineering of rules and incentives to align individual behavior with collective goals. Our finding that explicit constraints (settlement floor requirements) outperform information provision in guiding AI agent behavior independently rediscovers the rationale for these regulatory instruments. This connects to the broader mechanism design literature (Myerson, 1981; Maskin, 2008) and its application to payment systems (Bech & Garratt, 2003).

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
| 4 Banks, 8 Types (`4b_8t`) | 4 | Medium network, transition zone |
| Castro Exp2 (`castro_exp2`) | 2 | Replication of BIS/BoC paper setup |
| Lynx Day (`lynx_day`) | 4 | Calibrated to Bank of Canada's Lynx parameters |
| Liquidity Squeeze (`liquidity_squeeze`) | 2 | Mid-day liquidity drain |

**Complex scenarios (25 simulated days, 1 round with between-day optimization):**

| Scenario | Banks | Description |
|----------|-------|-------------|
| Periodic Shocks (`periodic_shocks`) | 5 | Recurring liquidity shocks every few days |
| Large Network (`large_network`) | 5 | Steady-state large interbank network |
| Lehman Month (`lehman_month`) | 6 | Calibrated to September 2008 crisis dynamics |

### Experiment Design

Each scenario was run with:
- **1 deterministic baseline** (FIFO policy, 0.5 liquidity fraction, no LLM optimization)
- **3 models × 3 independent runs** to capture variance from LLM stochasticity (the simulation itself is deterministic with seed 42)
- **v0.2 prompt engineering variants** (Castro Exp2 only): four conditions testing whether improved prompts can enhance LLM behavior — information provision (C1), settlement floor constraint (C2), strategy guidance (C3), and full compositional prompts (C4)

### Metrics

**Total system cost** is summed across all banks and all days. For simple scenarios, we report the converged last-day cost after iterative optimization. For complex multi-day scenarios, we sum per-day costs across all 25 days, as the simulation engine resets cost accumulators each day.

**Cumulative settlement rate** is the fraction of all arrived payments successfully settled across the entire simulation:

$$\text{Cumulative SR} = \frac{\sum_{\text{all days}} \text{total\_settled}}{\sum_{\text{all days}} \text{total\_arrived}}$$

This volume-weighted metric captures the full picture across multi-day runs — a day with 200 transactions weighs more than a day with 50, matching how regulators assess system performance.

### Data Integrity

During the campaign, we discovered and fixed a bug in the Python orchestration layer's cost delta computation (`_compute_cost_deltas()`) that produced incorrect feedback to the LLM optimizer in multi-day scenarios. All 38 affected experiments (multi-day scenarios with LLM optimization run before revision simcash-00168-v29) were quarantined and excluded from analysis. The 132 experiments reported here are all clean post-fix runs or single-day runs unaffected by the bug. Full documentation in `DATA-INTEGRITY.md`.
