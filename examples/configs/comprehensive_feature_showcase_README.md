# Comprehensive Feature Showcase - User Guide

**Scenario**: `comprehensive_feature_showcase.yaml`

## Overview

This scenario is designed to demonstrate **ALL core features** of the payment simulator in a single, narrative-driven business day. It tells the story of five banks with different profiles navigating a high-stress trading day with constrained liquidity.

## Quick Start

```bash
# From the api directory
cd api

# Run the simulation
.venv/bin/python -m payment_simulator.cli run-simulation \
  ../examples/configs/comprehensive_feature_showcase.yaml \
  --output results/comprehensive_showcase.json

# Or use the shorter path if running from project root
python -m payment_simulator.cli run-simulation \
  examples/configs/comprehensive_feature_showcase.yaml \
  --output results/comprehensive_showcase.json
```

## What This Scenario Demonstrates

### ✅ 1. LSM Settlements (Liquidity-Saving Mechanism)

**Bilateral Offsetting**: Heavy flows between METRO_CENTRAL (40%) and CORRESPONDENT_HUB (30%) create continuous bilateral netting opportunities.

**3-Agent Cycles**:
- HUB → REGIONAL → MOMENTUM → HUB
- METRO → HUB → REGIONAL → METRO

**4-Agent Cycles**:
- COMMUNITY → HUB → METRO → REGIONAL → COMMUNITY

**5-Agent Full System Cycle**: All five banks participate in circular flows, resolved with zero net liquidity consumption.

**Expected Impact**: LSM saves ~$500K+ in gross liquidity requirements, preventing mid-day gridlock.

### ✅ 2. Collateral Management

**Proactive Posting** (METRO_CENTRAL):
- Posts collateral at 70% day progress, BEFORE gap becomes critical
- Strategic gap coverage based on Queue 1 needs
- Demonstrates forward-looking liquidity management

**Reactive Posting** (REGIONAL_TRUST):
- Posts collateral at 78% day progress when gap emerges
- Quick response to immediate liquidity needs

**End-of-Tick Optimization** (METRO_CENTRAL):
- Withdraws excess collateral when headroom > 0.5 × Queue 1 value
- Minimizes collateral holding costs

**Strategic Partial Posting** (COMMUNITY_FIRST):
- Posts remaining $5K capacity despite $95K gap
- Demonstrates constrained collateral management

### ✅ 3. Credit Usage

**Range of Strategies**:
- METRO: Conservative (~$50K peak) - emergency use only
- REGIONAL: Moderate (~$120K peak) - cost-based decisions
- HUB: Balanced (~$140K peak) - steady utilization
- COMMUNITY: Near limit (~$145K peak) - forced by constraints
- MOMENTUM: Aggressive (~$280K peak) - liberal usage for velocity

**Cost Implications**: ~$8,500 total overdraft costs across all agents.

### ✅ 4. Payment Splitting

**When Splitting Activates**:
- Large payment ($5K+) needs to be sent
- Current liquidity buffer insufficient
- Policy compares: split friction ($75) vs delay cost vs overdraft cost

**REGIONAL_TRUST Examples**:
- Normal urgency: 2-way split ($5K → 2 × $2.5K)
- High urgency: 4-way split ($6K → 4 × $1.5K)

**CORRESPONDENT_HUB Examples**:
- Urgent $6.5K payment with tight deadline
- 4-way split to avoid expensive overdraft

**Impact**: ~$40K effective liquidity freed, ~$1,000 split friction costs paid.

### ✅ 5. Overdue Transactions & Penalties

**COMMUNITY_FIRST Stress Case**:
- **Tick 45**: $800 payment hits deadline, insufficient liquidity → marked OVERDUE
- **Immediate cost**: $2,500 one-time deadline penalty
- **Ongoing cost**: 5× escalated delay cost ($0.08/tick vs normal $0.016/tick)
- **Settlement**: Finally settles at tick 94 (49 ticks late!)
- **Total cost**: $2,503.92 (vs ~$0.80 if on time)

