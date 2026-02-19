# Reasoning Pipeline — Development Plan

**Status**: Draft  
**Date**: 2026-02-19  
**Scope**: Medium (~4h total across both tasks)  
**Branch**: `feature/interactive-web-sandbox`

## Goal

Wire LLM reasoning text end-to-end from backend through WebSocket to frontend, and build an expandable UX where users can explore each agent's reasoning per iteration — what the AI thought, what it proposed, and why.

## Current State (already working)

The pipeline is **mostly built**. Confirming what exists:

### Backend ✅
- `streaming_optimizer.py` captures `raw_response` (full LLM output text) and `thinking` (model's internal reasoning, if provider exposes it — Gemini exposes `thoughts_token_count` but not content)
- `game.py` stores results in `self.reasoning_history[aid]` via `_apply_result()`
- `get_state()` includes `reasoning_history` in the `game_state` WebSocket payload
- `optimization_complete` WS message includes the full result dict in `data`

### Frontend ✅
- `GameOptimizationResult` type has `raw_response?`, `thinking?`, `usage?`, `latency_seconds?`
- `AgentResponseDetail` component exists — toggle buttons for "Show Thinking" and "Show Full Response"
- `PolicyHistoryPanel` renders per-agent iteration history with `AgentResponseDetail` per round
- `useGameWebSocket.ts` stores game state from `game_state` messages (which include `reasoning_history`)

### What's actually missing

The pipeline works but the **UX is bare minimum** — raw `<pre>` text dumps. No formatting, no structure, no navigation. The backend data is there; the frontend presentation needs work.

---

## Task 1: Verify & Harden the Data Pipeline

**Time**: ~1h  
**Risk**: Low

### 1a. Verify `raw_response` reaches frontend

Run a real LLM experiment (3-bank, 3-round) and inspect:
- Browser DevTools → WS messages → confirm `game_state.reasoning_history[agent].raw_response` is non-empty
- Confirm `AgentResponseDetail` renders for each iteration
- Confirm the "Show Full Response" button works

### 1b. Handle edge cases

| Case | Expected behavior |
|------|-------------------|
| `raw_response` is empty (mock mode) | Hide "Full Response" button (already handled: `if (!hasRaw) return null`) |
| `thinking` is empty (Gemini doesn't expose it) | Hide "Thinking" button (already handled) |
| Very long responses (>50k chars) | Add character limit with "Show more" — currently just `max-h-64 overflow-y-auto` which is fine |
| Parse failure / fallback | Show `fallback_reason` badge + whatever `raw_response` was captured before failure |

### 1c. Add `reasoning_summary` from provider

Currently `reasoning_summary` in the type exists but isn't populated. Options:
- **Skip for now** — the full response is more useful than an auto-summary
- **Future**: Use the model's `reasoning_summary` feature if available

**Decision**: Skip — the full raw response is the primary content users want.

### Files to check (read-only verification)
- `web/backend/app/streaming_optimizer.py` — confirm `raw_response` in all code paths
- `web/backend/app/game.py` — confirm `_apply_result` preserves all fields
- `web/frontend/src/hooks/useGameWebSocket.ts` — confirm `game_state` handler stores full state

---

## Task 2: Reasoning Explorer UX

**Time**: ~3h  
**Risk**: Medium (UX design choices)

### Goal

Replace raw `<pre>` dumps with a structured, readable reasoning explorer that makes it genuinely interesting to see what each agent thought.

### Design

#### 2a. Redesign `AgentResponseDetail` → `ReasoningExplorer`

New component replacing the current `<pre>` blocks:

```
┌─────────────────────────────────────────────────┐
│ 🧠 BANK_A — Round 3 Reasoning                  │
│                                                  │
│ ┌─ Summary ────────────────────────────────────┐ │
│ │ Reduced liquidity 0.450 → 0.380.             │ │
│ │ Delay cost dominant — releasing sooner.       │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ [▼ Full Analysis]  [▼ Proposed Policy]  [Stats]  │
│                                                  │
│ ┌─ Full Analysis (expanded) ───────────────────┐ │
│ │ <markdown-rendered LLM text>                 │ │
│ │ - Structured sections                        │ │
│ │ - Cost analysis tables                       │ │
│ │ - Decision rationale                         │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ⏱ 23.4s · 📥 12,481 in · 📤 2,104 out · 🧠 8,192│
└─────────────────────────────────────────────────┘
```

**Key features:**
1. **Summary line** — extract from `reasoning` field (already a one-liner)
2. **Full Analysis** — render `raw_response` with markdown (reuse existing `MarkdownRenderer` from docs)
3. **Proposed Policy** — JSON viewer for `new_policy` (collapsible, syntax highlighted)
4. **Stats bar** — token usage, latency, acceptance status
5. **Accepted/Rejected badge** — green/red with bootstrap delta if available

#### 2b. Improve `PolicyHistoryPanel` iteration navigation

Current: flat list with tiny text. Redesign:

```
┌─────────────────────────────────────────────────┐
│ 📊 Policy History          [BANK_A] [BANK_B] ▾ │
│                                                  │
│  R1  ✓ 1.000→0.520  │ R2  ✓ 0.520→0.450        │
│  R3  ✓ 0.450→0.380  │ R4  ✗ 0.380→0.380 reject │
│  R5  ✓ 0.380→0.395  │                           │
│                                                  │
│ ─── Round 3 (selected) ─────────────────────────│
│ <ReasoningExplorer for round 3>                  │
└─────────────────────────────────────────────────┘
```

- Clickable round pills (not just expand/collapse all)
- Selected round shows full `ReasoningExplorer`
- Compact cost delta per round

#### 2c. Markdown rendering for LLM responses

The `raw_response` from the LLM is structured text (analysis paragraphs + JSON policy block). Parse it:
1. Split on the JSON policy block (detect `{"version":` or triple-backtick fence)
2. Render the analysis portion as markdown (headers, bullets, emphasis)
3. Render the JSON portion with syntax highlighting (reuse `CodeEditor` in readonly mode, or `react-json-view`)

**Reuse**: The docs view already has a markdown renderer. Import and use it.

### Files

#### New
| File | Purpose |
|------|---------|
| `web/frontend/src/components/ReasoningExplorer.tsx` | New component replacing `AgentResponseDetail` |

#### Modified
| File | Changes |
|------|---------|
| `web/frontend/src/views/GameView.tsx` | Replace `AgentResponseDetail` with `ReasoningExplorer`, redesign `PolicyHistoryPanel` iteration UX |
| `web/frontend/src/index.css` | Any light/dark mode variables for reasoning panels |

#### NOT Modified
| File | Reason |
|------|--------|
| `web/backend/app/*` | Backend already sends all needed data |
| `web/frontend/src/hooks/useGameWebSocket.ts` | Already handles `reasoning_history` correctly |
| `web/frontend/src/types.ts` | Types already complete |

### Tests

- [ ] Run real LLM experiment → verify `raw_response` appears in `ReasoningExplorer`
- [ ] Click through all rounds in `PolicyHistoryPanel` → each shows correct agent data
- [ ] Mock mode → no "Full Response" button (raw_response is empty for mocks)
- [ ] Light + dark mode → reasoning panels look correct
- [ ] Very long LLM response → scroll works, doesn't break layout
- [ ] Rejected round → shows rejection reason prominently

### Success Criteria

1. User can see **what the AI actually said** for any agent in any round
2. Response is **readable** — markdown rendered, not raw text dumps
3. Policy JSON is **syntax highlighted** and collapsible
4. Token usage and latency visible at a glance
5. Navigation between rounds is **one click**, not expand/collapse all
6. Works in both light and dark mode

---

## Web Invariants

- **WEB-INV-2 (Agent Isolation)**: Each agent's reasoning panel only shows that agent's data ✅
- **WEB-INV-4 (Cost Consistency)**: Reasoning summary references actual costs from the simulation ✅
- **WEB-INV-6**: ~~Dark mode only~~ (outdated — light mode is now default, both supported)

## Sequencing

1. Task 1 first (verify pipeline) — if data isn't flowing, Task 2 is pointless
2. Task 2a (ReasoningExplorer component) — standalone, testable
3. Task 2b (PolicyHistoryPanel redesign) — uses ReasoningExplorer
4. Task 2c (markdown rendering) — enhancement, can ship without it initially

## Open Questions

1. **Should we cache/truncate large responses?** The full Gemini response with 8192 thinking tokens can be 20k+ chars. Current `max-h-64 overflow-y-auto` handles this fine in the UI. Backend stores everything in memory (game state is ephemeral anyway). **Lean: no truncation.**

2. **Separate "Analysis" and "Policy JSON" sections?** LLM responses typically have a reasoning section followed by the JSON block. Splitting them makes the UI cleaner but requires reliable parsing. **Lean: yes, split on JSON block detection.**
