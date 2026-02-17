# UX First Impressions Report — SimCash Web Sandbox

**Date:** 2026-02-17  
**Reviewer:** Nash (research engineer persona, simulating a central banker / payments researcher arriving cold)  
**Build:** `feature/interactive-web-sandbox`, commit `5bb333db`

---

## Executive Summary

SimCash has the bones of a compelling research tool. The multi-day policy game is genuinely interesting — watching fractions converge over 10 days with cost evolution charts is the kind of thing that would hold a payments researcher's attention. But the current UX has significant friction that would lose a first-time user within 60 seconds. The biggest issues: **two competing entry points on the same page**, **no explanation of what you're looking at**, and **the most interesting view (Game) has information architecture problems**.

**Verdict:** Technically impressive, pedagogically opaque. Needs an information hierarchy pass before showing to anyone outside the project.

---

## Landing Page (Setup)

### What I See

The Setup page presents three modes via toggle buttons:
1. **Multi-Day Game** — scenario cards + game settings + "Start Game" button
2. **Presets** — simpler cards + "Launch Simulation" button  
3. **Custom Builder** — full parameter editor + "Launch Simulation" button

### Problems

#### P1: Two launch buttons, two systems, zero explanation (Critical)

The Multi-Day Game tab shows:
- A "🎮 Start Game" button (creates a multi-day policy game)
- Below it, an "AI Agent Reasoning" toggle + "🚀 Launch Simulation" button (creates a single-run sim)

These go to *completely different views* with different feature sets, different data models, different tab structures. A first-time user has no idea:
- What's the difference between "Start Game" and "Launch Simulation"?
- Why are there two AI toggles? The game has "Enable AI Optimization" + "Mock Mode"; the bottom has a separate "AI Agent Reasoning" toggle.
- Which one should I click?

**The "Launch Simulation" section at the bottom of the Multi-Day Game tab appears to be a remnant of the single-run mode that wasn't removed.** It shows up identically on all three tabs (Multi-Day Game, Presets, Custom Builder) and always creates a single-run sim. This is deeply confusing.

#### P2: No onboarding or context (High)

There's a heading "Payment System Simulator" and a subtitle "Watch AI agents make real-time decisions about liquidity allocation and payment timing." That's it. No explanation of:
- What is a "payment system simulator"? (RTGS? LSM? Why should I care?)
- What does "liquidity allocation" mean in this context?
- What is a "multi-day game" vs a regular simulation?
- What does "initial_liquidity_fraction" control?
- What are the cost types (liquidity, delay, penalty) and how do they trade off?

A central banker would have domain knowledge, but even they'd need context about *this specific model*. A researcher from another field would be completely lost.

#### P3: Cost rate metadata is cryptic (Medium)

Each scenario card shows: `💰 83 bps  ⏱ 0.2/¢/tick  ⚠️ $500`

What do these mean?
- "83 bps" — of what? Per year? Per tick? Of the liquidity pool?
- "0.2/¢/tick" — 0.2 cents per tick per what? Per unit of delayed payment?
- "$500" — is this per payment? Per day? This is the deadline penalty, but it's not labeled as such.

Even a payments expert would need a moment. A tooltip or legend would help enormously.

#### P4: Scenario cards lack differentiation (Medium)

Six of seven scenarios have identical cost rates (83 bps, 0.2/¢/tick, $500). The only differentiator is agent count and tick count. This makes them *look* interchangeable. The descriptions help ("Deterministic-style. Quick Nash equilibrium test" vs "Stochastic arrivals over 12 periods") but the cost badges are noise — they're the same for 6/7 cards.

The "High Stress" card stands out ($2,500 penalty) but this isn't visually emphasized enough — same card layout, same muted style.

---

## Game View (Multi-Day Policy Game)

### What Works Well

- **Day Timeline** — clickable day buttons are intuitive and visually clean
- **Fraction Evolution chart** — immediately communicates convergence. This is the hero visualization.
- **Cost Evolution chart** — shows the tradeoff dynamics clearly
- **Policy History** — compact fraction chain (1.000 → 0.625 → 0.410 → ...) is elegant
- **Accept/Reject display** — green/red borders with ✓/✗ are clear
- **Progress bar** — gradient fill communicates progress well
- **Auto-run** — works smoothly, day buttons fill in progressively

### Problems

#### P5: Day selector doesn't update right panel (High)

