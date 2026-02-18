# SimCash UX Improvement Plan

**Date:** 2026-02-18
**Source:** Two UX reviews — Central Banker persona + Bank of Canada Researcher persona
**Audiences:** (A) Technical researchers (payments/game theory), (B) General audience (curious economists, students, policymakers)
**Design principles:** Progressive disclosure, contextual help, research-grade trust, zero-config first run

---

## Design Philosophy

SimCash serves two audiences with different needs:

| | **Technical Researcher** | **General Audience** |
|---|---|---|
| **Goal** | Design experiments, validate hypotheses, export data | Understand the concept, see something cool, learn |
| **Tolerance for complexity** | High — wants full control | Low — wants guided experience |
| **Trust requirement** | Academic rigor (reproducibility, methodology) | Credibility (looks professional, clear explanations) |
| **Time to first insight** | Acceptable: 5 min | Required: 30 seconds |

**Strategy:** Progressive disclosure. The default experience serves the general audience. Power features reveal themselves as users demonstrate intent (clicking "Advanced", visiting Create tab, etc.).

---

## Implementation Waves

### Wave 1: First Impressions & Guided Onboarding (Priority: P0)
*Goal: Reduce time-to-first-insight from 30 min to 30 seconds.*

### Wave 2: Explainability & Trust (Priority: P1)
*Goal: Every number, chart, and result is self-explanatory. A researcher trusts the output.*

### Wave 3: Research Workflow (Priority: P1)
*Goal: Full experiment lifecycle — design, run, analyze, export, compare.*

### Wave 4: Creation Tools Polish (Priority: P2)
*Goal: Scenario and policy editors feel professional and discoverable.*

---

## Wave 1: First Impressions & Guided Onboarding

**Effort:** M-L (8-16 hours total)
**Impact:** Transforms the landing experience for both audiences

### 1A. Landing Page Redesign
**File:** `web/frontend/src/views/HomeView.tsx`
**Effort:** M (4h)

**Changes:**
- **Hero section rewrite:**
  - Title: "SimCash" (keep brand) + subtitle: "Watch AI agents learn to play the liquidity game"
  - Add one-liner: "Based on BIS Working Paper 1310 — AI agents for cash management in payment systems"
  - Add "🚀 Run Your First Experiment" primary CTA button (prominent, above the fold)
- **"How It Works" expanded by default on first visit:**
  - Use `localStorage` flag `simcash_seen_howit_works`
  - First visit: expanded with animated step indicators
  - Return visits: collapsed (user already knows)
- **Simplify the scenario list:**
  - Show 3 "Recommended" scenarios by default (2 Banks 12 Ticks, 3 Banks 6 Ticks, 2 Banks High Stress)
  - "Show all 7 scenarios ▾" expander for the rest
  - Each card gets a "▶ Quick Run" button that auto-launches with default settings
- **Game Settings progressive disclosure:**
  - Default: collapsed, showing only "⚙️ Advanced Settings" link
  - When "Quick Run" is used, settings are auto-configured (mock mode, 5 days, full complexity)
  - Only expand settings when user explicitly wants to customize

### 1B. Guided First Run
**Files:** New `GuidedTour.tsx` component, modifications to `GameView.tsx`
**Effort:** M (4h)

**Flow:**
1. User clicks "🚀 Run Your First Experiment"
2. Auto-selects "2 Banks, 12 Ticks" with mock mode, 5 days
3. Game view shows **annotated callout bubbles** on first run:
   - Bubble 1 (Day 0): "Each bank starts by committing 100% of its liquidity pool. The AI will learn this is too much."
   - Bubble 2 (after Day 1): "Day 1 results are in! See the costs? The AI optimizer is now analyzing what went wrong..."
   - Bubble 3 (Day 2+): "Watch the fraction drop — the AI is learning to commit less liquidity while still settling payments on time."
   - Bubble 4 (Game Complete): "The AI reduced costs by X%! It found that ~Y% is the sweet spot. Try a different scenario or build your own."
4. Store `simcash_completed_first_run` in localStorage
5. After first run: show "What's Next?" panel with 3 paths: Explore Scenarios, Build Your Own, Read the Docs

### 1C. Mock Mode Rename
**Files:** `GameSettingsPanel.tsx`, `HomeView.tsx`, `GameView.tsx`
**Effort:** S (1h)

