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

A basis point (bp) is 1/100th of a percent, so 100 bps = 1%. The rate is applied per tick, so the effective daily cost depends on how many ticks make up a day. For example, at 100 bps/tick over a 12-tick day, the daily cost is 12% of committed balance. When configuring scenarios, set this relative to the other cost rates — liquidity cost should typically be the cheapest, reflecting that holding reserves is preferable to the alternatives (delays, penalties, overdrafts).

## 2. Delay Cost (r_d)

Charged per cent of unsettled payment per tick. Represents the cost of failing to
settle a payment on time — client dissatisfaction, SLA penalties, reputational damage.

```
cost = unsettled_amount × rate per tick
```

More expensive than liquidity cost — banks should prefer committing funds upfront over letting payments sit.

## 3. Deadline Penalty

Charged when a payment misses its individual deadline (each payment has a specific tick by which it should settle). Supports two modes:

**Fixed mode** — a flat amount in cents, regardless of transaction size:
```
cost = amount per missed-deadline payment
```

**Rate mode** — basis points of the transaction amount, so penalties scale with payment value:
```
cost = transaction_amount × (bps / 10,000) per missed-deadline payment
```

Rate mode is useful when transactions vary widely in size. A flat $500 penalty is negligible for a $10M payment but severe for a $100 one. Rate mode keeps the penalty proportional.

Default: fixed, 50,000 cents ($500).

## 4. End-of-Day Penalty

A separate penalty for any payment still unsettled when the day ends. Same two modes as deadline penalty:

- **Fixed**: flat amount per unsettled payment
- **Rate**: basis points of the **remaining unsettled amount** (not the original transaction amount — partially settled payments incur proportionally less)

Default: fixed, 100,000 cents ($1,000). This creates a hard deadline for all payments.

## The Ordering Constraint

> ⚠️ **liquidity cost < delay cost < penalty cost** — this ordering is important for
> well-behaved incentives. Banks should always prefer committing liquidity (cheapest)
> over delaying payments (medium) over missing deadlines entirely (most expensive).
> If this ordering is violated, the strategic dynamics break down — agents may find it
> rational to ignore deadlines or hoard liquidity.
>
> Rate-based penalties help maintain this ordering across different transaction sizes,
> which is their primary motivation. The engine includes a validation warning when
> configured rates might violate this hierarchy for typical transaction amounts.

## Total Cost

Each agent's total cost is the sum across all ticks. The AI optimizer aims to minimize
this total by choosing the right `initial_liquidity_fraction` — the fraction
of the bank's liquidity pool to commit at the start of each day.