Clicking Day 5 updates the *left* panel (Day 5 Results, Day 5 Balances, Day 5 Events) but the *right* panel still shows:
- "Latest Reasoning" = Day 9 reasoning (the final optimization step)
- "Current Policies" = final fractions (0.131, 0.106)
- "Policy History" = full history with last entry bolded

**Expected behavior:** Clicking Day 5 should show Day 5's reasoning, Day 5's policies, and highlight Day 5 in the policy history. The user is trying to understand what happened *on that day* — showing the final state defeats the purpose of the day selector.

#### P6: "Day 0/10" state is empty and confusing (Medium)

When you first create a game, you see "Day 0/10" with an empty left panel and just "Current Policies" on the right (fraction=1.000). There's no guidance: "Click Next Day to simulate the first trading day" or similar. The empty state doesn't explain what's about to happen.

#### P7: Raw events list at bottom is overwhelming (Medium)

"Day 10 Events (251)" shows a raw dump of `Arrival`, `RtgsSubmission`, `PolicySubmit`, `RtgsImmediateSettlement`, `DeferredCreditApplied`, `CostAccrual` events. This is:
- Too low-level for the game view (this detail belongs in a drill-down)
- Not filterable (unlike the Events tab in single-run mode which has filters)
- Truncated at 100 with "... and 151 more" — the truncation is arbitrary

The game view should show a *summary* ("259 events: 45 arrivals, 45 settlements, 12 cost accruals...") with a "View details" expander.

#### P8: Balance chart is tiny and unlabeled (Low)

"Day 5 Balances" shows two overlapping lines in a ~80px tall chart with no axis labels, no legend, no hover tooltips. It's decorative, not informative. You can't tell what the Y values are or which line is which without squinting at colors.

#### P9: "mock" label in reasoning is jargon (Low)

Reasoning entries show `BANK_A  mock  ✓ ACCEPTED  1.000 → 0.625`. The word "mock" is an implementation detail — a user doesn't know or care that it's mock vs real LLM. If we must show it, make it a subtle badge, not inline text.

#### P10: No summary or conclusion when game completes (Medium)

When the game hits Day 10/10 and shows "COMPLETE", there's no summary:
- What fractions did agents converge to?
- How much did total system cost decrease from Day 1 to Day 10?
- Did the agents find a Nash equilibrium?
- How does this compare to the paper's expected result (~8-9%)?

The user just sees the same day-by-day view with disabled buttons. There should be a completion summary panel at the top.

---

## Single-Run Simulation View (Presets / Custom Builder → Launch Simulation)

### What Works Well

- **Dashboard** — agent cards with balance/cost breakdown are clean
- **Events tab** — well-formatted event log with search, type filter, agent filter
- **Analysis tab** — good post-sim summary with Payment Flow Summary table
- **Config tab** — (not screenshotted but presumably shows raw config)
- **7-tab navigation** — comprehensive

### Problems

#### P11: This is a completely separate app (Critical)

The single-run simulation and the multi-day game are fundamentally different products sharing the same URL:
- Different navigation (7 tabs vs 3 tabs)
- Different data models (ticks vs days)
- Different features (Events tab with filters vs raw event dump)
- Different concepts (single run vs multi-day optimization)

There's no cross-pollination. The excellent Events tab from single-run mode doesn't exist in game mode. The policy optimization from game mode doesn't exist in single-run mode. They should either be **unified** or **clearly separated** with different entry points.

#### P12: "Agent Reasoning" is empty and misleading (Medium)

The Agents tab in single-run mode says "No reasoning data yet. Enable AI reasoning and step through ticks." But AI reasoning in single-run mode is per-tick (if enabled), which is a completely different concept from the multi-day policy optimization. This is confusing if you just came from the game view.

---

## Custom Builder

### What Works Well

- Full parameter control (ticks, days, seed, cost rates, features)
- Bank management (add/remove, liquidity pools)
- Payment schedule editor
- Randomize / Export / Import JSON
- Cost constraint display ("r_c < r_d < r_b")

### Problems

#### P13: Goes to single-run mode, not game mode (High)

If I carefully configure a custom scenario with specific cost rates and agents, hitting "Launch Simulation" takes me to the single-run tick-stepper. There's no way to play a multi-day game with a custom scenario. The "Start Game" button (which goes to the game view) is only available in the Multi-Day Game tab and only uses built-in scenario packs.

This is a significant gap — the Custom Builder is the most interesting setup tool, but it connects to the less interesting run mode.

#### P14: "Days" field is confusing (Low)

