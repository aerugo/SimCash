# GameView UI Fixes — Implementation Plan

## Fix 1: Round → Day terminology (Frontend only)

**Files:** `web/frontend/src/views/GameView.tsx`

**Changes:**
- Line 566: `"Round Timeline"` → `"Day Timeline"`
- Line 574: `title` attr: `"Round ${i+1}"` → `"Day ${i+1}"`
- Line 597: `"Load Round {n} Replay"` → `"Load Day {n} Replay"`
- Line 885: `"Round ${selectedDay + 1} Reasoning"` → `"Day ${selectedDay + 1} Reasoning"`
- Line 1093: `"Round {day.day + 1} Events"` → `"Day {day.day + 1} Events"`
- Line 1319: Pills `R{i+1}` → `D{i+1}` (but see Fix 4 for day_num)
- Header (line ~288): already says "Day X/Y" — correct, leave as-is
- Button tooltips for Re-run (line 326): `"Re-run the last round"` → `"Re-run the last day"`

Search globally for "Round" and "round" in GameView.tsx and replace contextually. Don't change variable names, only user-facing strings.

---

## Fix 2: Empty reasoning note for non-thinking models (Frontend only)

**Files:** `web/frontend/src/views/GameView.tsx` — `ReasoningExplorer` component

**Find the `ReasoningExplorer` component** (search for `function ReasoningExplorer`). It likely has a section that shows thinking tokens. 

**Add:** When `result.thinking` is empty/null AND `result.usage?.thinking_tokens === 0` (or undefined), show:
```
"This model does not expose chain-of-thought reasoning tokens."
```
in a muted italic text where the thinking content would normally appear.

Only show this note if the result exists and has been completed (not mock). Don't show it for mock/simulated results.

---

## Fix 3: Policy Evolution always empty (Backend + Frontend)

### Backend (`web/backend/app/streaming_optimizer.py`):

The result dict at ~line 605 yields `new_policy`, `old_fraction`, `new_fraction` but NOT `old_policy`.

**Add `old_policy` to the result.** The current policy is passed into `stream_optimize` as part of the game state. Find where `current_fraction` is read (it comes from iterating the agent's current policy). At the same location, capture the full current policy dict and include it:

```python
"old_policy": current_policy,  # Add this alongside existing fields
```

Look for where `current_fraction` is extracted — that's where the current policy is accessible. The policy is in `game.policies[aid]` which should be passed through to the optimizer. Make a `copy.deepcopy()` before optimization mutates it.

### Backend (`web/backend/app/game.py`):

In `_apply_result()` (~line 478), the old policy is captured as `old_policy = self.policies[aid]` but only used for rollback. Ensure the `old_policy` from the streaming result is preserved (don't overwrite it).

### Frontend (`web/frontend/src/views/GameView.tsx`):

The Policy Evolution panel (lines 839-855) uses:
```tsx
const history = gameState.reasoning_history[aid] || [];
const latest = history[history.length - 1];
```

This only shows the LATEST entry. It should show the entry corresponding to the SELECTED day. Fix:
```tsx
// Find the reasoning entry for the selected day
const dayIndex = selectedDay ?? gameState.days.length - 1;
// reasoning_history entries should have day_num (see Fix 4)
// For now, use the last entry if selectedDay is null
const entry = history.find(r => r.day_num === dayIndex) ?? history[history.length - 1];
```

This depends on Fix 4 adding `day_num` to reasoning entries. As interim, keep current behavior but at least fix the old_policy issue so diffs work.

---

## Fix 4: Track failed optimizations + add day_num to reasoning entries (Backend + Frontend)

### Backend (`web/backend/app/game.py`):

**4a. Add `day_num` to optimization results.**

In `optimize_all_agents()`, before yielding results, tag each result with the day number:

```python
last_day = self.days[-1]
# ... after gathering results ...
for aid in self.agent_ids:
    if aid in results:
        results[aid]["day_num"] = last_day.day_num  # Add this
        self._store_prompt(last_day, aid, results[aid])
        self._apply_result(aid, results[aid])
```

**4b. Store fatal failures instead of silently discarding.**

Replace the fatal error path (lines 448-456):

```python
# BEFORE (silent discard):
if isinstance(r, Exception):
    await _send({"type": "experiment_error", ...})
    self.auto_run = False
    return {}

# AFTER (store failure for all agents):
if isinstance(r, Exception):
    error_msg = str(r)
    logger.error("Agent %s optimization failed fatally: %s", aid, error_msg)
    # Store failure record for ALL agents
    for a in self.agent_ids:
        failure_record = {
            "day_num": last_day.day_num,
            "failed": True,
            "failure_reason": f"Fatal LLM error for {aid}: {error_msg}",
            "reasoning": f"Optimization failed: {error_msg}",
            "accepted": False,
            "new_policy": None,
            "old_fraction": self.policies[a].get("parameters", {}).get("initial_liquidity_fraction"),
            "new_fraction": None,
            "mock": False,
        }
        self.reasoning_history[a].append(failure_record)
    await _send({"type": "experiment_error", ...})
    self.auto_run = False
    return {}
```

**4c. Track failed optimization on days.**

Add a `optimization_failed` field to `GameDay`:
- In `game.py` GameDay class: add `self.optimization_failed = False`
- In `main.py` WS handler: after failed optimization, set `day.optimization_failed = True`
- In serialization: persist and restore this field

### Frontend (`web/frontend/src/views/GameView.tsx`):

**4d. Day Timeline — show failure indicator:**

```tsx
{d.optimized && <span className="absolute -top-1 -right-1 text-[8px]">🧠</span>}
{d.optimization_failed && <span className="absolute -top-1 -right-1 text-[8px]">⚠️</span>}
```

**4e. Policy History pills — show day numbers and failures:**

```tsx
<span>D{r.day_num != null ? r.day_num + 1 : i + 1}</span>
// For failed entries:
{r.failed ? (
  <span style={{ color: 'var(--text-muted)' }}>⚠</span>
) : (
  <span style={{ color: r.accepted ? 'var(--color-success)' : 'var(--color-danger)' }}>
    {r.accepted ? '✓' : '✗'}
  </span>
)}
```

**4f. Add legend below Day Timeline:**

```tsx
<div className="text-[10px] mt-1.5" style={{ color: 'var(--text-muted)' }}>
  🧠 optimized · ⚠️ optimization failed
</div>
```

---

## Fix 5: Reasoning panel selected-day alignment (Frontend)

The "Latest Reasoning" panel should show reasoning for the SELECTED day in the timeline, not always the last entry.

Currently (line 891):
```tsx
const reasoningIndex = selectedDay ?? history.length - 1;
const latest = history[reasoningIndex];
```

This indexes by `selectedDay` directly, but `reasoning_history` is a sparse array (only optimization days). Day 5 might be index 3 in reasoning_history.

**Fix:** With `day_num` on each entry (from Fix 4a):
```tsx
const targetDay = selectedDay ?? gameState.days.length - 1;
const entry = history.find(r => r.day_num === targetDay) ?? history[history.length - 1];
```

If no match (day had no optimization), show a note: "No optimization on this day" or show the most recent prior entry.

---

## Execution Plan

**Subagent 1 — Frontend fixes (1, 2, 5):** Terminology, reasoning note, selected-day alignment. Pure `GameView.tsx` changes, no backend.

**Subagent 2 — Backend + Frontend fixes (3, 4):** Add `old_policy` to results, add `day_num`, store failures, update GameDay model, update serialization, update frontend pills/timeline.
