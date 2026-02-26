# Working Paper: SimCash — LLM-Optimized Payment Strategies in Simulated RTGS Environments

## Draft Notes — Conference Preparation
**Stefan [Surname TBD], Research Director, Banking and Payments Department, Bank of Canada**  
**In collaboration with Hugi Aegisberg (SimCash creator)**

---

## 1. Paper Positioning

### Target Venue
- Bank of Canada Staff Working Paper series
- Potentially: Journal of Financial Market Infrastructures, or conference presentation at Payments Canada / BIS / ECB workshops

### Core Research Question
**Can general-purpose LLMs discover operationally relevant payment strategies in simulated RTGS environments — and do these strategies reproduce stylized facts observed in real payment systems?**

### Why This Matters
1. The BIS WP 1310 (Arauz et al. 2025) showed LLMs can replicate *prudential* cash management in simplified settings. We extend this to *strategic* multi-agent optimization with heterogeneous participants, LSM mechanisms, and realistic operational features.
2. Central banks face a practical question: could AI agents eventually assist (or replace) human operators in intraday liquidity management? SimCash provides the first open-source platform to study this systematically.
3. The payment systems community lacks tools for testing AI-discovered strategies against known operational benchmarks (throughput guidelines, settlement patterns, crisis response).

### Contribution Relative to Literature
- **vs. BIS WP 1310**: We move from single-agent prompt-based experiments to multi-agent competitive optimization with heterogeneous banks, LSM, and intraday flow variation
- **vs. Castro et al. (2024/2025)**: We extend the game-theoretic framework to operationally realistic scenarios and test whether stylized facts emerge
- **vs. BoF-PSS2**: SimCash is open-source, integrates LLM optimization, and produces auditable decision-tree policies rather than black-box strategies
- **vs. Korinek (2025)**: We demonstrate the "AI agents for economics" vision in a specific, consequential domain — financial infrastructure

### Key Novelty
SimCash's LLM optimizer produces **interpretable decision trees** rather than opaque neural network policies. This is crucial for regulatory acceptance: a central bank could actually read, audit, and understand what the AI proposes.

---

## 2. Proposed Paper Structure

1. **Introduction** — Motivation, research question, contribution
2. **Related Literature** — RTGS modeling (Bech & Garratt 2003, Galbiati & Soramäki 2011, Castro et al. 2024/2025), AI in payments (Arauz et al. 2025), AI agents in economics (Korinek 2025)
3. **SimCash Platform** — Architecture, simulation engine, cost model, LSM implementation, LLM optimization loop
4. **Experimental Design** — Scenario taxonomy, calibration to real systems, experiment protocol
5. **Results**
   - 5.1 Baseline: Can AI find known equilibria? (Castro replication)
   - 5.2 Scaling: How do strategies change with network size?
   - 5.3 Realism: Do AI agents reproduce RTGS stylized facts?
   - 5.4 Stress: How do strategies adapt to crises?
   - 5.5 Mechanism Design: Does LSM configuration affect strategic behavior?
6. **Discussion** — Operational implications, limitations, regulatory considerations
7. **Conclusion**

---

## 3. Experiment Program

### Phase 1: Baseline Replication (Castro et al.)
**Purpose:** Establish that SimCash + LLM optimization recovers known results.

| Experiment | Scenario | Rounds | Key Question |
|-----------|----------|--------|-------------|
| B1 | 2 Banks, 3 Ticks | 10 | Does AI find the analytical equilibrium? |
| B2 | 2 Banks, 12 Ticks | 10 | Does AI discover intraday patterns (early caution → late urgency)? |
| B3 | BIS WP 1310 Liquidity-Delay | 10 | Does AI replicate the BIS Box 3 optimal pre-funding? |

### Phase 2: Network Scaling
**Purpose:** Document how strategy complexity grows with network size.

| Experiment | Scenario | Rounds | Key Question |
|-----------|----------|--------|-------------|
| N1 | 2 Banks, 8 Ticks | 10 | Bilateral baseline |
| N2 | 3 Banks, 6 Ticks | 10 | Does trilateral coordination emerge? Free-riding? |
| N3 | 4 Banks, 8 Ticks | 10 | Network cascade effects? |
| N4 | 5 Banks, 12 Ticks | 10 | Does efficiency degrade at scale? |

### Phase 3: Operational Realism (NEW SCENARIOS)
**Purpose:** Test whether AI discovers strategies resembling real RTGS operations.