The Custom Builder has a "Days" input (default: 1). This controls `num_days` in the simulation config, which is different from "Max Days" in the game settings (which controls how many optimization iterations to run). Same word, different meanings.

---

## Information Architecture

### Current Structure
```
Setup (tab)
├── Multi-Day Game → Start Game → Game View (3 tabs)
│   └── also: Launch Simulation → Dashboard (7 tabs)  ← CONFUSING
├── Presets → Launch Simulation → Dashboard (7 tabs)
│   └── also: Launch Simulation → Dashboard (7 tabs)
├── Custom Builder → Launch Simulation → Dashboard (7 tabs)
│   └── also: Launch Simulation → Dashboard (7 tabs)
Library (tab)
```

### Recommended Structure
```
Home
├── "Play the Game" → Scenario Selection → Game View
│   ├── Built-in scenarios (current scenario pack)
│   └── Custom scenario (bring Custom Builder here)
├── "Explore a Scenario" → Single-run Dashboard
│   ├── Presets
│   └── Custom Builder
Library
About / How It Works (new)
```

Key changes:
1. **Separate the two modes clearly** with distinct entry points and different framing
2. **Remove the "Launch Simulation" button from the Multi-Day Game tab** — it's noise
3. **Add a "How It Works" section** explaining the game, the cost model, and what convergence means
4. **Allow custom scenarios in game mode** — or explain why that's not supported

---

## Top 10 Recommendations (Priority Order)

| # | Issue | Severity | Effort | Recommendation |
|---|-------|----------|--------|----------------|
| 1 | Two launch buttons on same page | Critical | Low | Remove "Launch Simulation" from Multi-Day Game tab. Keep it only on Presets/Custom Builder. |
| 2 | Day selector doesn't update reasoning | High | Medium | When selectedDay changes, show that day's reasoning, policies, and costs on the right panel. |
| 3 | No onboarding | High | Medium | Add a 3-paragraph "How It Works" section or a collapsible explainer at the top of the Setup page. |
| 4 | Custom Builder can't start games | High | Medium | Wire Custom Builder output into the game creation API (build scenario YAML from form state). |
| 5 | No game completion summary | Medium | Low | Add a summary panel when game completes: convergence result, cost reduction %, comparison to equilibrium. |
| 6 | Raw events in game view | Medium | Low | Replace 251-event dump with a summary + collapsible detail view. |
| 7 | Cost rate labels are cryptic | Medium | Low | Add tooltips: "Liquidity cost: 83 basis points of committed funds per tick" etc. |
| 8 | Empty Day 0 state | Medium | Low | Add placeholder text: "Ready to start. Click ▶ Next Day to simulate the first trading day." |
| 9 | Balance chart too small | Low | Low | Double the height, add Y axis labels, add hover tooltips. |
| 10 | "mock" label visible to users | Low | Trivial | Hide or restyle as a tiny debug badge. |

---

## What Impressed Me

Despite the UX issues, the **underlying system is strong**:

- **Policy convergence is genuinely interesting to watch.** Seeing fractions drop from 1.0 to ~0.1 over 10 days with clear cost-reduction dynamics is compelling.
- **The Fraction Evolution chart is the star.** It immediately communicates what the game is about.
- **Events tab in single-run mode is well-designed.** Filterable, well-formatted, with tick headers.
- **Analysis tab gives a clean post-mortem.** Payment Flow Summary table + cost comparison bars.
- **Dark theme is attractive.** The gradient buttons are a bit flashy but the overall aesthetic is clean.
- **WebSocket streaming works.** Days appear progressively during auto-run with smooth phase transitions.
- **Cost breakdown per agent is clear.** Liquidity/Delay/Penalty/Total is the right decomposition.

The core experience — set up a game, run it, watch convergence — works. It just needs better framing and tighter information architecture.

---

## Appendix: Bugs Noticed

1. **"Day 10 Results seed=51"** — the heading runs "Results" and "seed" together without a space or separator: `Day 10 Resultsseed=51` (screenshot evidence)
2. **Events show `BANK_B→undefined`** — at tick 3 of Day 10, there are `QueuedRtgs BANK_B→undefined` events. The receiver_id is not resolving.
3. **Keyboard shortcuts bar overlaps content** — "Space: play/pause · →: step · R: reset" at the bottom overlaps the balance chart area (visible in Day 5 screenshot)
4. **Progress bar doesn't fill to 100% on completion** — the gradient bar at top shows full width, but it should be more celebratory (color change, animation)
