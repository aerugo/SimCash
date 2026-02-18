# SimCash UX Improvement Plan

**Date:** 2026-02-18
**Source:** UX reviews — Central Banker persona + Bank of Canada Researcher walkthrough
**User:** Someone who understands central banking and payment systems, is curious about AI/game theory, and wants to explore and run experiments. Not a software engineer, but not afraid of data.
**Design principles:** Self-explanatory interface, research-grade trust, fast path to insight, progressive depth

---

## Design Philosophy

One user, one flow. Assume they know what RTGS is, what liquidity means, why settlement matters. Don't explain central banking — explain *this tool*. Every control, result, and chart should be self-explanatory without requiring them to read docs first.

The goal: they land on the site, understand what SimCash does in 10 seconds, run an experiment in 30 seconds, and understand the results immediately. Then they go deeper — custom scenarios, starting policies, policy trees — at their own pace.

---

## Wave 1: Make the Tool Self-Explanatory

**Effort:** ~12h | **Impact:** The landing experience goes from "what is this?" to "I get it, let me try"

### 1A. Landing Page — Say What This Is
**Files:** `HomeView.tsx`
**Effort:** M (3h)

The current landing is a list of scenarios with no context. Fix:

- **Hero rewrite:** Keep "SimCash" brand. New subtitle: "Can AI agents learn to play the liquidity game?" One-liner below: "A multi-agent simulation where banks independently optimize their RTGS liquidity strategies — and we watch what happens."
- **Research context badge:** Small text below hero: "Extends the methodology of BIS Working Paper 1310 (Castro et al., 2025)"
- **"How It Works" expanded on first visit** (localStorage flag). Collapsed on return visits.
- **Primary CTA:** "▶ Run an Experiment" button that selects "2 Banks, 12 Ticks" and starts a 5-day mock game immediately. No configuration needed.
- **Scenario list:** Keep all 7, but add a ★ "Recommended first run" badge on "2 Banks, 12 Ticks"

### 1B. Rename Mock Mode
**Files:** `GameSettingsPanel.tsx`
**Effort:** S (1h)

"Mock Mode (no API costs)" is confusing. Change to:

- Toggle label: "AI Mode"
- Options: "Algorithmic" (current mock) / "LLM-Powered" (real Gemini)
- Tooltip: "Algorithmic mode uses rule-based optimization — fast and deterministic. LLM mode uses Gemini to reason about strategy in natural language — slower but produces richer reasoning traces."

### 1C. Fix Docs Model Reference
**Files:** `DocsView.tsx`
**Effort:** S (15min)

Replace "GPT-5.2" → "Gemini 2.5 Flash" or model-agnostic phrasing.

### 1D. Game Settings — Label Everything
**Files:** `GameSettingsPanel.tsx`
**Effort:** S (1h)

