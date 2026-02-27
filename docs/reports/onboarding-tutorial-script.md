# Onboarding Tutorial Script

**Selected Experiment:** `9af6fa02`  
**Scenario:** 2 Banks, 12 Ticks · **Model:** Gemini 2.5 Pro · **Preset:** full  

## Why This Experiment

It tells a story with three dimensions of learning:

**1. The liquidity fraction arc**
- Both banks start at 0.5 (too much idle capital)
- BANK_A goes to 0.0 (catastrophe), recovers to 0.5, steps down to 0.2, then 0.1
- BANK_B takes a steadier path: 0.5 → 0.2 → 0.1 → 0.2 → 0.15

**2. The decision tree evolution**
- Day 1: both banks use a flat `Release` (no logic at all)
- Day 2: BANK_B *invents* urgency-based triage (if deadline ≤ 3 ticks → Release, else check liquidity)
- Day 3: BANK_A independently discovers the same pattern, adds `is_overdue` handling
- Day 7: BANK_B adds a third layer — balance conservation (`hold_threshold`)
- Final: BANK_A has a 3-deep tree (urgency OR overdue → Release, else liquidity check → Hold), BANK_B has a 4-deep tree (urgency → Release, low balance → Hold, else liquidity check)

**3. The bootstrap safety net**
- 8 accepted, 10 rejected across both banks
- Rejected proposals include both structural changes (different trees) and parameter tweaks (fraction bumps)
- On Day 5, BANK_A tries fraction 0.1 → 0.25 with a *simpler* tree (flat Release) — rejected because it would regress

**Cost:** 99,600 → 39,028 = **60.8% reduction**

---

## Design Principles

1. **Show, don't tell.** Point at something. Let the user notice. Then explain why it matters.
2. **Narrative tension.** Use the Day 2 disaster as the turning point.
3. **Progressive disclosure.** Big picture first, mechanics after curiosity is primed.
4. **Earn every click.** Interactive beats should reveal something satisfying.
5. **Two sentences max per tooltip.** Bold the key insight.

---

## The Script

### ACT I — "The Setup" (4 beats)

User arrives at `/experiment/9af6fa02`. Completed experiment. We're exploring, not operating.

---

**Beat 1 · "Welcome"**
*Target: top-bar · Type: tooltip*

> This is a completed experiment. Two AI agents played a **10-round payment game** and optimized their strategy over 10 rounds. Let's see what they learned.

---

**Beat 2 · "The Players"**
*Target: model badge (🧠 gemini-2.5-pro)*
*Type: tooltip*

> **BANK_A** and **BANK_B**, each running Gemini 2.5 Pro. They're **information-isolated** — each bank sees only its own costs and events, never the other's strategy.

---

**Beat 3 · "The Question"**
*Target: policy-display*
*Type: tooltip*

> Each bank controls two things: **how much liquidity to commit** (the fraction) and **a decision tree** that decides when to release or hold payments. Both started at fraction 0.5 with a trivial tree that releases everything.

*Design note: This is the key reframe vs. the old tutorial — it's not just about the fraction, it's about the tree.*

---

**Beat 4 · "Explore the Timeline"**
*Target: round-timeline*
*Type: interactive — wait for user to click Day 1*

> Each button is a completed day. **🧠** means the AI optimized afterward. Click **Day 1** to start from the beginning.

---

### ACT II — "The Disaster" (5 beats)

Day 1 is selected. Both banks at fraction=0.5, flat Release trees. All costs are opportunity cost.

---

**Beat 5 · "Day 1: Wasted Capital"**
*Target: day-costs*
*Type: tooltip*

> Day 1 cost: **99,600** — but look at the breakdown. It's *all* opportunity cost. Zero delays, zero penalties. The banks held too much cash doing nothing.

---

**Beat 6 · "Two Different Reactions"**
*Target: reasoning panel*
*Type: tooltip*

> Both AIs saw the waste. BANK_A had a radical idea: **cut liquidity to zero.** BANK_B was more careful: drop to 0.2 and invent an urgency-based decision tree. Expand their reasoning to compare.

*Design note: This is the first hint that the tree matters. BANK_B didn't just change a number — it built logic.*

---

**Beat 7 · "See the Consequences"**
*Target: round-timeline*
*Type: interactive — wait for Day 2 click*

> Click **Day 2** to see what happened.

---

**Beat 8 · "The Crash"**
*Target: day-costs*
*Type: tooltip · 500ms delay for drama*

> 💥 **301,703** — a 3x increase. BANK_A's zero-liquidity gamble caused massive payment failures: 116,623 in delays, 165,000 in penalties. Meanwhile BANK_B's smarter tree kept its costs at just 20,080.

---

**Beat 9 · "Why It Didn't Get Worse"**
*Target: reasoning (✗ Rejected badges)*
*Type: tooltip*

> After Day 2, most proposals are **✗ Rejected**. The bootstrap test statistically compares proposals against the current policy — it won't accept changes that would likely make things worse. That's why BANK_A recovered instead of spiraling.

