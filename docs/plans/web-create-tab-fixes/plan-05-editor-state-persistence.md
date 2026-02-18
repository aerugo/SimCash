# Plan 05: Editor State Persistence Across Tab Switches

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox
**Priority**: P3

## Goal

Preserve Scenario Editor and Policy Editor state when the user navigates to other tabs and back. Currently, all editor state (YAML, name, description, validation results) resets to defaults on tab switch.

## Problem

A researcher writes a complex scenario YAML, adds events, fills in the name and description, then clicks "Scenarios" to check something — when they return to Create, everything is gone. This is frustrating and wastes work.

## Files

### Modified

| File | Changes |
|------|---------|
| `web/frontend/src/App.tsx` | Lift editor state to App level. Store `{scenarioYaml, scenarioName, scenarioDesc, policyJson}` in App state. Pass as props + callbacks to editor views. |
| `web/frontend/src/views/ScenarioEditorView.tsx` | Accept initial state as props. Call parent callbacks on state change. |
| `web/frontend/src/views/PolicyEditorView.tsx` | Accept initial state as props. Call parent callbacks on state change. |

### NOT Modified

| File | Why |
|------|-----|
| Backend | This is purely frontend state management |

## Phase 1: Lift State to App

**Est. Time**: 1.5h

### Frontend

1. **In `App.tsx`**, add state:
   ```typescript
   const [scenarioEditorState, setScenarioEditorState] = useState({
     yaml: BLANK_TEMPLATE,
     name: 'My Scenario',
     description: '',
   });
   const [policyEditorState, setPolicyEditorState] = useState({
     jsonText: JSON.stringify(DEFAULT_POLICY, null, 2),
   });
   ```

2. **Pass to editor views**:
   ```tsx
   <ScenarioEditorView
     initialState={scenarioEditorState}
     onStateChange={setScenarioEditorState}
     onGameLaunch={handleGameLaunch}
   />
   ```

3. **In `ScenarioEditorView.tsx`**, accept props:
   ```typescript
   interface Props {
     initialState?: { yaml: string; name: string; description: string };
     onStateChange?: (state: { yaml: string; name: string; description: string }) => void;
     onGameLaunch?: (config: GameSetupConfig) => void;
   }
   ```
   Initialize from `initialState`. Call `onStateChange` on every change (debounced if needed).

4. Same pattern for `PolicyEditorView.tsx`.

### Tests

**Frontend only** — `npx tsc -b && npm run build`

### UI Test Protocol

```
Protocol: Editor State Persistence
Wave: Create Tab Fixes

1. Open http://localhost:5173
2. Click Create → Scenario
3. Change scenario name to "My Test Scenario"
4. Edit YAML (change ticks_per_day to 20)
5. Click Setup tab
6. Click Create → Scenario tab
7. VERIFY: Name is "My Test Scenario", YAML shows ticks_per_day: 20
8. Click Create → Policy
9. Load "Smart Splitter" template
10. Click Setup tab
11. Click Create → Policy
12. VERIFY: Policy JSON shows smart_splitter policy

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] Frontend compiles clean
- [ ] Frontend builds successfully
- [ ] Scenario editor state survives tab round-trip
- [ ] Policy editor state survives tab round-trip
- [ ] UI test protocol passes
