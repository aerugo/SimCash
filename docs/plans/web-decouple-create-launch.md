# Decouple Scenario Editing from Launching + Terminology Cleanup

**Status**: Draft
**Date**: 2026-02-21
**Branch**: feature/interactive-web-sandbox
**Estimated effort**: ~3 hours (small-medium change)

## Goal

Separate scenario authoring (Create page) from experiment launching (Library), and unify all terminology around "rounds" instead of "days" for optimization iterations.

## Motivation

Currently the Create page mixes two concerns:
1. **Authoring** a scenario (defining agents, ticks, costs, events)
2. **Launching** an experiment (how many rounds, eval samples, AI mode)

This creates confusion because:
- "Game Settings" on the Create page duplicates "Launch Configuration" in the Library
- "Number of Days" (scenario physics) vs "Max Days"/"Max Repetitions" (optimization rounds) are confusingly similar
- Users can "Save & Launch" from Create but also launch from Library — two paths, different UIs

## Design

### Create page = authoring only
- Remove the Game Settings panel entirely
- Remove "Save & Launch" button
- Keep: Validate, Save, Update (for edit mode)
- After saving, show success message with link to Library to launch

### Library = the only place to launch
- Library already has a full Launch Configuration panel on scenario detail
- This becomes the single source of truth for launch settings
- Custom scenarios ("My Scenarios") are launchable from here like any other

### Terminology: "Rounds" everywhere
- All references to optimization iterations use "Rounds", never "Days" or "Repetitions"
- Scenario's `num_days` stays as "Days" — correctly refers to simulated business days
- Clear helper text distinguishing the two concepts

## Files

### Modified
| File | Changes |
|------|---------|
| `web/frontend/src/views/ScenarioEditorView.tsx` | Remove Game Settings panel, remove "Save & Launch" button, add post-save link to Library |
| `web/frontend/src/components/GameSettingsPanel.tsx` | Rename "Max Repetitions" → "Rounds", interval labels "Every round" / "Every N rounds" |
| `web/frontend/src/views/ScenarioLibraryView.tsx` | Rename "Max Days" → "Rounds", default to 10, fix hardcoded dark-mode classes to CSS vars, rename optimization interval labels |
| `web/frontend/src/views/HomeView.tsx` | Update tutorial launcher if it references Game Settings |
| `web/frontend/src/views/ScenarioEditorView.tsx` | Add helper text on "Number of Days": "Simulated business days per round" |

### NOT Modified
| File | Why |
|------|-----|
| Backend / API | `max_days` field name kept for compatibility; it's just a label issue |
| `simulator/` | Never touch the engine |

## Detailed Changes

### 1. ScenarioEditorView.tsx — Remove launch concerns

**Remove:**
- `GameSettingsPanel` import and usage
- `gameSettings` / `setGameSettings` state
- `saveAndLaunch` function
- "Save & Launch" button

**Keep:**
- Validate button
- Save button (for new scenarios)
- Update button (for editing existing)

**Add:**
- After successful save: toast/banner with "Scenario saved! [View in Library →]" link to `/library/scenarios` with My Scenarios tab active

### 2. GameSettingsPanel.tsx — Terminology only

This component is still used by `ScenarioLibraryView` (embedded in the launch config area), so keep it but fix labels:

- "Max Repetitions" → **"Rounds"**
- Slider helper: "How many times to run the scenario with AI optimization"
- "Evaluation Samples" — keep as-is (clear enough)
- Optimization Interval options:
  - "Every day (1)" → **"Every round"**
  - "Every 2 days" → **"Every 2 rounds"**
  - "Every 3 days" → **"Every 3 rounds"**
  - "Every 5 days" → **"Every 5 rounds"**
  - "Every 10 days" → **"Every 10 rounds"**
- Interval label: "Optimization Interval" → **"Optimize Every"**
- Interval helper: "How many rounds to run before the AI re-evaluates its policy"

### 3. ScenarioLibraryView.tsx — Terminology + styling

The Library launch panel currently has its own inline launch config (not using `GameSettingsPanel`). Two options:

**Option A**: Replace inline config with `GameSettingsPanel` component (DRY)
**Option B**: Just fix the labels inline

Recommend **Option A** — less code, single source of truth for launch settings.

Also:
- "Max Days" → **"Rounds"**
- Default: 10 (reasonable for most scenarios)
- Fix hardcoded `bg-slate-900`, `border-slate-700`, `text-slate-200` → CSS variables
- "Optimization Schedule" (every_round vs every_scenario_day): hide behind "Advanced" or keep as-is since it only shows for multi-day scenarios

### 4. ScenarioEditorView.tsx — Helper text

On the "Number of Days" field in the scenario form:
- Add helper: "Simulated business days per round. Optimization happens between rounds, not during days."

### 5. HomeView.tsx — Tutorial launcher

The tutorial launcher currently passes `max_days: 5`. This is fine — it goes directly to a game, not through the Create page. No change needed except updating the internal comment.

## Verification

```bash
cd web/frontend && npx tsc -b && npm run build
```

### UI Test Protocol

```
Protocol: Create/Launch Decoupling

1. Open https://simcash-487714.web.app
2. Navigate to Create → Scenario
3. VERIFY: No "Game Settings" panel visible
4. VERIFY: No "Save & Launch" button — only "Validate", "Save" (or "Update" in edit mode)
5. Fill in a scenario, click Validate, click Save
6. VERIFY: Success message with link to Library
7. Navigate to Library → Scenarios → My Scenarios
8. VERIFY: Saved scenario appears
9. Click on it to open detail
10. VERIFY: Launch Configuration shows "Rounds" (not "Max Days")
11. VERIFY: Optimization Interval says "Every round", "Every 2 rounds", etc.
12. Set Rounds=3, click Launch
13. VERIFY: Experiment starts, shows "Round 1/3"

Protocol: Terminology Consistency
1. Search entire UI for the word "days" in context of optimization
2. VERIFY: Only appears as "Number of Days" (scenario physics) or "Business days"
3. VERIFY: All optimization-related labels use "rounds"
```

## Success Criteria

- [ ] Create page has no launch-related settings
- [ ] Create page has no "Save & Launch" button
- [ ] Post-save shows link to Library
- [ ] Library launch config uses "Rounds" throughout
- [ ] Optimization interval uses "Every N rounds"
- [ ] "Number of Days" has helper text clarifying it's simulated business days
- [ ] Frontend builds clean
- [ ] Tutorial launcher still works
- [ ] Edit mode still works (Validate + Update)
