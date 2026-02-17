# SimCash Platform Expansion — Master Plan

**Date**: 2026-02-17  
**Author**: Nash  
**Status**: Draft  
**Based on**: 7 investigation reports in `docs/reports/new-scope/`

---

## The Core Problem

The SimCash web platform currently exposes a narrow slice of an extremely powerful system:

- **Engine**: 16 action types, 140+ context fields, 4 independent decision trees, 80+ context fields, state registers, LSM algorithms, priority systems, custom events, collateral management
- **Web UI**: "Pick a preset, watch agents tune one float"

The LLM optimization system is a general-purpose policy tree optimizer being used as a scalar parameter tuner. The scenario system supports crisis simulations, multi-phase events, asymmetric agents, and complex cost structures — none of which are accessible from the web.

This plan addresses 6 areas for expansion.

---

## 1. Advanced Scenarios

### Current State
The web has 6 hardcoded scenarios in `scenario_pack.py` — all 2-5 agent variations with simple cost structures. None use custom events, LSM, credit limits, or priority escalation.

### What Exists in the Engine
11 example configs in `examples/configs/` covering:
- **Crisis scenarios**: `target2_crisis_25day.yaml` — 3 phases (normal→shock→recovery) with DirectTransfer events draining liquidity
- **LSM scenarios**: `bis_liquidity_delay_tradeoff.yaml` — bilateral offsetting + cycle detection
- **Complex cost structures**: Different rates per experiment, deadline penalties, EOD penalties
- **Multi-agent asymmetry**: Different policies, arrival rates, and credit limits per agent
- **Custom events**: 7 event types including CollateralAdjustment, GlobalArrivalRateChange, DeadlineWindowChange

### Plan

**Phase 1: Scenario Library Backend**
- Create `/api/scenarios/library` endpoint serving scenarios from `examples/configs/` + paper configs
- Each scenario gets metadata: name, description, tags (crisis/LSM/simple/stochastic), difficulty, num_agents, features_used
- Validate scenarios via `SimulationConfig.from_dict()` before adding to library
- Categories: "Paper Experiments", "Crisis & Stress", "LSM Exploration", "Custom"

**Phase 2: Scenario Editor**
- YAML editor in the web UI with live validation
- Start from template or existing scenario
- Validation feedback: "This scenario uses LSM bilateral offsetting" / "Warning: 25 days × 5 agents will be slow"
- Save custom scenarios to user's storage (GCS)

**Phase 3: Scenario Event Builder**
- Visual timeline showing event scheduling
- Drag events onto ticks: liquidity shocks, rate changes, deadline changes
- Preview: "At tick 15, BANK_A loses 500,000 in collateral"

### Key Scenarios to Add Immediately
1. **TARGET2 Crisis** — 3-phase with liquidity drain events
2. **BIS Liquidity-Delay Tradeoff** — LSM bilateral + cycle detection
3. **Advanced Policy Crisis** — heterogeneous agents with different strategies
4. **Credit Limit Stress** — agents hitting bilateral/multilateral limits
5. **Priority Escalation** — deadline-driven priority changes

---

## 2. Advanced Policies

### Current State
The web creates policies with only `initial_liquidity_fraction` + trivial Release-all payment tree. The LLM is told to focus on this single float.

### What Exists in the Engine
30+ policy JSON files including:
- `sophisticated_adaptive_bank.json` — 4-tree policy with bank budgets, state registers, cooldowns
- `target2_priority_escalator.json` — priority-aware with RTGS priority management
- `smart_splitter.json` — intelligent payment splitting
- `memory_driven_strategist.json` — state register driven cross-tick memory

16 action types, 12 computation operators, 140+ context fields, 10 state registers per agent.

### Plan

**Phase 1: Policy Library**
- Serve built-in policies from `simulator/policies/` via `/api/policies/library`
- Each policy gets metadata: name, description, complexity level, trees used, actions used
- Users can browse, preview (tree visualization), and assign policies to agents
- Categories: "Simple", "Adaptive", "Crisis-Resilient", "TARGET2-Aligned"

**Phase 2: Policy Viewer**
- Render policy decision trees as visual flowcharts
- Show condition nodes with their expressions
- Show action nodes with their parameters  
- Highlight the evaluation path for a given context (replay mode)
- Side-by-side comparison of two policies

