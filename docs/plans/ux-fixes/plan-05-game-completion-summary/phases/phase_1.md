# Phase 1: Completion Summary Panel

**Status**: Pending

## Objective

Display a summary panel when game completes with convergence info, cost reduction stats, and equilibrium assessment.

## Invariants

- INV-1: Money is i64 — display as dollars
- INV-UI-8: Only when is_complete

## TDD Steps

### Step 1.1: RED — Write Failing Test

Create `web/frontend/src/__tests__/CompletionSummary.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { CompletionSummary } from '../components/CompletionSummary';
import { describe, it, expect } from 'vitest';

describe('CompletionSummary', () => {
  const props = {
    agentIds: ['BANK_A', 'BANK_B'],
    fractionHistory: {
      BANK_A: [1.0, 0.8, 0.6, 0.55, 0.54],
      BANK_B: [1.0, 0.7, 0.5, 0.48, 0.47],
    },
    costHistory: {
      BANK_A: [1500, 1200, 900, 850, 840],
      BANK_B: [1400, 1100, 800, 750, 740],
    },
    days: [
      { day: 0, total_cost: 2900 },
      { day: 1, total_cost: 2300 },
      { day: 2, total_cost: 1700 },
      { day: 3, total_cost: 1600 },
      { day: 4, total_cost: 1580 },
    ],
  };

  it('shows final fractions for each agent', () => {
    render(<CompletionSummary {...props} />);
    expect(screen.getByText(/0\.540/)).toBeInTheDocument();
    expect(screen.getByText(/0\.470/)).toBeInTheDocument();
  });

  it('shows cost reduction percentage', () => {
    render(<CompletionSummary {...props} />);
    // (2900 - 1580) / 2900 = ~45.5%
    expect(screen.getByText(/45/)).toBeInTheDocument();
  });

  it('shows equilibrium assessment', () => {
    render(<CompletionSummary {...props} />);
    // Last two fractions differ by < 0.02, should indicate convergence
    expect(screen.getByText(/converged|equilibrium/i)).toBeInTheDocument();
  });
});
```

### Step 1.2: GREEN — Implement

Create `web/frontend/src/components/CompletionSummary.tsx`:

```tsx
interface Props {
  agentIds: string[];
  fractionHistory: Record<string, number[]>;
  costHistory: Record<string, number[]>;
  days: { day: number; total_cost: number }[];
}

export function CompletionSummary({ agentIds, fractionHistory, costHistory, days }: Props) {
  const firstCost = days[0]?.total_cost ?? 0;
  const lastCost = days[days.length - 1]?.total_cost ?? 0;
  const costReduction = firstCost > 0 ? ((firstCost - lastCost) / firstCost) * 100 : 0;

  // Check equilibrium: last two fractions differ by < 0.02 for all agents
  const converged = agentIds.every(aid => {
    const h = fractionHistory[aid] ?? [];
    if (h.length < 2) return false;
    return Math.abs(h[h.length - 1] - h[h.length - 2]) < 0.02;
  });

  return (
    <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/30 rounded-xl p-5">
      <h3 className="text-lg font-bold text-green-400 mb-4">🏆 Game Complete</h3>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-xs text-slate-500 mb-1">Cost Reduction</div>
          <div className="text-2xl font-bold text-green-400">{costReduction.toFixed(1)}%</div>
          <div className="text-xs text-slate-500">
            {Math.round(firstCost).toLocaleString()} → {Math.round(lastCost).toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-1">Equilibrium</div>
          <div className={`text-lg font-bold ${converged ? 'text-green-400' : 'text-amber-400'}`}>
            {converged ? '✓ Converged' : '⟳ Not converged'}
          </div>
          <div className="text-xs text-slate-500">
            {converged ? 'Agents reached stable policies' : 'Fractions still changing'}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-xs text-slate-500 font-medium">Final Fractions</div>
        {agentIds.map(aid => {
          const h = fractionHistory[aid] ?? [];
          const final = h[h.length - 1] ?? 1;
          const initial = h[0] ?? 1;
          return (
            <div key={aid} className="flex items-center justify-between bg-slate-900/50 rounded px-3 py-1.5">
              <span className="font-mono text-sm text-slate-300">{aid}</span>
              <span className="font-mono text-sm">
                <span className="text-slate-500">{initial.toFixed(3)}</span>
                <span className="text-slate-600 mx-1">→</span>
                <span className="text-white font-bold">{final.toFixed(3)}</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Add to `GameView.tsx` after the progress bar:

```tsx
{gameState.is_complete && (
  <CompletionSummary
    agentIds={gameState.agent_ids}
    fractionHistory={gameState.fraction_history}
    costHistory={gameState.cost_history}
    days={gameState.days}
  />
)}
```

### Step 1.3: REFACTOR

Extract equilibrium check into a utility function.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/components/CompletionSummary.tsx` | Create |
| `web/frontend/src/views/GameView.tsx` | Modify — render CompletionSummary |
| `web/frontend/src/__tests__/CompletionSummary.test.tsx` | Create |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/CompletionSummary.test.tsx
```

## Completion Criteria

- [ ] Summary panel renders when game is complete
- [ ] Shows final fractions, cost reduction %, equilibrium status
- [ ] Does not render when game is in progress
- [ ] Tests pass
