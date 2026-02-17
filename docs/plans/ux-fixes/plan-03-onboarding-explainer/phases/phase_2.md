# Phase 2: Integrate into HomeView + localStorage Persistence

**Status**: Pending

## Objective

Add HowItWorks to HomeView and persist collapse state in localStorage so returning users don't see it repeatedly.

## Invariants

- INV-UI-6: Collapsible, remembers state

## TDD Steps

### Step 2.1: RED — Write Failing Test

Add to `web/frontend/src/__tests__/HowItWorks.test.tsx`:

```tsx
describe('HowItWorks localStorage', () => {
  beforeEach(() => localStorage.clear());

  it('reads initial state from localStorage', () => {
    localStorage.setItem('simcash-how-it-works-dismissed', 'true');
    render(<HowItWorks />);
    expect(screen.queryByText(/RTGS/)).toBeNull();
  });

  it('saves collapsed state to localStorage', () => {
    render(<HowItWorks defaultOpen={true} />);
    fireEvent.click(screen.getByText(/How It Works/));
    expect(localStorage.getItem('simcash-how-it-works-dismissed')).toBe('true');
  });
});
```

### Step 2.2: GREEN — Implement

Update `HowItWorks.tsx` to use localStorage:

```tsx
export function HowItWorks({ defaultOpen = false }: Props) {
  const [open, setOpen] = useState(() => {
    const dismissed = localStorage.getItem('simcash-how-it-works-dismissed');
    if (dismissed === 'true') return false;
    return defaultOpen;
  });

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (!next) {
      localStorage.setItem('simcash-how-it-works-dismissed', 'true');
    }
  };

  // ... replace onClick with toggle
```

Add to `HomeView.tsx` after the header, before mode toggle:

```tsx
import { HowItWorks } from '../components/HowItWorks';

// Inside return, after the header <div>:
<HowItWorks defaultOpen={true} />
```

### Step 2.3: REFACTOR

No significant refactoring.

## Files Changed

| File | Action |
|------|--------|
| `web/frontend/src/components/HowItWorks.tsx` | Modify — add localStorage |
| `web/frontend/src/views/HomeView.tsx` | Modify — import and render HowItWorks |
| `web/frontend/src/__tests__/HowItWorks.test.tsx` | Modify — localStorage tests |

## Verification

```bash
cd web/frontend && npx vitest run src/__tests__/HowItWorks.test.tsx
```

## Completion Criteria

- [ ] HowItWorks appears at top of HomeView
- [ ] Collapse state persists across page reloads
- [ ] Tests pass