**Key Insight**: Overdue penalties dwarf normal operating costs, creating strong incentive for proactive liquidity management.

### ✅ 6. Tactical Holding

**MOMENTUM_CAPITAL Congestion Management**:
- Detects system congestion (Queue 2 > 20 transactions)
- Holds trivial payments (<$200) to reduce RTGS load
- Releases only urgent or large payments

**METRO_CENTRAL Time-Based Strategy**:
- Early day (<60% progress): Holds unless 1.5× buffer available
- Late day (>60% progress): Aggressive release

**COMMUNITY_FIRST Cost Comparison**:
- Compares delay cost vs overdraft cost vs deadline penalty
- Holds when delay is cheapest option

### ✅ 7. Liquidity Buffers

**Policy-Specific Buffer Strategies**:
- METRO (Goliath): 1.5× buffer required early day
- REGIONAL (Agile): Dynamic buffer based on cost comparison
- MOMENTUM (Investment): Minimal buffer, aggressive release
- COMMUNITY (Adaptive): Cost-aware buffer management
- HUB (Smart Splitter): Balanced buffer with splitting flexibility

### ✅ 8. Cost Accruals

**Full Cost Breakdown** (expected end-of-day):
- Delay costs: ~$800
- Overdraft costs: ~$8,500
- Collateral costs: ~$1,200
- Deadline penalties: ~$7,500
- EOD penalties: ~$15,000
- Split friction: ~$1,000
- **Total system costs**: ~$34,000

## The Five Banks - Character Profiles

### 1. METRO_CENTRAL - "The Prudent Giant"
- **Profile**: Large money center bank, conservative strategy
- **Opening Balance**: $350,000 (strong)
- **Credit Limit**: $250,000 (rarely used)
- **Policy**: Goliath National Bank (time-adaptive, proactive collateral)
- **Signature Move**: Posts collateral at 70% day progress, withdraws excess at end-of-tick
- **Expected Settlement**: ~95%

### 2. REGIONAL_TRUST - "The Savvy Splitter"
- **Profile**: Mid-sized regional bank, tactical optimizer
- **Opening Balance**: $220,000 (moderate)
- **Credit Limit**: $200,000 (balanced usage)
- **Policy**: Agile Regional Bank (splitting + reactive collateral)
- **Signature Move**: Splits $5K payment 2-way to avoid $50/tick overdraft
- **Expected Settlement**: ~92%

### 3. MOMENTUM_CAPITAL - "The Aggressive Trader"
- **Profile**: High-velocity investment bank desk
- **Opening Balance**: $280,000 (good)
- **Credit Limit**: $320,000 (aggressively used)
- **Policy**: Momentum Investment Bank (congestion-aware, no collateral)
- **Signature Move**: Holds trivial payments during congestion, releases big ones
- **Expected Settlement**: ~90%

### 4. COMMUNITY_FIRST - "The Struggling Survivor"
- **Profile**: Small undercapitalized bank
- **Opening Balance**: $120,000 (severely constrained)
- **Credit Limit**: $150,000 (will max out)
- **Policy**: Adaptive Liquidity Manager (cost-aware, strategic collateral)
- **Signature Move**: Faces multiple overdue transactions, relies on LSM for survival
- **Expected Settlement**: ~78%

### 5. CORRESPONDENT_HUB - "The Network Connector"
- **Profile**: Central correspondent creating circular flows
- **Opening Balance**: $300,000 (solid)
- **Credit Limit**: $280,000 (steady usage)
- **Policy**: Smart Splitter (tactical splitting, balanced collateral)
- **Signature Move**: Creates LSM opportunities via balanced counterparty weights
- **Expected Settlement**: ~94%

## Timeline - Key Events to Watch

