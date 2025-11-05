# RTGS-First Game Design Doc

## 1) Purpose & core loop

**Purpose.** Simulate strategic intraday release/funding behavior of banks submitting payments into a T2-like RTGS with queues and liquidity-saving mechanisms (LSMs). Agents learn when to **send now**, **delay/pacing**, or **source liquidity** (overdraft/collateralized intraday credit), with outcomes shaped by **recycling** and **queue optimisation**. ([European Central Bank][2])

**Core loop (discrete ticks, e.g., 60–100 per day):**

1. **Arrivals.** New outgoing payment orders land at each bank, entering **Queue 1** (bank's internal queue).
2. **Decision hook (cash-manager role at Queue 1).** For its Queue 1 backlog, each bank decides what to **submit to RTGS** now vs. **hold in Queue 1**, whether to **split** large items into N separate transactions, and whether to **add liquidity** (draw intraday credit / post collateral / interbank borrow).
3. **RTGS settlement pass (Queue 2 processing).**

   * Submitted transactions enter **Queue 2** (RTGS central queue)
   * **Immediate settlement** if bank's **central bank balance + credit headroom** covers the item → debit payer bank, credit payee bank (final).
   * Otherwise remain in **Queue 2** awaiting liquidity
   * **LSM/optimisation** tries **offsetting** and **multilateral cycles/batches** to release queued items with minimal net liquidity. ([European Central Bank][1])
4. **Costs accrue.** Liquidity cost (overdraft/collateral), delay cost (Queue 1 only), split friction, deadline penalties.
5. **Public signals.** Coarse throughput/Queue 2 pressure published to all banks.
6. **Close.** End-of-day: penalties for unsettled transactions in Queue 1; any residuals in Queue 2 settled via expensive backstop.

> **Design intent:** Toggling credit regime and LSM strength should reproduce **gridlock vs. smooth-flow** phases seen in RTGS studies; LSMs reduce delays and liquidity usage, especially under scarcity. ([Nationalbanken][3])

## 2) Environment scaffold (T2-style)

* **Time:** Discrete ticks per day; optional multi-day episodes for learning.
* **Settlement rail:** Centralized **RTGS** (T2-style) with **queue** and **optimisation procedures/LSMs** (priorities, timed transactions available as options). ([European Central Bank][2])
* **Assumed currency/CB:** SEK at **Riksbank** operated on **T2** (conceptual assumption aligned with Riksbank’s plan). ([Riksbank][4])
* **Operating day:** Start/end ticks, optional throughput guidelines (e.g., % settled by mid-day), cut-offs.
* **Shock module:** Outage, intraday fee change, daylight cap shock, large one-off outflow, or counterparty-specific stress.

## 3) Actors & flow of funds

### 3.1 Payment lifecycle (single order)

1. **Client A → Bank A.** Bank A debits Client A internally (no interbank money moved). Transaction enters **Queue 1** (Bank A's internal queue).
2. **Bank A (decision at Queue 1).** Cash manager decides **when/how** to submit to RTGS; optionally pace a large amount by creating multiple separate transaction instructions (agent-initiated "splits").
3. **Submit to RTGS (Queue 1 → Queue 2).** Bank submits transaction to central RTGS system, entering **Queue 2** (RTGS central queue).
4. **RTGS settlement attempt.** If Bank A's **central bank balance + intraday credit** suffices → **immediate finality** (A debited, B credited). Else → remains in **Queue 2**. **LSM/optimisation** may offset cycles to settle with less liquidity. ([European Central Bank][1])
5. **Bank B → Client B.** Bank B credits Client B internally upon settlement notice.
6. **Recycling.** Bank B can immediately use incoming funds to pay others (liquidity recycling).

> **Two-Queue Architecture:** Transactions pass through two distinct queues:
> - **Queue 1 (Internal Bank Queue):** Where cash manager policy decisions occur (submit now vs. hold, split decisions, liquidity decisions)
> - **Queue 2 (RTGS Central Queue):** Where transactions await liquidity at the central bank; LSM/optimisation procedures operate here
>
> **Why queues & LSMs?** RTGS aims for fast real-time settlement **with reduced liquidity**, so systems run **optimisation procedures** continuously to dissolve queues via offsetting and cycles. ([European Central Bank][5])

### 3.2 Cash-manager decision points (what the AI will replace)

* **At Queue 1 (on arrival):** release to RTGS now vs. hold in Queue 1; **voluntarily split large items** into N separate payment instructions (agent-initiated "pacing").
* **Liquidity stance:** draw overdraft/collateralized intraday credit (vs. wait for inflows); adjust limits/buffers. (Collateralized intraday credit is standard in Nordic RTGS practice.) ([Nationalbanken][3])
* **While queued in Queue 2 (RTGS):** add liquidity to force settlement, or wait for LSM offset.
* **Near cut-offs:** prioritize urgent items; avoid EoD penalties regardless of liquidity cost.
* **After settlement:** free collateral/repay credit as inflows arrive to reduce cost.

> **Note on Splitting:** T2 does not support automatic partial settlement of individual transactions. Instead, **banks may voluntarily split large payments at their own initiative** at the Queue 1 decision point. When splitting:
> - The cash manager creates **N separate, independent payment instructions**
> - Each child transaction has its own transaction ID and is processed independently by RTGS
> - All children inherit the parent's sender, receiver, deadline, and priority
> - Each child has amount ≈ `parent_amount / N` (with last child getting any remainder)
> - This voluntary "pacing" is a **policy decision**, not a system feature
> - The RTGS engine (Queue 2) only ever sees fully-formed, complete payment instructions

## 4) Objects & data model

### 4.1 Payment order `Tx_k`

**Core Transaction Parameters:**
* `amount A_k` — Payment amount (integer, in minor currency units)
* `origin_bank i` — Sender agent ID
* `dest_bank j` — Receiver agent ID
* `arrival_tick t_a` — Tick when transaction arrives at sender's Queue 1
* `deadline_tick t_d` — Latest tick for settlement (transactions past deadline may be dropped)
* `priority` — Urgency level (range: 0-10, default: 5, higher = more urgent)
  - Used by policies to order Queue 1 release decisions
  - Can optionally affect Queue 2 (RTGS) processing order if T2 priority mode enabled
* `delay_penalty_slope p_k` — Cost per tick of delay in Queue 1
* `split_friction f_s` — Cost per split when transaction is divided (see below)

**Transaction Splitting Parameters:**
* `split_threshold`: Minimum payment size eligible for agent-initiated splitting (e.g., 250M SEK)
* `max_pacing_factor`: Maximum number of child transactions allowed per split (e.g., 8)
* `split_friction f_s`: Cost per additional split — formula: `f_s × (N-1)` for N-way split
* `min_chunk_size`: Minimum size of a child transaction (prevents spam-size splits)
* `stagger_policy`: Whether all N children are submitted to RTGS immediately or staggered over ticks

> **Note:** T2 offers priority and timed transaction features; simulator flags turn these on/off. ([European Central Bank][2])

**Transaction Lifecycle:**

Transactions progress through the following states:

1. **Pending** — Transaction has arrived but not yet fully settled
   - In Queue 1: Awaiting cash manager release decision
   - In Queue 2: Submitted to RTGS, awaiting liquidity or LSM offset
2. **Settled** — Transaction fully settled with immediate finality
   - Final state: funds transferred from sender to receiver at central bank
   - Settlement tick recorded for cost/delay calculations
3. **Dropped** — Transaction rejected or past deadline
   - Removed from queues without settlement
   - Deadline penalties apply

**Split Transaction Relationships:**
- When a transaction is split, the original becomes a "parent" and N "child" transactions are created
- Each child is an independent, complete transaction with its own ID and lifecycle
- Children inherit parent's sender, receiver, deadline, and priority
- Parent is removed from Queue 1; all N children enter Queue 1 (or are immediately submitted)

### 4.2 Bank/agent `Bank_i` state at tick `t`

* **Central-bank balance** `B_{i,t}` (RTGS/CLM working balance).
* **Credit headroom** `H_{i,t}` (intraday overdraft/collateralised credit).
* **Collateral posted** and its opportunity cost.
* **Queue 1 (internal queue)** of outgoing orders awaiting release decision (with ages, deadlines, counterparties).
* **Forecasts** of near-term inflows/outflows (rules- or model-based).
* **Funding options** (money-market borrowing cost per tick).
* **Public signals** (system throughput/Queue 2 pressure).
* **Limits** (daylight cap, counterparty limits), **cut-off times**.

### 4.3 Central RTGS engine

* **Accounts:** one settlement account per bank at the central bank.
* **Entry disposition:** each submitted payment triggers immediate settlement attempt; if not possible, it goes to **Queue 2 (RTGS central queue)**; the engine maintains **per-bank net debit** checks.
* **LSM/optimisation pass (each tick on Queue 2):**

  * **Bilateral offset** (A↔B with unequal amounts): Settles BOTH transactions simultaneously if the net difference can be covered. Example: A→B 500k, B→A 300k → both settle if A can cover net 200k outflow. Settles **full transaction values**, not partial amounts. ([docs/lsm-in-t2.md](lsm-in-t2.md))
  * **Multilateral cycle search** (A→B→C→…→A with unequal amounts): Detects payment cycles and settles **all transactions at full value** if each participant can cover their net position. Example: A→B (500k), B→C (800k), C→A (700k) settles all three if B can cover -300k net outflow. **No splitting of individual payments** — each settles in full or not at all. ([docs/lsm-in-t2.md](lsm-in-t2.md))
  * **All-or-nothing execution**: If any participant in a cycle lacks liquidity for their net position, the entire cycle fails and all transactions remain queued. This mirrors T2's atomic settlement behavior.
  * Optional **batch optimisation** under bank caps.

**Key T2 Principle**: LSM achieves liquidity savings through smart **grouping** of whole payments (not by splitting individual transactions). Cycles settle groups of unequal-value payments as long as net positions are fundable. ([European Central Bank][5], [docs/lsm-in-t2.md](lsm-in-t2.md))

## 5) Actions, transitions, rewards

### 5.1 Action space (per bank per tick)

* **Queue 1 release policy:** choose which transactions from Queue 1 to submit to RTGS; select by (i) release share from total, or (ii) top-K by priority/deadline; optionally **split** large payments into N separate transactions (voluntary agent-initiated "pacing").
* **RTGS options:** set **priority/timed** flag for selected items (if enabled). ([European Central Bank][2])
* **Liquidity policy:** (a) draw intraday **overdraft/collateralised credit** up to headroom, (b) **post/release collateral**, (c) money-market borrow/repay, (d) adjust internal buffers.
* **(Optional) Signalling:** publish a willingness-to-coordinate score (non-binding).

**Agent-Initiated Splitting ("Pacing"):**
Banks decide at the Queue 1 release decision point whether to split large payments:
* **When:** If `amount > split_threshold` and conditions warrant (insufficient liquidity, approaching deadlines, high Queue 2 pressure)
* **How:** Create N separate, independent payment instructions, each a complete transaction with its own ID
  - Each child has `amount ≈ parent_amount / N` (last child gets any remainder)
  - All children inherit parent's sender, receiver, deadline, priority
  - All N children can be submitted immediately or staggered over ticks (policy choice)
* **Cost:** Split friction `f_s × (N-1)` charged when split decision is made (e.g., splitting into 3 parts → 2× `f_s`)
* **Mechanism:** Splitting happens **at Queue 1 decision point**, before RTGS submission; Queue 2 (RTGS engine) only sees N fully-formed, independent instructions
* **Benefit:** Earlier liquidity recycling from settled parts; reduced delay penalties for urgent payments by getting partial value through sooner

### 5.2 Transition

* Settlement engine debits/credits central bank accounts or queues items; LSM may clear queued sets; update balances, credit usage, queues, and costs; publish throughput; advance time.

### 5.3 Cost & reward

We minimize **total intraday cost** (maximize its negative):

[
\text{Cost}_i =
\sum_t r^{\text{od}}*i\cdot \max(-B*{i,t},0),\Delta t

* c^{\text{coll}}_i \cdot \text{collateral}_t \cdot \Delta t
* \sum_k p_k \cdot \text{delay}_k
* \sum_k f_s \cdot (\text{splits}_k-1)
* \text{funding fees}
* \text{EoD penalty}.
  ]

**Cost Components and Timing:**

1. **Liquidity cost** (overdraft/collateral cost):
   - **When:** Accrued per tick based on negative balance or collateral posted at that tick
   - **Scope:** `r^{od}_i × max(-B_{i,t}, 0)` for priced overdraft regime, or `c^{coll}_i × collateral_t` for collateralized regime
   - **Interpretation:** Cost of using intraday credit to bridge liquidity gaps

2. **Delay cost** (Queue 1 only):
   - **When:** Accrued per tick for each transaction in Queue 1 (internal bank queue)
   - **Scope:** `p_k × delay_k` where delay_k = number of ticks transaction has spent in Queue 1
   - **Important:** Transactions in Queue 2 (RTGS central queue) do NOT incur delay costs — waiting for liquidity is expected behavior
   - **Interpretation:** Proxies client SLA penalties for holding back payments at the bank level

3. **Split friction cost**:
   - **When:** Charged immediately when cash manager decides to split at Queue 1 decision point
   - **Formula:** `f_s × (N-1)` where N = number of child transactions created
   - **Example:** Splitting into 4 parts incurs `3 × f_s` additional cost
   - **Interpretation:** Operational overhead (message processing, coordination, reconciliation) of creating multiple payment instructions instead of one

4. **Deadline penalties**:
   - **When:** Charged when transaction is dropped for exceeding deadline
   - **Scope:** Per-transaction penalty for missing settlement deadline

5. **End-of-day penalties**:
   - **When:** Charged at day close for each transaction remaining unsettled in Queue 1
   - **Interpretation:** Large penalty to incentivize intraday settlement completion

**Design rationale:** Split friction ensures agents only split when the benefit (reduced delay penalties, earlier liquidity recycling) outweighs the cost. Delay costs apply only to Queue 1 to distinguish policy-driven holds from liquidity-driven waits in Queue 2.

### 5.4 System KPIs

* **Throughput** (value settled / value due) path; **avg/max delay**; **gridlock incidence**; **intraday liquidity used** (sum of max net debits); **efficiency** (value settled / liquidity used); **queue length/age**. (LSMs should improve these under tight liquidity.) ([Nationalbanken][3])

## 6) Coordination incentives (why the “game”)

* With **collateralised** intraday credit costly, each bank prefers to **wait** for inflows; if all wait, **gridlock** forms and delays mount. **LSMs** alleviate but still need *feed* of releasable items. ([Nationalbanken][3])
* With **priced** overdrafts and meaningful delay costs, dynamics can resemble a **stag hunt**: both “send-early” and “send-late” are equilibria; expectations/throughput guidance select the outcome.
* **Two-bank toy** (per unit obligation): actions **C** (release) vs **D** (delay). Choose parameters s.t. **D** strictly dominates for a **PD** (temptation>reward>punishment>sucker), or swap to get **stag-hunt**. Use this for smoke tests of your learning agents.

> Empirical backdrop: RTGS studies show optimisation/LSM notably reduces delay and liquidity need; under scarce liquidity, benefits are largest. ([Nationalbanken][3])

## 7) Settlement engine (from minimal to richer)

**Minimal RTGS:**

* Process submitted items in priority/arrival order while payer bank's settlement balance + credit headroom ≥ 0; else push to **Queue 2 (RTGS central queue)**.

**Add LSM/optimisation (T2-realistic):**

* **Bilateral offset with unequal amounts**: For each bank pair (A,B), if both have queued payments to each other, settle BOTH at full value if the net sender can cover the difference. No transaction splitting — each settles completely or remains queued.
* **Multilateral cycle search with unequal amounts**: Detect payment cycles (A→B→C→A) and calculate each participant's net position. If all participants with net outflows can cover their positions, settle ALL transactions in the cycle at full value simultaneously. If any participant lacks liquidity, the entire cycle fails atomically.
* **Batch selection** subject to per-bank net debit caps; run every tick on **Queue 2**.
* Mirrors T2's **optimisation procedures** that continuously dissolve queues with reduced liquidity by smart grouping of whole payments, not by splitting individual transactions. ([European Central Bank][5], [docs/lsm-in-t2.md](lsm-in-t2.md))

**T2-style options (toggles):**

* **Priorities & timed transactions** (banks can mark urgency or schedule).
* **Liquidity reservation/limits** (per-bank caps, earmarks).
* **Central Liquidity Management (pooled view)**—model as a single `B_{i,t}` with optional buffers for other TARGET services (abstracted). ([European Central Bank][2])

## 8) Scenarios & shocks

* **Liquidity squeeze:** lower opening balances, raise collateral costs → observe LSM benefits and gridlock risk.
* **Throughput rule stress:** impose “≥X% settled by T” and measure behavior.
* **Large idiosyncratic outflow:** single bank suffers a noon margin call.
* **Fee regime switch:** priced overdraft ↔ collateralised credit.
* **Operational shock:** temporarily disable LSM to reveal dependence on optimisation.
* **Counterparty trust:** optional tit-for-tat pacing by bilateral history.

## 9) Observation & action encoding (for AI control)

* **State vector (example):**
  [
  [B_{i,t},\ H_{i,t},\ \text{collateral},\ \text{Queue 1 by age/priority/cpty},\ \text{deadlines},\ \widehat{\text{in/out}}_{t:t+h},\ \text{public throughput/Queue 2 pressure},\ \text{liquidity price},\ \text{ticks to cut-offs}]
  ]
* **Action heads:**

  * **Queue 1 release share** (r \in {0,.25,.5,.75,1}) for (i) total Queue 1 or (ii) top-K by priority/deadline;
  * **Splitting factor** (\in{1,2,4,8}) — number of child transactions to create (1 = no split);
  * **Priority/timed flags** (if T2 features enabled);
  * **Liquidity draw** (\in{0,\text{small},\text{med},\text{max}}) and **collateral delta**.
* **Reward:** negative of **Cost** each tick plus closing terms.
* **Algorithms:** PPO/SAC (optionally recurrent) + self-play.

## 10) Data generation & calibration

* **Arrivals:** non-homogeneous Poisson fitted to stylized diurnal curves (AM/PM peaks).
* **Sizes/deadlines:** heavy-tailed amounts; tag a share as **time-critical** (securities/payroll) vs. **flexible**.
* **Liquidity:** opening balances and credit caps set to make the system **liquidity-constrained** but solvable via LSM.
* **Benchmark realism knobs (from T2 docs):** enable **priorities**, **timed transactions**, **limits**, and **optimisation** to mirror T2’s liquidity-management features; do **not** hard-code real stats—use them only for plausibility checks. ([European Central Bank][2])

## 11) Test plan

1. **Two-bank toy:** verify PD vs stag-hunt regimes by parameter flip; confirm equilibrium behavior.
2. **Four-bank ring (equal amounts):** inject A→B, B→C, C→D, D→A cycle (all 500k); ensure LSM clears with small liquidity.
3. **T2-realistic LSM with unequal amounts:**
   - **Three-bank cycle (unequal):** A→B (500k), B→C (800k), C→A (700k). Verify: (a) all three settle at full value if B has 300k liquidity (net outflow), (b) cycle fails atomically if B lacks liquidity, leaving all three queued.
   - **Bilateral offset (unequal):** A→B (500k), B→A (300k). Verify both settle simultaneously with A covering net 200k.
   - **Net position calculation:** For any cycle, verify `sum(net_positions) = 0` (conservation).
4. **No-LSM ablation:** show higher delays/liquidity usage; re-enable and compare. ([Nationalbanken][3])
5. **Deadline stress:** verify prioritization/timed options reduce SLA misses when enabled (T2-style). ([European Central Bank][2])

---

## Appendix A — Minimal mapping to T2 vocabulary

* **Settlement asset:** central bank money; **immediate finality** on posting. ([European Central Bank][1])
* **Optimisation/LSM:** continuous queue-dissolving via offsetting & cycles. ([European Central Bank][5])
* **Features you may toggle:** payment **priorities**, **timed transactions**, **limits/reservations**, **liquidity pooling/CLM**. ([European Central Bank][2])
* **Sweden on T2 (assumption):** Riksbank has announced intention to connect RIX-RTGS to **T2**. ([Riksbank][4])

---

### Why this framing is simulation-ready

* It **pins the flow** at the RTGS layer where interbank settlement actually occurs (banks’ balances at the central bank), letting the **policy/AI** act at realistic decision hooks (release timing, liquidity sourcing). ([European Central Bank][1])
* It builds in **queues + optimisation** so you can study coordination failures (gridlock) and the benefit of LSMs under scarcity, matching the literature. ([Nationalbanken][3])
* It keeps T2-specific affordances as **toggles**, so you can dial realism up without changing the core mechanics. ([European Central Bank][2])

If we later find that a particular T2 feature (e.g., specific limit types) changes agent incentives materially, we can add it as a parameterized constraint without altering the loop structure.

[1]: https://www.ecb.europa.eu/press/economic-bulletin/articles/2020/html/ecb.ebart202005_03~4a20eae0c8.en.html?utm_source=chatgpt.com "Liquidity distribution and settlement in TARGET2 - European Central Bank"
[2]: https://www.ecb.europa.eu/paym/target/t2/html/index.en.html?utm_source=chatgpt.com "What is T2? - European Central Bank"
[3]: https://www.nationalbanken.dk/media/r2xgriaj/2001-mon4-grid67.pdf?utm_source=chatgpt.com "Gridlock Resolution in Payment Systems"
[4]: https://www.riksbank.se/en-gb/press-and-published/notices-and-press-releases/press-releases/2024/the-riksbank-wants-to-use-the-european-t2-platform-for-payment-settlement/?utm_source=chatgpt.com "The Riksbank wants to use the European T2 platform for payment ..."
[5]: https://www.ecb.europa.eu/paym/target/consolidation/profuse/shared/pdf/Business_Description_Document.en.pdf?utm_source=chatgpt.com "T2-T2S CONSOLIDATION - European Central Bank"