| Experiment | Scenario | Rounds | Key Question |
|-----------|----------|--------|-------------|
| R1 | Lynx Day (custom, 4 banks, 24 ticks) | 10 | Morning conservation → afternoon acceleration? |
| R2 | Hub & Spoke (custom, 5 banks) | 10 | Does the hub bank adopt different strategy than spokes? |
| R3 | Throughput Guidelines (custom) | 10 | Can AI learn to comply with throughput targets? |
| R4 | Heterogeneous Payment Sizes (custom) | 10 | Priority-sensitive strategies? Large vs. small payment treatment? |

### Phase 4: Crisis & Stress
**Purpose:** Test strategic adaptation under stress.

| Experiment | Scenario | Rounds | Key Question |
|-----------|----------|--------|-------------|
| S1 | 2 Banks, High Stress | 10 | Over-conservatism under extreme penalties? |
| S2 | Advanced Policy Crisis (3-day) | 5 | Multi-day adaptation? |
| S3 | Crisis Resolution (10-day) | 3 | Post-intervention behavior? Return to equilibrium? |
| S4 | Information-Driven Crisis (custom) | 5 | Liquidity hoarding dynamics? |

### Phase 5: LSM Mechanism Design
**Purpose:** How does LSM configuration affect equilibrium strategies?

| Experiment | Scenario | Rounds | Key Question |
|-----------|----------|--------|-------------|
| M1 | 4 Banks, 8 Ticks — no LSM | 10 | Pure RTGS baseline |
| M2 | 4 Banks, 8 Ticks — bilateral only | 10 | Bilateral netting effects |
| M3 | 4 Banks, 8 Ticks — bilateral + cycle | 10 | Full LSM (current default) |
| M4 | 4 Banks, 8 Ticks — TARGET2 sequencing | 10 | Algorithm sequencing effects |

---

## 4. Stylized Facts to Test For

From the RTGS literature, we expect well-functioning payment systems to exhibit:

1. **Intraday liquidity pattern**: Conservative early, aggressive late (Bech & Garratt 2003)
2. **Free-riding incentive**: Smaller banks delay to benefit from larger banks' liquidity (Galbiati & Soramäki 2011)
3. **Throughput clustering**: Payments bunch around throughput guideline checkpoints
4. **LSM queue management**: Strategic use of Queue 2 to reduce liquidity needs
5. **Crisis hoarding**: Liquidity conservation during uncertainty (as observed Sept 11, 2001 and 2008 crisis)
6. **Hub premium**: Clearing banks bear disproportionate costs in hub-spoke networks
7. **Settlement rate near 100%**: Real systems almost never fail to settle — penalty avoidance dominates

### Preliminary Evidence from Lynx Day (Experiment R1, pilot run)
- ✅ **100% settlement rate** maintained across all 5 rounds (171/171 payments)
- ✅ **Hub premium partially observed**: CLEARING_MAJOR bore all costs in Round 2 (delay=211)
- ⚠️ **Intraday pattern unclear**: Need tick-level replay analysis
- ⚠️ **Free-riding**: Three smaller banks achieved zero cost — potentially too easy. May need recalibration.
- ❌ **System found near-zero cost equilibrium too quickly**: Only 4 total cost by Round 5. Suggests scenario may not be challenging enough — need to reduce initial liquidity or increase payment volumes.

---

## 5. Calibration Notes

### What "Realistic" Means
We're not trying to replicate Lynx transaction-for-transaction. We're testing whether the *qualitative patterns* that emerge from AI optimization match what we observe in real systems. The scenarios should be:
- **Structurally realistic**: Heterogeneous participants, time-varying flows, LSM
- **Parametrically plausible**: Cost ratios that create genuine trade-offs
- **Computationally tractable**: LLM optimization needs <100 rounds to converge

### Key Calibration Challenges
1. **Cost ratios**: The delay/liquidity/penalty cost ratios determine what strategies are rational. Too cheap liquidity → trivial solution (borrow everything). Too expensive → trivial (delay everything). Need the sweet spot.
2. **Payment volumes**: Too few payments → degenerate equilibria (as seen in 2-bank, 2-tick). Too many → LLM can't process decision trees in reasonable time.
3. **LSM effectiveness**: If LSM is too powerful, it solves everything and strategies don't matter. Need scenarios where LSM helps but doesn't eliminate trade-offs.

---

## 6. Experiment Log

