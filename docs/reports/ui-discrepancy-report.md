# UI Discrepancy Report — GameView

**Date:** 2026-02-23  
**Context:** Game `custom:504c65d9`, Gemini 2.5 Pro, Lehman Month scenario, Day 17/25

---

## Issue 1: Round vs Day terminology mixup

**Observed:** "Round Timeline", "Load Round 16 Replay", "Round 16 Results" — but the header says "Day 17/25".

**Root cause:** The codebase uses "Round" and "Day" interchangeably. The original 2-agent simple mode was single-day-per-round, so "round = day". With multi-day scenarios (`every_scenario_day` schedule), a "round" is actually a multi-day scenario run. The UI never adapted.

**What it should say:**
- "Round Timeline" → "Day Timeline"
- "Load Round 16 Replay" → "Load Day 16 Replay"
- "Round 16 Results" → "Day 16 Results"
- Policy History pills should say D1, D2, D3 (not R1, R2, R3)

**Fix:** String replacements in `GameView.tsx`. The internal data model already uses `day_num` — it's purely a display label issue.

**Files:** `web/frontend/src/views/GameView.tsx` (lines 566, 574, 597, 1093, 1319)

---

## Issue 2: "🧠 Latest Reasoning" shows empty for Gemini models

**Observed:** The reasoning panel exists but shows no thinking content for Gemini 2.5 Pro.

**Root cause:** Gemini models return `thinking_tokens: 0` and empty `thinking` text. The `streaming_optimizer.py` captures a `thinking` field from the LLM response, but Gemini's thinking/reasoning is internal to the model and not exposed via the API in the same way as Anthropic's extended thinking or OpenAI's reasoning tokens.