Add inline explanations to every setting:
- **Policy Complexity:** Replace "Full power" label with: "Simple: fraction only | Standard: + payment timing | Full: all actions & conditions"
- **Evaluation Samples:** "1 = fast exploration, 10+ = statistically robust"
- **Optimization Interval:** Keep current description (it's good)

### 1E. Contextual Tooltips Pass
**Files:** Multiple views (HomeView, GameView, ScenarioForm, GameSettingsPanel)
**Effort:** M (3h)

Systematic pass — every abbreviation, unit, or domain term gets a tooltip:
- "bps/tick" → "basis points per trading period"
- "¢/tick" → "cents per trading period"  
- Bootstrap stats (Δ, CV, CI) → plain explanations
- Event types → plain English (see 2D below)

---

## Wave 2: Make the Results Interpretable

**Effort:** ~12h | **Impact:** After a game completes, the user understands what happened and why it matters

### 2A. Game Completion Summary
**Files:** New `GameSummary.tsx`, `GameView.tsx`
**Effort:** M (4h)

After game completes, generate a narrative from the data:

```
📊 Results

System cost fell from $149,400 (Day 1) to $18,822 (Day 10) — a 87% reduction.
All three banks converged to similar liquidity fractions (~12-13%), suggesting
a symmetric equilibrium. Zero deadline penalties from Day 4 onward — all
payments settled on time once agents found the right liquidity level.
```

Template-based, no LLM needed. Key data points:
- Cost trajectory (Day 1 → final)
- Whether fractions converged (symmetric vs asymmetric)
- Settlement performance (penalties → zero?)
- Comparison to FIFO baseline (Day 1 = FIFO by default)

### 2B. Settlement Rate in Game Complete Banner
**Files:** `GameView.tsx`, `game.py`
**Effort:** S (2h)

Add to the existing banner:
```
Day 1 Cost    Final Cost    Cost Reduction    Settlement Rate    Final Fractions
149,400       18,822        ↓ 87.4%           100% ✓             A: 0.127 · B: 0.131 · C: 0.120
```

Calculate: `settled_on_time / total_payments` from event data.

### 2C. Event Type Labels
**Files:** `GameView.tsx`
**Effort:** S (1h)

```typescript
const EVENT_LABELS = {
  'Arrival': 'Payment arrived',
  'RtgsSubmission': 'Submitted to RTGS',
  'RtgsImmediateSettlement': 'Settled',
  'QueuedRtgs': 'Queued (insufficient funds)',
  'DeferredCreditApplied': 'Credit facility used',
  'CostAccrual': 'Cost charged',
  'BilateralOffset': 'Bilateral netting',
  'CycleSettlement': 'Multilateral cycle settled',
};
```

### 2D. Policy History Shows More Than Fraction
**Files:** `GameView.tsx`
**Effort:** M (3h)

Current "Policy History" only shows fraction trajectory. Add:
- If the policy tree is non-trivial (not just Release-all), show a one-line summary: "Hold when balance < 50K, else Release" 
- Expandable view showing the full tree diff between days
- This feeds into the visual tree renderer (Wave 4) but even a text summary helps now

---

## Wave 3: Research Workflow

**Effort:** ~14h | **Impact:** Makes SimCash useful for actual research, not just demos

### 3A. Data Export
**Files:** New `ExportPanel.tsx`, `GET /api/games/{id}/export`
**Effort:** M (4h)

In Game Complete section, add export buttons:
- **CSV:** One row per agent per day — `day, agent_id, fraction, liquidity_cost, delay_cost, penalty_cost, total_cost, num_payments, num_settled, policy_json`
- **JSON:** Full game state — all days, all events, all policies, all reasoning

### 3B. "Run This" from Scenario Library
**Files:** `ScenarioLibraryView.tsx`, `App.tsx`
**Effort:** S (2h)

Each scenario card gets a "▶ Run" button → navigates to Setup with scenario pre-selected. One less step between browsing and experimenting.

### 3C. YAML Schema Reference
**Files:** `DocsView.tsx`
**Effort:** M (3h)

Field-by-field reference for scenario YAML and policy JSON:
- Every field: name, type, required/optional, default, description, valid values
- Example snippets
- Common mistakes (e.g., `deadline_range` goes inside `arrival_config`, schedule type is `OneTime` not `fixed_tick`)

### 3D. Re-run Controls
**Files:** `GameView.tsx`
**Effort:** S (1h)

After game completes:
- "🔄 New seed" — same scenario, new RNG seed
- "🔁 Replay" — exact same seed (verification)

### 3E. Baseline Comparison
**Files:** `GameView.tsx`, `game.py`
**Effort:** M (4h)

Day 1 of every game IS the FIFO baseline (fraction=1.0). Make this explicit:

```
              FIFO (Day 1)    Optimized (Day 10)    Change
System Cost   $149,400        $18,822               ↓ 87.4%
Avg Fraction  1.000           0.126                 ↓ 87.4%
Penalties     2               0                     ✓ eliminated
```

---

## Wave 4: Creation & Visualization

**Effort:** ~16h | **Impact:** Power features feel professional and discoverable

### 4A. Visual Policy Tree
**Files:** New `PolicyTreeView.tsx`
**Effort:** L (8h)

SVG tree diagram of decision trees. Show in:
- Policy Library detail view
- Policy Editor (live preview)
- Game View → Current Policies
- Starting Policy dropdown (preview on hover)

This is the most impactful single visualization. Policies are the core research object — they should be visible, not hidden in JSON.

### 4B. Form Field Labels
**Files:** `ScenarioForm.tsx`
**Effort:** S (2h)

Label every input. Currently the agent section has unlabeled spinbuttons — completely opaque to anyone who isn't the developer. Every field needs: label, units, and brief hint text.

### 4C. Policy Editor Reference Panel
**Files:** `PolicyEditorView.tsx`
**Effort:** M (4h)

Side panel with:
- Available actions with descriptions
- Available condition fields with types
- Example snippets (click to insert)
- Live validation feedback as you type

### 4D. Scenario Editor Quality of Life
**Files:** `ScenarioForm.tsx`
**Effort:** S (2h)

- Duplicate agent button
- Counterparty weight auto-balance (warn when ≠ 1.0, offer "equalize" button)
- "Save as template" (separate from Save & Launch)

---

## Execution Order

### Sprint 1: Self-Explanatory (Wave 1)
Total: ~8h
1. Fix docs "GPT-5.2" (15min)
2. Mock mode rename (1h)
3. Game settings labels (1h)  
4. Landing page rewrite (3h)
5. Contextual tooltips pass (3h)

### Sprint 2: Interpretable Results (Wave 2)
Total: ~10h
6. Settlement rate metric (2h)
7. Event type labels (1h)
8. Game completion summary (4h)
9. Policy history improvements (3h)

### Sprint 3: Research Workflow (Wave 3)
Total: ~14h
10. Run from scenario library (2h)
11. Re-run controls (1h)
12. Baseline comparison (4h)
13. Data export CSV/JSON (4h)
14. YAML schema reference (3h)

### Sprint 4: Creation & Visualization (Wave 4)
Total: ~16h
15. Form field labels (2h)
16. Scenario editor QoL (2h)
17. Policy editor reference (4h)
18. Visual policy tree renderer (8h)

**Total: ~48 hours across 4 sprints**

---

## Success Metrics

| Metric | Current | After Wave 1 | After Wave 4 |
|--------|---------|-------------|-------------|
| Time to first experiment | 30+ min | 30 sec | 30 sec |
| User can explain results without docs | Unlikely | Yes | Yes |
| Custom scenario creation (no errors) | 3+ attempts | 1-2 attempts | 1 attempt |
| Researcher trusts output for paper | Maybe | Likely | Confident |
