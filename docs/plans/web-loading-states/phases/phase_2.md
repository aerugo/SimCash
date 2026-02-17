# Phase 2: Frontend — Loading Overlay with Phase Indicator + Timer

**Status**: Pending

---

## Objective

Create a `LoadingOverlay` component that shows what phase the game is in (simulating / optimizing / idle) with an elapsed timer that counts up from operation start.

---

## Invariants Enforced in This Phase

- INV-2: Determinism — overlay is display-only

---

## TDD Steps

### Step 2.1: Create LoadingOverlay Component (GREEN)

**Create `web/frontend/src/components/LoadingOverlay.tsx`:**

```tsx
import { useEffect, useState } from 'react';

type Phase = 'idle' | 'simulating' | 'optimizing' | 'complete';

interface Props {
  phase: Phase;
  currentDay?: number;
  maxDays?: number;
  optimizingAgent?: string | null;
  startTime?: number | null;  // Unix timestamp from server
}

export function LoadingOverlay({ phase, currentDay, maxDays, optimizingAgent, startTime }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (phase === 'idle' || phase === 'complete' || !startTime) {
      setElapsed(0);
      return;
    }

    const interval = setInterval(() => {
      setElapsed(Date.now() / 1000 - startTime);
    }, 100);

    return () => clearInterval(interval);
  }, [phase, startTime]);

  if (phase === 'idle' || phase === 'complete') return null;

  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const phaseConfig = {
    simulating: {
      icon: '⚡',
      label: 'Simulating',
      color: 'text-yellow-400',
      bg: 'bg-yellow-900/20 border-yellow-700',
    },
    optimizing: {
      icon: '🧠',
      label: 'Optimizing',
      color: 'text-blue-400',
      bg: 'bg-blue-900/20 border-blue-700',
    },
  };

  const config = phaseConfig[phase];

  return (
    <div className={`flex items-center gap-3 px-4 py-2 rounded-lg border ${config.bg} animate-pulse`}>
      <span className="text-lg">{config.icon}</span>

      <div className="flex-1">
        <div className={`font-semibold ${config.color}`}>
          {config.label}
          {phase === 'simulating' && currentDay != null && maxDays &&
            ` Day ${currentDay + 1}/${maxDays}`
          }
          {phase === 'optimizing' && optimizingAgent &&
            ` — ${optimizingAgent}`
          }
        </div>
        <div className="text-xs text-gray-500">
          Elapsed: {formatTime(elapsed)}
          {phase === 'optimizing' && elapsed > 10 &&
            <span className="ml-2 text-gray-600">(LLM calls can take 30-120s)</span>
          }
        </div>
      </div>

      {/* Progress bar for simulation (known bounds) */}
      {phase === 'simulating' && currentDay != null && maxDays && (
        <div className="w-24 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-yellow-500 transition-all duration-300"
            style={{ width: `${((currentDay + 1) / maxDays) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
```

### Step 2.2: Wire into GameView (GREEN)

```tsx
import { LoadingOverlay } from './LoadingOverlay';

// In GameView
<LoadingOverlay
  phase={currentPhase}
  currentDay={gameState?.current_day}
  maxDays={gameState?.max_days}
  optimizingAgent={optimizingAgent}
  startTime={phaseStartTime}
/>
```

### Step 2.3: Track phase start time in WS hook

Update `useGameWebSocket` to capture `timestamp` from server messages:

```typescript
case 'simulation_start':
  return { ...s, currentPhase: 'simulating', phaseStartTime: msg.timestamp ?? Date.now() / 1000 };
case 'optimization_start':
  return { ...s, currentPhase: 'optimizing', optimizingAgent: msg.agent_id, phaseStartTime: msg.timestamp ?? Date.now() / 1000 };
```

### Step 2.4: Refactor

- Add ETA estimation based on historical per-day timing
- Pulse animation only on actual phase changes (not every render)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/LoadingOverlay.tsx` | Create | Phase indicator + timer |
| `web/frontend/src/components/GameView.tsx` | Modify | Wire overlay |
| `web/frontend/src/hooks/useGameWebSocket.ts` | Modify | Track phaseStartTime |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Overlay visible during simulating/optimizing phases
- [ ] Hidden when idle or complete
- [ ] Elapsed timer counts up from phase start
- [ ] Day progress shown during simulation
- [ ] Agent name shown during optimization
- [ ] Helpful hint after 10s of optimization
- [ ] TypeScript compiles cleanly
