# Phase 1: Empty State Guidance Panel

**Status**: Pending

## Objective

Show helpful guidance when game has zero days simulated.

## Invariants

- INV-UI-11: Only when days.length === 0

## TDD Steps

### Step 1.1: RED — Write Failing Test

Create `web/frontend/src/__tests__/GameView.empty.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { GameView } from '../views/GameView';
import { vi, describe, it, expect } from 'vitest';

vi.mock('../hooks/useGameWebSocket', () => ({
  useGameWebSocket: (_id: string, initial: any) => ({
    gameState: initial,
    connected: true,
    phase: 'idle',
    optimizingAgent: null,
    simulatingDay: null,
    streamingText: {},
    step: vi.fn(),
    autoRun: vi.fn(),
    stop: vi.fn(),
  }),
}));

vi.mock('../api', () => ({
  getGameDayReplay: vi.fn(),
}));

describe('GameView empty state', () => {
  it('shows guidance when no days simulated', () => {
    const state = {
      game_id: 'test',
      current_day: 0,
      max_days: 10,
      is_complete: false,
      use_llm: false,
      agent_ids: ['BANK_A', 'BANK_B'],
      current_policies: {},
      days: [],
      fraction_history: {},
      cost_history: {},
      reasoning_history: {},
    };
    render(<GameView gameId="test" gameState={state} onUpdate={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText(/Ready to start/)).toBeInTheDocument();
    expect(screen.getByText(/Next Day/)).toBeInTheDocument();
  });

  it('hides guidance once days exist', () => {
    const state = {
      game_id: 'test',
      current_day: 1,
      max_days: 10,
      is_complete: false,
      use_llm: false,
      agent_ids: ['BANK_A'],
      current_policies: {},
      days: [{ day: 0, seed: 1, costs: {}, policies: {}, events: [], balance_history: {}, total_cost: 0 }],
      fraction_history: {},
      cost_history: {},
      reasoning_history: {},
    };
    render(<GameView gameId="test" gameState={state} onUpdate={vi.fn()} onReset={vi.fn()} />);
    expect(screen.queryByText(/Ready to start/)).toBeNull();
  });
});
```

### Step 1.2: GREEN — Implement

In `GameView.tsx`, add after the progress bar:

```tsx
{gameState.days.length === 0 && (
  <div className="bg-slate-800/50 rounded-xl border border-dashed border-slate-600 p-8 text-center">
    <div className="text-4xl mb-3">🏦</div>
    <h3 className="text-lg font-semibold text-slate-300 mb-2">Ready to start</h3>
    <p className="text-sm text-slate-400 max-w-md mx-auto">
      Click <strong>▶ Next Day</strong> to simulate the first trading day.
      Each day, the AI agent will observe costs and propose improved liquidity policies.
    </p>
  </div>
)}
```

### Step 1.3: REFACTOR

No refactoring needed.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/GameView.tsx` | Modify — add empty state |
| `web/frontend/src/__tests__/GameView.empty.test.tsx` | Create |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/GameView.empty.test.tsx
```

## Completion Criteria

- [ ] Guidance shows at Day 0 with no simulated days
- [ ] Guidance disappears after first day
- [ ] Tests pass