**Phase 3: Policy Editor**
- JSON editor with schema validation + autocomplete
- Visual tree builder (drag condition/action nodes)
- Field picker showing all 140+ available context fields with descriptions
- Action picker showing available actions per tree type
- Parameter editor with type constraints
- "Test this policy" button — run a quick simulation

**Phase 4: Full LLM Policy Optimization**
- Remove the "focus on initial_liquidity_fraction" constraint
- Allow users to configure which parameters, fields, and actions the LLM can use
- Constraint presets: "Simple (liquidity only)", "Standard (Release/Hold/Split)", "Full (all actions)"
- Show the LLM's decision tree evolution across days — not just the fraction

---

## 3. UX Restructure: Scenario-First Flow

### Current State
Landing page shows preset buttons → click → simulation starts. No browsing, no context, no progression.

### Proposed Flow

```
Landing Page
├── "Explore Scenarios" → Scenario Library
│   ├── Paper Experiments (exp1, exp2, exp3)
│   ├── Crisis & Stress Testing
│   ├── LSM Exploration
│   ├── Custom (user-created)
│   └── Each card shows: description, agents, ticks, features, difficulty
│       └── Click → Scenario Detail Page
│           ├── Full description + what to look for
│           ├── Choose policy mode: Manual / AI-Optimized / Built-in Policy
│           ├── Choose optimization depth: Simple (1 param) / Standard / Full
│           ├── Configure: days, eval samples, seed
│           └── "Launch Simulation" → Game View
│
├── "Build Your Own" → Scenario Editor
│   ├── Start from template or blank
│   ├── YAML editor with validation
│   ├── Event timeline builder
│   └── "Validate & Launch"
│
└── "My Simulations" → Saved Games
    ├── Resume in-progress games
    ├── View completed results
    └── Download DuckDB files
```

### Key UX Principles
- **Scenario-first**: The scenario is the research question. Policy is the answer.
- **Progressive disclosure**: Simple mode hides complexity. Advanced mode reveals everything.
- **Context-rich**: Each scenario explains what it tests and what to watch for.
- **No dead ends**: Every scenario can be modified, every policy can be edited.

---

## 4. Policy Version Display

### Current State
The web shows "Day N" results and LLM reasoning text, but doesn't clearly show how the policy evolved structurally across days.

### Plan

**Policy Evolution Timeline**
- Visual timeline showing policy versions across days
- Each day shows: parameter values, tree structure hash, change summary
- Click a day → see full policy JSON + diff from previous day
- Color-coded: 🟢 accepted, 🔴 rejected, ⭐ best so far

**Policy Diff View**
- Side-by-side comparison of day N vs day N-1
- Highlight changed nodes, parameters, conditions
- Show WHY it changed (link to LLM reasoning)

**Policy Tree Visualization**
- Render the current policy as a flowchart
- Animate: show which path was taken for each payment in the last day
- Stats overlay: "This branch was taken 45% of the time"

**Parameter Trajectory Charts**
- Already in the LLM prompt system (`parameter_trajectories`) — surface in UI
- Line chart of each parameter over days
- Mark accepted/rejected iterations

---

## 5. Optimization Interval Configuration

### Current State
Optimization happens every day (after every N ticks). This is hardcoded.

### What's Possible
The engine supports multi-day runs with configurable seeds per day. The optimization can happen at any interval.

### Plan

**Configurable Optimization Frequency**
```
Optimization interval: [Every day ▾]
  - Every day (after each N-tick simulation)
  - Every 2 days
  - Every 5 days  
  - Every N days (custom)
  - Manual (user triggers optimization)
```

**Why This Matters**
- **Every day**: Fast iteration, policy changes frequently, may not converge
- **Every 5 days**: More data per evaluation, more stable policies, slower convergence
- **Manual**: Researcher controls when to optimize — useful for studying policy stability
- **Different intervals per agent**: "BANK_A optimizes daily, BANK_B optimizes weekly" — asymmetric adaptation speed

**Implementation**
- `Game` class gets `optimization_interval: int` parameter
- `run_day()` only calls optimization when `day_num % interval == 0`
- Between optimization days, agents play with their current policy (gathering more data)
- Bootstrap evaluation uses all days since last optimization (more samples)

**Advanced: Event-Triggered Optimization**
- Optimize after a crisis event ("the market just crashed, rethink your strategy")
- Optimize when cost exceeds threshold ("you're bleeding money, adapt")
- This maps to how real treasury departments work — they don't optimize on a fixed schedule

---

## 6. Expanded Documentation

