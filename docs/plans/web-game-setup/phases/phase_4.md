# Phase 4: Polish — Scenario Descriptions, Cost Preview, Validation

**Status**: Pending

---

## Objective

Enrich the setup UI with detailed scenario descriptions, cost parameter previews (showing what delay/penalty/opportunity costs look like), and client-side input validation with helpful error messages.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — cost rates displayed as dollars but stored/sent as integer cents

---

## TDD Steps

### Step 4.1: Cost Rate Preview (RED)

Need a helper that formats cost rates for human display:

```typescript
// web/frontend/src/utils/format.ts
export function formatCostRate(key: string, value: number): string {
  // cost rates are in various units — format appropriately
  if (key.includes('bps')) return `${value} bps`;
  if (key.includes('penalty')) return `$${(value / 100).toFixed(2)}`;
  if (key.includes('per_cent')) return `${value}¢/tick`;
  return `${value}`;
}

export function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
}
```

### Step 4.2: Enhanced Scenario Cards (GREEN)

Update `GameSetup.tsx` scenario cards to show cost breakdown:

```tsx
{/* Inside scenario card */}
{s.cost_rates && (
  <div className="mt-3 space-y-1">
    <p className="text-xs text-gray-500 font-semibold">Cost Parameters:</p>
    {Object.entries(s.cost_rates).slice(0, 3).map(([k, v]) => (
      <div key={k} className="flex justify-between text-xs text-gray-500">
        <span>{k.replace(/_/g, ' ')}</span>
        <span className="font-mono">{formatCostRate(k, v)}</span>
      </div>
    ))}
  </div>
)}
```

### Step 4.3: Client-Side Validation (GREEN)

Add validation before calling API:

```tsx
const validate = (config: GameSetupConfig): string | null => {
  if (config.max_days < 1 || config.max_days > 100) return 'Days must be 1-100';
  if (config.num_eval_samples < 1 || config.num_eval_samples > 50) return 'Eval samples must be 1-50';
  if (config.use_llm && config.num_eval_samples > 10) {
    return 'With real LLM, keep eval samples ≤ 10 (each costs API credits)';
  }
  return null;
};
```

### Step 4.4: Refactor

- Add tooltips explaining each parameter
- Show estimated runtime (mock: ~1s/day, LLM: ~30-120s/day)
- Highlight recommended settings for new users

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/utils/format.ts` | Create | Cost formatting helpers |
| `web/frontend/src/components/GameSetup.tsx` | Modify | Cost preview, validation, tooltips |

## Verification

```bash
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
# Manual: verify cost rates display correctly for each scenario
```

## Completion Criteria

- [ ] Each scenario card shows top cost parameters formatted as dollars/bps
- [ ] Client-side validation prevents invalid configs
- [ ] Warning shown for expensive LLM + high sample count combos
- [ ] Estimated runtime displayed based on config
- [ ] All money values display in dollars (converted from cents)
