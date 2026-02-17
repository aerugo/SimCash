# Phase 2: Visual Indicator for Historical Reasoning

**Status**: Pending

## Objective

Add a visual cue when viewing historical (non-latest) reasoning so users know they're looking at a past day.

## Invariants

- INV-UI-4: Selected day controls display
- INV-UI-5: Latest day has no special indicator

## TDD Steps

### Step 2.1: RED — Write Failing Test

Add to `web/frontend/src/__tests__/GameView.reasoning.test.tsx`:

```tsx
it('shows "historical" badge when viewing a past day', () => {
  const state = makeState();
  render(<GameView gameId="test" gameState={state} onUpdate={vi.fn()} onReset={vi.fn()} />);

  // Click day 1 (index 0)
  const dayButtons = screen.getAllByRole('button').filter(b => b.textContent === '1');
  fireEvent.click(dayButtons[0]);

  expect(screen.getByText('Day 1 Reasoning')).toBeInTheDocument();
  // Should show a "viewing history" indicator
  expect(screen.getByText(/historical/i)).toBeInTheDocument();
});

it('does NOT show historical badge for latest day', () => {
  const state = makeState();
  render(<GameView gameId="test" gameState={state} onUpdate={vi.fn()} onReset={vi.fn()} />);

  // Click latest day (day 3, index 2)
  const dayButtons = screen.getAllByRole('button').filter(b => b.textContent === '3');
  fireEvent.click(dayButtons[0]);

  expect(screen.queryByText(/historical/i)).toBeNull();
});
```

### Step 2.2: GREEN — Implement

Add a small badge next to the section title:

```tsx
<h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
  🧠 {selectedDay !== null && selectedDay < gameState.days.length - 1
    ? `Day ${selectedDay + 1} Reasoning`
    : 'Latest Reasoning'}
  {selectedDay !== null && selectedDay < gameState.days.length - 1 && (
    <span className="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/20 text-amber-400 font-medium">
      historical
    </span>
  )}
</h3>
```

### Step 2.3: REFACTOR

Extract `isHistorical` boolean:
```tsx
const isHistorical = selectedDay !== null && selectedDay < gameState.days.length - 1;
```

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/GameView.tsx` | Modify — add historical badge |
| `web/frontend/src/__tests__/GameView.reasoning.test.tsx` | Modify — add badge tests |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/GameView.reasoning.test.tsx
```

## Completion Criteria

- [ ] Historical days show amber "historical" badge
- [ ] Latest day does not show badge
- [ ] Tests pass