### Current State
`DocsView.tsx` has 720 lines covering basic concepts. Focused on the paper's exp2 case.

### What Needs Covering

**Tier 1: Core Concepts** (existing, needs expansion)
- What is SimCash (broaden beyond "2 banks tuning a fraction")
- RTGS, LSM, queuing — good, keep
- Cost model — needs all 7 cost types documented
- Game theory — needs the Prisoner's Dilemma / Stag Hunt framing from concept doc

**Tier 2: Scenarios** (new)
- What is a scenario and what can it configure
- Scenario parameter reference (all fields from the YAML schema)
- Payment generation modes (deterministic, Poisson, LogNormal, custom)
- Custom events: types, scheduling, examples
- Scenario design guide: "How to create a crisis scenario"
- Scenario library walkthrough

**Tier 3: Policies** (new)
- What is a policy tree and how does it work
- The 4 tree types and when they're evaluated
- All 16 actions with descriptions and use cases
- All 140+ context fields organized by category
- Expression system: comparisons, arithmetic, parameters
- State registers: cross-tick memory
- Policy design patterns: "The Cautious Banker", "The Aggressive Market Maker"
- Policy cookbook: common patterns with code examples

**Tier 4: LLM Optimization** (new)
- How LLM optimization works (the loop)
- Constraint configuration: what you allow the LLM to do
- Bootstrap evaluation explained
- Multi-agent isolation and Nash equilibrium
- Convergence: what it means and when to expect it
- Advanced: tuning optimization parameters

**Tier 5: Research Guides** (new)
- "Replicating Castro et al. (2025)" — step by step
- "Designing a stress test" — crisis events + policy resilience
- "Exploring LSM effectiveness" — bilateral vs multilateral offsetting
- "Finding Nash equilibria" — multi-agent convergence dynamics
- "Building a custom experiment" — end to end

### Implementation
- Keep `DocsView.tsx` but restructure as a table of contents linking to sections
- Each section is collapsible or paginated
- Add search
- Add code examples (YAML for scenarios, JSON for policies)
- Add diagrams where useful (policy tree flowcharts, settlement flow)

---

## Implementation Priority

### Wave 1: Foundation (1-2 weeks)
1. **Scenario Library backend** — serve existing configs with metadata
2. **Policy Library backend** — serve existing policies with metadata
3. **Scenario Library UI** — browsable cards, filters, detail pages
4. **Restructured landing page** — scenario-first flow

### Wave 2: Visibility (1 week)
5. **Policy version timeline** — show policy evolution across days
6. **Parameter trajectory charts** — surface existing data in UI
7. **Policy diff view** — compare day-to-day changes
8. **Expanded docs: Tiers 1-2** — scenarios + core concepts

### Wave 3: Power Features (1-2 weeks)
9. **Optimization interval config** — configurable frequency
10. **Wider LLM constraints** — allow full decision tree optimization
11. **Policy viewer** — render trees as flowcharts
12. **Expanded docs: Tiers 3-4** — policies + optimization

### Wave 4: Creation Tools (2-3 weeks)
13. **Scenario editor** — YAML with validation
14. **Event timeline builder** — visual event scheduling
15. **Policy editor** — JSON with schema autocomplete
16. **Expanded docs: Tier 5** — research guides

---

## Testing & Verification Strategy

Every wave ships with three layers of verification: automated tests, integration tests, and UI testing protocols. Nothing is "done" until all three pass.

### Layer 1: Automated Tests (CI-grade, run on every commit)

**Backend unit tests** (pytest, mocked engine where needed):

| Wave | Tests | What They Verify |
|------|-------|-----------------|
| 1 | Scenario library: all 11 example configs load via `SimulationConfig.from_dict()` without error | Engine accepts every scenario we serve |
| 1 | Scenario library: metadata (name, tags, num_agents) matches actual config content | No stale/wrong metadata |
| 1 | Policy library: all 30+ policy JSONs parse via `TreePolicy::from_json()` (through FFI) | Every policy we serve is engine-valid |
| 1 | Policy library: metadata matches actual policy structure (trees used, actions used) | No stale/wrong metadata |
| 1 | Scenario + policy cross-product: each scenario can run 1 tick with each compatible policy | No silent incompatibilities |
| 2 | Policy diff: given two policy JSONs, diff output correctly identifies changed nodes/params | Diff logic is accurate |
| 2 | Parameter trajectory: given a game with 5 days, trajectory data matches actual day-by-day values | No data loss in the pipeline |
| 3 | Optimization interval: game with interval=3 only optimizes on days 0, 3, 6... | Interval logic works |
| 3 | Wide constraints: LLM output with Split/Hold/conditions passes ConstraintValidator | Validation accepts what we allow |
| 3 | Wide constraints: LLM output with disallowed actions is rejected | Validation rejects what we forbid |
| 4 | Scenario editor: valid YAML → passes validation, invalid YAML → clear error message | Editor validation works |
| 4 | Custom events: scenario with DirectTransfer event at tick 5 → balance changes at tick 5 | Events actually fire |
| 4 | Policy editor: valid JSON → passes TreePolicy validation, invalid → clear error | Editor validation works |

