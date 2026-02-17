# Phase 3: Frontend — Wire Setup → Create Game → Transition to GameView

**Status**: Pending

---

## Objective

Connect the GameSetup component to the backend API: fetch scenarios on mount, call `POST /api/games` on start, and transition to GameView with the created gameId.

---

## Invariants Enforced in This Phase

- INV-2: Determinism — game creation passes config through cleanly; no client-side mutation

---

## TDD Steps

### Step 3.1: Add API Functions (RED)

**Update `web/frontend/src/api.ts`:**

```typescript
import type { GameScenario, GameSetupConfig, GameState } from './types';

const API = '/api';

export async function getGameScenarios(): Promise<GameScenario[]> {
  const resp = await fetch(`${API}/games/scenarios`);
  if (!resp.ok) throw new Error(`Failed to fetch scenarios: ${resp.status}`);
  const data = await resp.json();
  return data.scenarios;
}

export async function createGame(config: GameSetupConfig): Promise<{ game_id: string; game: GameState }> {
  const resp = await fetch(`${API}/games`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `Failed to create game: ${resp.status}`);
  }
  return resp.json();
}
```

### Step 3.2: Wire State Management (GREEN)

**Update `web/frontend/src/App.tsx` (or parent component):**

```tsx
import { useState, useEffect } from 'react';
import { GameSetup } from './components/GameSetup';
import { GameView } from './components/GameView';
import { getGameScenarios, createGame } from './api';
import type { GameScenario, GameSetupConfig } from './types';

function GameFlow() {
  const [gameId, setGameId] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<GameScenario[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGameScenarios()
      .then(setScenarios)
      .catch((e) => setError(e.message));
  }, []);

  const handleStart = async (config: GameSetupConfig) => {
    setLoading(true);
    setError(null);
    try {
      const result = await createGame(config);
      setGameId(result.game_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setGameId(null);
  };

  if (gameId) {
    return <GameView gameId={gameId} onBack={handleBack} />;
  }

  return (
    <>
      {error && (
        <div className="max-w-4xl mx-auto p-4">
          <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-2 rounded">
            {error}
          </div>
        </div>
      )}
      <GameSetup scenarios={scenarios} loading={loading} onStart={handleStart} />
    </>
  );
}
```

### Step 3.3: Refactor

- Add `onBack` prop to `GameView` for returning to setup
- Ensure game cleanup (`DELETE /api/games/{id}`) on back navigation
- Consider URL-based routing (`/game/:id`) for shareable links

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/api.ts` | Modify | Add `getGameScenarios()`, update `createGame()` |
| `web/frontend/src/App.tsx` | Modify | Add GameFlow with setup → game transition |
| `web/frontend/src/components/GameView.tsx` | Modify | Add `onBack` prop |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
# Manual: start frontend + backend, verify flow works
```

## Completion Criteria

- [ ] Scenarios load on mount from `/api/games/scenarios`
- [ ] Clicking "Start Game" calls `POST /api/games` with config
- [ ] On success, transitions to GameView with new gameId
- [ ] Error states display correctly (network error, invalid scenario)
- [ ] "Back" button returns to setup screen
- [ ] Loading spinner shown during game creation
