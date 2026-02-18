# How the Simulator Works

*Ticks, queues, and settlement mechanics*

## Discrete-Time Simulation

Time in SimCash proceeds in **ticks** — atomic time units within a simulated
trading day. A typical scenario has 12 ticks per day, representing the business hours of
a payment system.

## Payment Lifecycle

At each tick, the engine processes payments through these steps:

1. **Arrivals** — New payments arrive (stochastically or from a fixed schedule)
2. **Policy Execution** — Each bank's policy tree decides: Release or Hold each queued payment
3. **Settlement** — Released payments attempt RTGS settlement (requires sufficient balance)
4. **Cost Accrual** — Liquidity costs tick, delay costs accumulate on unsettled payments
5. **End-of-Day** — At the last tick, deadline penalties apply to unsettled payments

## Two-Queue Architecture

The engine uses a two-queue design inspired by TARGET2:

- **Internal Queue (Q1)** — Bank-controlled strategic queue. The policy tree decides what to release.
- **RTGS Queue (Q2)** — Central system queue. Payments released from Q1 attempt immediate gross settlement.

## Liquidity-Saving Mechanisms (LSM)

Optionally, the engine supports T2-compliant LSM features:

- **Bilateral Offsetting** — Netted settlement when two banks owe each other
- **Multilateral Cycle Detection** — Settles circular payment chains simultaneously

LSM features are available but not used in the current paper experiments.

## Determinism

> ℹ️ SimCash is fully deterministic. Given the same seed and configuration, it produces
> byte-identical output. All randomness flows through a seeded xorshift64* RNG, and all
> money is represented as 64-bit integers (cents) — never floating point.