**Changes:**
- Rename "Mock Mode (no API costs)" → "🤖 Simulated AI — fast, deterministic, great for exploration"
- Rename the non-mock state → "🧠 LLM-Powered AI — real language model reasoning (slower, uses API)"
- Add info tooltip: "Simulated AI uses algorithmic optimization. LLM-Powered AI uses a real language model (Gemini) to reason about strategy. Both produce valid experimental results; LLM mode adds natural-language reasoning."

---

## Wave 2: Explainability & Trust

**Effort:** L (16-24 hours total)
**Impact:** Makes every result interpretable. Builds academic credibility.

### 2A. Game Completion Summary — Narrative Interpretation
**Files:** New `GameSummary.tsx` component, `GameView.tsx`
**Effort:** M (4h)

After game completes, show a generated narrative:
```
📊 Experiment Summary

Three banks played a 10-day liquidity coordination game starting from
FIFO (commit 100%). All three independently discovered that committing
~12% of their pool is near-optimal — a 87% cost reduction.

Key observations:
• All banks converged to similar strategies (symmetric Nash equilibrium)
• Zero deadline penalties from Day 4 onward (100% on-time settlement)
• Total system cost stabilized at $18,822/day (vs. $149,400 on Day 1)
• The convergence pattern matches theoretical predictions from Castro et al. (2025)

This suggests that in symmetric payment networks, independent AI optimizers
can find near-efficient equilibria without explicit coordination.
```

Generate this from game data — template-based, no LLM needed:
- Compare final fractions (symmetric vs asymmetric)
- Calculate settlement rate (payments settled / total payments)
- Compare to Day 1 baseline
- Note whether penalties hit zero (full settlement achieved)

### 2B. Settlement Rate Metric
**Files:** `GameView.tsx`, `game.py` (backend response)
**Effort:** M (2h)

Add to the Game Complete banner:
```
Day 1 Cost    Final Cost    Cost Reduction    Settlement Rate    Final Fractions
149,400       18,822        ↓ 87.4%           100% ✓            A: 0.127 · B: 0.131 · C: 0.120
```

Calculate from events: `settlement_rate = RtgsImmediateSettlement / (RtgsImmediateSettlement + unsettled_at_eod)`

### 2C. Contextual Tooltips Everywhere
**Files:** Multiple views
**Effort:** M (3h)

Add `<Tooltip>` components to every non-obvious term:
- **Cost Rates section:** "Liquidity Cost (bps/tick)" → "How much it costs to hold committed liquidity per trading period. 83 basis points means the bank pays 0.83% of committed funds per tick."
- **Policy Complexity:** "Simple: AI only adjusts how much liquidity to commit. Standard: AI also decides when to release/hold payments. Full: AI has complete freedom — all actions, conditions, and parameters."
- **Evaluation Samples:** "Number of simulation runs per evaluation. More samples = more statistically reliable, but slower. 1 = quick exploration, 10+ = research-grade."
- **Optimization Interval:** "How often the AI re-evaluates. Every day = rapid adaptation. Every 3 days = more data per decision, slower learning."
- **Bootstrap statistics** (Δ, CV, CI): "Δ = cost change from previous day (negative = improvement). CV = coefficient of variation (lower = more consistent). CI = 95% confidence interval."

### 2D. Event Type Labels
**Files:** `GameView.tsx`
**Effort:** S (1h)

Map engine event types to plain English:
```typescript
const EVENT_LABELS: Record<string, string> = {
  'Arrival': 'Payment arrived',
  'RtgsSubmission': 'Submitted for settlement',
  'RtgsImmediateSettlement': 'Settled immediately',
  'PolicySubmit': 'Policy decision made',
  'CostAccrual': 'Cost charged',
  'QueuedRtgs': 'Queued (insufficient funds)',
  'DeferredCreditApplied': 'Credit facility used',
  'ScenarioEventExecuted': 'Scenario event triggered',
  'BilateralOffset': 'Bilateral netting applied',
  'CycleSettlement': 'Multilateral cycle settled',
};
```

### 2E. Fix Docs "GPT-5.2" Reference
**Files:** `DocsView.tsx`
**Effort:** S (15min)

Replace all "GPT-5.2" references with "Gemini" or make it model-agnostic: "powered by a large language model (currently Gemini 2.5 Flash via Google Vertex AI)".

---

## Wave 3: Research Workflow

**Effort:** L (20-30 hours total)
**Impact:** Makes SimCash a serious research tool, not just a demo.

