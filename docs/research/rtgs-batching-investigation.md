# Research Brief: RTGS Batching vs Real-Time Settlement

## Executive Summary

**Research Question**: Should the SimCash RTGS system implement batching delays for non-urgent transactions to improve liquidity efficiency, or would this violate the fundamental principles of Real-Time Gross Settlement systems?

**Context**: The current simulator settles transactions immediately via RTGS when liquidity is available, and only queues them when liquidity is insufficient. The LSM (Liquidity-Saving Mechanism) then finds offsets in queued transactions. The question is whether **intentional batching delays** could improve liquidity usage even when agents have sufficient funds to settle immediately.

---

## Background: Current Simulator Behavior

### RTGS Settlement Flow
1. Transaction arrives at agent's queue
2. Policy decides whether to release (or holds due to liquidity preservation)
3. If released, RTGS attempts immediate settlement
4. If insufficient liquidity → transaction remains queued
5. LSM runs periodically to find bilateral/multilateral offsets in queued transactions

### LSM (Existing Batch-like Mechanism)
- **Bilateral offsets**: A→B and B→A settle simultaneously with net flow
- **Multilateral cycles**: A→B→C→A settle simultaneously with net flows
- **Key point**: LSM only operates on *already-queued* transactions (those that couldn't settle via RTGS)

---

## Research Questions

### 1. **RTGS Design Principles**

**Q1.1**: What is the formal definition of "Real-Time Gross Settlement"?
- Does "real-time" strictly mean "immediate upon arrival"?
- Or does it allow for "within same business day" with optimization windows?

**Q1.2**: How do major RTGS systems actually behave?
- **Fedwire (US Federal Reserve)**: Settlement timing policies?
- **TARGET2 (Eurozone)**: Any batching or queuing strategies?
- **CHAPS (UK)**: Real-time vs deferred elements?
- **BOJ-NET (Japan)**: Hybrid models?

**Q1.3**: Do real RTGS systems ever intentionally delay transactions?
- Are there priority tiers with different settlement urgency?
- Do central banks allow participant banks to hold low-priority payments?
- What mechanisms exist for participants to manage liquidity timing?

### 2. **Batching in Payment Systems**

**Q2.1**: What are "Deferred Net Settlement" (DNS) systems?
- How do they differ from RTGS?
- Examples: ACH (US), BACS (UK)
- Liquidity efficiency vs settlement risk trade-offs

**Q2.2**: What are "hybrid" payment systems?
- Systems that combine RTGS and DNS features
- Example: CHIPS (Clearing House Interbank Payments System)
- How do they balance real-time settlement with netting benefits?

**Q2.3**: Are there successful real-world examples of "intentional batching windows" within RTGS?
- Specific times of day for batch processing?
- Participant-controlled release timing?
- Central bank-mandated optimization periods?

### 3. **Liquidity Efficiency vs Settlement Finality**

**Q3.1**: What is the cost of batching delays?
- **Settlement risk**: Longer time between transaction initiation and finality
- **Intraday credit risk**: Sender's balance uncertain until settlement
- **Operational risk**: What if market conditions change during batch window?
- **Systemic risk**: Could synchronized batches create volatility spikes?

**Q3.2**: What is the benefit of batching delays?
- **Liquidity savings**: Potential for more offsetting transactions
- **Reduced overdraft costs**: Less reliance on intraday credit
- **Fewer gridlocks**: Better chance of multilateral offsets
- **Lower collateral requirements**: Less need for posted collateral

**Q3.3**: How do real banks manage this trade-off?
- Do banks voluntarily delay payments to optimize liquidity?
- Are there regulatory constraints on delaying customer payments?
- What are the service level expectations (SLA) for different payment types?

### 4. **Priority Tiers and Urgency**

**Q4.1**: How do real RTGS systems handle payment prioritization?
- High-priority (urgent): Settle immediately regardless of liquidity cost?
- Low-priority (routine): Can be delayed for optimization?
- Do priority systems effectively create "implicit batching"?

**Q4.2**: What determines payment urgency in practice?
- Market infrastructure payments (securities settlement): Always urgent
- Interbank loans: Typically urgent
- Customer payments: May vary by type
- Central bank operations: Highest priority

**Q4.3**: How does the current simulator's priority system compare?
- SimCash has priority 0-10 and deadlines
- Policies can hold transactions based on priority
- Is this sufficient to model real-world urgency-based batching?

### 5. **Gridlock and Systemic Risk**

**Q5.1**: Could intentional batching INCREASE gridlock risk?
- If all banks batch simultaneously → synchronized liquidity crunches?
- If batches are staggered → some banks accumulate larger queues?
- Historical examples of batching-related gridlocks?

**Q5.2**: Do real RTGS systems have "anti-gridlock" features?
- Queue prioritization algorithms
- Central bank liquidity provision
- Forced settlement mechanisms
- LSM-like multilateral offset algorithms

**Q5.3**: How does the current simulator handle gridlock?
- LSM finds cycles but doesn't force settlement
- Policies decide release timing
- Should there be time-based forcing mechanisms?

### 6. **Implementation Considerations for SimCash**

**Q6.1**: What would "intentional batching" look like in the simulator?

**Option A: Policy-Level Batching**
- Policies could voluntarily hold transactions even with sufficient liquidity
- Wait for a "batch window" (e.g., every 5-10 ticks)
- Release all queued transactions together for LSM to process
- **Pro**: Aligns with real-world bank behavior
- **Con**: Requires sophisticated policy logic

**Option B: System-Level Batching**
- RTGS could have configurable "batch intervals"
- All releases within interval accumulate
- At interval end, process all together
- **Pro**: Simple to implement
- **Con**: May not reflect real RTGS systems

**Option C: Hybrid (Current Approach)**
- RTGS settles immediately when possible
- Natural queuing due to liquidity constraints
- LSM finds offsets in accumulated queues
- **Pro**: May already be realistic
- **Con**: Misses intentional optimization strategies

**Q6.2**: What are the simulation implications?
- Would batching improve settlement rates in existing scenarios?
- Would it reduce overdraft costs?
- Would it better match real-world metrics?
- How would it affect research validity?

### 7. **Research Methodology**

**Recommended Approach:**

1. **Literature Review**
   - Central bank publications (BIS, Fed, ECB, BoE, BoJ)
   - Academic papers on RTGS design
   - Industry standards (SWIFT, CLS documentation)

2. **Comparative Analysis**
   - Document settlement timing for major RTGS systems
   - Identify any batching or delay mechanisms
   - Map priority tiers and urgency handling

3. **Empirical Data** (if available)
   - Intraday settlement patterns from real RTGS systems
   - Distribution of settlement times after transaction initiation
   - Evidence of strategic timing by participants

4. **Simulation Experiments**
   - Implement policy-based batching in SimCash
   - Compare metrics: settlement rate, liquidity usage, costs, gridlocks
   - Test across multiple scenarios (stress vs normal conditions)

5. **Expert Consultation** (if possible)
   - Payment system operators
   - Central bank market operations staff
   - Payment system researchers

---

## Key References to Consult

### Central Bank Documents
- Bank for International Settlements (BIS): "Statistics on payment, clearing and settlement systems in the CPMI countries"
- Federal Reserve: "Fedwire Funds Service Operating Circular"
- European Central Bank: "TARGET2 User Handbook"
- Bank of England: "CHAPS Reference Manual"

### Academic Literature
- Bech, M., & Garratt, R. (2003). "The intraday liquidity management game"
- Martin, A., & McAndrews, J. (2008). "Liquidity-saving mechanisms"
- Mills, D., & Nesmith, T. (2008). "Risk and concentration in payment and securities settlement systems"

### Industry Standards
- CPMI-IOSCO: "Principles for Financial Market Infrastructures" (PFMI)
- ISO 20022: Real-time payment message standards

---

## Expected Outcomes

**Scenario 1: Real RTGS Systems Do Batch**
- **Implication**: SimCash should implement batching to be realistic
- **Action**: Design configurable batching mechanism (policy or system level)
- **Research question**: What batching intervals and rules are most realistic?

**Scenario 2: Real RTGS Systems Don't Batch**
- **Implication**: Current simulator approach is correct
- **Action**: No changes needed; "batching" happens naturally via queuing + LSM
- **Research question**: Why is immediate settlement preferred despite liquidity costs?

**Scenario 3: Hybrid Approach**
- **Implication**: Some transactions batch, others settle immediately
- **Action**: Enhance priority/urgency system to model this distinction
- **Research question**: What determines which transactions are urgent?

---

## Critical Success Factors

1. **Definitional Clarity**: Establish precise meaning of "RTGS", "batching", "deferred settlement"
2. **Real-World Validation**: Ground analysis in actual system documentation, not theoretical ideals
3. **Trade-off Quantification**: Measure liquidity savings vs settlement delay costs
4. **Risk Assessment**: Evaluate systemic risk implications of batching strategies
5. **Regulatory Compliance**: Ensure any changes align with payment system standards

---

## Timeline Estimate

- **Phase 1: Literature Review** (2-3 days)
  - Central bank docs, academic papers, industry standards

- **Phase 2: System Comparison** (2-3 days)
  - Document major RTGS systems' actual behavior

- **Phase 3: Analysis & Recommendations** (1-2 days)
  - Synthesize findings, evaluate options for SimCash

- **Phase 4: Experimental Validation** (Optional, 2-3 days)
  - Implement prototype, run simulations, compare metrics

**Total: 5-11 days**

---

## Open Questions for Discussion

1. **Terminology**: Is what we're calling "batching" actually just "strategic queuing"?

2. **Realism vs Optimization**: Should SimCash prioritize:
   - Accurately modeling real RTGS systems as they exist?
   - Exploring optimal theoretical settlement strategies?
   - Both (configurable modes)?

3. **Policy vs System**: Should batching be:
   - A policy decision (agents choose to batch)?
   - A system constraint (RTGS enforces batch windows)?
   - Both (system provides capability, policies use it)?

4. **Backward Compatibility**: If we add batching:
   - Should existing scenarios still work?
   - Should there be a "classic RTGS" mode?
   - How do we document the differences?

---

## Deliverables

1. **Research Report**: Comprehensive findings on real-world RTGS batching practices
2. **Design Proposal**: If batching is warranted, detailed implementation plan
3. **Comparative Analysis**: SimCash current behavior vs real-world systems
4. **Recommendations**: Should SimCash change, and if so, how?

---

## Contact for Questions

**Research Lead**: [To be assigned]

**Technical Liaison**: Payment simulator development team

**Domain Experts**: Central bank payment systems researchers (external consultation)

---

*Document Version: 1.0*
*Date: 2025-11-14*
*Status: Research Brief - Awaiting Investigation*
