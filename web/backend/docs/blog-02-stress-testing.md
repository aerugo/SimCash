# Designing Financial Stress Tests with SimCash

*How to model crisis scenarios, liquidity shocks, and central bank interventions in a simulated RTGS system*

## Why Stress Testing Matters

In 2008, the payment systems that underpin global finance didn't break — but they came
terrifyingly close. Lehman Brothers' default sent shockwaves through every major RTGS system.
Banks that had comfortably recycled incoming payments to fund outgoing ones suddenly found
themselves staring at empty queues. The liquidity that everyone counted on — other banks'
payments flowing in — simply stopped.

The lesson was clear: you can't test a payment system's resilience only on sunny days.
Real-Time Gross Settlement systems process trillions of euros daily, and their stability
depends on every participant maintaining adequate liquidity. When one major bank fails to
deliver, the cascading effects can freeze the entire network. Stress testing isn't a
regulatory checkbox — it's the only way to understand how your system behaves when the
assumptions underlying normal operations stop being true.

But traditional stress testing is expensive and slow. You need custom models, carefully
calibrated parameters, weeks of engineering time. SimCash was built to change that.

## How SimCash Models Crises

At its core, SimCash's scenario system lets you define **what happens** and
**when it happens** — then hands the rest to the simulation engine. Scenarios
are multi-phase narratives with configurable events at each stage:

- **Liquidity shocks:** Suddenly reduce one or more banks' available liquidity
  at a specific tick — modeling an unexpected outflow, a collateral call, or a credit line revocation.
- **Payment surges:** Inject a burst of high-value payments into the system,
  simulating end-of-day settlement rushes or margin calls during volatile markets.
- **Participant failures:** Remove a bank from the system entirely, modeling
  a Lehman-style default where all expected incoming payments vanish.
- **Central bank interventions:** Inject emergency liquidity at a specific
  tick — the lender-of-last-resort stepping in to prevent systemic collapse.

Each scenario phase has a name, a duration (in ticks), and a set of events. You can chain
phases to create complex narratives: "normal operations for 4 ticks, then a liquidity shock,
then observe the cascade for 6 ticks, then the central bank intervenes." The engine handles
the rest — payment processing, queue management, cost accounting, deadline tracking — all
running at the same fidelity as a normal simulation.

## Walking Through: The TARGET2 Crisis Scenario

SimCash ships with a built-in scenario called **TARGET2 Crisis**, modeled on
the dynamics of the European Central Bank's RTGS system during a sovereign debt crisis.
Here's what happens when you run it:

**Phase 1 — Normal Operations (Ticks 1-3):** Three banks operate normally.
Payments arrive via Poisson process, amounts are log-normally distributed. Banks settle
payments as they come in, recycling incoming liquidity to fund outgoing obligations.
Everything works smoothly. Costs are low.

**Phase 2 — The Shock (Tick 4):** Bank C suffers a sudden liquidity drain —
its available balance drops by 60%. This models a large unexpected outflow: a margin call,
a deposit flight, a collateral haircut. Bank C's outgoing payments immediately start queuing.

**Phase 3 — The Cascade (Ticks 5-8):** Here's where it gets interesting.
Banks A and B were counting on incoming payments from Bank C to fund their own obligations.
Those payments are now stuck in C's queue. A and B's own queues start growing. The delay
costs compound: each tick a payment sits in queue, it accrues penalties. If deadlines pass,
the failure costs are even steeper.

**Phase 4 — Intervention (Tick 9):** The central bank injects emergency
liquidity into Bank C. The queued payments start flowing again. But the damage is done —
the cascade has already pushed costs far above normal levels across all participants.

What should you watch for? The **delay cost curve** tells the story. In normal
operations, delay costs are near zero. After the shock, they spike — first for Bank C,
then for A and B with a 1-2 tick lag. The total system cost often triples or quadruples
relative to the no-shock baseline. The spread between banks reveals who was most dependent
on C's incoming payments.

## AI Agents vs. Static Policies Under Stress

Here's what makes SimCash's stress testing genuinely novel: you can pit **adaptive
AI agents** against **static rule-based policies** and watch how they
respond to the same crisis.

A static FIFO policy doesn't know a crisis is happening. It processes payments in order,
commits the same liquidity fraction it always does, and watches helplessly as costs spike.
A more sophisticated decision-tree policy might have crisis-response rules — "if queue
depth exceeds X, delay low-priority payments" — but those rules were written before the
crisis happened. They can't adapt to the specific shape of this particular shock.

An LLM-powered agent, by contrast, gets a full performance report after each tick. It
sees the queue building, the delay costs spiking, the pattern of which payments are failing.
And it adjusts. In our experiments, AI agents facing the TARGET2 Crisis scenario typically
respond within 2-3 rounds: they increase their liquidity commitment, shift to more
aggressive release of queued payments, and accept higher liquidity costs to avoid the
compounding delay penalties. The total crisis cost for AI-managed banks is consistently
15-30% lower than for static-policy banks facing the same shock.

This isn't magic — it's exactly what a skilled human cash manager would do. But the AI does
it faster, more consistently, and without the panicked phone calls.

## Building Your Own Stress Tests

The scenario editor in SimCash's web interface lets you design custom stress tests without
writing code. You define phases visually — drag to set durations, click to add events,
configure parameters with sliders:

- **Choose your topology:** How many banks? What's the initial liquidity distribution?
- **Define the baseline:** Set payment arrival rates, amount distributions,
  and the normal operating period.
- **Add the shock:** Pick which bank gets hit, the severity (10% drain to 90%),
  and the timing.
- **Configure the response:** Add a central bank intervention phase, or don't —
  and see what happens without a backstop.
- **Assign policies:** Give each bank a different strategy — one AI-managed,
  one FIFO, one custom decision tree — and compare their crisis responses head-to-head.

You can save scenarios, share them, and run them repeatedly with different random seeds to
build statistical confidence. The bootstrap evaluation system applies here too: run 50
seeds of the same crisis and you'll know whether one policy's crisis performance is genuinely
better or just got lucky with payment timing.

## What Researchers Can Learn

Stress testing in SimCash isn't just about finding the breaking point. It's about
understanding the **transmission mechanism** — how a shock at one node propagates
through the network, which relationships amplify it, and which policies contain it.

Central bank researchers can use this to evaluate intervention timing: is it better to
inject liquidity immediately, or wait to see if the market self-corrects? Banking
supervisors can study concentration risk: what happens when the most-connected bank fails?
And policy designers can test resilience requirements: how much committed liquidity does
each bank need to survive a worst-case shock without central bank help?

The answers aren't theoretical. They come from running thousands of simulated crises with
realistic payment flows, realistic cost structures, and agents that behave like real
decision-makers. That's the value of a sandbox: you can break things safely, learn from
the wreckage, and build better systems before the next crisis arrives.
