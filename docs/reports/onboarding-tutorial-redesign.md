# Onboarding Tutorial Redesign Plan

**Date:** 2026-02-27  
**Author:** Nash  
**Status:** Proposal

---

## 1. Current Tour: What Exists

The current onboarding tutorial (`useTour.ts` + `TourOverlay.tsx`) is an 18-step guided tour across 3 phases, all within `GameView`:

| # | Phase | Target | Content |
|---|-------|--------|---------|
| 1 | 1 | `top-bar` | Welcome, round counter |
| 2 | 1 | `next-btn` | Run one round |
| 3 | 1 | `rerun-btn` | Re-run (determinism) |
| 4 | 1 | `auto-btn` | Auto-run + speed |
| 5 | 1 | `export-btn` | CSV/JSON export |
| 6 | 1 | `progress-bar` | Round progress |
| 7 | 1 | `empty-state` | Initial policy explanation |
| 8 | 1 | `next-btn` | **Action step:** run first round (waitForRound) |
| 9 | 2 | `round-timeline` | Day selector + 🧠 icons |
| 10 | 2 | `day-costs` | Cost breakdown + settlement rate |
| 11 | 2 | `balance-chart` | Tick-by-tick balance chart |
| 12 | 2 | `cost-evolution` | Cost evolution across rounds |
| 13 | 2 | `reasoning` | AI reasoning panel |
| 14 | 2 | `policy-display` | Current policies |
| 15 | 3 | `auto-btn` | **Action step:** start auto-run (waitForAuto) |
| 16 | 3 | `replay` | Tick replay |
| 17 | 3 | `payment-trace` | Payment lifecycle trace |
| 18 | 3 | `notes` | Notes panel |

**Post-tour:** A completion modal explains simulated vs real AI.

### Tour Trigger
- URL param `?tour=1` + localStorage `simcash_tour_done` not set
- No explicit "Start Tutorial" button in the UI

---

## 2. Features NOT Covered by the Current Tour

The following features exist in the current GameView and broader platform but have **zero tutorial coverage**:

### 2.1 GameView Features Missing from Tour

| Feature | Component/Area | Why It Matters |
|---------|---------------|----------------|
| **Activity Feed** | `ActivityFeed` | Real-time event stream showing simulation progress, optimization status, retries, errors. Users don't know it exists or what the color-coded events mean. |
| **Prompt Explorer** | `PromptExplorer` section (collapsible) | Lets users inspect the exact LLM prompts sent per day/agent — token breakdown, block-by-block anatomy. Key for researchers. |
| **Policy Diff View** | `PolicyDiffView` in reasoning cards | Shows what changed between old and new policy (tree diffs). Only appears in `full` constraint mode. |
| **Policy Viewer Modal** | `PolicyViewerModal` (🔍 View Policy button) | Full tree visualization of a policy with parameters, payment tree, bank tree. Users may never discover the button. |
| **Rejected Policy Inspector** | 🚫 View Rejected Policy button | Shows policies the bootstrap test rejected. Critical for understanding why the AI *didn't* change. |
| **Bootstrap Statistics** | Δ, CV, CI, n= in reasoning cards | Statistical validation of policy proposals. Researchers need to understand these. |
| **Model/Latency/Token Metadata** | Reasoning card footer | Shows which model was used, response time, token counts. |
| **Policy History Panel** | `PolicyHistoryPanel` | Per-agent timeline of all optimization attempts with accept/reject status. |
| **Liquidity Fraction Evolution Chart** | Evolution chart (simple mode) | Visual convergence of fraction parameter over rounds. |
| **Policy Evolution Panel** | `PolicyEvolutionPanel` (full mode) | Shows policy tree changes across rounds. |
| **Stall Detection & Resume** | Stall banner + Resume button | Auto-detects when server stops responding; users need to know they can resume. |
| **Experiment Error Recovery** | Error banner + retry with Next/Auto | When LLM fails after all retries, users need to know the experiment isn't dead. |
| **Connection Status Indicator** | Green/amber/red dot in top bar | Real-time WS connection health. |
| **Optimization Summary** | `optimization_summary` display | Shows success/failure rate of optimizations across the experiment. |
| **Speed Control (detailed)** | Fast/Normal/Slow toggle | Tour mentions Auto but doesn't explain the 3 speed modes and what they mean (0s/3s/8s pause). |
| **Completion Summary** | Green banner at experiment end | Cost reduction %, final fractions, final policies. Tour ends before this appears. |
| **Event Summary (lazy-loaded)** | `EventSummary` component | Aggregated event counts with tooltips explaining each event type. Lazy-loads from replay API. |
| **Scenario Link** | Clickable scenario name in top bar | Links back to the scenario definition in the library. |
| **Starting Policy Links** | 📋 Starting policies in top bar | Links to the starting policies used. |
| **Cycle/Day Display** | `every_scenario_day` schedule display | Shows "Day X/Y · Cycle Z" for multi-day scenarios. |
| **Quality Badge** | `COMPLETE ⚠️` for degraded experiments | Indicates some optimizations failed. |
| **Guest/Read-Only Mode** | Read-only banner for guests | Guests see experiments but can't control them. |
| **ReasoningExplorer** | Expandable full response + markdown | Collapsible raw LLM response with formatted markdown. |