### Pilot Experiments (2026-02-21)

#### P1: 2 Banks, 2 Ticks (Library)
- **Config**: 3 rounds, Live AI (Vertex), Full decision trees
- **Result**: Degenerate equilibrium. Zero liquidity allocation, 0% settlement, pure delay management. 75.9% cost reduction (100K → 24,130).
- **Interpretation**: Action space too small. The AI discovered it's cheaper to pay delay costs than allocate any liquidity. This validates Castro et al.'s finding that minimal scenarios can produce corner solutions.
- **Paper relevance**: Use as motivating example for why complexity matters.

#### P2: Lynx Day — Intraday Flow Patterns (Custom)
- **Config**: 5 rounds, Live AI (Vertex), Full decision trees. 4 heterogeneous banks (CLEARING_MAJOR: 5000 balance, CLEARING_SECOND: 3000, REGIONAL_BANK: 1500, SMALL_BANK: 500). 24 ticks/day. 5 GlobalArrivalRateChange events for intraday pattern. Bilateral + cycle LSM.
- **Result**: 
  - Round 1 cost: 3, Final cost: 4 (cost increase, not reduction)
  - 100% settlement rate throughout
  - Round 2 spike to 215 (CLEARING_MAJOR delay costs), then recovery
  - All banks converged to fraction=0.500
  - Three smaller banks at zero cost all 5 rounds
- **Interpretation**: LSM + sufficient liquidity → near-trivial equilibrium. The scenario needs more tension. Options: (a) reduce opening balances, (b) increase payment volumes, (c) add deadline pressure, (d) increase liquidity costs.
- **Paper relevance**: Demonstrates importance of calibration. Also shows LSM effectiveness — which is itself a finding worth documenting.

#### B3: BIS WP 1310 — Liquidity-Delay Trade-off (10 rounds, Live AI, Full trees)
- **Config**: 2 banks (FOCAL_BANK, COUNTERPARTY), 3 ticks/day, deterministic, LSM. Liquidity cost 150 bps/tick, delay 0.01/tick/cent, priority delay multipliers.
- **Result**:
  - Round 1 cost: 22,500 → Final cost: 15,000 (33.3% reduction)
  - Settlement rate: 75.0% (3/4 payments, stable from R2-R10)
  - FOCAL_BANK: frac=0.000, 50% settled, delay=15,000
  - COUNTERPARTY: frac=0.500, 100% settled, zero cost
  - Converged by Round 2, stable for 8 more rounds
- **Interpretation**: **Asymmetric Nash equilibrium with free-riding.** The AI finds an individually rational but socially suboptimal outcome. FOCAL_BANK "gives up" on liquidity allocation — delay costs are cheaper than liquidity costs for that agent. COUNTERPARTY free-rides at half allocation. This reproduces the classic coordination failure in RTGS systems (Galbiati & Soramäki 2011). The AI does NOT find the Pareto-optimal cooperative outcome.
- **Paper relevance**: **KEY RESULT.** Demonstrates: (1) LLM finds stable equilibrium, (2) equilibrium exhibits known strategic pathology (free-riding), (3) individual rationality ≠ social optimality. Perfect contrast with cooperative mechanism design literature.

#### N3: 4 Banks, 8 Ticks (10 rounds, Live AI, Full trees)
- **Config**: 4 homogeneous banks (BANK_A through BANK_D), 8 ticks/day, stochastic.
- **Result**:
  - Round 1 cost: 132,800 → Final cost: 112,216 (15.5% reduction)
  - 100% settlement rate throughout
  - **Symmetry breaking**: BANK_A found frac=0.190 (cost 12,616) while B/C/D at frac=0.500 (cost 33,200)
  - All costs are liquidity costs — zero delay, zero penalty
  - BANK_B uniquely has a [Release] action in payment tree
  - LLM hallucinated invalid field reference (`bilateral_offset_available`) for BANK_C at Round 7, causing experiment error. Recovered.
- **Interpretation**: **Spontaneous symmetry breaking in a symmetric game.** Despite identical initial conditions, one bank (A) discovers a more efficient strategy and diverges. The others remain at the initial "safe" allocation. This mirrors real RTGS dynamics where some banks are more active optimizers than others. The hallucination issue is also paper-relevant: LLM agents can propose invalid strategies that crash the system — a critical operational risk.
- **Paper relevance**: (1) Symmetry breaking as emergent phenomenon, (2) LLM reliability/hallucination in critical infrastructure context, (3) 100% settlement maintained despite divergent strategies — LSM cushions the network.


