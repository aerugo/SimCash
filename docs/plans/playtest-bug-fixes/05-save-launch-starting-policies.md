# Feature: Starting Policies in Scenario Editor Save & Launch

## Problem

The Scenario Editor's "Save & Launch" button creates a game with default FIFO policies. There's no way to set starting policies or enable LLM optimization from the Create tab — those controls only exist on the Setup → Multi-Day Game tab.

## Design

### Option A: Add controls to Scenario Editor (recommended)

Add a collapsible "Game Settings" section between Validate/Save & Launch buttons and the event timeline:

```
[✅ Validate] [🚀 Save & Launch]

▶ Game Settings (optional)
  Max Days: [=====|---] 5
  ☑ Enable AI Optimization   ☐ Mock Mode
  Policy Complexity: [Full ▾]
  
  ▶ Starting Policies (optional)
    (same per-agent dropdown + fraction slider as Setup tab)
```

This reuses the same components from HomeView.tsx. Agent IDs are derived from the YAML (already parsed for validation).

### Option B: "Open in Setup" button

Instead of duplicating controls, add a button that takes the custom scenario to the Setup tab's Multi-Day Game view where all controls already exist. This avoids duplication but adds a navigation step.

**Recommendation: Option A** — researchers expect to configure and launch from one place.

## Implementation

### Phase 1: Extract shared components

**New file: `web/frontend/src/components/GameSettingsPanel.tsx`**

Extract the game settings (max days, eval samples, optimization interval, constraint preset, mock mode, starting policies) from `HomeView.tsx` into a reusable component:

```typescript
interface GameSettingsPanelProps {
  agentIds: string[];
  policyLibrary: LibraryPolicy[];
  policyDetails: Record<string, string>;
  onSettingsChange: (settings: GameSettings) => void;
}
```

### Phase 2: Wire into Scenario Editor

**File: `web/frontend/src/views/ScenarioEditorView.tsx`**

Add `<GameSettingsPanel>` below the Validate button. On "Save & Launch", include the game settings in the launch payload.

### Phase 3: Update Save & Launch handler

Currently `handleSaveAndLaunch` in `ScenarioEditorView.tsx` calls `onGameLaunch` with just the YAML. Update to also pass game settings (max_days, use_llm, mock_reasoning, starting_policies, etc.).

## Tests

- GameSettingsPanel renders with correct agent IDs from YAML
- Starting policy dropdowns show library policies with fractions
- Save & Launch sends starting policies in the payload
- Game starts with correct fractions from Scenario Editor

## Scope

- **Files**: 1 new component, 2 modified (ScenarioEditorView, HomeView refactor)
- **Effort**: 1-2 hours
- **Risk**: Medium — refactoring HomeView, but no engine changes
