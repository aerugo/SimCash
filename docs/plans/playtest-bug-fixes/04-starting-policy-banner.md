# Bug Fix: Static "fraction = 1.000" Banner Text

## Problem

The Game View's "Ready to Start" panel always shows:
> All agents start with **fraction = 1.000** (commit 100% of their pool)

Even when custom starting policies with different fractions are applied (e.g., BANK_A=0.30, BANK_C=0.35, BANK_D=0.70).

## Root Cause

The banner text is hardcoded in `GameView.tsx`. It doesn't read from the game state's current policies.

## Fix

### Phase 1: Dynamic banner text

**File: `web/frontend/src/views/GameView.tsx`**

Find the static text and replace with dynamic content from the game state:

```typescript
// Before:
<p>All agents start with <strong>fraction = 1.000</strong> ...</p>

// After:
{(() => {
  const policies = gameState.current_policies;
  const fractions = Object.entries(policies).map(([aid, p]) => p.initial_liquidity_fraction);
  const allSame = fractions.every(f => f === fractions[0]);
  if (allSame) {
    return <p>All agents start with <strong>fraction = {fractions[0].toFixed(3)}</strong> ...</p>;
  }
  return (
    <p>Agents start with different fractions: {Object.entries(policies).map(([aid, p]) =>
      <span key={aid}>{aid}: <strong>{p.initial_liquidity_fraction.toFixed(3)}</strong></span>
    ).reduce((prev, curr) => [prev, ', ', curr])}</p>
  );
})()}
```

### Phase 2: Conditional helper text

When fractions differ, show:
> "Agents start with custom policies. The optimizer will refine these over multiple days."

When all same (default):
> "All agents start with **fraction = X.XXX** (commit X% of their pool). The optimizer will learn to reduce this over multiple days."

## Tests

- Launch with all default FIFO → banner shows "All agents start with fraction = 1.000"
- Launch with custom starting policies → banner lists per-agent fractions
- Launch with "Apply to all" same policy → banner shows single fraction

## Scope

- **Files**: 1 frontend (GameView.tsx)
- **Effort**: 10 minutes
- **Risk**: Minimal — display-only change