### 2.2 Platform Features Outside GameView (Not in Tour at All)

| Feature | Route/View | Description |
|---------|-----------|-------------|
| **Home / Launch** | `HomeView` `/` | Quick-launch from scenario library, "How It Works" explainer |
| **Scenario Library** | `ScenarioLibraryView` `/library/scenarios` | Browse, fork, inspect YAML scenarios |
| **Policy Library** | `PolicyLibraryView` `/library/policies` | Browse, inspect, use starting policies |
| **Create → Scenario Editor** | `ScenarioEditorView` `/create` | Build custom scenarios with visual form + YAML |
| **Create → Policy Editor** | `PolicyEditorView` `/create?editPolicy` | Write/edit policy JSON with validation |
| **Experiments List** | `ExperimentsView` `/experiments` | All your experiments, status, filtering, delete |
| **Game Settings Panel** | `GameSettingsPanel` (in scenario editor) | Rounds, eval samples, constraint preset, LLM toggle, model selection, max proposals, per-agent starting policies |
| **Prompt Anatomy Panel** | `PromptAnatomyPanel` (in config) | Prompt block configuration, smart suggestions |
| **API Keys** | `ApiKeysView` `/api-keys` | BYOK for OpenAI/Anthropic/Google models |
| **Admin Dashboard** | `AdminDashboard` `/admin` | User management, impersonation |
| **Docs** | `DocsView` `/docs` | In-app documentation |
| **Event Timeline Builder** | `EventTimelineBuilder` | Visual scenario event scheduling |

---

## 3. Recommended Tutorial Example

**Use one of Stefan's completed experiments** that demonstrates the most features. Ideal criteria:
- Uses real LLM (not simulated AI) — shows reasoning, prompt explorer, model metadata
- `full` constraint preset — shows policy diffs, tree visualization
- Multiple rounds (≥5) — shows convergence, policy history, evolution charts
- Has some rejected policies — shows bootstrap stats, rejected policy viewer
- Preferably a well-known scenario (e.g., `exp2` or one from the scenario library)

**Recommendation:** Pre-select a specific completed experiment from Stefan's library (UID `NZlbZF9Y7CbzjbW3L8Cvf4sm8dN2`) and hard-code its `game_id` as the tutorial example. The tour would open this experiment in read-only/replay mode so the user can explore real results without waiting for LLM responses.

This is a key design change: **the tutorial should walk through a completed experiment** rather than forcing users to run one from scratch (which takes minutes with real LLM).

---

## 4. Proposed Redesign

### 4.1 Architecture: Multi-Page Tour

Replace the single-phase GameView-only tour with a **multi-page guided experience** that covers the full platform.

**Structure:**

```
Chapter 1: Welcome & Orientation (HomeView)
Chapter 2: Understanding Scenarios (ScenarioLibraryView)  
Chapter 3: The Experiment Runner (GameView — pre-loaded example)
Chapter 4: Deep Dive: AI Reasoning (GameView — reasoning section)
Chapter 5: Advanced Analysis (GameView — advanced features)
Chapter 6: Creating Your Own (CreateView)
```

### 4.2 Detailed Step Plan

#### Chapter 1: Welcome & Orientation (5 steps)
1. **Welcome banner** — "SimCash is a research platform where AI agents learn to optimize payment strategies in an interbank coordination game."
2. **Navigation sidebar** — Point out Library, Create, Experiments, Docs sections.
3. **How It Works** — Highlight the "How It Works" explainer on the home page (if present).
4. **Quick Launch** — "You can start an experiment directly from a scenario in the library."
5. **Transition** — "Let's look at an actual experiment. We'll load a completed one so you can explore the results."

#### Chapter 2: Exploring a Completed Experiment — Interface (8 steps)

*Loads Stefan's example experiment.*