---

### ACT III — "The Recovery" (6 beats)

Shift from disaster to learning. The trees evolve, fractions converge.

---

**Beat 10 · "The Learning Curve"**
*Target: cost-evolution chart*
*Type: tooltip*

> Spike on Day 2, then steady decline. **Hover the points** to see each bank's costs separately — notice BANK_B was stable while BANK_A recovered.

---

**Beat 11 · "Watch the Trees Grow"**
*Target: round-timeline*
*Type: interactive — wait for Day 4 click*

> Click **Day 4** and look at the policies below. Something interesting happened to the decision trees.

---

**Beat 12 · "From Nothing to Strategy"**
*Target: policy-display*
*Type: tooltip · then prompt to click View Policy*

> On Day 1, both trees were a single node: "Release everything." By Day 4, BANK_A checks **urgency OR overdue status** first, then checks if it has enough liquidity, and **Holds** if not. Click **🔍 View Policy** on BANK_A to see the full tree.

*Interaction: Wait for PolicyViewerModal to open.*

---

**Beat 13 · "The Decision Tree"**
*Target: PolicyViewerModal*
*Type: tooltip on modal*

> This is the tree the AI evolved through optimization. **Three conditions, three possible actions.** It learned to prioritize urgent payments, check available funds, and hold back when liquidity is tight — all by reasoning about its own results. Close when you're done exploring.

*Interaction: Wait for modal close.*

---

**Beat 14 · "Independent Discovery"**
*Target: round-timeline*
*Type: interactive — wait for Day 7 click*

> Now click **Day 7**. BANK_B evolved its tree independently — check what it came up with.

---

**Beat 15 · "Convergence and Divergence"**
*Target: policy-display (or View Policy on BANK_B)*
*Type: tooltip*

> BANK_B arrived at a **4-deep tree** — it added a balance conservation layer that BANK_A didn't. Same problem, same starting point, but the AIs invented **different strategies** that both work. BANK_A checks overdue status; BANK_B checks balance thresholds. Neither can see the other's approach.

---

### ACT IV — "The Deep Dive" (6 beats)

The user now understands the experiment. Show them the analytical tools.

---

**Beat 16 · "What Got Rejected"**
*Target: policy-history panel*
*Type: tooltip · interactive*

> The **Policy History** shows every optimization attempt. Click a **✗** pill — you'll see exactly what the AI proposed and why the bootstrap test blocked it. Some rejections changed the tree; others just tweaked the fraction.

*Interaction: Wait for user to click a rejected pill.*

---

**Beat 17 · "The Rejected Policy"**
*Target: 🚫 View Rejected Policy button*
*Type: interactive*

> Click **🚫 View Rejected Policy** to see the tree that was proposed. Compare it to the accepted policy — sometimes the AI simplifies the tree (losing intelligence), sometimes it makes a parameter bet that the stats don't support.

*Interaction: Wait for modal open, then close.*

---

**Beat 18 · "Bootstrap Stats"**
*Target: bootstrap stats row (Δ, CV, CI)*
*Type: tooltip*

> **Δ** is the expected cost change (negative = worse). **CV** measures reliability. **CI** is the 95% confidence interval. When CI crosses zero, the system can't be confident the change helps — so it rejects.

---

**Beat 19 · "Under the Hood"**
*Target: Prompt Explorer (collapsed)*
*Type: interactive — wait for expand*

> Expand **🔍 Prompt Explorer** to see the exact prompt the AI received. Each colored block is a section — system instructions, cost data, scenario rules, policy constraints. The token bar shows how the prompt budget is spent.

---

**Beat 20 · "Tick Replay"**
*Target: replay section*
*Type: tooltip*

> For any day, **Load Replay** to step through tick-by-tick. Watch balances rise and fall as payments settle. Like a debugger for the payment system.

---

**Beat 21 · "Payment Trace"**
*Target: payment-trace tab*
*Type: tooltip*

> Switch to **Payment Trace** to follow individual payments from arrival to settlement or expiry. This is where you see the decision tree *in action* — which payments got held, which got released.

---

### ACT V — "The Payoff" (4 beats)

---

**Beat 22 · "The Result"**
*Target: completion-summary*
*Type: tooltip*

> **60.8% cost reduction** over 10 rounds. Two AIs independently invented multi-condition payment strategies, found near-optimal liquidity fractions, and drove system costs from 99,600 to 39,028 — without any prior knowledge of payment systems.

---

**Beat 23 · "Your Workspace"**
*Target: notes panel + export-btn*
*Type: tooltip*

> **Notes** saves observations to your browser (included in JSON exports). **Export** gives you CSV or JSON with the full policy history, reasoning, and cost data for analysis in R, Python, or Excel.

---

**Beat 24 · "Activity Feed"**
*Target: activity-feed*
*Type: tooltip*

> During a live experiment, the **Activity Feed** streams everything in real time — simulations running, AI thinking, retries, errors. Color-coded so you can spot problems at a glance.

