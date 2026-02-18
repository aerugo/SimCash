# Bug Fix: Event Builder Field Name Mismatch

## Problem

The `EventTimelineBuilder.tsx` `PARAM_FIELDS` uses different field names than the engine expects for several event types. Events created via the builder fail validation.

## Field Mapping (Current → Correct)

| Event Type | Builder Field | Engine Field | Source |
|---|---|---|---|
| `GlobalArrivalRateChange` | `new_rate` | `multiplier` | `docs/reference/scenario/scenario-events.md` |
| `AgentArrivalRateChange` | `agent_id` | `agent` | same |
| `AgentArrivalRateChange` | `new_rate` | `multiplier` | same |
| `CollateralAdjustment` | `agent_id` | `agent` | same |
| `CollateralAdjustment` | `amount` | `delta` | same |
| `DeadlineWindowChange` | `new_min` | `min_ticks_multiplier` | same |
| `DeadlineWindowChange` | `new_max` | `max_ticks_multiplier` | same |

Additionally, `LiquidityInjection` and `CreditLimitChange` are NOT real engine event types — they don't exist in the reference docs or the Rust engine.

## Fix

### Phase 1: Fix PARAM_FIELDS mapping

**File: `web/frontend/src/components/EventTimelineBuilder.tsx`**

```typescript
const PARAM_FIELDS: Record<EventType, FieldDef[]> = {
  DirectTransfer: [
    { key: 'from_agent', label: 'From Agent', type: 'agent' },
    { key: 'to_agent', label: 'To Agent', type: 'agent' },
    { key: 'amount', label: 'Amount', type: 'number' },
  ],
  GlobalArrivalRateChange: [
    { key: 'multiplier', label: 'Rate Multiplier', type: 'number' },
  ],
  AgentArrivalRateChange: [
    { key: 'agent', label: 'Agent', type: 'agent' },
    { key: 'multiplier', label: 'Rate Multiplier', type: 'number' },
  ],
  DeadlineWindowChange: [
    { key: 'min_ticks_multiplier', label: 'Min Ticks Multiplier', type: 'number' },
    { key: 'max_ticks_multiplier', label: 'Max Ticks Multiplier', type: 'number' },
  ],
  CollateralAdjustment: [
    { key: 'agent', label: 'Agent', type: 'agent' },
    { key: 'delta', label: 'Delta (±cents)', type: 'number' },
  ],
};
```

### Phase 2: Remove fake event types

Remove `LiquidityInjection` and `CreditLimitChange` from:
- `EVENT_TYPES` in `types.ts`
- `PARAM_FIELDS`, `EVENT_COLORS`, `EVENT_LABELS` in `EventTimelineBuilder.tsx`

These don't exist in the engine. If we want them later, they need Rust implementation first.

### Phase 3: Update labels for clarity

- "Rate Multiplier" instead of "New Rate" (it's a multiplier, not an absolute rate)
- "Delta (±cents)" instead of "Amount" for CollateralAdjustment (delta can be negative)
- "Min/Max Ticks Multiplier" instead of "New Min/Max"

## Tests

- Create a GlobalArrivalRateChange event via builder → validate scenario → should pass
- Create a CollateralAdjustment event → YAML contains `agent` and `delta` (not `agent_id` and `amount`)
- Ensure removed event types don't appear in dropdown

## Scope

- **Files**: 2 frontend (EventTimelineBuilder.tsx, types.ts)
- **Effort**: 15 minutes
- **Risk**: Low — frontend only, no engine changes
