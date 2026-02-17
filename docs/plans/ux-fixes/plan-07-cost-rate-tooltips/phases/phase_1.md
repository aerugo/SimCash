# Phase 1: Add Tooltips to Cost Rate Badges

**Status**: Pending

## Objective

Add `title` attributes to cost rate spans in scenario cards with plain-language explanations.

## Invariants

- INV-UI-10: Tooltip text must be accurate

## TDD Steps

### Step 1.1: RED — Write Failing Test

Add to `web/frontend/src/__tests__/HomeView.test.tsx`:

```tsx
import { waitFor } from '@testing-library/react';

// Update mock to return scenarios with cost_rates
vi.mock('../api', () => ({
  getGameScenarios: vi.fn().mockResolvedValue([
    {
      id: '2bank_12tick',
      name: 'Test Scenario',
      description: 'desc',
      ticks_per_day: 12,
      num_agents: 2,
      cost_rates: {
        liquidity_cost_per_tick_bps: 83,
        delay_cost_per_tick_per_cent: 0.2,
        deadline_penalty: 50000,
      },
    },
  ]),
}));

describe('Cost rate tooltips', () => {
  it('has tooltip on liquidity cost badge', async () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    await waitFor(() => {
      const badge = screen.getByTitle(/liquidity cost/i);
      expect(badge).toBeInTheDocument();
    });
  });

  it('has tooltip on delay cost badge', async () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    await waitFor(() => {
      const badge = screen.getByTitle(/delay cost/i);
      expect(badge).toBeInTheDocument();
    });
  });

  it('has tooltip on deadline penalty badge', async () => {
    render(<HomeView presets={mockPresets} onLaunch={vi.fn()} onGameLaunch={vi.fn()} />);
    await waitFor(() => {
      const badge = screen.getByTitle(/deadline penalty/i);
      expect(badge).toBeInTheDocument();
    });
  });
});
```

### Step 1.2: GREEN — Implement

In `HomeView.tsx`, update the cost rate badges in the scenario cards:

```tsx
{s.cost_rates && (
  <div className="text-xs text-slate-500 mt-2 flex gap-3">
    <span title={`Liquidity cost: ${s.cost_rates.liquidity_cost_per_tick_bps} basis points of committed funds charged per tick`}>
      💰 {s.cost_rates.liquidity_cost_per_tick_bps} bps
    </span>
    <span title={`Delay cost: ${s.cost_rates.delay_cost_per_tick_per_cent} cents per cent of unsettled payment per tick`}>
      ⏱ {s.cost_rates.delay_cost_per_tick_per_cent}/¢/tick
    </span>
    <span title={`Deadline penalty: $${(s.cost_rates.deadline_penalty / 100).toLocaleString()} per unsettled payment at end of day`}>
      ⚠️ ${(s.cost_rates.deadline_penalty / 100).toLocaleString()}
    </span>
  </div>
)}
```

### Step 1.3: REFACTOR

Consider extracting tooltip text to constants for reuse (Custom Builder has similar fields).

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/views/HomeView.tsx` | Modify — add title attributes |
| `web/frontend/src/__tests__/HomeView.test.tsx` | Modify — tooltip tests |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/HomeView.test.tsx
```

## Completion Criteria

- [ ] All three cost rate badges have hover tooltips
- [ ] Tooltip text explains the parameter in plain language
- [ ] Tests pass
