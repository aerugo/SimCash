# Phase 3: Frontend — Detailed Rejection Tooltip/Modal

**Status**: Pending

---

## Objective

Create a detail modal showing the full paired delta table, CV computation, and threshold comparisons. Users click a reasoning card to see why it was accepted/rejected in detail.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — delta table shows cents, converted to dollars in display

---

## TDD Steps

### Step 3.1: Create DeltaDetailModal (GREEN)

**Create `web/frontend/src/components/DeltaDetailModal.tsx`:**

```tsx
import { useState } from 'react';
import type { EvaluationMetadata } from '../types';

interface Props {
  evaluation: EvaluationMetadata;
  agentId: string;
  dayNum: number;
  onClose: () => void;
}

export function DeltaDetailModal({ evaluation, agentId, dayNum, onClose }: Props) {
  const { delta_sum, mean_delta, cv, ci_lower, ci_upper, accepted,
          rejection_reason, num_samples, old_mean_cost, new_mean_cost } = evaluation;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-900 rounded-xl p-6 max-w-lg w-full mx-4 border border-gray-700"
           onClick={e => e.stopPropagation()}>

        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-white">
            Evaluation Detail — {agentId}, Day {dayNum}
          </h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white">✕</button>
        </div>

        {/* Verdict */}
        <div className={`p-3 rounded-lg mb-4 ${
          accepted ? 'bg-green-900/30 border border-green-700' : 'bg-red-900/30 border border-red-700'
        }`}>
          <p className={`font-bold ${accepted ? 'text-green-300' : 'text-red-300'}`}>
            {accepted ? '✓ Policy Accepted' : '✗ Policy Rejected'}
          </p>
          {rejection_reason && <p className="text-sm text-red-400 mt-1">{rejection_reason}</p>}
        </div>

        {/* Cost comparison */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="p-3 bg-gray-800 rounded">
            <p className="text-xs text-gray-500">Old Policy Mean Cost</p>
            <p className="text-lg font-mono text-gray-200">
              ${(old_mean_cost / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </p>
          </div>
          <div className="p-3 bg-gray-800 rounded">
            <p className="text-xs text-gray-500">New Policy Mean Cost</p>
            <p className="text-lg font-mono text-gray-200">
              ${(new_mean_cost / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </p>
          </div>
        </div>

        {/* Acceptance criteria table */}
        <table className="w-full text-sm mb-4">
          <thead>
            <tr className="text-gray-500 border-b border-gray-700">
              <th className="text-left py-2">Criterion</th>
              <th className="text-right py-2">Value</th>
              <th className="text-right py-2">Threshold</th>
              <th className="text-center py-2">Pass</th>
            </tr>
          </thead>
          <tbody className="text-gray-300">
            <tr>
              <td className="py-1">Delta Sum (Δ)</td>
              <td className="text-right font-mono">${(delta_sum / 100).toFixed(2)}</td>
              <td className="text-right font-mono">&gt; 0</td>
              <td className="text-center">{delta_sum > 0 ? '✓' : '✗'}</td>
            </tr>
            <tr>
              <td className="py-1">Coefficient of Variation</td>
              <td className="text-right font-mono">{cv.toFixed(4)}</td>
              <td className="text-right font-mono">&lt; 0.5</td>
              <td className="text-center">{cv < 0.5 ? '✓' : '✗'}</td>
            </tr>
            <tr>
              <td className="py-1">95% CI Lower Bound</td>
              <td className="text-right font-mono">${(ci_lower / 100).toFixed(2)}</td>
              <td className="text-right font-mono">&gt; 0</td>
              <td className="text-center">{ci_lower > 0 ? '✓' : '✗'}</td>
            </tr>
          </tbody>
        </table>

        {/* Samples */}
        <p className="text-xs text-gray-500">
          Based on {num_samples} paired samples.
          Mean delta: ${(mean_delta / 100).toFixed(2)}.
          95% CI: [${(ci_lower / 100).toFixed(2)}, ${(ci_upper / 100).toFixed(2)}]
        </p>
      </div>
    </div>
  );
}
```

### Step 3.2: Wire Modal into ReasoningCard

```tsx
// In ReasoningCard.tsx
const [showDetail, setShowDetail] = useState(false);

// Add clickable area
<div onClick={() => evaluation && setShowDetail(true)} className="cursor-pointer">
  ...existing card content...
</div>

{showDetail && evaluation && (
  <DeltaDetailModal
    evaluation={evaluation}
    agentId={agentId}
    dayNum={dayNum}
    onClose={() => setShowDetail(false)}
  />
)}
```

### Step 3.3: Refactor

- Add keyboard support (Escape to close modal)
- Add per-sample delta table (expandable section in modal)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/DeltaDetailModal.tsx` | Create | Detailed evaluation modal |
| `web/frontend/src/components/ReasoningCard.tsx` | Modify | Add click-to-show-detail |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Modal shows old/new mean costs
- [ ] Acceptance criteria table with pass/fail per criterion
- [ ] Dollar values properly converted from cents
- [ ] Modal closeable via ✕ button, backdrop click, Escape key
- [ ] TypeScript compiles cleanly
