"""Methods section for web version."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_methods(provider: DataProvider) -> str:
    """Generate the methods/framework section in blog style."""
    _ = provider

    return """## The Framework

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
"""