#### S1: 2 Banks, High Stress (10 rounds, Live AI, Full trees)
- **Config**: 2 banks, 12 ticks/day, stochastic. Deadline penalty $2,500, EOD penalty $5,000 (5× normal).
- **Result**:
  - Round 1 cost: 99,600 → Final cost: 44,609 (55.2% reduction — strongest optimization)
  - 100% settlement rate throughout (50/50 in final round)
  - BANK_A: frac=0.200, liq=398, delay=579, total=20,499
  - BANK_B: frac=0.230, liq=458, delay=1,202, total=24,110
  - Zero penalties ever triggered despite 5× penalty rates
  - Cost evolution: smooth downward curve, steepest learning R4-R7
- **Interpretation**: **Penalty-driven optimization is strongest.** Three-phase learning: (1) over-allocate to avoid scary penalties, (2) progressively reduce liquidity, (3) accept small delay costs as optimal trade-off. The 55.2% reduction vs. 33.3% in BIS suggests high-penalty environments create stronger optimization incentives. Both banks maintain 100% settlement throughout — the AI is risk-averse to penalties, which is exactly what a prudent human cash manager would be.
- **Contrast with BIS**: BIS (low penalties) → asymmetric equilibrium, 75% settlement, free-riding. High Stress → symmetric equilibrium, 100% settlement, cooperative-like behavior. **Penalty structure fundamentally alters strategic dynamics.** This is a mechanism design insight: stronger penalties produce better system outcomes despite higher individual costs.
- **Paper relevance**: **KEY RESULT.** Demonstrates that incentive structure (penalty calibration) determines whether AI agents converge to cooperative or adversarial equilibria. Direct implication for RTGS designers: throughput guidelines backed by meaningful penalties may produce better system-level outcomes than relying on voluntary cooperation.

---

## 7. Emerging Paper Narrative

### The Big Picture
Across four experiments, a coherent story is emerging about how LLM-based agents behave in payment systems:

1. **Complexity threshold**: Minimal scenarios (2 banks, 2 ticks) produce degenerate results. Meaningful strategic behavior requires sufficient action-space complexity.

2. **Known pathologies emerge naturally**: The AI discovers free-riding, asymmetric equilibria, and coordination failures without being taught these concepts. This validates SimCash as a tool for studying strategic interactions.

3. **Incentive structure matters enormously**: Low penalties → adversarial, asymmetric outcomes (BIS: 75% settlement). High penalties → cooperative-like, symmetric outcomes (High Stress: 100% settlement, 55% cost reduction). This is a mechanism design result.

4. **Symmetry breaking in symmetric games**: Even with identical agents, the LLM optimization process can break symmetry — one bank discovers a more efficient strategy while others remain at a safe default (4-bank result).

5. **LSM as coordination mechanism**: When LSM is effective and liquidity is sufficient, it eliminates most strategic tension (Lynx Day: near-zero costs). This means interesting experiments need to calibrate LSM power vs. liquidity scarcity.

6. **LLM reliability as operational risk**: Hallucinated field references can crash experiments. In a real deployment, this would be a critical failure mode requiring robust validation layers.

### Proposed Contribution Statement
"We introduce SimCash, an open-source platform for studying AI-discovered payment strategies in simulated RTGS environments. Using LLM-based policy optimization, we demonstrate that: (1) general-purpose AI agents discover known strategic pathologies (free-riding, coordination failure) without domain-specific training; (2) penalty structure is a key determinant of whether AI agents converge to cooperative or adversarial equilibria; (3) spontaneous symmetry breaking occurs in symmetric multi-bank games; and (4) LSM mechanisms substantially reduce the strategic complexity of payment coordination. Our results have implications for the design of AI-assisted liquidity management systems and the calibration of RTGS incentive mechanisms."


