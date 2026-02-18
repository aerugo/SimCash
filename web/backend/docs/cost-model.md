# The Cost Model

*How banks are penalized — and why it matters*

The cost model creates the incentive structure that drives strategic behavior. It consists
of three primary costs, ordered by severity:

## 1. Liquidity Cost (r_c)

Proportional to committed funds per tick. Measured in basis points (bps). This represents
the opportunity cost of holding reserves in the settlement account rather than investing
them elsewhere.

```
cost = committed_balance × (bps / 10000) per tick
```

The rate depends on the scenario: Castro's r_c = 0.1 is divided by ticks per day,
giving 500 bps/tick (2-tick scenarios), 333 bps/tick (3-tick), or 83 bps/tick (12-tick).
Always the cheapest cost — you prefer committing liquidity over the alternatives.

## 2. Delay Cost (r_d)

Charged per cent of unsettled payment per tick. Represents the cost of failing to
settle a payment on time — client dissatisfaction, SLA penalties, reputational damage.

```
cost = unsettled_amount × rate per tick
```

Castro baseline: r_d = 0.2 per cent per tick. More expensive than liquidity cost.

## 3. Deadline Penalty

A flat fee for each payment that misses its individual deadline (each payment has
a specific tick by which it should settle). Represents regulatory penalties or failed obligations.

```
cost = penalty_amount per unsettled payment at its deadline
```

Default: $500 (50,000 cents) per payment.

## 4. End-of-Day Penalty

A separate large penalty for any payment still unsettled when the day ends.
Default: $1,000 (100,000 cents). This creates a hard deadline for all payments.

## The Ordering Constraint

> ⚠️ **r_c < r_d < r_b** — Castro et al. require
> this ordering: liquidity cost < delay cost < borrowing/penalty cost. Banks should
> always prefer committing liquidity (cheapest) over delaying payments (medium) over missing
> deadlines entirely (most expensive). If this ordering is violated, the incentives break down.

## Total Cost

Each agent's total cost is the sum across all ticks. The AI optimizer aims to minimize
this total by choosing the right `initial_liquidity_fraction` — the fraction
of the bank's liquidity pool to commit at the start of each day.