### 3A. Data Export
**Files:** New `ExportPanel.tsx`, backend endpoint `GET /api/games/{id}/export`
**Effort:** M (4h)

After game completes, show export options:
- **CSV** — one row per agent per day: `day, agent_id, fraction, liquidity_cost, delay_cost, penalty_cost, total_cost, settlement_rate, policy_json`
- **JSON** — full game state including all events, policies, and reasoning
- **Summary PDF** — the narrative summary + all charts as a printable report (stretch goal)

Backend: serialize game state to requested format. Frontend: download buttons in Game Complete section.

### 3B. YAML/JSON Schema Reference in Docs
**Files:** `DocsView.tsx` (new "Schema Reference" section)
**Effort:** M (3h)

Add a complete field-by-field reference:
```markdown
## Scenario YAML Reference

### simulation
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| ticks_per_day | integer | yes | — | Trading periods per simulated day (1-100) |
| num_days | integer | yes | — | Simulated days per game-day (usually 1) |
| rng_seed | integer | yes | — | Random seed for reproducibility |

### agents[].arrival_config
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rate_per_tick | float | yes | — | Expected payments per tick (Poisson λ) |
| deadline_range | [int, int] | yes | — | [min, max] ticks until deadline |
| ...
```

Generate from the Pydantic schema if possible (DRY).

### 3C. "Run This Scenario" from Library
**Files:** `ScenarioLibraryView.tsx`, `App.tsx`
**Effort:** S (2h)

Add a "▶ Run" button to each scenario card that:
1. Sets the scenario in the Setup tab
2. Navigates to Setup with the scenario pre-selected
3. Optionally: launches directly with default settings

### 3D. Re-run with Different Seed
**Files:** `GameView.tsx`
**Effort:** S (1h)

After game completes, add:
- "🔄 Re-run (new seed)" — same scenario, random new seed
- "🔁 Re-run (same seed)" — exact replication
- "📊 Run 10x" — batch mode (stretch: run 10 seeds, show distribution of outcomes)

### 3E. Baseline Comparison
**Files:** `GameView.tsx`, `game.py`
**Effort:** M (4h)

After game completes, show comparison:
```
                    FIFO Baseline    AI Optimized    Improvement
System Cost/Day     $149,400         $18,822         ↓ 87.4%
Settlement Rate     94.2%            100%            ↑ 5.8pp
Avg Fraction        1.000            0.126           ↓ 87.4%
```

Backend: run a single FIFO day as baseline during game creation. Store Day 1 (FIFO) results separately.

---

## Wave 4: Creation Tools Polish

**Effort:** L (16-24 hours total)
**Impact:** Makes custom scenario/policy creation feel professional.

### 4A. Form Field Labels & Tooltips
**Files:** `ScenarioForm.tsx`
**Effort:** S (2h)

Every form input needs:
- A visible label (currently some spinbuttons are unlabeled)
- A tooltip explaining the field
- Units displayed inline (e.g., "Pool (cents)" or better: convert to dollars in display)

### 4B. Visual Decision Tree Renderer
**Files:** New `PolicyTreeView.tsx`
**Effort:** L (8h)

SVG-based tree visualization:
```
                    ┌─────────────────┐
                    │ balance < 50000? │
                    └────────┬────────┘
                      yes ╱     ╲ no
                    ┌─────┐   ┌──────────────┐
                    │ Hold │   │ urgent > 0.8?│
                    └─────┘   └──────┬───────┘
                              yes ╱     ╲ no
                          ┌───────┐  ┌─────────┐
                          │Release│  │PostColl. │
                          └───────┘  └─────────┘
```

Show in:
- Policy Library detail view
- Policy Editor (live preview as you edit JSON)
- Game View → Current Policies section
- Starting Policy dropdown (preview on hover)

### 4C. Policy Editor Autocomplete & Reference Panel
**Files:** `PolicyEditorView.tsx`
**Effort:** M (4h)

Side panel showing:
- Available actions: Release, Hold, Split, Delay, PostCollateral, ReleaseWithCredit, Drop, NoAction, AddState, ResubmitToRtgs
- Available condition fields: balance, queue_length, tick, urgency_ratio, etc.
- Available operators: gt, lt, gte, lte, eq, between, and, or, not
- Example snippets that can be clicked to insert

### 4D. Duplicate Agent Button
**Files:** `ScenarioForm.tsx`
**Effort:** S (30min)