#### R1-v2: Liquidity Squeeze — Heterogeneous Network (10 rounds, Live AI, Full trees)
- **Config**: Custom scenario. 4 heterogeneous banks: MAJOR_BANK (balance 300K, pool 500K, rate 3.0/tick), MID_BANK_1 & 2 (150K, 300K, rate 2.0), SMALL_BANK (50K, 100K, rate 1.0). 12 ticks/day. LSM bilateral+cycle. Delay 0.15/¢/tick, liquidity 100bps/tick, deadline $1,500, EOD $5,000, overdraft 50bps, overdue multiplier 2×.
- **Design rationale**: Create genuine resource scarcity — opening balances cover ~60% of expected daily volumes. Force meaningful trade-offs between liquidity holding, delay acceptance, and settlement risk.
- **Result**:
  - Round 1 cost: 72,000 → Final cost: 66,245 (8.0% reduction)
  - 100% settlement rate throughout (87/87 in final round)
  - **Differentiated strategies by bank size:**
    - MAJOR_BANK: frac=0.400, liq=480, delay=0, total=24,000
    - MID_BANK_1: frac=0.500, liq=360, delay=245, total=18,245
    - MID_BANK_2: frac=0.500+[Release], liq=360, delay=0, total=18,000
    - SMALL_BANK: frac=0.500+[Release], liq=120, delay=0, total=6,000
  - Costs scale proportionally with bank size (30K:18K:18K:6K ≈ 5:3:3:1)
  - Balance dynamics: MAJOR ~$5,238, MID ~$2,619, SMALL near zero
  - Systematic LLM hallucination: `bilateral_offset_available` (nonexistent field)
- **Interpretation**: **Most operationally realistic result.** Four key findings:
  1. **Size-dependent optimization**: MAJOR_BANK reduces liquidity fraction more aggressively (0.400 vs 0.500) because it recycles more incoming payments — exactly what real clearing banks do.
  2. **Symmetry breaking between identical agents**: MID_BANK_1 accepts delay costs while MID_BANK_2 doesn't, despite identical parameterization. Path dependence in LLM optimization.
  3. **Active payment management**: Two banks developed Release actions (proactive queue release) while two didn't. The AI discovered that active payment management can substitute for passive liquidity holding.
  4. **Proportional cost scaling**: Cost allocation mirrors real RTGS fee structures where costs scale with transaction volumes.
  5. **Modest optimization (8%)**: The scenario leaves less room for dramatic improvement compared to High Stress (55%), but this is more realistic — well-calibrated systems don't have 50% waste to eliminate.
- **Paper relevance**: **KEY RESULT — HEADLINE SCENARIO.** This is the most operationally realistic experiment and should anchor the paper's main findings. Demonstrates that LLMs discover bank-size-appropriate strategies, active vs. passive payment management, and realistic cost structures — all without domain-specific training.

---

## 8. Summary of Results Table (for paper)

| Experiment | Banks | Ticks | R1 Cost | Final Cost | Δ% | Settlement | Key Finding |
|-----------|-------|-------|---------|-----------|-----|-----------|------------|
| 2B 2T (pilot) | 2 | 2 | 100,000 | 24,130 | -75.9% | 0% | Degenerate: zero settlement |
| BIS WP 1310 | 2 | 3 | 22,500 | 15,000 | -33.3% | 75% | Asymmetric Nash, free-riding |
| 4B 8T | 4 | 8 | 132,800 | 112,216 | -15.5% | 100% | Symmetry breaking, hallucination |
| High Stress | 2 | 12 | 99,600 | 44,609 | -55.2% | 100% | Penalty-driven cooperation |
| Lynx Day | 4 | 24 | 3 | 4 | +33% | 100% | LSM dominance, trivial eq. |
| **Liq. Squeeze** | **4** | **12** | **72,000** | **66,245** | **-8.0%** | **100%** | **Size-dependent strategies** |

---

## 9. Open Questions

1. **Reproducibility**: How sensitive are results to the random seed? Need multiple runs per scenario.
2. **LLM model dependence**: SimCash uses GLM-4.7 via Vertex AI. Would results differ with GPT-4, Claude, etc.?
3. **Decision tree interpretability**: Can we extract human-readable strategy descriptions from the JSON trees?
4. **Convergence**: How many rounds until policies stabilize? Is there cycling?
5. **Welfare analysis**: Can we measure system-level efficiency (total cost, settlement rate) vs. individual rationality?

---

## 8. Next Steps

- [ ] Run Phase 1 baselines (B1-B3) with 10 rounds each
- [ ] Build Hub & Spoke scenario
- [ ] Build Throughput Guidelines scenario  
- [ ] Recalibrate Lynx Day (reduce liquidity, increase volumes)
- [ ] Run Phase 2 network scaling (N1-N4)
- [ ] Analyze tick-level replays for intraday patterns
- [ ] Extract and compare decision trees across rounds

---

*Last updated: 2026-02-21*
