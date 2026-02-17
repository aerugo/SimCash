# Phase 1: Restyle Mock Label

**Status**: Pending

## Objective

Replace plain "mock" text with a subtle gray pill badge with hover tooltip.

## Invariants

- INV-UI-12: Mock indicator still present

## TDD Steps

### Step 1.1: RED — Write Failing Test

Add to `web/frontend/src/__tests__/GameView.reasoning.test.tsx`:

```tsx
it('renders mock indicator as a badge with tooltip', () => {
  const state = makeState();
  render(<GameView gameId="test" gameState={state} onUpdate={vi.fn()} onReset={vi.fn()} />);

  // Should have a title attribute explaining mock mode
  const mockBadge = screen.getByTitle(/mock mode/i);
  expect(mockBadge).toBeInTheDocument();
  expect(mockBadge.textContent).toBe('M');
});
```

### Step 1.2: GREEN — Implement

In `GameView.tsx`, replace all instances of:

```tsx
{latest.mock && <span className="text-[10px] text-slate-600">mock</span>}
```

With:

```tsx
{latest.mock && (
  <span
    title="Mock mode — reasoning generated without API call"
    className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-700 text-[8px] text-slate-500 font-bold cursor-help"
  >
    M
  </span>
)}
```

Apply the same change in the `PolicyHistoryPanel` component:

```tsx
// Before:
{r.mock && <span className="text-slate-600">mock</span>}

// After:
{r.mock && (
  <span
    title="Mock mode — reasoning generated without API call"
    className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-slate-700 text-[7px] text-slate-500 font-bold cursor-help"
  >
    M
  </span>
)}
```

### Step 1.3: REFACTOR

Extract mock badge to a tiny `MockBadge` component:

```tsx
function MockBadge({ size = 'sm' }: { size?: 'sm' | 'xs' }) {
  const cls = size === 'sm'
    ? 'w-4 h-4 text-[8px]'
    : 'w-3.5 h-3.5 text-[7px]';
  return (
    <span
      title="Mock mode — reasoning generated without API call"
      className={`inline-flex items-center justify-center rounded-full bg-slate-700 text-slate-500 font-bold cursor-help ${cls}`}
    >
      M
    </span>
  );
}
```

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/GameView.tsx` | Modify — restyle mock labels (2 locations) |
| `web/frontend/src/__tests__/GameView.reasoning.test.tsx` | Modify — badge test |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/GameView.reasoning.test.tsx
```

## Completion Criteria

- [ ] "mock" text replaced with small gray pill "M"
- [ ] Pill has tooltip explaining mock mode
- [ ] Both reasoning section and policy history updated
- [ ] Tests pass
