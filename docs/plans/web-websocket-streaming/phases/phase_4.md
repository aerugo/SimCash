# Phase 4: Frontend — Progressive UI Updates from WS Stream

**Status**: Pending

---

## Objective

Wire the `useGameWebSocket` hook into `GameView` so charts animate as days arrive, reasoning appears in real-time per agent, and the UI shows what phase the game is in.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — chart values are cents; display conversion in tooltip only
- INV-GAME-2: Agent Isolation — reasoning cards show per-agent, not mixed

---

## TDD Steps

### Step 4.1: Replace REST with WS in GameView (RED → GREEN)

**Update `web/frontend/src/components/GameView.tsx`:**

```tsx
import { useGameWebSocket } from '../hooks/useGameWebSocket';

interface GameViewProps {
  gameId: string;
  onBack?: () => void;
}

export function GameView({ gameId, onBack }: GameViewProps) {
  const {
    connected, gameState, currentPhase, optimizingAgent, lastDay, error,
    step, autoRun, stop,
  } = useGameWebSocket(gameId);

  // Charts update reactively from gameState changes
  // No more polling or manual fetch after step/auto

  return (
    <div>
      {/* Connection status indicator */}
      <div className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />

      {/* Phase indicator */}
      {currentPhase === 'simulating' && (
        <div className="text-yellow-400 animate-pulse">⏳ Simulating day...</div>
      )}
      {currentPhase === 'optimizing' && (
        <div className="text-blue-400 animate-pulse">
          🧠 {optimizingAgent} thinking...
        </div>
      )}

      {/* Controls use WS commands instead of REST */}
      <button onClick={step} disabled={currentPhase !== 'idle'}>Step</button>
      <button onClick={() => autoRun(500)}>Auto</button>
      <button onClick={stop}>Stop</button>

      {/* Charts re-render on gameState change */}
      {gameState && (
        <>
          {/* Existing chart components, fed from gameState.cost_history / fraction_history */}
        </>
      )}

      {/* Reasoning panel shows latest reasoning with animation */}
      {gameState?.reasoning_history && (
        <div className="space-y-2">
          {Object.entries(gameState.reasoning_history).map(([aid, history]) => (
            <div key={aid} className="p-3 bg-gray-800 rounded">
              <h4 className="font-semibold text-gray-300">{aid}</h4>
              {history.length > 0 && (
                <p className={`text-sm text-gray-400 ${
                  optimizingAgent === aid ? 'animate-pulse' : ''
                }`}>
                  {history[history.length - 1].reasoning}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Step 4.2: Animate Chart Updates

Add CSS transitions for chart data changes:

```css
/* Smooth chart transitions when new data points arrive */
.chart-line { transition: d 300ms ease-in-out; }
.chart-point { transition: cx 300ms, cy 300ms; }
```

### Step 4.3: Refactor

- Extract phase indicator as `GamePhaseIndicator` component
- Add sound/haptic feedback option for day completion
- Ensure charts handle partial data gracefully (data arriving mid-render)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/components/GameView.tsx` | Modify | Replace REST with WS hook |
| `web/frontend/src/components/GamePhaseIndicator.tsx` | Create | Phase status component |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
# Manual: start backend + frontend, create game, verify streaming works
```

## Completion Criteria

- [ ] GameView uses `useGameWebSocket` instead of REST for step/auto
- [ ] Charts update progressively as days stream in
- [ ] Phase indicator shows simulating/optimizing/complete
- [ ] Per-agent optimization status visible during auto-run
- [ ] Connection status dot (green/red)
- [ ] Stop button cancels auto-run mid-stream
