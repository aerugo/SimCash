# Phase 2: Frontend — Start Game from Custom Builder

**Status**: Pending

## Objective

Add a "🎮 Start Game" button to the Custom Builder tab that creates a multi-day game using the current custom config.

## Invariants

- INV-1: Money is i64

## TDD Steps

### Step 2.1: RED — Write Failing Test

Add to `web/frontend/src/__tests__/HomeView.test.tsx`:

```tsx
it('shows Start Game button on Custom Builder tab', () => {
  render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
  fireEvent.click(screen.getByText('🛠 Custom Builder'));
  expect(screen.getByText('🎮 Start Game')).toBeInTheDocument();
});

it('calls onGameLaunch with inline_config when Start Game clicked', () => {
  const onGameLaunch = vi.fn();
  render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={onGameLaunch} />);
  fireEvent.click(screen.getByText('🛠 Custom Builder'));
  fireEvent.click(screen.getByText('🎮 Start Game'));
  expect(onGameLaunch).toHaveBeenCalledWith(
    expect.objectContaining({ inline_config: expect.any(Object) })
  );
});
```

### Step 2.2: GREEN — Implement

In `HomeView.tsx`, add after the Custom Builder actions row:

```tsx
{mode === 'custom' && onGameLaunch && (
  <button
    onClick={() => onGameLaunch({
      inline_config: config,
      use_llm: config.use_llm,
      mock_reasoning: config.mock_reasoning,
      max_days: 10,
      num_eval_samples: 1,
    })}
    className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-500 to-pink-500 font-semibold text-white hover:from-violet-400 hover:to-pink-400 transition-all shadow-lg shadow-violet-500/20 mt-4"
  >
    🎮 Start Game
  </button>
)}
```

Update `web/frontend/src/types.ts` to extend `GameSetupConfig`:

```tsx
export interface GameSetupConfig {
  scenario_id?: string;
  inline_config?: Record<string, unknown>;
  use_llm: boolean;
  mock_reasoning: boolean;
  max_days: number;
  num_eval_samples: number;
}
```

Update `web/frontend/src/api.ts` `createGame` to pass `inline_config`:

```tsx
export async function createGame(config: GameSetupConfig) {
  const resp = await fetch(`${API}/api/games`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return resp.json();
}
```

### Step 2.3: REFACTOR

Ensure consistent styling between "Start Game" and "Launch Simulation" buttons.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/HomeView.tsx` | Modify — add Start Game button |
| `web/frontend/src/types.ts` | Modify — extend GameSetupConfig |
| `web/frontend/src/api.ts` | Modify — pass inline_config |
| `web/frontend/src/__tests__/HomeView.test.tsx` | Modify |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/HomeView.test.tsx
```

## Completion Criteria

- [ ] "Start Game" button appears on Custom Builder tab
- [ ] Clicking it calls onGameLaunch with inline_config
- [ ] Tests pass
