# Phase 4: Frontend — Policy History Timeline

**Status**: Pending

---

## Objective

Create a visual timeline showing accepted (green) vs rejected (red) policy proposals per agent across all days. This gives a bird's-eye view of the optimization process.

---

## Invariants Enforced in This Phase

- INV-GAME-2: Agent Isolation — separate timeline per agent

---

## TDD Steps

### Step 4.1: Create PolicyTimeline Component (GREEN)

**Create `web/frontend/src/components/PolicyTimeline.tsx`:**

```tsx
import type { GameOptimizationResult } from '../types';

interface Props {
  agentId: string;
  history: GameOptimizationResult[];
}

export function PolicyTimeline({ agentId, history }: Props) {
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-semibold text-gray-400">{agentId}</h4>
      <div className="flex gap-1 items-center">
        {history.map((entry, i) => (
          <div
            key={i}
            title={`Day ${i}: ${entry.accepted ? 'Accepted' : 'Rejected'} — ${entry.old_fraction.toFixed(3)}→${entry.new_fraction?.toFixed(3) ?? 'kept'}`}
            className={`w-6 h-6 rounded-sm flex items-center justify-center text-xs font-bold cursor-pointer transition-transform hover:scale-125 ${
              entry.accepted
                ? 'bg-green-700 text-green-200'
                : 'bg-red-700 text-red-200'
            }`}
          >
            {i}
          </div>
        ))}
        {history.length === 0 && (
          <span className="text-xs text-gray-600">No proposals yet</span>
        )}
      </div>

      {/* Fraction line chart (mini sparkline) */}
      <div className="flex items-end gap-px h-8">
        {history.map((entry, i) => {
          const fraction = entry.accepted
            ? (entry.new_fraction ?? entry.old_fraction)
            : entry.old_fraction;
          const height = Math.max(2, fraction * 100);
          return (
            <div
              key={i}
              className={`w-4 rounded-t ${entry.accepted ? 'bg-green-600' : 'bg-red-600'}`}
              style={{ height: `${height}%` }}
              title={`Day ${i}: fraction=${fraction.toFixed(3)}`}
            />
          );
        })}
      </div>

      {/* Summary */}
      {history.length > 0 && (
        <div className="text-xs text-gray-500">
          {history.filter(e => e.accepted).length} accepted,{' '}
          {history.filter(e => !e.accepted).length} rejected
        </div>
      )}
    </div>
  );
}
```

### Step 4.2: Wire into GameView

```tsx
import { PolicyTimeline } from './PolicyTimeline';

// In GameView, add timeline section
<section className="mt-6">
  <h3 className="text-lg font-semibold text-gray-300 mb-3">Policy History</h3>
  <div className="space-y-4">
    {gameState.agent_ids.map(aid => (
      <PolicyTimeline
        key={aid}
        agentId={aid}
        history={gameState.reasoning_history[aid] || []}
      />
    ))}
  </div>
</section>
```

### Step 4.3: Refactor

- Add click on timeline node to scroll to corresponding ReasoningCard
- Color fraction chart bars based on whether the fraction improved costs

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/PolicyTimeline.tsx` | Create | Accept/reject timeline |
| `web/frontend/src/components/GameView.tsx` | Modify | Add timeline section |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Timeline shows green/red squares per day per agent
- [ ] Hover shows fraction change details
- [ ] Mini sparkline shows fraction evolution
- [ ] Summary counts accepted/rejected
- [ ] Separate timeline per agent (INV-GAME-2)
- [ ] TypeScript compiles cleanly
