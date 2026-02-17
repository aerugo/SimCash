# Phase 4: Frontend — Display Accepted/Rejected Status + Delta Stats

**Status**: Pending

---

## Objective

Show bootstrap evaluation results in the reasoning panel: accepted/rejected badges, delta statistics, CV values, and confidence intervals.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — display deltas in dollars (converted from cents)

---

## TDD Steps

### Step 4.1: Add Types (RED)

**Update `web/frontend/src/types.ts`:**

```typescript
export interface EvaluationMetadata {
  delta_sum: number;
  mean_delta: number;
  cv: number;
  ci_lower: number;
  ci_upper: number;
  accepted: boolean;
  rejection_reason: string;
  num_samples: number;
  old_mean_cost: number;
  new_mean_cost: number;
}

// Update GameOptimizationResult
export interface GameOptimizationResult {
  reasoning: string;
  old_fraction: number;
  new_fraction?: number;
  accepted: boolean;
  mock?: boolean;
  evaluation?: EvaluationMetadata;
}
```

### Step 4.2: Evaluation Badge Component (GREEN)

**Create `web/frontend/src/components/EvaluationBadge.tsx`:**

```tsx
import type { EvaluationMetadata } from '../types';

interface Props {
  evaluation: EvaluationMetadata;
}

export function EvaluationBadge({ evaluation }: Props) {
  const { accepted, rejection_reason, delta_sum, cv, ci_lower, ci_upper, num_samples } = evaluation;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
      accepted
        ? 'bg-green-900/50 text-green-300 border border-green-700'
        : 'bg-red-900/50 text-red-300 border border-red-700'
    }`}>
      <span>{accepted ? '✓ Accepted' : '✗ Rejected'}</span>

      <span className="text-xs opacity-70">
        Δ={delta_sum > 0 ? '+' : ''}{(delta_sum / 100).toFixed(2)}
        {' '}CV={cv.toFixed(3)}
        {' '}CI=[{(ci_lower / 100).toFixed(2)}, {(ci_upper / 100).toFixed(2)}]
        {' '}n={num_samples}
      </span>

      {!accepted && rejection_reason && (
        <span className="text-xs text-red-400" title={rejection_reason}>
          — {rejection_reason}
        </span>
      )}
    </div>
  );
}
```

### Step 4.3: Wire into Reasoning Panel (GREEN)

Update the reasoning display in `GameView.tsx`:

```tsx
import { EvaluationBadge } from './EvaluationBadge';

// Inside reasoning panel
{result.evaluation && (
  <EvaluationBadge evaluation={result.evaluation} />
)}
```

### Step 4.4: Refactor

- Add tooltip with full paired delta table on hover
- Color-code delta (green for improvement, red for worse)
- Show "No bootstrap" label when evaluation is absent

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/types.ts` | Modify | Add `EvaluationMetadata` |
| `web/frontend/src/components/EvaluationBadge.tsx` | Create | Accept/reject badge |
| `web/frontend/src/components/GameView.tsx` | Modify | Wire badge into reasoning panel |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Accepted proposals show green badge with ✓
- [ ] Rejected proposals show red badge with ✗ and reason
- [ ] Delta, CV, CI displayed in compact format
- [ ] Values converted from cents to dollars for display
- [ ] Badge only shown when evaluation metadata present
- [ ] TypeScript compiles cleanly
