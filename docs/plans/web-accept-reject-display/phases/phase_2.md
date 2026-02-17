# Phase 2: Frontend — Rejection Badges on Reasoning Cards

**Status**: Pending

---

## Objective

Create a `ReasoningCard` component that displays reasoning text with clear accept/reject visual distinction: green border + ✓ for accepted, red border + ✗ for rejected, with rejection reason text.

---

## Invariants Enforced in This Phase

- INV-GAME-2: Agent Isolation — each card shows one agent's result

---

## TDD Steps

### Step 2.1: Create ReasoningCard Component (GREEN)

**Create `web/frontend/src/components/ReasoningCard.tsx`:**

```tsx
import type { GameOptimizationResult } from '../types';

interface Props {
  agentId: string;
  result: GameOptimizationResult;
  dayNum: number;
}

export function ReasoningCard({ agentId, result, dayNum }: Props) {
  const accepted = result.accepted;
  const evaluation = result.evaluation;

  return (
    <div className={`rounded-lg border-2 p-4 ${
      accepted
        ? 'border-green-700 bg-green-900/10'
        : 'border-red-700 bg-red-900/10'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold text-gray-200">
          {agentId} — Day {dayNum}
        </h4>
        <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
          accepted
            ? 'bg-green-800 text-green-200'
            : 'bg-red-800 text-red-200'
        }`}>
          {accepted ? '✓ Accepted' : '✗ Rejected'}
        </span>
      </div>

      {/* Fraction change */}
      <div className="text-sm text-gray-400 mb-2">
        Fraction: {result.old_fraction.toFixed(3)}
        {result.new_fraction != null && (
          <>
            {' → '}
            <span className={accepted ? 'text-green-300' : 'text-red-300 line-through'}>
              {result.new_fraction.toFixed(3)}
            </span>
            {!accepted && (
              <span className="text-gray-500 ml-1">(kept {result.old_fraction.toFixed(3)})</span>
            )}
          </>
        )}
      </div>

      {/* Reasoning text */}
      <p className="text-sm text-gray-400 leading-relaxed">{result.reasoning}</p>

      {/* Rejection reason */}
      {!accepted && evaluation?.rejection_reason && (
        <div className="mt-2 px-3 py-2 bg-red-900/30 rounded text-xs text-red-300">
          <strong>Reason:</strong> {evaluation.rejection_reason}
        </div>
      )}

      {/* Bootstrap stats (compact) */}
      {evaluation && (
        <div className="mt-2 flex gap-4 text-xs text-gray-500">
          <span>Δ: ${(evaluation.delta_sum / 100).toFixed(2)}</span>
          <span>CV: {evaluation.cv.toFixed(3)}</span>
          <span>95% CI: [${(evaluation.ci_lower / 100).toFixed(2)}, ${(evaluation.ci_upper / 100).toFixed(2)}]</span>
          <span>n={evaluation.num_samples}</span>
        </div>
      )}

      {/* Mock indicator */}
      {result.mock && (
        <span className="text-xs text-gray-600 mt-1 inline-block">🎭 mock</span>
      )}
    </div>
  );
}
```

### Step 2.2: Wire into GameView (GREEN)

Replace inline reasoning display with `ReasoningCard`:

```tsx
import { ReasoningCard } from './ReasoningCard';

// In reasoning panel
{Object.entries(gameState.reasoning_history).map(([aid, history]) => (
  <div key={aid} className="space-y-2">
    {history.map((result, i) => (
      <ReasoningCard key={i} agentId={aid} result={result} dayNum={i} />
    ))}
  </div>
))}
```

### Step 2.3: Refactor

- Collapse old reasoning cards by default, expand latest
- Add animation for new cards appearing

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/ReasoningCard.tsx` | Create | Accept/reject reasoning card |
| `web/frontend/src/components/GameView.tsx` | Modify | Use ReasoningCard in reasoning panel |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Accepted cards have green border + ✓ badge
- [ ] Rejected cards have red border + ✗ badge + rejection reason
- [ ] Rejected fraction change shown with strikethrough
- [ ] Bootstrap stats displayed when available
- [ ] Mock indicator shown for mock reasoning
- [ ] TypeScript compiles cleanly
