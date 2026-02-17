# Game Concept Document Analysis

**Date:** 2026-02-17  
**Source:** `docs/game_concept_doc.md`  
**Purpose:** Thorough analysis of the SimCash concept document — vision, mechanics, and gap assessment against current web sandbox implementation.

---

## 1. Full Vision

SimCash is a **payment system simulator** for studying strategic behavior in interbank Real-Time Gross Settlement (RTGS) systems. It models the daily coordination problem banks face: balancing liquidity costs against delay costs when settling payments through a central bank.

### Core Purpose Statement

> "A tool for studying strategic behavior in interbank payment systems."

### Four Primary Use Cases

1. **Understand coordination** — How banks coordinate (or fail to coordinate) intraday payment flows
2. **Study LSM effectiveness** — Liquidity-saving mechanisms under various conditions
3. **Train AI agents** — To make cash management decisions
4. **Explore policy questions** — Around payment system design

### Real-World Grounding

The simulation draws from:
- **TARGET2 (T2)**: Eurosystem's RTGS (~€1.7 trillion daily)
- **Fedwire**: US Federal Reserve RTGS
- **RIX-RTGS**: Sweden's Riksbank system

### The Fundamental Tension (The "Game")

> "Liquidity costs money... Delay costs money."

Banks face a **coordination problem**: if Bank A waits for incoming payments before sending, and Bank B does the same, both suffer delays — even though cooperation (sending simultaneously) would benefit everyone. This is explicitly described as resembling a **Prisoner's Dilemma** or **Stag Hunt** depending on parameters.

---

## 2. Game Mechanics, Phases, and Player Interactions

### 2.1 Time Structure

- Business days divided into **discrete ticks** (60-100 per day)
- Each tick is a decision point for banks
- Deterministic: same seed + config = identical results

### 2.2 Two-Queue Architecture

| Queue | Location | Purpose | Costs | Strategic? |
|-------|----------|---------|-------|-----------|
| **Queue 1** (Internal) | Bank-side | Bank holds payments before submitting | Delay costs accrue | Yes — the cash manager's desk |
| **Queue 2** (Central RTGS) | Central bank | Payments awaiting liquidity | No delay costs | No — mechanical waiting |

> "Banks choose when to submit payments (strategic decision), but once submitted, payments either settle immediately or wait for liquidity (mechanical process)."

### 2.3 Agents (Banks)

Each bank maintains:
- **Settlement Account Balance** — reserves at central bank
- **Credit Headroom** — intraday credit (collateralized or priced)
- **Payment Obligations** — outgoing payments with amounts, deadlines, priorities

### 2.4 Transaction Properties

- **Amount** (integer cents, no floating point)
- **Deadline** (latest tick for settlement)
- **Priority** (0-10 internal, plus RTGS declared priority)
- **Counterparties** (sender/receiver)

### 2.5 Settlement Mechanics

#### Immediate RTGS Settlement
1. Check if sender's balance + credit headroom covers amount
2. If yes → immediate debit/credit (final, irreversible)
3. If no → enters Queue 2

#### Liquidity-Saving Mechanisms (LSM)

Three algorithms run in sequence:

1. **Algorithm 1 (FIFO)**: Settle queued payments in submission order
2. **Algorithm 2 (Bilateral Offsetting)**: A owes B $500k, B owes A $300k → both settle if A covers net $200k
3. **Algorithm 3 (Multilateral Cycle Detection)**: A→B, B→C, C→A cycles settle simultaneously

**Key LSM principles:**
- Full-value settlement (no splitting by LSM)
- Atomic execution (all-or-nothing)
- Conservation (net positions sum to zero)
- Limit-aware

**Entry Disposition Offsetting**: Before entering Queue 2, check for immediate bilateral offset opportunity.

### 2.6 Cash Manager's Decisions

The core player decisions per tick:

1. **When to release payments** — early (avoid delay costs, risk running short) vs. hold (wait for incoming, risk gridlock)
2. **How much liquidity to access** — draw credit (pay costs) vs. wait (risk delays)
3. **Whether to split large payments** — partial settlement vs. operational costs
4. **Priority assignment** — internal priority (0-10) vs. RTGS declared priority (HighlyUrgent/Urgent/Normal)