**Frontend type checks** (TypeScript strict, run on every commit):
- `tsc -b` must pass with zero errors
- All new types for scenario metadata, policy metadata, policy diffs must be properly typed

**Determinism regression**:
- Run each library scenario with seed 42 for 1 day, record total costs per agent
- Store as golden values in `web/backend/tests/golden/`
- Any change to golden values = either a bug or an intentional engine change (must be reviewed)

### Layer 2: Integration Tests (slower, run before deploy)

These use the real Rust engine (not mocked) and test the full FastAPI → engine → response pipeline:

| Wave | Test | What It Proves |
|------|------|---------------|
| 1 | Create game from every library scenario, step 1 day, verify response has correct agent count and non-zero costs | Full pipeline works for all scenarios |
| 1 | Create game with a library policy assigned to agents, step 1 day, verify policy was actually used (not FIFO fallback) | Policy assignment actually enters the engine |
| 2 | Run 5-day game, verify `/api/games/{id}` response includes policy versions for each day | Policy history is persisted |
| 3 | Run game with interval=2, verify day 1 has no optimization step, day 2 does | Interval controls optimization |
| 3 | Run game with wide constraints + real LLM (GPT-5.2), verify returned policy has conditions (not just Release-all) | LLM actually generates complex policies when allowed |
| 4 | POST custom scenario YAML → create game → step 1 day → verify events fired | Custom scenarios work end-to-end |
| 4 | POST custom scenario with invalid YAML → verify 400 with clear error | Validation catches bad input |

**Cost verification** (critical — "an economist would spot the seams"):
- For every library scenario, run 1 day and verify:
  - `sum(per_agent_costs) == total_cost` (no rounding drift)
  - All cost components are non-negative
  - If delay cost > 0, there must be held payments in the event log
  - If overdraft cost > 0, balance must have gone negative at some tick
  - If settlement rate < 100%, unsettled count must be > 0
  - Event count matches tick count × expected events per tick (roughly)

### Layer 3: UI Testing Protocols (manual + browser automation)

These are click-through protocols I execute using the browser tool after each wave ships. Each protocol has explicit pass/fail criteria.

#### Protocol W1-1: Scenario Library Navigation
```
1. Open https://simcash-997004209370.europe-north1.run.app
2. Sign in with Google
3. Navigate to Scenario Library
4. VERIFY: At least 10 scenarios visible with cards
5. VERIFY: Each card shows name, description, agent count, tick count, tags
6. Click a crisis scenario (e.g., TARGET2 Crisis)
7. VERIFY: Detail page shows full description, features used, cost parameters
8. Click "Launch Simulation"
9. VERIFY: Game starts, first day runs, events appear
10. VERIFY: Agent count matches scenario (e.g., 3 for TARGET2 Crisis, not 2)
```

#### Protocol W1-2: Policy Library Assignment
```
1. Navigate to Scenario Library → pick any scenario
2. Before launching, browse Policy Library
3. VERIFY: At least 15 policies visible
4. VERIFY: Each shows name, description, complexity, trees used
5. Assign different policies to different agents
6. Launch simulation, step 1 day
7. VERIFY: Agent reasoning/events differ between agents (not identical)
8. VERIFY: If policy uses Hold action, some payments should be held (not all released)
```

#### Protocol W1-3: Scenario-First UX Flow
```
1. Fresh page load (clear cache)
2. VERIFY: Landing page shows "Explore Scenarios" prominently (not just preset buttons)
3. Click through to a scenario → configure → launch
4. VERIFY: Flow feels natural, no dead ends, back buttons work
5. Try "Build Your Own" if available, or "My Simulations"
6. VERIFY: Saved games appear and can be resumed
```