6. **Top bar overview** — Connection indicator (green dot), scenario name (clickable link to library), round/cycle counter, model badge (🧠 gpt-4.1), starting policy links.
7. **Activity Feed** — "This real-time feed shows everything happening: simulation progress, AI thinking, retries, errors. Color-coded by severity."
8. **Progress bar** — Shows completion progress.
9. **Day Timeline** — "Click any day to review results. The 🧠 icon means AI optimized after that day. ⚠️ means optimization failed."
10. **Day Costs** — Settlement rate banner, per-agent cost breakdown (liquidity / delay / penalty / total), fraction display.
11. **Balance Chart** — "Hover to see exact balances at each tick. Watch the interplay of outgoing and incoming payments."
12. **Cost Evolution Chart** — "Track system cost across all rounds. Hover data points for per-agent detail."
13. **Completion Summary** — "When done, you see total cost reduction, final fractions/policies."

#### Chapter 3: AI Reasoning & Policy Optimization (10 steps)

14. **Reasoning Panel overview** — "After each round, each agent independently analyzes its own results. 🔒 information-isolated means they can't see each other's strategies."
15. **Reasoning Card anatomy** — Agent name, accept/reject badge, fraction change (old → new), summary text.
16. **Bootstrap Statistics** — "Δ = cost change, CV = reliability, CI = confidence interval. The system uses statistical validation to prevent bad policy changes."
17. **View Policy button** — **Action step:** Click 🔍 View Policy. Shows PolicyViewerModal with tree visualization (payment tree, bank tree, parameters).
18. **Rejected Policy** — If available, click 🚫 View Rejected Policy. "Not all proposals are accepted — the bootstrap test protects against regressions."
19. **ReasoningExplorer** — Expand full LLM response. "Click to read the AI's complete analysis in markdown."
20. **Model metadata** — "See which model was used, response latency, and token counts."
21. **Policy History Panel** — "Browse every optimization attempt for each agent. Click a day pill to see that round's reasoning."
22. **Policy Diff View** — (full mode) "See exactly what changed in the decision tree between rounds."
23. **Liquidity Fraction / Policy Evolution** — "Watch how the key parameter converges over time."

#### Chapter 4: Advanced Features (8 steps)

24. **Tick Replay** — "Load any day's replay to step through tick-by-tick. See balances, events, and settlements at each moment."
25. **Payment Trace** — "Switch to Payment Trace for a per-payment lifecycle view — arrival, queue, settlement, or expiry."
26. **Event Summary** — "The Event Summary tab aggregates events by type. Hover the ℹ️ icons for explanations (Arrival, RtgsImmediateSettlement, BilateralOffset, etc.)."
27. **Prompt Explorer** — **Action step:** Expand Prompt Explorer. "Inspect the exact prompts sent to the AI. See token counts per block, compare across days."
28. **Export** — "Download results as CSV (for R/Python/Excel) or JSON (includes notes). Notes are embedded in JSON exports."
29. **Notes** — "Jot observations as you go. Auto-saved to browser, included in JSON export."
30. **Speed Control** — "⏩ Fast = no pause, ▶️ Normal = 3s pause, 🐢 Slow = 8s pause between rounds."
31. **Error & Stall Recovery** — "If the AI fails or the connection drops, you'll see banners with Resume/Retry options. Experiments are checkpointed — nothing is lost."

#### Chapter 5: The Broader Platform (6 steps)

32. **Experiments List** — Navigate to `/experiments`. "All your experiments in one place. Filter by status, see settlement rates and costs at a glance."
33. **Scenario Library** — Navigate to `/library/scenarios`. "Browse community scenarios. Click to inspect the YAML configuration."
34. **Policy Library** — Navigate to `/library/policies`. "Browse and inspect starting policies. Use them when launching experiments."
35. **Create → Scenario Editor** — Navigate to `/create`. "Build custom scenarios: set agents, payment flows, cost parameters, scheduled events."
36. **Create → Policy Editor** — Switch to Policy tab. "Write or paste policy JSON. The editor validates against the schema."
37. **Game Settings** — "Configure rounds, constraint mode (simple vs full), LLM model, evaluation samples, per-agent starting policies."

#### Finale (1 step)

38. **Completion** — "You've seen everything SimCash offers! Start by picking a scenario from the library, or create your own. The AI will learn — watch it converge."

### 4.3 Implementation Changes

#### Tour System Upgrades

1. **Multi-page navigation** — Tour steps need a `route` field. When advancing to a step on a different page, `navigate()` first, then wait for the target element to appear.

