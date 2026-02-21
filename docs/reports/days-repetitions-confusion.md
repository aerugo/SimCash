# Days vs Repetitions: Terminology Confusion Report

**Date**: 2026-02-21
**Author**: Nash
**Status**: Investigation complete, proposal ready

## The Problem

Users encounter the term "days" in three different contexts with three different meanings, and the relationship between them is unclear:

### Context 1: Scenario Definition (`num_days` in YAML)
- **Where**: Scenario Editor → Simulation → "Number of Days"
- **What it means**: How many simulated business days the engine runs per scenario execution. A 3-day scenario with 12 ticks/day = 36 ticks total.
- **Example**: The crisis scenario has `num_days: 10` — the crisis unfolds over 10 simulated business days.

### Context 2: Game Settings (`max_days` / "Max Repetitions")
- **Where**: Game Settings panel in Create page, and Launch Configuration in Library
- **What it means**: How many optimization rounds (iterations) the AI agent gets to improve its policy. Each "round" runs the entire scenario once with the current policy, tallies costs, then optimizes.
- **Current label in Create page**: "Max Repetitions" (recently renamed from "Max Days")
- **Current label in Library launch**: Still "Max Days"

### Context 3: Optimization Interval
- **Where**: Game Settings panel
- **What it means**: How many rounds between AI optimization steps. At interval=1, the AI optimizes after every round. At interval=5, it runs 5 rounds before proposing a change.
- **Options**: "Every day (1)", "Every 2 days", "Every 3 days", etc.
- **Problem**: Uses "days" terminology, confusing with scenario days.

## Current Code Architecture

```
Scenario YAML:
  simulation.num_days = N     → Engine runs N business days per execution
  simulation.ticks_per_day = T → T ticks per business day

Game Settings (launch-time):
  max_days = M                → M optimization rounds total
  optimization_interval = I   → Optimize every I rounds
  num_eval_samples = S        → S bootstrap samples per evaluation
```

So if you have a 3-day scenario with max_days=10 and optimization_interval=2:
- The engine runs 3 business days (36 ticks) per round
- There are 10 rounds total
- The AI optimizes after rounds 2, 4, 6, 8, 10 (5 optimization steps)

## Where the Confusion Manifests

| Surface | Label | Actual Meaning | User Likely Thinks |
|---------|-------|----------------|-------------------|
| Scenario Editor | "Number of Days" | Simulated business days in scenario | ✅ Clear |
| Create → Game Settings | "Max Repetitions" | Optimization rounds | ⚠️ Better after rename, but relationship to scenario days unclear |
| Library → Launch Config | "Max Days" | Optimization rounds | ❌ Confused with scenario days |
| Game Settings | "Every day (1)" | Every round | ❌ "day" = round? scenario day? |
| Game Settings | "Every 2 days" | Every 2 rounds | ❌ Same confusion |
| Experiment view | "Round 5/10" | Optimization round 5 of 10 | ✅ Clear (uses "round") |

**Additional confusion**: There's a separate `optimization_schedule` parameter (`every_round` vs `every_scenario_day`) for multi-day scenarios where optimization can happen between scenario days rather than between full scenario executions. This is a power-user feature that makes the "days" terminology even more ambiguous.

## Proposal: Unified Terminology

### Principle: Three distinct concepts, three distinct words

| Concept | Proposed Term | Definition |
|---------|--------------|------------|
| Simulated business days in scenario | **Days** | How many business days the engine simulates per run. Defined in the scenario YAML. |
| Optimization iterations | **Rounds** | How many times the scenario is run with (potentially) updated policies. The AI optimizes between rounds. |
| Ticks per day | **Ticks** | The time granularity within a business day. |

### Specific Changes

#### 1. Library Launch Configuration (ScenarioLibraryView.tsx)
- "Max Days" → **"Rounds"**
- Default: 1 (matching the Create page default)
- Helper text: "Number of optimization rounds — the scenario runs once per round"

#### 2. Game Settings Panel (GameSettingsPanel.tsx)
- Already renamed to "Max Repetitions" → change to **"Rounds"** for consistency
- Optimization Interval options: "Every day (1)" → **"Every round"**, "Every 2 days" → **"Every 2 rounds"**, etc.
- Label: "Optimization Interval" → **"Optimize Every"**
- Helper text: "How many rounds between AI policy updates"

#### 3. Backend field names (non-breaking)
- Keep `max_days` in the API/backend (renaming would break checkpoints)
- Add comment: `# "max_days" is legacy naming; represents optimization rounds`

#### 4. Scenario Editor
- "Number of Days" stays as-is — this correctly refers to simulated business days
- Consider adding helper text: "Business days simulated per round"

#### 5. Experiment View
- Already uses "Round X/Y" — ✅ no change needed

#### 6. Remove `optimization_schedule` from default UI
- The `every_round` vs `every_scenario_day` distinction is confusing for most users
- Hide behind an "Advanced" toggle if kept at all
- Default: `every_round` (optimize between full scenario runs)

### Implementation Estimate

This is a **small change** (< 2 hours) — purely UI label/text updates:

| File | Change |
|------|--------|
| `GameSettingsPanel.tsx` | "Max Repetitions" → "Rounds", interval labels |
| `ScenarioLibraryView.tsx` | "Max Days" → "Rounds", default 1, helper text |
| `ScenarioEditorView.tsx` | Add helper text on "Number of Days" |
| `HomeView.tsx` | Update tutorial config if needed |

No backend changes. No API changes. No data migration.