### 2.7 Dual Priority System (TARGET2-aligned)

**Internal Priority (0-10):**
- Urgent (8-10), Normal (4-7), Low (0-3)
- Controls Queue 1 ordering

**RTGS Declared Priority:**
- HighlyUrgent > Urgent > Normal
- Controls Queue 2 processing order
- Banks can withdraw and resubmit with different RTGS priority

**Priority Escalation:**
```
escalated_priority = min(10, original_priority + max_boost × progress)
```

### 2.8 Bilateral and Multilateral Limits

- **Bilateral**: Max outflow to specific counterparty per day
- **Multilateral**: Max total outflow to all counterparties
- Exceeded → payments queue (don't fail)

### 2.9 Cost Structure

| Cost Type | Formula Basis | When |
|-----------|---------------|------|
| **Overdraft** | `bps × |negative_balance| × (1/ticks_per_day) / 10000` | Per tick |
| **Collateral** | `bps × posted_collateral × (1/ticks_per_day) / 10000` | Per tick |
| **Delay (Queue 1 only)** | `penalty_per_tick × (current - arrival)` | Per tick |
| **Deadline penalty** | Fixed one-time charge | On deadline miss |
| **Overdue delay** | `penalty × overdue_multiplier(5×) × ticks_overdue` | Per tick after deadline |
| **Split friction** | `cost × (num_parts - 1)` | Per split event |
| **End-of-day penalty** | `penalty × (remaining/original)` | End of day |

### 2.10 Emergent Phenomena (Expected)

- **Gridlock** — circular dependency when all banks wait
- **Morning slowness / afternoon rush** — delay then rush pattern
- **Free-riding** — delay while others pay, benefit from incoming liquidity

---

## 3. Scenarios, Policies, and Optimization

### 3.1 Policy System

**Decision Tree DSL** — JSON-based condition/action trees:
- Condition nodes evaluate expressions against context (140+ fields)
- Action nodes: release, hold, split, post_collateral

**Four tree types:**

| Tree | When Evaluated | Controls |
|------|---------------|----------|
| `payment_tree` | Per pending payment | Release/hold/split |
| `bank_tree` | Once per tick (before payments) | Bank-wide decisions |
| `strategic_collateral_tree` | Before settlement attempts | Collateral posting |
| `end_of_tick_collateral_tree` | After all settlements | End-of-tick adjustments |

**Built-in policies:** Fifo, Deadline, LiquidityAware, TreePolicy

**Policy context** provides 140+ fields including balance state, queue state, transaction details, time, costs, and 10 custom registers for inter-tick memory.

### 3.2 Configuration Toggles

| Toggle | Default | Effect |
|--------|---------|--------|
| `entry_disposition_offsetting` | false | Bilateral offset check at Queue 2 entry |
| `algorithm_sequencing` | true | LSM algorithm sequence |
| `deferred_crediting` | false | Defer credits to end of tick |
| `priority_mode` | false | Strict priority band processing in Queue 2 |
| `priority_escalation.enabled` | false | Auto-boost priority near deadlines |
| `queue1_ordering` | "Fifo" | Queue 1 sort mode |

### 3.3 The Single-Agent Optimization Perspective

**Information set:**
- Known: current balance, pending payments, historical incoming patterns, cost parameters
- Unknown: future arrivals, other banks' strategies, exact incoming timing

**Liquidity Beats concept:**
> Incoming settlements modeled as fixed external events — "like a musical beat, these are the rhythmic moments when liquidity arrives."

Historical transaction timing offsets are preserved, implicitly capturing LSM effects, Queue 2 dynamics, and gridlock patterns.

### 3.4 The Coordination Game

Explicitly modeled as a 2×2 game:

|  | B: Wait | B: Pay Early |
|--|---------|-------------|
| **A: Pay Early** | A loses | Mutual gain |
| **A: Wait** | GRIDLOCK | B loses |

**Game structure depends on cost ratios:**
- High delay costs → Pay early dominates
- Low delay costs, high liquidity costs → Wait dominates
- Balanced → Mixed strategies, LSM crucial

### 3.5 Multi-Agent Convergence

1. Each agent uses policies from previous day
2. Simulate interactions
3. Observe outcomes
4. Update policies via bootstrap evaluation
5. Converge toward approximate equilibrium

> "This delayed best-response dynamic is realistic—real treasury departments analyze yesterday's data to inform today's decisions."

### 3.6 Research Questions

**Liquidity Management:** Minimum liquidity for target settlement rates, collateralized vs. priced credit, value of LSM

**Coordination:** Policies encouraging early release, throughput guidelines, AI vs. rule-based strategies

**System Design:** Priority features, optimal LSM design, intraday credit pricing

**Stress Testing:** Liquidity squeezes, operational issues, correlated shocks

---

## 4. Current Web Sandbox Implementation

Based on the `web/` directory structure:

### Backend (`web/backend/app/`)

| Module | Implements |
|--------|-----------|
| `main.py` | FastAPI app, routes |
| `simulation.py` | Runs Rust engine via PyO3 |
| `game.py` | Game session management |
| `models.py` | Data models |
| `config.py` | Configuration |
| `auth.py` | Firebase authentication |
| `storage.py` | Persistence (likely Firestore) |
| `presets.py` | Preset scenario configurations |
| `scenario_pack.py` | Scenario pack management |
| `policy_runner.py` | Policy execution |
| `llm_agent.py` | LLM-based policy optimization |
| `streaming_optimizer.py` | WebSocket streaming for LLM optimization |
| `bootstrap_eval.py` | Bootstrap evaluation of policies |
| `admin.py` | Admin dashboard API |

### Frontend (`web/frontend/src/`)

**Views:**
- `HomeView` — Landing page
- `DashboardView` — Main simulation dashboard
- `GameView` — Game interaction view
- `ConfigView` — Configuration editor
- `AgentsView` — Agent management
- `AnalysisView` — Results analysis
- `EventsView` — Event log viewer
- `LibraryView` — Scenario/policy library
- `ReplayView` — Simulation replay
- `DocsView` — Documentation

**Components:**
- `BalanceChart`, `CostChart` — Time-series visualization
- `AgentCards`, `AgentDetailModal` — Agent status display
- `AgentReasoningPanel` — LLM reasoning display
- `PaymentFlow`, `QueueVisualization` — Payment flow visualization
- `EventLog` — Event stream display
- `Controls` — Simulation controls (play/pause/step)
- `SimulationSummary` — Results summary
- `HowItWorks` — Educational content
- `LoginPage` — Authentication UI
- `AdminDashboard` — Admin interface
- `Toast` — Notifications

**Infrastructure:**
- Firebase auth (`firebase.ts`, `AuthContext.tsx`)
- WebSocket game connection (`useGameWebSocket.ts`)
- API client (`api.ts`)

### Tests

Tests exist for: auth, storage, admin, bootstrap eval, game API, game engine, game setup, GIL release, real LLM integration, WebSocket streaming.

---

## 5. Gaps Between Vision and Current Implementation

### 5.1 What the Web Sandbox Likely Implements ✅

Based on file names and the Rust engine backing:
- Basic simulation execution (Rust engine via PyO3)
- Agent/bank management with balance tracking
- Payment flow visualization (Queue 1 → Queue 2)
- Real-time simulation with tick-by-tick controls
- LLM-based policy optimization with streaming
- Bootstrap evaluation
- Firebase authentication and user management
- Scenario presets and libraries
- WebSocket-based live updates
- Cost tracking and chart visualization
- Admin dashboard

### 5.2 Concept Doc Features Likely NOT Fully Exposed in Web UI 🔶

1. **Full configuration toggle surface** — The concept doc describes many toggles (entry disposition offsetting, deferred crediting, priority mode, etc.) that may not all be exposed in the web config UI

2. **Multi-day convergence loop** — The concept doc describes iterative multi-day policy convergence; the web sandbox likely runs single-day simulations

3. **Game-theoretic analysis** — The Prisoner's Dilemma / Stag Hunt framing, Nash equilibrium convergence visualization

4. **Throughput guidelines** — Marked as `[ ]` (unchecked) in the validation checklist — not yet implemented

5. **Interactive "cash manager" role** — The concept doc frames the player as a cash manager making decisions; the web sandbox appears more observer-oriented (watch AI agents) than hands-on player

6. **Stress testing scenarios** — Liquidity squeezes, operational failures, correlated shocks — likely not prebuilt

7. **Full priority system visualization** — Dual priority (internal vs RTGS), priority escalation curves, withdrawal/resubmission

8. **Bilateral/multilateral limit configuration per agent** — May exist in engine but not in web UI

9. **Custom register system** — 10 numeric registers for policy memory across ticks — likely engine-supported but not web-exposed

10. **Payment splitting decisions** — Split friction costs and strategic splitting UI

### 5.3 Structural Gaps 🔴

1. **No "game" framing** — The concept doc is titled "game concept" but the web sandbox appears to be a simulation viewer, not a game. There's no:
   - Player-controlled bank (you ARE the cash manager)
   - Scoring/leaderboard
   - Progressive difficulty
   - Tutorial/onboarding as gameplay

2. **No multiplayer** — The coordination game is the heart of the concept, but the web sandbox appears single-user

3. **No explicit scenario progression** — The concept doc implies scenarios of increasing complexity; the web sandbox has presets but likely no guided progression

4. **Research question framework** — The concept doc lists specific research questions; the web sandbox doesn't appear to structure exploration around answering these

---

## 6. Key Quotes and Design Principles

### The Fundamental Tension
> "Liquidity costs money. Holding large reserves at the central bank ties up capital that could earn returns elsewhere."
> "Delay costs money. Client service agreements, regulatory deadlines, and reputational concerns create pressure to settle payments promptly."

### The Two Queues Are Sacred
> "This separation reflects reality: banks choose when to submit payments (strategic decision), but once submitted, payments either settle immediately or wait for liquidity (mechanical process). The distinction is crucial for understanding where AI agents can meaningfully intervene."

### Determinism Is Non-Negotiable
> "Same seed + same configuration = identical results. All randomness comes from the seeded RNG. No system time, network calls, or non-deterministic operations."

### Full-Value Settlement
> "Individual payments always settle at their original amount. LSM reduces liquidity requirements by smart grouping, not by splitting payments."

### Integer Arithmetic
> "Always in integer cents—no floating point"

### Delay Costs Only in Queue 1
> "Payments held by the bank create client-facing delays. Payments queued at the central bank (Queue 2) are waiting for system-level liquidity—the bank has already submitted, so no further delay penalty applies."

### Liquidity Beats
> "Like a musical beat, these are the rhythmic moments when liquidity arrives. The AI cannot change when other banks pay—it can only decide how to respond."

### Realistic Dynamics
> "This delayed best-response dynamic is realistic—real treasury departments analyze yesterday's data to inform today's decisions, not react instantaneously."

### Cost Ratios Drive Game Structure
> "High delay costs → Pay early is dominant strategy. Low delay costs, high liquidity costs → Wait is dominant strategy. Balanced costs → Mixed strategies emerge, LSM becomes crucial."

---

## Summary

The game concept document is a **deeply rigorous, research-grade specification** of an interbank payment simulation. It precisely defines:

- The two-queue architecture and settlement mechanics
- TARGET2-aligned LSM algorithms and priority systems
- A complete cost model with explicit formulas
- Game-theoretic framing of the coordination problem
- AI agent optimization via bootstrap evaluation
- Configuration toggles for exploring different system designs

The **current web sandbox** implements the core simulation engine and provides a solid visualization/interaction layer with LLM optimization. However, it remains primarily a **simulation tool** rather than the **"game"** the concept document's title implies. The biggest gaps are:

1. **No player-as-cash-manager gameplay**
2. **No multiplayer coordination dynamics**
3. **Throughput guidelines not implemented** (only unchecked validation item)
4. **Research question exploration framework missing**
5. **Many engine features (priority system, limits, deferred crediting) likely not fully surfaced in web UI**

The engine appears to implement the full concept; the web layer surfaces a subset for demonstration and AI optimization purposes.
