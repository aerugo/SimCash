# Phase 3: Frontend — WebSocket Hook with Message Dispatch

**Status**: Pending

---

## Objective

Create a `useGameWebSocket` React hook that connects to the game WebSocket, dispatches typed messages to state reducers, handles reconnection, and provides send/control functions.

---

## Invariants Enforced in This Phase

- INV-2: Determinism — WebSocket is read-only for state; game state comes from server

---

## TDD Steps

### Step 3.1: Add WS Message Types (RED)

**Update `web/frontend/src/types.ts`:**

```typescript
// WebSocket message types
export type WSMessageType =
  | 'game_state'
  | 'day_complete'
  | 'simulation_start'
  | 'optimization_start'
  | 'optimization_complete'
  | 'llm_calling'
  | 'llm_complete'
  | 'game_complete'
  | 'error';

export interface WSMessage {
  type: WSMessageType;
  data?: any;
  day?: number;
  agent_id?: string;
  reasoning?: GameOptimizationResult;
  message?: string;
}
```

### Step 3.2: Implement Hook (GREEN)

**Create `web/frontend/src/hooks/useGameWebSocket.ts`:**

```typescript
import { useCallback, useEffect, useRef, useState } from 'react';
import type { GameState, DayResult, GameOptimizationResult, WSMessage } from '../types';

interface GameWSState {
  connected: boolean;
  gameState: GameState | null;
  currentPhase: 'idle' | 'simulating' | 'optimizing' | 'complete';
  optimizingAgent: string | null;
  lastDay: DayResult | null;
  error: string | null;
}

interface GameWSActions {
  step: () => void;
  autoRun: (speedMs?: number) => void;
  stop: () => void;
  requestState: () => void;
}

export function useGameWebSocket(gameId: string): GameWSState & GameWSActions {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<GameWSState>({
    connected: false,
    gameState: null,
    currentPhase: 'idle',
    optimizingAgent: null,
    lastDay: null,
    error: null,
  });

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/games/${gameId}`);
    wsRef.current = ws;

    ws.onopen = () => setState(s => ({ ...s, connected: true, error: null }));
    ws.onclose = () => setState(s => ({ ...s, connected: false }));
    ws.onerror = () => setState(s => ({ ...s, error: 'WebSocket connection failed' }));

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);

      setState(s => {
        switch (msg.type) {
          case 'game_state':
            return { ...s, gameState: msg.data, currentPhase: msg.data.is_complete ? 'complete' : s.currentPhase };
          case 'simulation_start':
            return { ...s, currentPhase: 'simulating' };
          case 'day_complete':
            return { ...s, lastDay: msg.data, currentPhase: 'idle' };
          case 'optimization_start':
            return { ...s, currentPhase: 'optimizing', optimizingAgent: msg.agent_id ?? null };
          case 'optimization_complete':
            return { ...s, optimizingAgent: null };
          case 'game_complete':
            return { ...s, gameState: msg.data, currentPhase: 'complete' };
          case 'error':
            return { ...s, error: msg.message ?? 'Unknown error' };
          default:
            return s;
        }
      });
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [gameId]);

  return {
    ...state,
    step: useCallback(() => send({ action: 'step' }), [send]),
    autoRun: useCallback((speedMs = 1000) => send({ action: 'auto', speed_ms: speedMs }), [send]),
    stop: useCallback(() => send({ action: 'stop' }), [send]),
    requestState: useCallback(() => send({ action: 'state' }), [send]),
  };
}
```

### Step 3.3: Refactor

- Add reconnection with exponential backoff
- Add message queue for messages received before handler is ready
- Consider `useReducer` instead of `useState` for complex state

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/types.ts` | Modify | Add WS message types |
| `web/frontend/src/hooks/useGameWebSocket.ts` | Create | WebSocket hook |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Hook connects to WS on mount, disconnects on unmount
- [ ] All message types dispatched to correct state updates
- [ ] `currentPhase` tracks simulation lifecycle
- [ ] `step()`, `autoRun()`, `stop()` send correct commands
- [ ] Error state populated on WS errors
- [ ] TypeScript compiles cleanly