```typescript
export interface TourStep {
  target: string;
  content: string;
  chapter: number;
  route?: string;        // NEW: navigate here before showing step
  waitForRound?: boolean;
  waitForAuto?: boolean;
  waitForElement?: boolean; // NEW: poll until target appears
  action?: 'click' | 'expand'; // NEW: prompt user to interact
  highlightArea?: boolean; // NEW: highlight a larger region
}
```

2. **Pre-loaded example experiment** — The tour needs a known `game_id` for a completed experiment. Options:
   - Hard-code a specific Stefan experiment ID
   - Create a dedicated "tutorial experiment" fixture that ships with the platform
   - API endpoint: `GET /api/tutorial-experiment` returns a suitable completed experiment

3. **Chapter progress** — Show chapter titles and progress (not just step N/M).

4. **Restart tour button** — Add to user settings / nav sidebar: "🎓 Restart Tutorial". Currently the only trigger is `?tour=1` on first visit.

5. **Skip to chapter** — Let users jump to specific chapters if they only want to learn about one area.

#### New `data-tour` Targets Needed

Add these attributes to GameView and other views:

```
activity-feed          → ActivityFeed component
prompt-explorer        → PromptExplorer section
policy-viewer-btn      → 🔍 View Policy button (in reasoning card)
rejected-policy-btn    → 🚫 View Rejected Policy button  
bootstrap-stats        → Δ/CV/CI row in reasoning card
model-metadata         → Model/latency/tokens row
policy-history         → PolicyHistoryPanel
policy-diff            → PolicyDiffView section
fraction-evolution     → Fraction evolution chart
connection-indicator   → Green/amber/red dot
completion-summary     → Green completion banner
event-summary-tab      → Event Summary tab button
speed-control          → Speed toggle (separate from auto-btn)
stall-banner           → Stall/error recovery banner
scenario-link          → Clickable scenario name
starting-policies      → Starting policy links

# Outside GameView:
nav-sidebar            → Main navigation
experiments-list       → Experiments table
scenario-library       → Scenario cards/list
policy-library         → Policy cards/list  
scenario-editor        → Scenario form
policy-editor          → Policy JSON editor
game-settings          → GameSettingsPanel
how-it-works           → HowItWorks component
```

#### UX Improvements

1. **Chapter header cards** — At the start of each chapter, show a full-screen card explaining what the chapter covers before diving into step-by-step.

2. **Interactive steps** — Some steps should prompt user interaction (click a button, expand a panel) rather than just pointing at things. Mark these with a distinct button style ("Try it →" instead of "Next").

3. **Contextual re-entry** — If a user visits a feature for the first time (detected via localStorage), offer a mini-tour for just that feature. E.g., first time opening Prompt Explorer → 3-step micro-tour.

4. **Mobile responsiveness** — Current tour uses fixed positioning that can break on mobile. New design should handle viewport constraints better.

---

## 5. Prioritized Implementation Plan

### Phase 1: Quick Wins (1-2 days)
- Add missing `data-tour` attributes to all GameView features
- Add 10+ new steps to the existing tour covering Activity Feed, Prompt Explorer, Policy Viewer, Bootstrap Stats, Policy History, Completion Summary
- Add "🎓 Restart Tutorial" button to nav sidebar
- Keep single-page (GameView only) for now

### Phase 2: Example Experiment (1 day)  
- Pick a completed experiment from Stefan's library
- Create API endpoint or fixture to load it as the tutorial example
- Modify tour to open in read-only mode on a real completed experiment

### Phase 3: Multi-Page Tour (2-3 days)
- Implement route-aware tour system with `navigate()` support
- Add Chapter 1 (Welcome) and Chapter 5 (Platform) steps
- Add chapter progress UI

### Phase 4: Polish (1 day)
- Interactive "Try it" steps
- Chapter header cards
- Contextual micro-tours for first-time feature discovery
- Mobile testing

---

## 6. Summary

The current 18-step tour covers ~40% of GameView's features and 0% of the broader platform. The redesigned 38-step tour across 6 chapters would cover:

- **All GameView features** including Activity Feed, Prompt Explorer, Policy Viewer/Diff, Bootstrap stats, Policy History, Error Recovery, Event Summary, Speed Controls, Completion Summary
- **Platform navigation** including Experiments List, Scenario/Policy Libraries, Create/Edit views, Game Settings
- **A real completed experiment** as the walkthrough example (no waiting for LLM)

The phased approach lets us ship quick improvements (Phase 1) while building toward the full multi-page experience.
