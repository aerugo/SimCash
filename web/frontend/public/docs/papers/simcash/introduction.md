# Discovering Equilibrium-like Behavior with LLM Agents

*A Payment Systems Case Study* — **Hugi Aegisberg**

---

Can Large Language Models discover stable strategies through reasoning alone — without
knowing they're playing a game?

We gave LLM agents a real problem: manage liquidity in a payment system where holding
cash is expensive but running out causes settlement delays. Each agent sees only its own
costs and transactions — never what the other side is doing. Through 9
independent runs across 3 scenarios, these agents reliably converged to
stable policy profiles in an average of 22.1 iterations.

But here's the twist: **stability doesn't mean optimality**. In symmetric games, agents
consistently fell into coordination traps — Pareto-dominated outcomes where both sides
ended up worse off than where they started. The identity of the "free-rider" was determined
by whoever made the first aggressive move, not by any structural advantage.

Stochastic environments told a different story. With uncertain payment timing and bootstrap
policy evaluation, agents found near-symmetric allocations without the coordination
collapse seen in deterministic settings.

These results suggest LLM-based optimization can discover stable strategies without
explicit game theory, but also show that greedy, non-communicating agents reliably
converge to coordination traps — exactly what theory predicts for rational agents
without coordination mechanisms.

## What is SimCash?

Payment systems are where banks settle debts with each other in real-time. Every day,
trillions of dollars flow through systems like Fedwire (US), TARGET2 (EU), and Lynx
(Canada). Banks face a fundamental tradeoff: hold enough cash reserves to settle payments
quickly, or minimize idle capital and risk delays.

This is a game-theoretic problem. Your optimal strategy depends on what the other banks
do — if everyone holds plenty of cash, the system runs smoothly. If your counterparty
is cash-rich, you can free-ride with minimal reserves since their payments to you will
fund your outgoing obligations.

Traditional approaches use analytical game theory or reinforcement learning with neural
networks. We tried something different: **LLM agents that reason in natural language**
about their liquidity strategy, adjusting it iteration by iteration based on observed
costs — just like a human treasury manager would.

## Key Contributions

1. **SimCash Framework** — A hybrid Rust/Python simulator with LLM-based policy
   optimization under strict information isolation between agents

2. **Empirical Comparison** — Side-by-side comparison with game-theoretic predictions
   from Castro et al., revealing both alignment and systematic deviations

3. **Coordination Failure Analysis** — Demonstration that greedy, non-communicating
   LLM agents converge to stable but Pareto-dominated outcomes in symmetric games

4. **Bootstrap Evaluation** — A methodology for policy evaluation under stochastic
   transaction arrivals with fixed-environment assumptions

## The Framework

### Simulation Engine

SimCash runs a discrete-time simulation where:

- Time advances in **ticks** (atomic time units)
- Banks hold **balances** in settlement accounts
- **Transactions** arrive with amounts, counterparties, and deadlines
- Settlement follows **RTGS** (Real-Time Gross Settlement) rules — payments settle individually and immediately when the sender has sufficient funds

### Cost Model

Each bank's total cost is the sum of:

- **Liquidity cost** — proportional to reserves held (opportunity cost of idle capital)
- **Delay penalty** — accumulates per tick for unsettled transactions
- **End-of-day penalty** — large cost for transactions still unsettled at day's end

The tradeoff is clear: hold more cash → lower delay costs but higher liquidity costs.
Hold less cash → cheaper capital but risk settlement delays and penalties.

### How LLM Optimization Works

At each iteration:

1. **Context construction** — The agent receives its own policy, a filtered simulation
   trace (only its own transactions and balances), and its cost history
2. **LLM proposal** — The agent proposes a new `initial_liquidity_fraction` parameter
3. **Evaluation** — Run simulation(s) with the proposed policy
4. **Update** — Accept or reject based on mode-specific rules
5. **Convergence check** — Stop when policies stabilize

The critical design choice: **strict information isolation**. Each agent sees only its
own costs, its own transactions, and its own balance changes. It never sees the other
agent's strategy, costs, or balance. The only signal about counterparty behavior comes
from observing when incoming payments arrive — a realistic level of transparency in
actual RTGS systems.

### Two Evaluation Modes

**Deterministic-Temporal Mode** (Experiments 1 & 3):
- Fixed payment schedules, single simulation per iteration
- **Unconditional acceptance** — all proposed policies are accepted regardless of cost impact
- Convergence when both agents' liquidity fractions stabilize (≤5% change for 5 iterations)
- This identifies *stable profiles*, not optimal ones

**Bootstrap Mode** (Experiment 2):
- Stochastic transaction arrivals (Poisson process)
- Each iteration: run context simulation → bootstrap 50 resampled transaction schedules → evaluate old and new policy on identical samples
- **Risk-adjusted acceptance**: policy must show (1) lower mean cost, (2) statistically significant improvement, and (3) acceptable variance (CV ≤ 0.5)
- Convergence requires cost stability, no significant trend, and low regret over 5 iterations

### The Three Experiments

**Experiment 1: 2-Period Asymmetric** (Deterministic)
- 2 ticks per day, asymmetric payment demands
- Bank A sends less early; Bank B sends more early
- Theory predicts: A ≈ 0% liquidity (free-rider), B ≈ 20%

**Experiment 2: 12-Period Stochastic** (Bootstrap)
- 12 ticks per day, Poisson arrivals, LogNormal amounts
- Theory predicts: both agents in 10–30% range

**Experiment 3: 3-Period Symmetric** (Deterministic)
- 3 ticks per day, identical payment demands for both banks
- Theory predicts: symmetric allocation (~20% each)

Each experiment runs 3 independent passes to test reproducibility.

### LLM Configuration

- Model: `openai:gpt-5.2`
- Reasoning effort: `high`
- Temperature: 0.5
- Max iterations: 50 per pass
