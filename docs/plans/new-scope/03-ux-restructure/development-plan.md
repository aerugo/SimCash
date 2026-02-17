# UX Restructure: Scenario-First Flow — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 1, Item 4  
**Depends on**: Plans 01 (Scenario Library) and 02 (Policy Library)

## Goal

Restructure the landing page from flat preset buttons to a scenario-first flow: Browse Library → Select Scenario → Configure (policies, optimization, days) → Launch. The UX should make a new user productive in 30 seconds while giving researchers full control.

## Web Invariants

- **WEB-INV-6**: Dark Mode Only
- **WEB-INV-7**: Relative URLs

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/views/LaunchView.tsx` | Scenario detail + configuration + launch flow |
| `web/frontend/src/components/GameConfigPanel.tsx` | Configuration panel: policy assignment, LLM mode, max days, eval samples, optimization interval |

### Modified
| File | Changes |
|------|---------|
| `web/frontend/src/views/HomeView.tsx` | Replace preset buttons with scenario library entry point + "My Simulations" |
| `web/frontend/src/App.tsx` | Navigation restructure: Home → Library → Launch → Game |

### NOT Modified
| File | Why |
|------|-----|
| `web/backend/` | No backend changes needed — uses existing endpoints from Plans 01 + 02 |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Redesign HomeView: library entry + my simulations | 2h | tsc + build |
| 2 | Build LaunchView: scenario detail + config panel | 3h | tsc + build |
| 3 | Navigation flow: Home → Library → Launch → Game | 2h | tsc + build + UI protocol |

## Phase 1: HomeView Redesign

Replace current preset buttons with:
- **Hero section**: SimCash title + one-liner
- **"Explore Scenarios" card** → navigates to Scenario Library
- **"My Simulations" card** → shows saved games (from GCS index), resume/delete
- **Quick start**: "Jump into a 2-bank scenario" shortcut for new users

## Phase 2: LaunchView

When a user selects a scenario from the library, they land here:

```
┌──────────────────────────────────────────────────┐
│  TARGET2 Crisis Simulation                        │
│  3 banks, 20 ticks/day, 25 days                  │
│                                                    │
│  Description: Three-phase crisis scenario with...  │
│  Features: [LSM] [Custom Events] [Multi-agent]    │
│                                                    │
│  ┌─ Agent Policies ───────────────────────────┐   │
│  │ BANK_A: [FIFO ▾]  [Browse Policies]        │   │
│  │ BANK_B: [FIFO ▾]  [Browse Policies]        │   │
│  │ BANK_C: [FIFO ▾]  [Browse Policies]        │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  ┌─ Optimization ─────────────────────────────┐   │
│  │ Mode: [Mock ▾]  (Mock / Real GPT-5.2)      │   │
│  │ Constraint Depth: [Simple ▾]               │   │
│  │ Interval: [Every day ▾]                     │   │
│  │ Max Days: [25]  Eval Samples: [1]           │   │
│  └────────────────────────────────────────────┘   │
│                                                    │
│              [ Launch Simulation ]                  │
└──────────────────────────────────────────────────┘
```

**GameConfigPanel.tsx** handles all configuration. It's reusable — can appear in LaunchView or as a sidebar in GameView.

## Phase 3: Navigation Flow

Tab structure becomes:
```
Home | Scenarios | Policies | [Active Game] | Docs
```

Flow:
1. **Home** → hero + quick start + my simulations
2. **Scenarios** → ScenarioLibraryView (browse/filter)
3. Click scenario → **LaunchView** (configure + launch)
4. Launch → **GameView** (existing, with game running)
5. **Policies** → PolicyLibraryView (browse, for reference)
6. **Docs** → DocsView (existing)

Back navigation: LaunchView → Scenarios, GameView → Home (with confirmation if game running).

### UI Test Protocol

```
Protocol: W1-UX-Flow
Wave: 1

1. Open app, sign in
2. VERIFY: Home page shows "Explore Scenarios" and "My Simulations"
3. Click "Explore Scenarios"
4. VERIFY: Scenario library loads with cards
5. Click a scenario
6. VERIFY: LaunchView shows scenario details + config panel
7. VERIFY: Agent list matches scenario agent count
8. Change a policy assignment for one agent
9. Set max days to 5
10. Click "Launch Simulation"
11. VERIFY: Game starts, GameView loads, correct agents shown
12. Step 1 day
13. VERIFY: Simulation runs correctly
14. Navigate back to Home
15. VERIFY: "My Simulations" shows the game just created
16. Click it
17. VERIFY: Game resumes where we left off

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] Landing page guides users to scenario library naturally
- [ ] LaunchView shows all configuration options
- [ ] Policy assignment per agent works
- [ ] Full flow: Home → Library → Launch → Game → Home works
- [ ] "My Simulations" shows saved games
- [ ] Quick start path works for impatient users
