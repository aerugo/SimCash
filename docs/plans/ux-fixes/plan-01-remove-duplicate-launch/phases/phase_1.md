# Phase 1: Conditionally Render Launch Section

**Status**: Pending

## Objective

Hide the "AI Reasoning" toggle and "Launch Simulation" button when the Multi-Day Game tab is active.

## Invariants

- INV-UI-1: Game tab must not show Launch Simulation
- INV-UI-2: Presets and Custom Builder tabs must still show it

## TDD Steps

### Step 1.1: RED — Write Failing Test

Create `web/frontend/src/__tests__/HomeView.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { HomeView } from '../views/HomeView';
import { vi, describe, it, expect } from 'vitest';

const mockPresets = [
  { id: 'exp1', name: 'Test Preset', description: 'desc', ticks_per_day: 2, num_agents: 2 },
];

// Mock the API call
vi.mock('../api', () => ({
  getGameScenarios: vi.fn().mockResolvedValue([]),
}));

describe('HomeView Launch button visibility', () => {
  it('does NOT show Launch Simulation on Game tab', () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    // Game tab is default (mode='game')
    expect(screen.queryByText('🚀 Launch Simulation')).toBeNull();
  });

  it('shows Launch Simulation on Presets tab', () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    fireEvent.click(screen.getByText('📋 Presets'));
    expect(screen.getByText('🚀 Launch Simulation')).toBeInTheDocument();
  });

  it('shows Launch Simulation on Custom Builder tab', () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    fireEvent.click(screen.getByText('🛠 Custom Builder'));
    expect(screen.getByText('🚀 Launch Simulation')).toBeInTheDocument();
  });

  it('shows AI Reasoning section on Presets tab but not Game tab', () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    // Game tab (default) — no AI Reasoning section for single-run
    expect(screen.queryByText('🧠 AI Agent Reasoning (GPT-5.2)')).toBeNull();

    fireEvent.click(screen.getByText('📋 Presets'));
    expect(screen.getByText('🧠 AI Agent Reasoning (GPT-5.2)')).toBeInTheDocument();
  });
});
```

**Expected**: Tests fail because Launch Simulation renders on all tabs.

### Step 1.2: GREEN — Implement Fix

In `web/frontend/src/views/HomeView.tsx`, wrap the AI Reasoning section and Launch button in a `mode !== 'game'` check:

```tsx
// Before (unconditional):
      {/* AI Reasoning */}
      <div className="bg-slate-800/50 ...">
        ...
      </div>

      <button onClick={handleLaunch} ...>
        🚀 Launch Simulation
      </button>

// After (conditional):
      {mode !== 'game' && (
        <>
          {/* AI Reasoning */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-300">🧠 AI Agent Reasoning (GPT-5.2)</h3>
                <p className="text-xs text-slate-500 mt-1">Watch agents think through decisions in real-time</p>
              </div>
              <Toggle label="" value={config.use_llm} onChange={v => setConfig({ ...config, use_llm: v })} />
            </div>
            {config.use_llm && (
              <div className="flex items-center justify-between pt-3 border-t border-slate-700/50">
                <div>
                  <span className="text-xs text-slate-400">Mock Mode</span>
                  <span className="text-[10px] text-slate-600 ml-2">
                    {config.mock_reasoning ? '(no API costs)' : '⚠ Uses OpenAI API'}
                  </span>
                </div>
                <Toggle label="" value={config.mock_reasoning} onChange={v => setConfig({ ...config, mock_reasoning: v })} />
              </div>
            )}
          </div>

          <button
            onClick={handleLaunch}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-violet-500 font-semibold text-white hover:from-sky-400 hover:to-violet-400 transition-all shadow-lg shadow-sky-500/20"
          >
            🚀 Launch Simulation
          </button>
        </>
      )}
```

### Step 1.3: REFACTOR

No refactoring needed — this is a minimal one-line conditional wrapper.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/HomeView.tsx` | Modify — wrap bottom section in `{mode !== 'game' && ...}` |
| `web/frontend/src/__tests__/HomeView.test.tsx` | Create — visibility tests |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/HomeView.test.tsx
```

## Completion Criteria

- [ ] "Launch Simulation" button does NOT appear on Multi-Day Game tab
- [ ] "Launch Simulation" button appears on Presets and Custom Builder tabs
- [ ] AI Reasoning toggle section follows the same visibility rules
- [ ] All tests pass