### Early Day (Ticks 0-30)
- ⏱️ METRO: Conservative holding (1.5× buffer requirement)
- ⏱️ MOMENTUM: Aggressive release begins
- ⏱️ COMMUNITY: Queue building up
- 🔄 LSM: Bilateral offsetting active (METRO ↔ HUB)

### Mid-Day (Ticks 30-60)
- ✂️ REGIONAL: First payment split (tick ~35)
- 📈 MOMENTUM: Tactical holding activates (congestion detected)
- ⚠️ COMMUNITY: First transaction becomes overdue (tick 45)
- 🔄 LSM: 3-cycle and 4-cycle resolutions accelerate

### Late Day (Ticks 60-85)
- 💰 METRO: Proactive collateral posting (tick ~70)
- 💰 REGIONAL: Reactive collateral posting (tick ~78)
- 🚨 COMMUNITY: Multiple overdue transactions (3 total)
- 🔄 LSM: 5-agent full system cycle detected and settled

### EOD Rush (Ticks 85-100)
- 💸 METRO: Collateral withdrawal optimization (tick ~90)
- ✅ COMMUNITY: First overdue transaction finally settles (tick 94)
- 🏁 ALL: EOD rush flag active, aggressive releases
- 📊 Final settlements and penalty calculations

## What to Look For in Results

### Key Metrics

**Settlement Rates**:
```
METRO_CENTRAL:        ~95% (excellent)
CORRESPONDENT_HUB:    ~94% (excellent)
REGIONAL_TRUST:       ~92% (good)
MOMENTUM_CAPITAL:     ~90% (good)
COMMUNITY_FIRST:      ~78% (struggling)
System Average:       ~90%
```

**LSM Impact**:
- Look for `lsm_bilateral_settlements` events
- Look for `lsm_cycle_settlements` events with `cycle_length: 3-5`
- Total liquidity saved should be ~$500K+

**Collateral Operations**:
- Search for `collateral_posted` events (4 agents)
- Search for `collateral_withdrawn` events (METRO at end-of-tick)
- Total collateral costs in cost breakdown

**Overdue Transactions**:
- Search for `transaction_status_changed` to `Overdue`
- Count of overdue transactions by agent
- Deadline penalty charges (3 × $2,500 = $7,500)

**Payment Splits**:
- Search for `transaction_split` events
- Count 2-way vs 4-way splits
- Split friction costs

### Cost Analysis

Compare costs across agents to understand strategy effectiveness:

**Most Expensive Components**:
1. EOD penalties (~$15K) - largest cost
2. Overdraft costs (~$8.5K) - from aggressive credit usage
3. Deadline penalties (~$7.5K) - COMMUNITY's overdue transactions
4. Delay costs (~$800) - base holding costs
5. Collateral costs (~$1.2K) - strategic liquidity
6. Split friction (~$1K) - tactical optimization

**Agent Cost Rankings** (expected):
1. COMMUNITY_FIRST: Highest costs (overdue penalties + high overdraft)
2. MOMENTUM_CAPITAL: High costs (aggressive overdraft usage)
3. REGIONAL_TRUST: Moderate costs (balanced + split friction)
4. CORRESPONDENT_HUB: Moderate costs (balanced strategy)
5. METRO_CENTRAL: Lowest costs (conservative, strategic)

### Gridlock Analysis

Without LSM, system would gridlock around tick 40-50 when:
- COMMUNITY_FIRST exhausts liquidity
- Circular dependencies form
- Queue 2 grows beyond settlement capacity

With LSM:
- Bilateral offsetting clears ~150+ paired transactions
- Cycle resolution breaks ~60+ circular dependencies
- System remains operational throughout day

## Understanding Policy Differences

### Collateral Strategies

**Proactive (METRO - Goliath)**:
```
✅ Posts early (70% day progress)
✅ Anticipates gaps before critical
✅ Withdraws excess to minimize costs
📊 Result: Lower stress, higher flexibility, moderate collateral costs
```

