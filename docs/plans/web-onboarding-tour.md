# Onboarding Tour — Development Plan

**Status**: Draft  
**Date**: 2026-02-19  
**Branch**: feature/interactive-web-sandbox  
**Target**: ~7 minute guided tour for first-time users

## Goal

A special "tour mode" for the experiment runner that walks users through every major UI component with contextual tooltips/highlights. The tour introduces the interface *before* any experiment runs, then guides the user through running their first round, interpreting results, and using auto-run. It should feel like a friendly colleague showing you around — not a wall of text.

## Design Principles

1. **Progressive** — show one thing at a time, don't overwhelm
2. **Interactive** — user clicks through at their own pace (not timed)
3. **Integrated** — tour runs inside the real GameView, not a separate page
4. **Skippable** — "Skip tour" always visible
5. **Minimal code** — tooltip overlay + step state machine, no heavy library

## Tour Flow (~18 steps, ~7 minutes)

### Phase 1: Interface Overview (before starting — steps 1-8, ~3 min)

| Step | Target Element | Tooltip Content |
|------|---------------|-----------------|
| 1 | Top bar (title + round counter) | "Welcome! This is the experiment runner. You'll watch AI agents learn to optimize payment strategies over multiple rounds. The counter shows your progress." |
| 2 | ▶ Next button | "Click **Next** to run one round at a time. Each round simulates a full day of interbank payments." |
| 3 | 🔄 Re-run button | "**Re-run** replays the last round with the same random seed — useful for verifying results are deterministic." |
| 4 | ⏩ Auto button + speed control | "**Auto** runs all remaining rounds automatically. Use the speed control to adjust pacing — fast skips the pause between rounds." |
| 5 | 📥 Export button | "Export your results as **CSV** or **JSON** for further analysis in R, Python, or Excel." |
| 6 | Progress bar | "This tracks how many rounds have completed out of the total." |
| 7 | Empty state / "Ready to Start" panel | "Each agent starts with an initial liquidity policy. The AI optimizer will refine it after each round based on observed costs." |
| 8 | (CTA) | "Let's run the first round! Click **▶ Next** to begin." |

### Phase 2: First Round Results (after round 1 completes — steps 9-14, ~2.5 min)

| Step | Target Element | Tooltip Content |
|------|---------------|-----------------|
| 9 | Round Timeline | "Each numbered button is a completed round. Click any to review its results. The 🧠 icon means the AI optimized policies after that round." |
| 10 | Day Costs panel | "This is the cost breakdown — liquidity cost (holding money), delay cost (slow payments), and penalties (missed deadlines). The settlement rate shows what percentage of payments cleared." |
| 11 | Balance chart | "Watch how each bank's balance moves tick-by-tick through the day. Dips mean outgoing payments; rises mean incoming." |
| 12 | Cost Evolution chart | "This chart tracks total system cost across rounds. With good optimization, you should see costs trend downward." |
| 13 | AI Reasoning panel | "After each round, the AI analyzes what went wrong and proposes policy changes. You can expand to read its full reasoning." |
| 14 | Policy display | "The current policy for each agent — showing the liquidity fraction (how much of their pool to commit) and the decision tree (when to release or hold payments)." |

### Phase 3: Auto-run & Advanced (steps 15-18, ~1.5 min)

| Step | Target Element | Tooltip Content |
|------|---------------|-----------------|
| 15 | (CTA) | "Now let's see the AI learn! Click **⏩ Auto** to run the remaining rounds automatically." |
| 16 | Tick Replay section | "After any round, click **Load Replay** to step through tick-by-tick — see exactly which payments settled and when." |
| 17 | Payment Trace toggle | "The **Payment Trace** shows every individual payment's lifecycle — when it arrived, queued, settled, or expired." |
| 18 | Notes panel + completion | "Use the **Notes** panel to jot down observations. When the experiment completes, you'll see a summary with total cost reduction. That's the tour — happy experimenting! 🎉" |

**Post-tour note** (shown once after dismissing step 18):
> "💡 This experiment used **simulated AI** for instant results. Real experiments use an LLM (like Gemini) which takes 10-40 seconds per optimization round — but produces genuinely novel strategies."

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `web/frontend/src/components/TourOverlay.tsx` | Tour step tooltip + highlight + skip/next/back buttons |
| `web/frontend/src/hooks/useTour.ts` | Step state machine, localStorage persistence (don't show again) |

### Modified Files

| File | Changes |
|------|---------|
| `web/frontend/src/views/GameView.tsx` | Add `data-tour="step-N"` attributes to target elements; render `<TourOverlay>` when tour active |
| `web/frontend/src/views/HomeView.tsx` | Quick Experiment button passes `?tour=1` query param |

### NOT Modified

| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `web/backend/` | Tour is purely frontend |

## Implementation Details

### TourOverlay Component

- Renders a semi-transparent backdrop with a "cutout" around the target element
- Tooltip positioned above/below/left/right of target (auto-positioned to stay in viewport)
- Shows: step text, step counter ("3 of 18"), Next/Back/Skip buttons
- Target element found via `document.querySelector('[data-tour="step-N"]')`
- Scroll target into view if offscreen
- Phase 2 steps (9-14) wait until `gameState.days.length >= 1` before advancing

### useTour Hook

```typescript
interface TourState {
  active: boolean;
  step: number;
  phase: 1 | 2 | 3;
  waitingForRound: boolean;  // true between step 8 and 9
}
```

- Step 8 sets `waitingForRound = true` and hides overlay
- When `gameState.days.length` goes from 0 → 1, advance to step 9
- Step 15 sets `waitingForAuto = true`, advances when autoRunning starts
- `localStorage.setItem('simcash_tour_done', '1')` on completion/skip

### Data-tour Attributes

Add to GameView elements:
```
data-tour="top-bar"
data-tour="next-btn"
data-tour="rerun-btn"
data-tour="auto-btn"
data-tour="export-btn"
data-tour="progress-bar"
data-tour="empty-state"
data-tour="round-timeline"
data-tour="day-costs"
data-tour="balance-chart"
data-tour="cost-evolution"
data-tour="reasoning"
data-tour="policy-display"
data-tour="replay"
data-tour="payment-trace"
data-tour="notes"
```

## Phases

| Phase | What | Est. Time |
|-------|------|-----------|
| 1 | `useTour` hook + `TourOverlay` component | 2h |
| 2 | Add `data-tour` attrs to GameView, wire up tour | 1h |
| 3 | HomeView: add tour param, auto-start tour for onboarding | 30m |
| 4 | Polish: positioning, animations, responsive | 1h |

## Success Criteria

- [ ] Tour auto-starts when launched from "Quick Experiment" with `?tour=1`
- [ ] All 18 steps render correctly with proper positioning
- [ ] Phase 2 waits for round 1 to complete before continuing
- [ ] Skip button works at any step
- [ ] Tour doesn't show again after completion (localStorage)
- [ ] Tour works on both desktop and mobile widths
- [ ] "Simulated AI" note shown at completion
- [ ] Frontend TypeScript compiles clean
- [ ] Frontend builds successfully
