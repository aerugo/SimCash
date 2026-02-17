# Phase 1: Create HowItWorks Component

**Status**: Pending

## Objective

Build a collapsible explainer component with four sections explaining SimCash.

## Invariants

- INV-UI-6: Must be collapsible
- INV-UI-7: Content accuracy

## TDD Steps

### Step 1.1: RED — Write Failing Test

Create `web/frontend/src/__tests__/HowItWorks.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { HowItWorks } from '../components/HowItWorks';
import { describe, it, expect } from 'vitest';

describe('HowItWorks', () => {
  it('renders collapsed by default with toggle button', () => {
    render(<HowItWorks />);
    expect(screen.getByText(/How It Works/)).toBeInTheDocument();
    // Content should be hidden initially
    expect(screen.queryByText(/RTGS/)).toBeNull();
  });

  it('expands to show content when clicked', () => {
    render(<HowItWorks />);
    fireEvent.click(screen.getByText(/How It Works/));
    expect(screen.getByText(/RTGS/)).toBeInTheDocument();
    expect(screen.getByText(/initial_liquidity_fraction/)).toBeInTheDocument();
  });

  it('collapses again on second click', () => {
    render(<HowItWorks />);
    fireEvent.click(screen.getByText(/How It Works/));
    expect(screen.getByText(/RTGS/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/How It Works/));
    expect(screen.queryByText(/RTGS/)).toBeNull();
  });

  it('shows all four explanation sections', () => {
    render(<HowItWorks />);
    fireEvent.click(screen.getByText(/How It Works/));
    expect(screen.getByText(/What This Simulates/)).toBeInTheDocument();
    expect(screen.getByText(/The Game Loop/)).toBeInTheDocument();
    expect(screen.getByText(/Key Parameter/)).toBeInTheDocument();
    expect(screen.getByText(/Cost Tradeoffs/)).toBeInTheDocument();
  });
});
```

### Step 1.2: GREEN — Implement

Create `web/frontend/src/components/HowItWorks.tsx`:

```tsx
import { useState } from 'react';

interface Props {
  defaultOpen?: boolean;
}

export function HowItWorks({ defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 mb-6">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <span className="text-sm font-semibold text-slate-300">
          💡 How It Works
        </span>
        <span className="text-slate-500 text-xs">
          {open ? '▲ hide' : '▼ show'}
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 text-sm text-slate-400">
          <div>
            <h4 className="font-medium text-slate-300 mb-1">🏦 What This Simulates</h4>
            <p>
              An RTGS (Real-Time Gross Settlement) payment system where banks must decide
              how much liquidity to commit each day. Banks face a strategic tradeoff:
              commit more liquidity (costly) or risk payment delays and penalties.
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">🔄 The Game Loop</h4>
            <p>
              Each day: (1) Banks commit liquidity based on their policy, (2) Payments
              arrive and settle in real-time, (3) Costs are tallied, (4) An AI agent
              analyzes the results and proposes improved policies for the next day.
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">🎯 Key Parameter</h4>
            <p>
              <code className="text-xs bg-slate-900 px-1 py-0.5 rounded text-sky-400">
                initial_liquidity_fraction
              </code>{' '}
              — the fraction of a bank's liquidity pool to commit at the start of each day
              (0.0 = commit nothing, 1.0 = commit everything). The AI optimizes this value.
            </p>
          </div>

          <div>
            <h4 className="font-medium text-slate-300 mb-1">⚖️ Cost Tradeoffs</h4>
            <p>
              Three competing costs: <strong>Liquidity cost</strong> (proportional to
              committed funds per tick), <strong>Delay cost</strong> (per cent of unsettled
              payment per tick), and <strong>Deadline penalty</strong> (fixed fee per
              unsettled payment at end of day). The optimal fraction balances all three.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Step 1.3: REFACTOR

Clean up — no major refactoring needed for a self-contained component.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/components/HowItWorks.tsx` | Create |
| `web/frontend/src/__tests__/HowItWorks.test.tsx` | Create |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/HowItWorks.test.tsx
```

## Completion Criteria

- [ ] Component renders collapsed by default
- [ ] Clicking expands/collapses
- [ ] All four sections render with accurate content
- [ ] Tests pass
