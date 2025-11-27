# BIS AI Cash Management RTGS Model

## Source

**Paper**: "AI agents for cash management in payment systems"
**Authors**: Iñaki Aldasoro and Ajit Desai
**Publication**: BIS Working Papers No. 1310, November 2025
**Institutions**: Bank for International Settlements, Bank of Canada

---

## Overview

This document describes the simplified RTGS (Real-Time Gross Settlement) model used in the BIS working paper to evaluate whether generative AI agents can perform high-level intraday liquidity management in wholesale payment systems. The model is intentionally stylized to test fundamental cash management heuristics rather than replicate full system complexity.

---

## System Architecture

### Basic RTGS Concept

The paper models a standard RTGS system where:

1. **Participants**: Large financial institutions (primarily banks)
2. **Settlement**: Transactions settle in real-time, one-by-one
3. **Liquidity Source**: Central bank provides liquidity to participants in exchange for collateral
4. **Examples**: Fedwire (US), CHAPS (UK), TARGET2 (Eurozone), Lynx (Canada)

### Cash Manager's Information Set

The cash manager has access to:

- **Available collateral** for initial liquidity decisions
- **Internal payment queue** visibility (pending outgoing payments)
- **Continuous updates** on incoming transactions from counterparties
- **Historical transaction patterns** for prediction

---

## Core Decision Framework

### Two Critical Decisions

Cash managers face two fundamental choices (per Bech and Garratt, 2003):

1. **Liquidity Allocation**: How much collateralized liquidity to secure at the start of the day
2. **Payment Choices**: Managing the pace at which payments are processed throughout the day

### The Liquidity-Delay Trade-off

This is the central tension in the model:

| Strategy | Benefit | Cost |
|----------|---------|------|
| **More liquidity upfront** | Fewer payment delays | Higher opportunity cost (collateral) |
| **Less liquidity upfront** | Lower opportunity cost | Potential delays, gridlock, or emergency borrowing |

### Payment Recycling

A key mechanism in the model: incoming payments from other participants can be **recycled** as liquidity for outgoing transactions, reducing the need for pre-funded collateralized liquidity.

---

## Cost Structure

The paper uses the following cost parameters:

| Cost Type | Rate | Description |
|-----------|------|-------------|
| **Liquidity allocation cost** | 1.5% | Opportunity cost of pledging collateral at start of day |
| **Delay cost (non-urgent)** | 1.0% | Penalty for delaying regular payments |
| **Delay cost (urgent)** | 1.5% | Higher penalty for delaying time-sensitive payments |
| **Emergency borrowing** | >1.5% | Higher rate than initial allocation (end-of-day shortfall) |

---

## Experimental Scenarios

The paper tests three increasingly complex scenarios to evaluate AI agent decision-making.

### Scenario 1: Precautionary Decision

**Purpose**: Test ability to preserve liquidity under uncertainty

**Setup**:
- Liquidity limit: $10
- Current queue: Two pending payments of $1 each
- Future uncertainty: Potential urgent $10 payment in next period
- Time horizon: 2 periods

**State Representation**:
```
Period 1:
  - Available liquidity: $10
  - Queue: [$1, $1]
  - Possible future: $10 urgent payment (probability unspecified initially)

Period 2:
  - Potential urgent payment: $10
```

**Optimal Behavior**: Delay both $1 payments to preserve full liquidity for potential urgent payment.

**Key Insight**: The agent should exhibit **precautionary** behavior, prioritizing liquidity preservation when high-value urgent payments are possible.

**Robustness Tests**:
- Varied probability of urgent payment from 50% down to 0.1%
- Agent maintained precautionary stance until probability became negligible (<0.25%)
- Replaced "urgent" with synonyms ("important", "priority", "time-sensitive", "high-delay cost") - no change
- Scaled amounts from $1/$10 to $1B/$10B - no change

---

### Scenario 2: Navigating Priorities

**Purpose**: Test ability to prioritize payments considering probabilistic inflows

**Setup**:
- Liquidity limit: $10
- Current queue: $1 and $2 payments pending
- Incoming probability: 90% chance of receiving $2 (recyclable as liquidity)
- Future uncertainty: 50% probability of urgent $10 payment in period 2
- Time horizon: 2 periods

**State Representation**:
```
Period 1:
  - Available liquidity: $10
  - Queue: [$1, $2]
  - Expected inflow: $2 (90% probability, recyclable)

Period 2:
  - Potential urgent payment: $10 (50% probability)
```

**Optimal Behavior**: Process only the $1 payment; hold $2 payment while waiting to see if the $2 inflow arrives.

**Key Insight**: The agent balances **current liquidity needs** against **anticipated future obligations**, using probabilistic reasoning about incoming payments.

**Observed Behavior**: Agent showed mostly consistent responses but occasionally chose more conservative approach (delay both payments) in 1/10 runs.

---

### Scenario 3: Liquidity-Delay Trade-off

**Purpose**: Test optimal initial liquidity allocation across multiple periods with costs

**Setup**:
- Pre-period: Allocate initial liquidity at 1.5% cost
- Time horizon: 3 periods

