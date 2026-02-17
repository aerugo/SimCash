# Phase 1: Event Summary with Collapsible Detail

**Status**: Pending

## Objective

Categorize events by type and show a compact summary. Full event list available via toggle.

## Invariants

- INV-UI-9: All events remain accessible

## TDD Steps

### Step 1.1: RED — Write Failing Test

Create `web/frontend/src/__tests__/EventSummary.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { EventSummary } from '../components/EventSummary';
import { describe, it, expect } from 'vitest';

const events = [
  { tick: 0, event_type: 'PaymentArrival', sender_id: 'A', receiver_id: 'B', amount: 5000 },
  { tick: 0, event_type: 'PaymentArrival', sender_id: 'B', receiver_id: 'A', amount: 3000 },
  { tick: 1, event_type: 'Settlement', sender_id: 'A', receiver_id: 'B', amount: 5000 },
  { tick: 1, event_type: 'CostAccrual', agent_id: 'A' },
  { tick: 1, event_type: 'CostAccrual', agent_id: 'B' },
  { tick: 2, event_type: 'Settlement', sender_id: 'B', receiver_id: 'A', amount: 3000 },
];

describe('EventSummary', () => {
  it('shows compact summary counts', () => {
    render(<EventSummary events={events} dayNum={1} />);
    expect(screen.getByText(/2 arrivals/i)).toBeInTheDocument();
    expect(screen.getByText(/2 settlements/i)).toBeInTheDocument();
    expect(screen.getByText(/2 cost accruals/i)).toBeInTheDocument();
  });

  it('hides individual events by default', () => {
    render(<EventSummary events={events} dayNum={1} />);
    expect(screen.queryByText('PaymentArrival')).toBeNull();
  });

  it('shows all events when expanded', () => {
    render(<EventSummary events={events} dayNum={1} />);
    fireEvent.click(screen.getByText(/show all/i));
    expect(screen.getAllByText('PaymentArrival').length).toBe(2);
    expect(screen.getAllByText('Settlement').length).toBe(2);
  });
});
```

### Step 1.2: GREEN — Implement

Create `web/frontend/src/components/EventSummary.tsx`:

```tsx
import { useState, useMemo } from 'react';

interface Props {
  events: Record<string, unknown>[];
  dayNum: number;
}

export function EventSummary({ events, dayNum }: Props) {
  const [expanded, setExpanded] = useState(false);

  const summary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of events) {
      const t = String(e.event_type ?? 'unknown');
      counts[t] = (counts[t] ?? 0) + 1;
    }
    return counts;
  }, [events]);

  const labels: Record<string, string> = {
    PaymentArrival: 'arrivals',
    Settlement: 'settlements',
    CostAccrual: 'cost accruals',
    DeadlinePenalty: 'penalties',
    LiquidityCommit: 'liquidity commits',
  };

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-300">
          Day {dayNum} Events ({events.length})
        </h3>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          {expanded ? '▲ Hide' : '▼ Show all'}
        </button>
      </div>

      {/* Summary line */}
      <div className="flex flex-wrap gap-2 text-xs text-slate-400">
        {Object.entries(summary).map(([type, count]) => (
          <span key={type} className="bg-slate-900/50 rounded px-2 py-0.5">
            {count} {labels[type] ?? type}
          </span>
        ))}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="mt-3 max-h-48 overflow-y-auto text-xs font-mono text-slate-400 space-y-0.5">
          {events.map((e, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-slate-600 w-6">{String(e.tick)}</span>
              <span className="text-sky-400">{String(e.event_type)}</span>
              {'sender_id' in e && <span>{String(e.sender_id)}→{String(e.receiver_id)}</span>}
              {'amount' in e && <span className="text-emerald-400">${(Number(e.amount) / 100).toLocaleString()}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

Replace the events section in `GameView.tsx`:

```tsx
// Before: raw event dump
// After:
{day && day.events.length > 0 && (
  <EventSummary events={day.events} dayNum={day.day + 1} />
)}
```

### Step 1.3: REFACTOR

Remove the old inline event rendering code.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/components/EventSummary.tsx` | Create |
| `web/frontend/src/views/GameView.tsx` | Modify — use EventSummary |
| `web/frontend/src/__tests__/EventSummary.test.tsx` | Create |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/EventSummary.test.tsx
```

## Completion Criteria

- [ ] Compact summary shows event type counts
- [ ] Events hidden by default
- [ ] Expandable to show all events
- [ ] Tests pass