**Reactive (REGIONAL - Agile Regional)**:
```
⏰ Waits until gap appears (78% progress)
⏰ Quick response to immediate needs
⏰ Keeps collateral posted
📊 Result: Higher stress, adequate response, moderate collateral costs
```

**None (MOMENTUM - Investment Bank)**:
```
❌ No collateral management
💰 Relies purely on aggressive credit usage
📊 Result: High overdraft costs, simple strategy
```

### Splitting Strategies

**Tactical (REGIONAL - Agile Regional)**:
```
if payment > $3K && buffer insufficient:
  if urgent: split 4-way
  else: split 2-way

Cost comparison: $75 split fee vs $50/tick overdraft
📊 Decision: Split when avoiding multi-tick overdraft
```

**Smart (HUB - Smart Splitter)**:
```
if payment > $3K && buffer < payment:
  compare: split_cost vs delay_cost vs overdraft_cost
  if split cheapest: split (2-way or 4-way based on urgency)

📊 Holistic cost optimization
```

## Validation Checklist

After running the simulation, verify these features activated:

- [ ] Bilateral LSM settlements occurred (METRO ↔ HUB)
- [ ] 3-agent cycle settlements occurred
- [ ] 4-agent cycle settlements occurred
- [ ] 5-agent full system cycle occurred (at least once)
- [ ] METRO posted collateral proactively (~tick 70)
- [ ] METRO withdrew collateral (~tick 90)
- [ ] REGIONAL posted collateral reactively (~tick 78)
- [ ] COMMUNITY had 3+ overdue transactions
- [ ] Deadline penalties charged (3 × $2,500)
- [ ] REGIONAL split payments (multiple times)
- [ ] HUB split payments (multiple times)
- [ ] MOMENTUM held trivial payments during congestion
- [ ] All cost types represented in final breakdown
- [ ] System-wide settlement rate ~85-92%

## Advanced Analysis Questions

Use this scenario to explore:

1. **LSM Efficacy**: What happens if you disable LSM? (System gridlocks)
2. **Cost Optimization**: Which policy has lowest total costs? (METRO)
3. **Splitting Value**: How much does splitting save vs pure overdraft? (~$3-4K)
4. **Overdue Impact**: What if overdue_delay_multiplier = 10.0? (Even higher costs)
5. **Collateral Timing**: Proactive vs reactive - which is cheaper? (Depends on inflow timing)

## Troubleshooting

**Simulation doesn't start**:
- Check that all policy JSON files exist in `backend/policies/`
- Verify YAML syntax with `yamllint comprehensive_feature_showcase.yaml`

**No LSM activations**:
- Check `lsm_config` is enabled
- Verify circular counterparty weights are present
- Ensure insufficient liquidity forces queueing

**No overdue transactions**:
- Increase arrival rates or reduce opening balances
- Shorten deadline ranges
- Reduce credit limits

**Simulation runs too fast/slow**:
- Adjust `ticks_per_day` (100 = 5 min ticks, 200 = 2.5 min ticks)
- Reduce/increase arrival rates

## Extending This Scenario

Ideas for variations:

1. **More Stress**: Reduce opening balances by 30%, increase arrival rates by 20%
2. **Less Stress**: Double opening balances, add 6th well-capitalized "Central Bank" agent
3. **Longer Horizon**: Change to `num_days: 3` to see multi-day patterns
4. **Different Policies**: Swap policies around (e.g., give COMMUNITY a more aggressive policy)
5. **Cost Sensitivity**: Vary `overdue_delay_multiplier` from 1.0 to 10.0

## References

- **Policy Documentation**: See `backend/policies/*.json` for policy implementations
- **LSM Documentation**: `docs/lsm-specification.md` (if exists)
- **Overdue Transactions**: `docs/overdue-transactions.md`
- **Cost Model**: `docs/cost-model.md` (if exists)
- **Other Example Scenarios**: `examples/configs/` directory

---

**Last Updated**: 2025-11-05
**Scenario Version**: 1.0
**Tested With**: SimCash v0.3.0+
