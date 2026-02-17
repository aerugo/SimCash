# Phase 2: Frontend — GameSetup Component with Scenario Cards + Config

**Status**: Pending

---

## Objective

Create a `GameSetup` component that displays available scenarios as selectable cards, provides configuration sliders for max_days and num_eval_samples, and toggles for mock/real LLM. This is a pure UI component — wiring to the API happens in Phase 3.

---

## Invariants Enforced in This Phase

- INV-1: Money display — cost rates shown in dollars (converted from integer cents)
- INV-GAME-1: Policy Reality — show that different scenarios have different cost structures

---

## TDD Steps

### Step 2.1: Define Types (RED — types don't compile without implementation)

**Add to `web/frontend/src/types.ts`:**

```typescript
export interface GameScenario {
  id: string;
  name: string;
  description: string;
  num_agents: number;
  ticks_per_day: number;
  cost_rates: Record<string, number>;
  difficulty: string;
}

export interface GameSetupConfig {
  scenario_id: string;
  use_llm: boolean;
  mock_reasoning: boolean;
  max_days: number;
  num_eval_samples: number;
}
```

### Step 2.2: Build Component (GREEN)

**Create `web/frontend/src/components/GameSetup.tsx`:**

```tsx
import { useState } from 'react';
import type { GameScenario, GameSetupConfig } from '../types';

interface GameSetupProps {
  scenarios: GameScenario[];
  loading: boolean;
  onStart: (config: GameSetupConfig) => void;
}

export function GameSetup({ scenarios, loading, onStart }: GameSetupProps) {
  const [selectedScenario, setSelectedScenario] = useState<string>('2bank_12tick');
  const [maxDays, setMaxDays] = useState(10);
  const [useLlm, setUseLlm] = useState(false);
  const [mockReasoning, setMockReasoning] = useState(true);
  const [numEvalSamples, setNumEvalSamples] = useState(1);

  const handleStart = () => {
    onStart({
      scenario_id: selectedScenario,
      use_llm: useLlm,
      mock_reasoning: mockReasoning,
      max_days: maxDays,
      num_eval_samples: numEvalSamples,
    });
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-3xl font-bold text-white">New Game</h1>

      {/* Scenario Selection */}
      <section>
        <h2 className="text-xl font-semibold text-gray-200 mb-4">Choose Scenario</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {scenarios.map((s) => (
            <button
              key={s.id}
              onClick={() => setSelectedScenario(s.id)}
              className={`p-4 rounded-lg border-2 text-left transition-all ${
                selectedScenario === s.id
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-gray-700 bg-gray-800 hover:border-gray-500'
              }`}
            >
              <h3 className="font-semibold text-white">{s.name}</h3>
              <p className="text-sm text-gray-400 mt-1">{s.description}</p>
              <div className="flex gap-3 mt-3 text-xs text-gray-500">
                <span>{s.num_agents} agents</span>
                <span>{s.ticks_per_day} ticks/day</span>
                <span className="capitalize">{s.difficulty}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* Configuration */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-200">Configuration</h2>

        {/* Max Days */}
        <div>
          <label className="text-sm text-gray-400">
            Days: <span className="text-white font-mono">{maxDays}</span>
          </label>
          <input
            type="range"
            min={1}
            max={50}
            value={maxDays}
            onChange={(e) => setMaxDays(Number(e.target.value))}
            className="w-full mt-1"
          />
        </div>

        {/* Eval Samples */}
        <div>
          <label className="text-sm text-gray-400">
            Eval Samples: <span className="text-white font-mono">{numEvalSamples}</span>
          </label>
          <input
            type="range"
            min={1}
            max={20}
            value={numEvalSamples}
            onChange={(e) => setNumEvalSamples(Number(e.target.value))}
            className="w-full mt-1"
          />
          <p className="text-xs text-gray-500 mt-1">
            More samples = more robust cost estimates, but slower
          </p>
        </div>

        {/* LLM Toggle */}
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-gray-300">
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(e) => {
                setUseLlm(e.target.checked);
                if (e.target.checked) setMockReasoning(false);
              }}
            />
            Use Real LLM (GPT-5.2)
          </label>

          {!useLlm && (
            <label className="flex items-center gap-2 text-gray-400 text-sm">
              <input
                type="checkbox"
                checked={mockReasoning}
                onChange={(e) => setMockReasoning(e.target.checked)}
              />
              Mock reasoning
            </label>
          )}
        </div>
      </section>

      {/* Start Button */}
      <button
        onClick={handleStart}
        disabled={loading}
        className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white font-semibold rounded-lg transition-colors"
      >
        {loading ? 'Creating game...' : 'Start Game'}
      </button>
    </div>
  );
}
```

### Step 2.3: Refactor

- Extract `ScenarioCard` as a sub-component if the file grows
- Ensure slider accessibility (aria-label, keyboard support)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/types.ts` | Modify | Add `GameScenario`, `GameSetupConfig` types |
| `web/frontend/src/components/GameSetup.tsx` | Create | Setup component with scenario cards + config |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] `GameSetup` component renders scenario cards from props
- [ ] Selected scenario has visual highlight
- [ ] max_days slider works (1-50, default 10)
- [ ] num_eval_samples slider works (1-20, default 1)
- [ ] LLM toggle switches between real/mock
- [ ] `onStart` callback fires with correct `GameSetupConfig`
- [ ] TypeScript compiles without errors