---

**Beat 25 · "What's Next"**
*Target: none (centered completion card)*
*Type: modal*

> **You've seen the full lifecycle.**
>
> 🎬 **Browse scenarios** in the Library — or create your own  
> 🧠 **Bring your API key** (Settings) to run with GPT, Claude, or Gemini  
> 🔬 **Change the constraint preset** — try "simple" (fraction only) vs "full" (fraction + decision trees)  
> 📊 **Compare runs** — same scenario, different models. See who learns faster.
>
> Every run produces different strategies. See what emerges.

*Button: "Start Exploring" → dismisses, navigates to home.*

---

## Implementation Reference

### Experiment Data at a Glance

```
Day  | Cost    | A frac | A tree    | B frac | B tree    | Story
-----|---------|--------|-----------|--------|-----------|------
  1  |  99,600 |  0.50  | Release   |  0.50  | Release   | All opportunity cost
  2  | 301,703 |  0.00  | Release   |  0.20  | 3-deep    | 💥 A goes to zero
  3  |  69,720 |  0.50  | 3-deep    |  0.20  | 3-deep    | A recovers + invents tree
  4  |  49,691 |  0.20  | 3-deep+   |  0.10  | 3-deep    | Both stepping down
  5  |  50,342 |  0.10  | 3-deep+   |  0.10  | 3-deep    | Near optimal
  6  |  53,722 |  0.10  | 3-deep+   |  0.10  | 3-deep    | Holding (rejections)
  7  |  42,606 |  0.10  | 3-deep+   |  0.20  | 4-deep    | B adds balance layer
  8  |  41,336 |  0.10  | 3-deep+   |  0.15  | 4-deep    | B fine-tunes
  9  |  40,089 |  0.10  | 3-deep+   |  0.15  | 4-deep    | Convergence
 10  |  39,028 |  0.10  | 3-deep+   |  0.15  | 4-deep    | Final: -60.8%

Tree legend:
  Release   = flat "Release everything"
  3-deep    = urgency → liquidity check → Hold
  3-deep+   = (urgency OR overdue) → liquidity check → Hold
  4-deep    = urgency → balance conservation → liquidity check → Hold
```

### BANK_A's Final Tree (Day 4 onward)
```
IF (ticks_to_deadline ≤ 3) OR (is_overdue)
  → Release
ELSE IF effective_liquidity ≥ amount
  → Release
ELSE
  → Hold
```
Parameters: `urgency_threshold=3, hold_threshold=100000, split_threshold=1000000`

### BANK_B's Final Tree (Day 7 onward)
```
IF ticks_to_deadline ≤ 3
  → Release
ELSE IF balance < 50000
  → Hold (conserve liquidity)
ELSE IF effective_liquidity > amount
  → Release
ELSE
  → Hold
```
Parameters: `urgency_threshold=3, hold_threshold=50000`

### Key Tutorial Moments for Tree Viewing
1. **Beat 12-13:** User opens BANK_A Day 4 policy → sees 3-condition tree that didn't exist on Day 1
2. **Beat 14-15:** User checks BANK_B Day 7 → sees a *different* 4-condition tree solving the same problem
3. **Beat 16-17:** User inspects a rejected policy → sees the AI tried to simplify/modify the tree and got blocked

### Rejected Proposals Worth Highlighting
- **BANK_A Day 5 (reject[4]):** Proposed going back to a flat `Release` with fraction 0.25 — *lost all tree intelligence*. Bootstrap caught the regression.
- **BANK_B Day 8 (reject[7]):** Proposed identical tree and fraction (0.15) but with no actual change — bootstrap Δ=14,244 with CV=3.95 (wildly uncertain). Correctly rejected as noise.

### New `data-tour` Targets Needed
```
activity-feed          → ActivityFeed component
completion-summary     → green completion banner
policy-history         → PolicyHistoryPanel
rejected-policy-btn    → 🚫 View Rejected Policy button
bootstrap-stats        → Δ/CV/CI row in reasoning cards
prompt-explorer        → collapsible Prompt Explorer section
```

### Interaction Types
```typescript
type TourInteraction =
  | { type: 'click-day'; day: number }       // wait for selectedDay
  | { type: 'open-modal'; target: string }   // wait for element to appear
  | { type: 'close-modal' }                  // wait for modal to close
  | { type: 'expand'; target: string }       // wait for section expand
  | { type: 'click-pill'; selector: string } // wait for history pill click
```

### Act Transitions
Brief centered interstitials (1.5s auto-advance or click):
- → Act II: *"Let's see what the AI did next..."*
- → Act III: *"The AI learned from its mistake."*
- → Act IV: *"Now let's look at how it thinks."*
- → Act V: *"Time to zoom out."*

### Tour Entry Points
- **First visit:** Auto-start if `localStorage.simcash_tour_done` not set
- **Manual:** "🎓 Tutorial" in nav sidebar → `/experiment/9af6fa02?tour=1`
- **Reset:** Clear `simcash_tour_done` from localStorage