The panel title "Latest Reasoning" is also misleading — it shows the `reasoning` summary text (which IS populated) and the `thinking` tokens (which aren't). The "empty" appearance is likely because:
1. The `thinking` expandable section in `ReasoningExplorer` is hidden when `thinking` is empty (correct).
2. The `reasoning` text IS shown but may appear sparse since Gemini doesn't produce verbose chain-of-thought.

**What it should say:** When `thinking_tokens === 0` and no thinking text is available, show a note like: *"This model does not expose reasoning tokens."*

**Fix:** In `AgentReasoningCard` / `ReasoningExplorer`, detect when thinking is unavailable and show an explanatory note. Check if `result.thinking` is empty and `result.usage?.thinking_tokens === 0`.

**Files:** `web/frontend/src/views/GameView.tsx` (around line 1209-1215, `ReasoningExplorer` component)

---

## Issue 3: "📊 Policy Evolution" always shows "No policy changes"

**Observed:** Every agent shows "No policy changes" even on days where policies clearly changed (fraction values moved, bootstrap accepted/rejected).

**Root cause:** The Policy Evolution panel (line 839-855) renders `PolicyDiffView` with `latest.old_policy` and `latest.new_policy`. However, the `old_policy` field is **never populated** in the optimization result.

In `streaming_optimizer.py`, the result dict yields:
```python
{
    "new_policy": new_policy,
    "old_fraction": current_fraction,
    "new_fraction": new_fraction,
    ...
}
```

There is no `old_policy` key in the result. The `PolicyDiffView` component receives `undefined` for both `oldPolicy` and `newPolicy` (since `latest` is indexed by `selectedDay` which may not align with reasoning_history indices), computes zero diffs, and shows "No policy changes".

**Two bugs compound here:**
1. **Missing `old_policy` in result dict** — `streaming_optimizer.py` never includes the pre-optimization policy JSON.
2. **Index mismatch** — The Policy Evolution panel uses `history[history.length - 1]` (latest reasoning entry), but reasoning_history has fewer entries than days (only optimization days). So `latest` may not correspond to the selected day.

**Fix:**
1. In `streaming_optimizer.py`, add `"old_policy": current_policy` to the result dict (the current policy is already available as `game.policies[aid]` before optimization).
2. In the Policy Evolution panel, show diffs for all agents on the currently selected day, not just the latest entry.

**Files:**
- `web/backend/app/streaming_optimizer.py` (~line 605) — add `old_policy`
- `web/backend/app/game.py` (~line 494) — ensure old_policy is passed through
- `web/frontend/src/views/GameView.tsx` (lines 839-855) — fix indexing

---

## Issue 4: 16 days in timeline but only 11 pills in Policy History

**Observed:** Round Timeline shows 16 day buttons. Policy History (for WEAK_BANK) shows R1-R11.

**Root cause:** This is **correct behavior**, not a bug. Policy History pills correspond to **optimization events**, not simulation days. In `every_scenario_day` mode:

- The multi-day scenario (Lehman Month) has N scenario-days per round.
- Optimization runs at the end of each scenario (after all scenario-days complete).
- If optimization hasn't run yet for days 12-16 (still in the current scenario run), there are no reasoning_history entries for those days.

### Investigation: Why 16 days but only 11 optimization pills?

With `optimization_interval=1` (default), `should_optimize(day_num)` returns `True` for EVERY day. So all 16 days should trigger optimization. The 5 missing pills are NOT from skipped scheduling — they're from **fatal optimization failures**.

**The fatal failure path** (`game.py` line 448-456):
```python
for i, r in enumerate(gather_results):
    if isinstance(r, Exception):
        # Fatal: abort ALL agents, return {}, stop auto-run
        self.auto_run = False
        return {}
```

When ANY agent's LLM call fails fatally (e.g., 429 rate limit exhausted after 5 retries), `optimize_all_agents()` returns empty `{}` and no results are stored for ANY agent. This means:
- All 6 agents lose that optimization round
- `reasoning_history` gets no entry for any agent
- `day.optimized` stays `False` (no 🧠 emoji)
- Auto-run stops (requiring user to click "Auto" again to resume)

**Evidence from logs:** The Cloud Run logs show repeated `429 RESOURCE_EXHAUSTED` errors for Gemini 2.5 Pro during this game's run. With `MAX_CONCURRENT=3` (lowered from 10 to reduce rate limiting), 6 agents still create bursts. Each failed attempt retries up to 5 times with backoff, but if all 5 attempts 429, the agent fails fatally.

**The 5 missing optimizations correspond to 5 rate-limit-induced fatal failures.** Stefan would have needed to resume auto-run each time.

**This is a significant UX problem:**
1. The user has no indication that optimization was attempted but failed
2. The day timeline shows no 🧠 but doesn't explain why
3. Policy History pills silently skip those days
4. The game stops auto-running without clear indication

**Recommendations:**
1. Store failed optimization attempts in `reasoning_history` with a `failed: true` flag
2. Show failed optimization days with a ⚠️ emoji in the timeline
3. Show gray/failed pills in Policy History for days where optimization was attempted but failed
4. Add `day_num` to each reasoning_history entry so pills can show actual day numbers
5. Consider auto-retry on 429 at the `optimize_all_agents` level (not just per-agent)

**Files:** 
- `web/backend/app/game.py` (lines 448-456) — store failure instead of silently discarding
- `web/backend/app/streaming_optimizer.py` — include `day_num` in result
- `web/frontend/src/views/GameView.tsx` (line 1319) — use `r.day_num` for label, show failures

---

## Issue 5: Brain emoji 🧠 on some but not all days in Round Timeline

**Observed:** Some day buttons in the timeline have a small 🧠 indicator, others don't.

**Root cause:** Two causes:

1. **Successful optimization** — `day.optimized = True` is set in `main.py` (lines 833, 856, 983) after LLM optimization completes. Days with 🧠 had successful optimization.

2. **Failed optimization** — Days without 🧠 had either (a) no optimization attempted (impossible with `interval=1`), or (b) optimization was attempted but failed fatally due to rate limits (see Issue 4 investigation). The failure path returns `{}` without setting `day.optimized = True`.

So the brain emoji is accurate — it shows which days had successful optimization. But it's misleading because it doesn't distinguish "not attempted" from "attempted and failed".

**Recommendation:** 
- 🧠 = successful optimization
- ⚠️ = attempted but failed  
- No emoji = not scheduled (only relevant if `optimization_interval > 1`)
- Add a legend below the timeline explaining the icons

**Files:** `web/frontend/src/views/GameView.tsx` (line 582), `web/backend/app/game.py` (track failed attempts)

---

## Summary of Required Fixes

| # | Issue | Severity | Type | Effort |
|---|-------|----------|------|--------|
| 1 | Round→Day terminology | Medium | Frontend string changes | Small |
| 2 | Empty reasoning for Gemini | Low | Frontend UX note | Small |
| 3 | Policy Evolution always empty | **High** | Backend missing data + frontend index bug | Medium |
| 4 | Pill count ≠ day count | **High** | Fatal failures silently discarded | Medium |
| 5 | Brain emoji explanation | Medium | Missing failure state tracking | Medium |

### Priority order: 3 → 4 → 1 → 5 → 2
