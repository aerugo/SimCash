# Phase 4: Frontend — Skeleton/Shimmer States for Charts

**Status**: Pending

---

## Objective

Show skeleton/shimmer placeholder states for charts that are about to update, giving visual feedback that new data is incoming. Smooth transition from skeleton to real chart data.

---

## Invariants Enforced in This Phase

- INV-1: No actual data displayed during skeleton state (avoid stale data confusion)

---

## TDD Steps

### Step 4.1: Create ChartSkeleton Component (GREEN)

**Create `web/frontend/src/components/ChartSkeleton.tsx`:**

```tsx
interface Props {
  height?: number;
  label?: string;
}

export function ChartSkeleton({ height = 200, label }: Props) {
  return (
    <div className="relative rounded-lg overflow-hidden" style={{ height }}>
      {/* Shimmer background */}
      <div className="absolute inset-0 bg-gray-800">
        <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite]
          bg-gradient-to-r from-transparent via-gray-700/50 to-transparent" />
      </div>

      {/* Fake chart lines */}
      <svg className="absolute inset-0 w-full h-full opacity-20" viewBox="0 0 100 50">
        <path
          d="M0,40 Q25,20 50,30 T100,25"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          className="text-gray-600"
        />
        <path
          d="M0,35 Q25,35 50,25 T100,35"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          className="text-gray-600"
          strokeDasharray="3,3"
        />
      </svg>

      {/* Label */}
      {label && (
        <div className="absolute bottom-2 left-3 text-xs text-gray-600">{label}</div>
      )}
    </div>
  );
}
```

### Step 4.2: Add Shimmer Keyframe to Tailwind Config

**Update `web/frontend/tailwind.config.ts` or global CSS:**

```css
@keyframes shimmer {
  100% { transform: translateX(100%); }
}
```

### Step 4.3: Conditional Chart Rendering in GameView

```tsx
import { ChartSkeleton } from './ChartSkeleton';

// In GameView chart section
{currentPhase === 'simulating' ? (
  <ChartSkeleton height={250} label="Cost chart updating..." />
) : (
  <CostChart data={gameState?.cost_history} />
)}

// Or use a fade transition:
<div className={`transition-opacity duration-300 ${currentPhase === 'simulating' ? 'opacity-50' : 'opacity-100'}`}>
  <CostChart data={gameState?.cost_history} />
  {currentPhase === 'simulating' && (
    <div className="absolute inset-0 flex items-center justify-center">
      <span className="text-sm text-gray-400 animate-pulse">Updating...</span>
    </div>
  )}
</div>
```

### Step 4.4: Refactor

- Use `opacity-50` overlay instead of full skeleton replacement for better UX (keep old data visible)
- Add smooth data transitions: new chart points slide in from right
- Consider using `framer-motion` or CSS transitions for chart data changes

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/ChartSkeleton.tsx` | Create | Shimmer placeholder |
| `web/frontend/src/components/GameView.tsx` | Modify | Conditional skeleton/overlay |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Skeleton shown when chart data is loading/updating
- [ ] Shimmer animation smooth and not CPU-intensive
- [ ] Old data stays visible (dimmed) during updates
- [ ] New data appears with smooth transition
- [ ] TypeScript compiles cleanly
