# Phase 1: Index Reasoning by Selected Day

**Status**: Pending

## Objective

Make the "Latest Reasoning" panel show reasoning for the currently selected day, not always the final entry.

## Invariants

- INV-UI-4: Selected day controls reasoning display
- INV-UI-5: Default shows latest

## TDD Steps

### Step 1.1: RED — Write Failing Test

Create `web/frontend/src/__tests__/GameView.reasoning.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
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

const makeState = () => ({
  game_id: 'test',
  current_day: 3,
  max_days: 10,
  is_complete: false,
  use_llm: true,
  agent_ids: ['BANK_A'],
  current_policies: { BANK_A: { initial_liquidity_fraction: 0.5 } },
  days: [
    { day: 0, seed: 1, costs: { BANK_A: { liquidity_cost: 100, delay_cost: 50, penalty_cost: 0, total: 150 } }, policies: { BANK_A: { initial_liquidity_fraction: 1.0 } }, events: [], balance_history: { BANK_A: [100] }, total_cost: 150 },
    { day: 1, seed: 2, costs: { BANK_A: { liquidity_cost: 80, delay_cost: 60, penalty_cost: 0, total: 140 } }, policies: { BANK_A: { initial_liquidity_fraction: 0.8 } }, events: [], balance_history: { BANK_A: [80] }, total_cost: 140 },
    { day: 2, seed: 3, costs: { BANK_A: { liquidity_cost: 60, delay_cost: 70, penalty_cost: 0, total: 130 } }, policies: { BANK_A: { initial_liquidity_fraction: 0.5 } }, events: [], balance_history: { BANK_A: [60] }, total_cost: 130 },
  ],
  fraction_history: { BANK_A: [1.0, 0.8, 0.5] },
  cost_history: { BANK_A: [150, 140, 130] },
  reasoning_history: {
    BANK_A: [
      { reasoning: 'Day 1 reasoning text', accepted: true, mock: true, old_fraction: 1.0, new_fraction: 0.8, bootstrap: null, rejection_reason: null },
      { reasoning: 'Day 2 reasoning text', accepted: true, mock: true, old_fraction: 0.8, new_fraction: 0.5, bootstrap: null, rejection_reason: null },
      { reasoning: 'Day 3 reasoning text', accepted: false, mock: true, old_fraction: 0.5, new_fraction: 0.4, bootstrap: null, rejection_reason: 'CV too high' },
    ],
  },
});

describe('GameView reasoning by selected day', () => {
  it('shows reasoning for selected day, not always latest', () => {
    const state = makeState();
    render(<GameView gameId="test" gameState={state} onUpdate={vi.fn()} onReset={vi.fn()} />);

    // Click day 1 button (index 0)
    const dayButtons = screen.getAllByRole('button').filter(b => b.textContent === '1');
    fireEvent.click(dayButtons[0]);

    // Should show Day 1's reasoning
    expect(screen.getByText('Day 1 reasoning text')).toBeInTheDocument();
    expect(screen.queryByText('Day 3 reasoning text')).toBeNull();
  });
});
```

**Expected**: Fails because reasoning always shows latest (Day 3).

### Step 1.2: GREEN — Implement

In `GameView.tsx`, change the "Latest Reasoning" section to use `selectedDay` index:

```tsx
// Before:
const latest = history[history.length - 1];

// After:
const dayIndex = selectedDay ?? history.length - 1;
const latest = history[dayIndex];
```

Full replacement in the reasoning section:

```tsx
{/* Day-specific reasoning */}
{gameState.reasoning_history && Object.keys(gameState.reasoning_history).length > 0 && (
  <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
    <h3 className="text-sm font-semibold text-slate-300 mb-3">
      🧠 {selectedDay !== null && selectedDay < gameState.days.length - 1
        ? `Day ${selectedDay + 1} Reasoning`
        : 'Latest Reasoning'}
    </h3>
    <div className="space-y-3">
      {gameState.agent_ids.map((aid, i) => {
        const history = gameState.reasoning_history[aid] ?? [];
        const dayIndex = selectedDay ?? history.length - 1;
        const entry = history[dayIndex];
        if (!entry) return null;
        const bs = entry.bootstrap;
        return (
          <div key={aid} className={`bg-slate-900/50 rounded-lg p-3 border-l-2 ${
            entry.accepted ? 'border-green-500' : 'border-red-500'
          }`}>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs" style={{ color: AGENT_COLORS[i % AGENT_COLORS.length] }}>
                {aid}
              </span>
              {entry.mock && <span className="text-[10px] text-slate-600">mock</span>}
              {entry.accepted
                ? <span className="text-green-400 text-[10px] font-medium">✓ ACCEPTED</span>
                : <span className="text-red-400 text-[10px] font-medium">✗ REJECTED</span>
              }
              {entry.old_fraction != null && entry.new_fraction != null && (
                <span className="text-[10px] text-slate-500 font-mono">
                  {entry.old_fraction.toFixed(3)} → {entry.new_fraction.toFixed(3)}
                </span>
              )}
            </div>
            {bs && (
              <div className="flex gap-3 text-[10px] text-slate-500 mb-1 font-mono">
                <span>Δ={bs.delta_sum.toLocaleString()}</span>
                <span>CV={bs.cv.toFixed(2)}</span>
                <span>CI=[{bs.ci_lower.toLocaleString()},{bs.ci_upper.toLocaleString()}]</span>
                <span>n={bs.num_samples}</span>
              </div>
            )}
            {!entry.accepted && entry.rejection_reason && (
              <div className="text-[10px] text-red-400/80 mb-1">
                {entry.rejection_reason}
              </div>
            )}
            <p className="text-xs text-slate-400 leading-relaxed">{entry.reasoning}</p>
          </div>
        );
      })}
    </div>
  </div>
)}
```

### Step 1.3: REFACTOR

Extract `dayIndex` computation to a shared variable at the top of the component to avoid duplication.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/GameView.tsx` | Modify — index reasoning by selectedDay |
| `web/frontend/src/__tests__/GameView.reasoning.test.tsx` | Create |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/GameView.reasoning.test.tsx
```

## Completion Criteria

- [ ] Clicking Day 1 shows Day 1's reasoning
- [ ] Clicking Day N shows Day N's reasoning
- [ ] Default (latest day) still shows latest reasoning
- [ ] Tests pass