**Period Structure**:

| Period | Outgoing | Delay Cost | Incoming Probability | Incoming Amount |
|--------|----------|------------|---------------------|-----------------|
| 1 | $5 | 1.0% | 99% | $5 |
| 2 | $10 (90% prob, urgent) | 1.5% | 99% | $5 |
| 3 | Clear remaining queue | Borrow at >1.5% if short | - | - |

**State Representation**:
```
Pre-Period:
  - Decision: How much liquidity to allocate at 1.5% cost

Period 1:
  - Queue: [$5]
  - Delay cost: 1% if not processed
  - Expected inflow: $5 (99% probability, recyclable)

Period 2:
  - Queue: Possibly [$10] (90% probability, urgent)
  - Delay cost: 1.5% if not processed
  - Expected inflow: $5 (99% probability, recyclable)

Period 3:
  - Must clear any remaining queue
  - Emergency borrowing at rate > 1.5% if needed
```

**Optimal Behavior**: Allocate $5 initially (covers first payment), rely on high-probability incoming payments for subsequent obligations.

**Key Insight**: The agent minimizes opportunity cost of pre-funding while accepting minimal risk, given the high probability (99%) of incoming recyclable payments.

**Observed Behavior**: Consistent in most runs but occasionally chose higher allocation (more conservative) in 2/10 runs.

---

## Model Parameters Summary

### Fixed Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Liquidity limit | $10 (base case) | Maximum available central bank credit |
| Settlement | Real-time | Immediate if liquidity available |

### Variable Parameters (Tested)

| Parameter | Range Tested |
|-----------|--------------|
| Probability of urgent payment | 0.1% - 50% |
| Probability of incoming payment | 10% - 99% |
| Payment amounts | $1 - $1 billion |

---

## Key Model Simplifications

The paper explicitly notes several simplifications relative to real RTGS systems:

1. **Single agent perspective**: Focus on one bank's decisions, not multi-agent dynamics
2. **No system-specific details**: Abstracted from Fedwire/CHAPS/TARGET2/Lynx specifics
3. **Simplified cost structure**: Three cost types rather than complex fee schedules
4. **Discrete periods**: Rather than continuous time
5. **Binary payment states**: Pending or settled (no partial settlement in base model)
6. **No gridlock modeling**: Multi-agent circular dependencies not tested
7. **No strategic interaction**: Other agents' behavior not modeled

---

## Comparison to SimCash Model

### Similarities

| Feature | BIS Model | SimCash |
|---------|-----------|---------|
| RTGS settlement | Yes | Yes |
| Liquidity constraints | Yes | Yes |
| Payment queuing | Yes | Yes |
| Delay costs | Yes | Yes (overdue penalties, deadline penalties) |
| Payment prioritization | Urgent vs non-urgent | Priority levels (0-10) |
| Incoming payment recycling | Yes (implicit) | Yes (explicit in settlement logic) |

### SimCash Extensions Beyond BIS Model

| Feature | BIS Model | SimCash |
|---------|-----------|---------|
| Multi-agent dynamics | No | Yes |
| LSM (Liquidity Saving Mechanism) | No | Yes (bilateral/multilateral offsets) |
| Collateral management | Implicit | Explicit (collateralized credit limits) |
| Divisible payments | No | Yes (split payments) |
| Arrival rate modeling | No | Yes (Poisson, distributions) |
| Tick-based time | Periods | Configurable ticks per day |
| Policy DSL | No | Yes (custom agent strategies) |
| Deterministic replay | No | Yes (seeded RNG) |
| Multiple priority levels | 2 (urgent/non-urgent) | 11 (0-10 scale) |

---

## Implications for SimCash Development

### Validated Design Choices

The BIS paper validates several SimCash architectural decisions:

1. **Delay costs matter**: Time-based penalties drive strategic behavior
2. **Liquidity recycling is key**: Incoming payments reduce pre-funding needs
3. **Priority differentiation works**: Agents can learn to prioritize urgent payments
4. **Probabilistic reasoning**: Agents benefit from considering expected inflows

### Potential Enhancements Suggested

Based on the BIS experiments, SimCash could consider:

1. **AI-assisted policy evaluation**: Use LLM agents to evaluate policy effectiveness
2. **Simplified "tutorial" scenarios**: Three-scenario progression for onboarding
3. **Cost structure tuning**: Validate delay cost ratios (1.5x for urgent vs regular)
4. **End-of-day penalty calibration**: Higher borrowing costs for EOD shortfalls

---

## References

- Bech, M.L. and Garratt, R. (2003). "The intraday liquidity management game." *Journal of Economic Theory* 109(2), 198-219.
- Castro, P., Desai, A., Du, H., Garratt, R., and Rivadeneyra, F. (2025). "Estimating policy functions in payment systems using reinforcement learning." *ACM Transactions on Economics and Computation* 13(1), 1-31.
- Galbiati, M. and Soramäki, K. (2011). "An agent-based model of payment systems." *Journal of Economic Dynamics and Control* 35(6), 859-875.

---

*Document created: November 2025*
*Based on BIS Working Paper 1310*
