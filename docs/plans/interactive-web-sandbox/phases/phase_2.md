# Phase 2: Frontend Multi-Tab Layout + Home + Scenarios

**Status**: Pending
**Started**: —

## Objective

Replace the single-page layout with a tabbed interface. Build the Home (scenario selection + custom builder) and Scenario Library views.

## Implementation Steps

### Step 2.1: Tab Layout Component

Create `src/components/TabLayout.tsx`:
- Horizontal tab bar at top (below header)
- Tabs: 🏠 Home, 📊 Dashboard, 📋 Events, ⚙️ Config, 🔄 Replay, 📈 Analysis, 🎮 Scenarios
- Active tab highlighted with accent color
- Tab state managed in App.tsx
- Some tabs disabled until simulation is created (Dashboard, Events, Config, Replay, Analysis)

### Step 2.2: Refactor App.tsx

- Replace single-page layout with tab-driven rendering
- State: `activeTab`, `simId`, `simState`, etc.
- Render only the active tab's content
- Pass simulation data down to tab views as props

### Step 2.3: Home View

Create `src/views/HomeView.tsx`:
- Preset scenario cards (exp1, exp2, exp3) — click to select
- "Custom Scenario" card → opens scenario builder
- "Launch Simulation" button → creates sim, switches to Dashboard tab
- Show scenario summary after selection (ticks, agents, cost rates)

### Step 2.4: Scenario Builder Form

Create `src/views/ScenarioBuilder.tsx`:
- **Banks section**: Number of banks (2-8), name each, set liquidity pool (dollar input → cents)
- **Cost rates section**: Sliders for liquidity_cost_bps, delay_cost, eod_penalty, deadline_penalty
  - Visual constraint indicator: r_c < r_d < r_b
- **Payment schedule section**: Add/remove payments (sender, receiver, amount, tick, deadline)
  - Table with add/delete rows
- **Settings section**: ticks_per_day, num_days, rng_seed, deferred_crediting, LSM toggles
- **Import/Export**: JSON textarea for import/export
- **"Randomize"** button: fills form with random valid config
- **"Validate"** button: calls POST /api/scenarios/validate
- **"Save to Library"** button: calls POST /api/scenarios

### Step 2.5: Scenario Library View

Create `src/views/ScenariosView.tsx`:
- Grid of scenario cards (presets + custom)
- Each card shows: name, agent count, tick count, key cost rates
- Actions: Load (→ Home), Edit, Delete, Duplicate
- Create new button → opens builder

### Step 2.6: Extended API Client

Update `src/api.ts`:
- `getScenarios()`, `createScenario()`, `updateScenario()`, `deleteScenario()`
- `validateScenario()`
- `getSimConfig()`, `exportSim()`, `replayTick()`, `getSimEvents()`

Update `src/types.ts`:
- Scenario types, ScenarioConfig, validation response types

## Files

| File | Action |
|------|--------|
| `src/components/TabLayout.tsx` | CREATE |
| `src/views/HomeView.tsx` | CREATE |
| `src/views/ScenarioBuilder.tsx` | CREATE |
| `src/views/ScenariosView.tsx` | CREATE |
| `src/views/DashboardView.tsx` | CREATE (extract from App.tsx) |
| `src/App.tsx` | MODIFY — tab-driven layout |
| `src/api.ts` | MODIFY — add new API calls |
| `src/types.ts` | MODIFY — add new types |

## Completion Criteria
- [ ] Tab navigation works between all views
- [ ] Can select preset and launch simulation
- [ ] Can build custom scenario with form
- [ ] Scenario builder validates cost constraints
- [ ] Can save/load/delete custom scenarios
- [ ] Import/Export JSON works
- [ ] TypeScript builds without errors