Add "📋 Duplicate" button next to each agent's "✕ Delete" button. Copies all settings with incremented ID (BANK_A → BANK_A_copy).

### 4E. Counterparty Weight Auto-Balance
**Files:** `ScenarioForm.tsx`
**Effort:** S (1h)

When adding a new agent:
- Auto-add it to all existing agents' counterparty weights with equal share
- Show warning when weights don't sum to ~1.0
- "Auto-balance" button that distributes weights equally

---

## Implementation Priority Matrix

| Wave | Item | Effort | Impact (Researcher) | Impact (General) | Priority |
|------|------|--------|--------------------|--------------------|----------|
| 1 | 1A. Landing page redesign | M | ★★★ | ★★★★★ | **P0** |
| 1 | 1B. Guided first run | M | ★★ | ★★★★★ | **P0** |
| 1 | 1C. Mock mode rename | S | ★★★ | ★★★★ | **P0** |
| 2 | 2A. Game completion summary | M | ★★★★★ | ★★★★ | **P1** |
| 2 | 2B. Settlement rate metric | M | ★★★★★ | ★★★ | **P1** |
| 2 | 2C. Contextual tooltips | M | ★★★★ | ★★★★★ | **P1** |
| 2 | 2D. Event type labels | S | ★★★ | ★★★★ | **P1** |
| 2 | 2E. Fix docs GPT-5.2 | S | ★★★★★ | ★★ | **P0** |
| 3 | 3A. Data export (CSV/JSON) | M | ★★★★★ | ★ | **P1** |
| 3 | 3B. Schema reference in docs | M | ★★★★★ | ★ | **P1** |
| 3 | 3C. Run from scenario library | S | ★★★★ | ★★★★ | **P1** |
| 3 | 3D. Re-run with different seed | S | ★★★★ | ★★ | **P2** |
| 3 | 3E. Baseline comparison | M | ★★★★★ | ★★★ | **P1** |
| 4 | 4A. Form field labels | S | ★★★★ | ★★★★ | **P1** |
| 4 | 4B. Visual decision tree | L | ★★★★★ | ★★★ | **P2** |
| 4 | 4C. Policy editor reference | M | ★★★★ | ★ | **P2** |
| 4 | 4D. Duplicate agent button | S | ★★★ | ★★ | **P2** |
| 4 | 4E. Counterparty auto-balance | S | ★★★ | ★★ | **P2** |

---

## Execution Plan

### Sprint 1 (Wave 1 — this week): First Impressions
1. **1C. Mock mode rename** (1h) — quick win, immediate clarity
2. **2E. Fix docs GPT-5.2** (15min) — factual error, must fix
3. **1A. Landing page redesign** (4h) — hero rewrite, progressive disclosure, quick-run buttons
4. **1B. Guided first run** (4h) — annotated callouts, first-run detection

### Sprint 2 (Wave 2): Explainability
5. **2B. Settlement rate metric** (2h) — add to game complete banner
6. **2A. Game completion summary** (4h) — narrative template from game data
7. **2C. Contextual tooltips** (3h) — systematic pass through all views
8. **2D. Event type labels** (1h) — mapping table

### Sprint 3 (Wave 3): Research Workflow
9. **3C. Run from scenario library** (2h) — button + navigation
10. **3A. Data export** (4h) — CSV/JSON download
11. **3E. Baseline comparison** (4h) — FIFO baseline in game complete
12. **3B. Schema reference** (3h) — docs section

### Sprint 4 (Wave 4): Creation Polish
13. **4A. Form field labels** (2h)
14. **4D. Duplicate agent** (30min)
15. **4E. Auto-balance weights** (1h)
16. **4B. Visual decision tree** (8h) — the big one
17. **4C. Policy editor reference** (4h)

**Total estimated effort: ~48 hours across 4 sprints**

---

## Success Metrics

| Metric | Current | Target (Wave 1) | Target (Wave 4) |
|--------|---------|-----------------|-----------------|
| Time to first experiment (new user) | 30+ min | 30 seconds | 30 seconds |
| Can explain what they saw (general) | 20% | 80% | 95% |
| Can design custom experiment (researcher) | After 1h reading | After 15 min | After 5 min |
| UX rating (researcher) | 7/10 | 8/10 | 9/10 |
| UX rating (general) | 4/10 | 7/10 | 8/10 |
