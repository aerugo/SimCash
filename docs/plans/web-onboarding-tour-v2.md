# Onboarding Tour v2 — Implementation Plan

**Status:** Ready  
**Date:** 2026-02-27  
**Branch:** `feature/onboarding-tour-v2`  
**Depends on:** `feature/interactive-web-sandbox` (current working branch)  
**Script:** `docs/reports/onboarding-tutorial-script.md`  
**Example Experiment:** `9af6fa02` (Stefan's 2-bank Gemini 2.5 Pro run)

## Summary

Replace the existing 18-step simulated-AI tour with a 25-beat narrative tour that walks through a **real completed experiment** with rich decision trees, accepted/rejected policies, and 60.8% cost reduction. The tour teaches the tree evolution story, not just the fraction slider.

## Local Dev Setup

The tutorial uses a specific completed experiment (`9af6fa02`, Stefan's 2-bank Gemini 2.5 Pro run). This experiment data has been downloaded from GCS and committed to the local data directory so the entire tutorial can be developed and tested on localhost without any network dependency.

**Files needed (already in place):**
```
web/backend/data/NZlbZF9Y7CbzjbW3L8Cvf4sm8dN2/games/9af6fa02.json  (5MB checkpoint)
web/backend/data/NZlbZF9Y7CbzjbW3L8Cvf4sm8dN2/games/index.json     (minimal, 1 game)
web/backend/data/experiments/registry.json                            (global lookup)
```

**Start local dev:**
```bash
# Terminal 1: Backend (no auth, local storage, no GCS)
cd web/backend
SIMCASH_STORAGE_MODE=local SIMCASH_AUTH_MODE=none uv run uvicorn app.main:app --host 127.0.0.1 --port 8642

# Terminal 2: Frontend
cd web/frontend
npm run dev
```

**Verified:** `curl http://127.0.0.1:8642/api/games/9af6fa02` returns full game state with all 10 days, policy trees, reasoning history, and cost data. The Firestore warnings at startup are harmless (admin seeding fails, but the game loads from local JSON).

**⚠️ Do NOT commit the data files to git.** Add to `.gitignore`:
```
web/backend/data/NZlbZF9Y7CbzjbW3L8Cvf4sm8dN2/
web/backend/data/experiments/
```

In production, the experiment is already in GCS and accessible via the public API.

## What Changes vs v1

| Aspect | v1 (current) | v2 (new) |
|--------|-------------|----------|
| Experiment | Simulated AI, user runs it live | Pre-loaded real result (`9af6fa02`) |
| Steps | 18, mostly read-only tooltips | 25, with interactive discovery beats |
| Scope | Fraction + basic UI | Full tree evolution, bootstrap, prompt explorer |
| Interactions | 2 (run round, start auto) | ~8 (click days, open modals, expand panels) |
| Entry | `?tour=1` only | Sidebar button + `?tour=1` + first-visit auto |

## Architecture

### Files to Create

| File | Purpose |
|------|---------|
| *None* | Reuse existing `useTour.ts` and `TourOverlay.tsx`, extend in place |

### Files to Modify

| File | Changes |
|------|---------|
| `hooks/useTour.ts` | Replace step definitions with v2 beats; add interaction types; add `TUTORIAL_GAME_ID` constant |
| `components/TourOverlay.tsx` | Add act transition interstitials; handle new interaction types (click-day, open-modal, expand) |
| `views/GameView.tsx` | Add new `data-tour` attributes; wire interaction callbacks to tour state |
| `Layout.tsx` | Add "🎓 Tutorial" button to nav sidebar |
| `views/HomeView.tsx` | Update tour launch to navigate to example experiment |

### NOT Modified

| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `web/backend/` | Tour is purely frontend; experiment data served from local JSON checkpoint |

---

## Implementation Phases

### Phase 0: Setup & Exploration (30 min)

1. Create branch `feature/onboarding-tour-v2` from current working branch
2. Ensure `.gitignore` excludes `web/backend/data/NZlbZF9Y7CbzjbW3L8Cvf4sm8dN2/` and `web/backend/data/experiments/`
3. Start backend: `cd web/backend && SIMCASH_STORAGE_MODE=local SIMCASH_AUTH_MODE=none uv run uvicorn app.main:app --host 127.0.0.1 --port 8642`
4. Start frontend: `cd web/frontend && npm run dev`
5. **Screenshot:** Navigate to `http://localhost:5173/experiment/9af6fa02` — verify the full completed experiment renders with all 10 days, policy trees, reasoning cards, cost charts
6. **Screenshot:** Open the existing tour on a fresh experiment to document v1 behavior (for comparison)

**Checkpoint:** Local dev stack running, example experiment renders fully at localhost, baseline screenshots saved.

---

### Phase 1: New `data-tour` Targets (45 min)

Add `data-tour` attributes to elements that the v2 script references but v1 doesn't target:

```
activity-feed          → ActivityFeed component wrapper div
completion-summary     → green completion banner in GameView
policy-history         → PolicyHistoryPanel wrapper
rejected-policy-btn    → 🚫 View Rejected Policy button (in AgentReasoningCard)
bootstrap-stats        → Δ/CV/CI row in AgentReasoningCard
prompt-explorer        → collapsible PromptExplorerSection wrapper
model-badge            → 🧠 model badge in top bar
```

Also: ensure existing targets (`reasoning`, `policy-display`, `cost-evolution`, etc.) still have correct placement.

**Screenshot after:** Navigate to `/experiment/9af6fa02`, inspect that all `data-tour` elements are present and correctly positioned. Screenshot the page with DevTools highlighting the tour targets.

**Checkpoint:** All 16+ tour target elements exist in the DOM when viewing the example experiment.

---

### Phase 2: Tour Step Definitions (1 hour)

Rewrite `TOUR_STEPS` in `useTour.ts` with the 25 beats from the script.

New step interface:

```typescript
export const TUTORIAL_GAME_ID = '9af6fa02';

export interface TourStep {
  id: string;               // e.g. 'welcome', 'the-crash'
  act: 1 | 2 | 3 | 4 | 5;
  target: string;           // data-tour attribute value
  content: string;          // supports **bold**
  interaction?: TourInteraction;
  delay?: number;           // ms before showing tooltip
}

export type TourInteraction =
  | { type: 'click-day'; day: number }
  | { type: 'open-modal'; target: string }
  | { type: 'close-modal' }
  | { type: 'expand'; target: string }
  | { type: 'click-pill' }
  | { type: 'none' };
```

Enter all 25 beats with correct targets, content text, and interaction specs.

**No screenshots needed** — this is pure data entry. But verify TypeScript compiles clean.

**Checkpoint:** `useTour.ts` has all 25 steps, types compile, no regressions in existing tour logic.

---

### Phase 3: Interaction System (2 hours)

This is the core engineering work. The v1 tour has only two interaction types (`waitForRound`, `waitForAuto`). We need a general-purpose interaction system.

#### 3a. `click-day` interaction
- Tour tooltip says "Click Day N"
- Tour enters waiting state (overlay stays visible but Next is hidden)
- When `selectedDay` changes to the target day, tour advances
- Implementation: `useTour` exposes a `notifyDaySelected(day: number)` callback; GameView calls it from its day-selector onClick

#### 3b. `open-modal` interaction
- Tour says "Click 🔍 View Policy"
- Tour enters waiting state
- When `PolicyViewerModal` mounts (or any target modal), tour advances
- Implementation: Use a MutationObserver or a simple `useEffect` that checks for the modal's presence in DOM, or have the modal call `notifyModalOpen()`

#### 3c. `close-modal` interaction
- After showing the modal tooltip, wait for modal to close
- Implementation: Inverse of open-modal — detect when the modal unmounts

#### 3d. `expand` interaction
- Tour says "Expand Prompt Explorer"
- Wait for the collapsible section to open
- Implementation: The section's `isOpen` state change triggers `notifyExpand(target)`

#### 3e. `click-pill` interaction
- Tour says "Click a ✗ pill"
- Wait for any rejected pill in PolicyHistoryPanel to be clicked
- Implementation: PolicyHistoryPanel calls `notifyPillClicked()` on selection

#### Integration pattern
Add a `TourContext` (or extend existing tour hook) that provides notification callbacks. Components call these callbacks on relevant user actions. The tour hook listens and advances when the expected interaction occurs.

```typescript
// In useTour.ts
const notifyInteraction = useCallback((type: string, detail?: unknown) => {
  if (!state.active || !state.waitingForInteraction) return;
  const step = TOUR_STEPS[state.step];
  if (!step.interaction) return;
  // Match interaction type and advance
  if (step.interaction.type === 'click-day' && type === 'day-selected' && detail === step.interaction.day) {
    advance();
  }
  // ... etc for other types
}, [state]);
```

**Screenshot after each interaction type:** Test each interaction by running through the relevant tour beats. Screenshot the tooltip, the waiting state, and the state after interaction completes.

**Checkpoint:** All 5 interaction types work. Tour can advance through beats 4, 7, 11, 12-13, 14, 16-17, 19 without manual Next clicks.

---

### Phase 4: Act Transitions (45 min)

Between acts, show a brief centered interstitial:

```
→ Act II: "Let's see what the AI did next..."
→ Act III: "The AI learned from its mistake."
→ Act IV: "Now let's look at how it thinks."
→ Act V: "Time to zoom out."
```

Implementation:
- When advancing from the last beat of an act to the first beat of the next, show a fullscreen interstitial instead of the normal tooltip
- Centered text on a dimmed backdrop
- Auto-advances after 2s OR on click
- Subtle fade-in/fade-out transition

Add to `TourOverlay.tsx` as a new render mode (`interstitial` vs `tooltip`).

**Screenshot:** Capture each of the 4 act transitions. Verify text is readable, backdrop is correct, timing feels right.

**Checkpoint:** Act transitions display correctly between all 5 acts.

---

### Phase 5: Tour Entry Points (45 min)

#### 5a. Sidebar "Tutorial" button
- Add `🎓 Tutorial` button to `Layout.tsx` nav sidebar
- On click: navigate to `/experiment/9af6fa02?tour=1`
- Clear `simcash_tour_done` from localStorage before navigating

#### 5b. First-visit auto-start
- When user visits HomeView for the first time (no `simcash_tour_done` in localStorage), show a welcome card: "New here? Take a 5-minute guided tour of a real AI experiment." with "Start Tour" and "Skip" buttons
- "Start Tour" navigates to `/experiment/9af6fa02?tour=1`
- "Skip" sets `simcash_tour_done` in localStorage

#### 5c. Update existing `?tour=1` handling
- Currently starts the old tour on any GameView
- Change: if `gameId === TUTORIAL_GAME_ID`, start v2 tour; otherwise start a mini-tour (future work, out of scope)

**Screenshot:** The sidebar button, the first-visit welcome card, and the tour starting from the sidebar button.

**Checkpoint:** All three entry points work. Tour starts correctly from each.

---

### Phase 6: Completion Card (30 min)

Replace the current `TourCompletionNote` (which explains simulated vs real AI — no longer relevant since we're using a real experiment) with the "What's Next" card from the script:

- 4 suggested next actions with emoji
- "Start Exploring" button → navigate to home
- Sets `simcash_tour_done` in localStorage

**Screenshot:** The completion card. Verify it looks good, buttons work, localStorage is set.

**Checkpoint:** Tour completes cleanly, user lands on home page.

---

### Phase 7: Full Playthrough & Polish (1.5 hours)

This is the critical QA phase. **Do not skip.**

#### 7a. Full playthrough with screenshots
Walk through all 25 beats in the browser. **Screenshot every beat.** Check:

- [ ] Tooltip positions correctly (not clipped, not overlapping the target)
- [ ] Content text is readable and correct (matches the script)
- [ ] Bold text renders properly
- [ ] Spotlight cutout highlights the right element
- [ ] Interactive beats wait correctly and advance on the right action
- [ ] Act transitions display and auto-advance
- [ ] Back button works across act boundaries
- [ ] Skip button works at any point
- [ ] Progress bar shows correct chapter/beat

#### 7b. Edge cases
- [ ] Tour on mobile viewport (375px width) — tooltips don't overflow
- [ ] Tour with slow network (example experiment takes time to load) — show loading state
- [ ] Refresh mid-tour — tour resumes at correct step (or resets gracefully)
- [ ] Tour targets that are in collapsed/scrolled-away sections — scroll into view works
- [ ] Elements that render conditionally (completion summary only shows when complete, activity feed may be empty)

#### 7c. Visual polish
- [ ] Tooltip entrance animation (subtle fade + slide)
- [ ] Spotlight ring matches theme (light mode + dark mode)
- [ ] Act transition text is centered and readable on both themes
- [ ] No z-index conflicts with modals opened during the tour

#### 7d. Performance
- [ ] No MutationObserver leaks
- [ ] Tour doesn't re-render the entire GameView on step change
- [ ] Cleanup on unmount

**Screenshot:** Save the full 25-beat screenshot sequence as `docs/plans/tour-v2-screenshots/` for review.

**Checkpoint:** All beats work, all edge cases handled, screenshot gallery complete.

---

### Phase 8: Code Cleanup & Commit (30 min)

1. Remove any dead code from v1 that's no longer used
2. Add JSDoc comments to new interaction types
3. Verify TypeScript strict mode passes
4. Verify `npm run build` succeeds
5. Run existing tests (if any)
6. Commit with message: `feat(tour): v2 onboarding tour with real experiment walkthrough`
7. Push to branch

---

## Time Estimate

| Phase | Task | Time |
|-------|------|------|
| 0 | Setup & exploration | 30 min |
| 1 | New data-tour targets | 45 min |
| 2 | Tour step definitions | 1 hr |
| 3 | Interaction system | 2 hr |
| 4 | Act transitions | 45 min |
| 5 | Tour entry points | 45 min |
| 6 | Completion card | 30 min |
| 7 | Full playthrough & polish | 1.5 hr |
| 8 | Cleanup & commit | 30 min |
| **Total** | | **~8 hours** |

## Screenshot Checkpoints Summary

| After Phase | What to Screenshot | Purpose |
|-------------|-------------------|---------|
| 0 | Baseline experiment view, old tour steps | Document starting point |
| 1 | All `data-tour` elements highlighted | Verify targets exist |
| 3 (each sub) | Each interaction type working | Verify interaction system |
| 4 | All 4 act transitions | Verify interstitials |
| 5 | Sidebar button, welcome card, tour start | Verify entry points |
| 6 | Completion card | Verify ending |
| 7 | **All 25 beats sequentially** | Full QA |

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Example experiment `9af6fa02` gets deleted | Create a backend fixture/snapshot; or flag it as protected in storage |
| Public API changes break experiment loading | Pin the experiment data structure; add a health check |
| Modal/panel interactions are fragile across React re-renders | Use `data-tour-modal` attributes + MutationObserver rather than React state coupling |
| Tour breaks on mobile | Phase 7b explicitly tests 375px viewport; keep tooltip max-width at 320px |
| Old tour code conflicts | Phase 1 works alongside old code; Phase 8 removes dead paths |

## Success Criteria

- [ ] Tour walks through all 25 beats on the real example experiment
- [ ] User opens BANK_A's decision tree modal and sees the 3-condition tree
- [ ] User opens BANK_B's Day 7 tree and sees the 4-condition tree
- [ ] User inspects a rejected policy with bootstrap stats
- [ ] Prompt Explorer expands and is explained
- [ ] Cost evolution, balance chart, payment trace are all highlighted
- [ ] Act transitions feel smooth and add narrative rhythm
- [ ] Tour accessible from sidebar button, first-visit card, and URL param
- [ ] Tour works on both light and dark themes
- [ ] Full screenshot gallery exists in `docs/plans/tour-v2-screenshots/`
- [ ] TypeScript compiles clean, build succeeds