#### Protocol W2-1: Policy Evolution Visibility
```
1. Create a game with AI optimization enabled, run 5 days
2. VERIFY: Policy timeline shows 5 versions
3. Click day 3 → VERIFY: full policy JSON visible
4. VERIFY: Diff between day 2 and day 3 highlights changes
5. VERIFY: Parameter trajectory chart shows values over 5 days
6. VERIFY: Accepted/rejected status marked per day
```

#### Protocol W2-2: Policy Diff Accuracy
```
1. Run a game where the LLM changes initial_liquidity_fraction
2. Open diff view between two days
3. VERIFY: Changed parameter is highlighted
4. VERIFY: Unchanged parts of the policy are NOT highlighted
5. If tree structure changed (conditions added/removed), VERIFY: structural diff is shown
```

#### Protocol W3-1: Optimization Interval
```
1. Create game with optimization_interval = 3
2. Step through days 0-6
3. VERIFY: Day 0 runs with default policy (no optimization before first day)
4. VERIFY: Days 1-2 show "Playing with current policy" (no LLM call)
5. VERIFY: Day 3 triggers optimization, reasoning panel shows LLM output
6. VERIFY: Days 4-5 play with day 3's policy
7. VERIFY: Day 6 triggers optimization again
```

#### Protocol W3-2: Complex Policy Optimization
```
1. Create game with wide constraint preset ("Standard" or "Full")
2. Enable real LLM, run 5 days
3. VERIFY: LLM produces policies with CONDITION NODES (not just Release-all)
4. VERIFY: Policy uses at least 2 different actions (e.g., Release + Hold)
5. VERIFY: Condition references valid context fields (balance, ticks_to_deadline)
6. VERIFY: Policy actually affects simulation (Hold actions → some payments delayed)
7. VERIFY: Cost changes across days (not flat line)
```

#### Protocol W3-3: The Economist Test
```
For each library scenario, run 3 days and check:
1. VERIFY: Costs make intuitive sense for the scenario parameters
2. VERIFY: Higher delay penalties → agents release earlier
3. VERIFY: Crisis events visibly impact costs (spike at event tick)
4. VERIFY: LSM scenarios show bilateral/multilateral offsets in event log
5. VERIFY: Priority escalation scenarios show priority changes near deadlines
6. VERIFY: No impossible states (negative costs, >100% settlement with unsettled payments, etc.)
```

#### Protocol W4-1: Scenario Editor
```
1. Open scenario editor
2. Paste a valid YAML → VERIFY: "Valid ✓" indicator
3. Modify num_agents to 7 → VERIFY: validation passes (or warns if too many)
4. Remove required field → VERIFY: clear error message
5. Add a DirectTransfer event at tick 10 → VERIFY: preview shows event
6. Launch simulation → VERIFY: event fires at tick 10 (visible in event log)
```

#### Protocol W4-2: Policy Editor
```
1. Open policy editor
2. Load an existing policy from library
3. Modify a condition threshold → VERIFY: validation passes
4. Add an invalid field reference → VERIFY: clear error
5. Save and assign to agent → run 1 day
6. VERIFY: modified policy is what the engine used (check events match expected behavior)
```

### Automation Strategy

- **Layer 1 + 2**: Run in CI via `pytest`. All must pass before deploy.
- **Layer 3**: I execute manually after each wave deploy using the browser tool. Results logged in `memory/ui-test-results-YYYY-MM-DD.md`.
- **Regression**: After each wave, re-run ALL previous wave protocols (not just the new wave's). This catches regressions.
- **Golden file updates**: When a protocol passes, snapshot key values (costs, event counts) as golden files. Future runs diff against golden.

### The Non-Negotiable Rule

**If a policy is displayed as "the agent decided to Hold payments" but the simulation settled them all via FIFO → that's a critical bug.** The test suite must verify that displayed policies are the policies the engine actually executed. This is tested by:
1. Assigning a Hold-heavy policy → verifying unsettled payments exist
2. Assigning a Split policy → verifying split events in the log
3. Comparing FIFO baseline costs vs policy costs → they must differ

---

## What This Unlocks

Today: "Watch two AI agents tune a single number in a simple 2-bank scenario."

Tomorrow: "Design a 5-bank crisis scenario with liquidity shocks at tick 15, assign different strategies to each bank, let the LLM optimize full decision trees with conditional payment release, splitting, priority escalation, and collateral management — then watch them converge to a Nash equilibrium over 25 simulated days."

The engine can already do this. The web just needs to let it.
