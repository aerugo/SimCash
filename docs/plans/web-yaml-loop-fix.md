# YAML ↔ Form Infinite Update Loop — Fix Plan

**Status**: Draft
**Date**: 2026-02-19
**Branch**: `feature/interactive-web-sandbox`

## Problem

The Scenario Editor crashes with "Maximum update depth exceeded" when switching between Form and YAML views, or when the form-generated YAML differs from the input YAML.

### Root Cause

`ScenarioForm` works in a round-trip cycle:

```
yaml (prop) → parseYamlToForm(yaml) → data (form state)
user edits → mutate data → formToYaml(data) → onYamlChange(newYaml)
parent setYaml(newYaml) → new yaml prop → parseYamlToForm → ...
```

The loop occurs because **`formToYaml(parseYamlToForm(yaml))` is not idempotent**:

1. **Field rename**: Input has `eod_penalty_per_transaction: 100000`, parser outputs `eod_penalty: {mode: fixed, amount: 100000}` — different YAML text
2. **PenaltyMode normalization**: Bare int `50000` becomes `{mode: fixed, amount: 50000}` — different YAML text
3. **Key ordering**: `jsYaml.dump` may reorder keys differently from the original
4. **Float precision**: `0.2` might round-trip as `0.2000000001` etc.

Each difference produces a new YAML string → re-triggers parse → produces another slightly different YAML → infinite loop.

## Solution

**Make `ScenarioForm` own its form state internally, only syncing outward.** Stop re-parsing the YAML prop on every render.

### Approach: Internal State with Controlled Sync

```
yaml prop → parseYamlToForm → initial form state (only on mount or explicit YAML edit)
form edits → update internal state → formToYaml → onYamlChange (outward only)
```

Key changes:

1. **`ScenarioForm` uses `useState` for form data** instead of `useMemo` from the yaml prop
2. **Only re-parse from yaml when the user explicitly edits the YAML text** (i.e., when switching from YAML tab back to Form tab)
3. **Add a `yamlGeneration` counter** — the parent increments it when the yaml changes externally (template selection, YAML editor), and ScenarioForm re-parses only when the generation changes

### Alternative (simpler): Debounce + String Comparison

After `formToYaml(copy)`, compare the result with the current `yaml` prop. If they produce the same `parseYamlToForm` output (deep-equal the form data), don't call `onYamlChange`. This avoids the loop without restructuring state ownership.

Implementation:
- In `update()`, after computing `newYaml = formToYaml(copy)`:
  - Parse it back: `roundTripped = parseYamlToForm(newYaml)`
  - `formToYaml(roundTripped)` → if it equals `newYaml`, the round-trip is stable, safe to emit
  - The key insight: only emit if `newYaml !== yaml` (string compare) — if they're equal, no-op

Actually the simplest fix:

### **Recommended Fix: Compare Before Emitting**

In `ScenarioForm.update()`:

```typescript
const update = useCallback((mutate: (d: ScenarioFormData) => void) => {
  if (!data) return;
  const copy: ScenarioFormData = JSON.parse(JSON.stringify(data));
  mutate(copy);
  const newYaml = formToYaml(copy);
  if (newYaml !== yaml) {  // ← only emit if actually different
    onYamlChange(newYaml);
  }
}, [data, onYamlChange, yaml]);
```

**But this alone isn't enough** — the problem is also in the initial parse. When yaml first arrives with `eod_penalty_per_transaction`, `parseYamlToForm` renames it to `eod_penalty`, and `formToYaml` emits `eod_penalty`. Next render, `yaml` has `eod_penalty_per_transaction` again (parent hasn't changed), so they're always different → loop.

### **Full Fix**

1. **`ScenarioForm` uses `useState` + `useEffect` with stabilization:**

```typescript
export function ScenarioForm({ yaml, onYamlChange }: Props) {
  const [data, setData] = useState<ScenarioFormData | null>(() => parseYamlToForm(yaml));
  const [lastYaml, setLastYaml] = useState(yaml);

  // Re-parse only when yaml prop changes externally
  if (yaml !== lastYaml) {
    const newData = parseYamlToForm(yaml);
    if (newData && JSON.stringify(newData) !== JSON.stringify(data)) {
      setData(newData);
    }
    setLastYaml(yaml);
  }

  const update = useCallback((mutate: (d: ScenarioFormData) => void) => {
    setData(prev => {
      if (!prev) return prev;
      const copy: ScenarioFormData = JSON.parse(JSON.stringify(prev));
      mutate(copy);
      onYamlChange(formToYaml(copy));
      return copy;
    });
  }, [onYamlChange]);
```

This way:
- Form state is internal (`useState`), not re-derived every render
- External yaml changes (template pick, YAML editor) sync in via the `yaml !== lastYaml` check
- Form edits emit outward but don't re-trigger a parse loop
- `JSON.stringify` deep-compare prevents unnecessary state updates

## Files

| File | Changes |
|------|---------|
| `web/frontend/src/components/ScenarioForm.tsx` | Refactor state management (see above) |

## Tests

- `npx tsc -b` + `npm run build` must pass
- UI: Open editor → edit form fields → switch to YAML tab → no crash
- UI: Edit YAML directly → switch to Form tab → form shows correct values
- UI: Pick template → form updates → no crash
- Console: zero "Maximum update depth exceeded" errors

## Verification

```bash
cd web/frontend && npx tsc -b && npm run build
```

UI test:
1. Open /create
2. Change ticks_per_day from 12 to 6
3. Switch to YAML tab — VERIFY: no crash, YAML shows ticks_per_day: 6
4. Switch back to Form — VERIFY: shows 6
5. Switch Deadline Penalty to Rate mode, set 50 bps
6. Switch to YAML tab — VERIFY: shows `deadline_penalty: {mode: rate, bps_per_event: 50}`
7. Open console — VERIFY: zero "Maximum update depth" errors

## Risk

Low — the form component is self-contained, no other components depend on its internal state management pattern.
