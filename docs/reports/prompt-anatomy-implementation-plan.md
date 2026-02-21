# Prompt Anatomy: Implementation Plan

**Date:** 2026-02-21  
**Author:** Nash  
**Status:** Ready for implementation  
**Depends on:** `prompt-anatomy-and-control.md` (design), `experiment-runner-audit.md` (reference)

## Overview

This document turns the design report into a concrete implementation plan with file-level changes, data models, API endpoints, and frontend components. All four phases are equal priority but Phase 1 is the dependency for the rest.

## Block Registry

Based on Dennis's audit of the experiment runner, here's the complete block registry mapping existing code to named blocks:

### System Prompt Blocks

These come from `SystemPromptBuilder` in `system_prompt_builder.py`. The builder currently produces one monolithic string from ~11 internal sections. We need to make each section a named block.

| Block ID | Builder Method | Current Source | Notes |
|----------|---------------|----------------|-------|
| `sys_expert_intro` | `_build_expert_intro()` | Hardcoded text | ~200 tokens, always included |
| `sys_experiment_custom` | `_build_customization()` | `prompt_customization` from experiment config | 0-500 tokens, **currently missing from web** |
| `sys_domain_explanation` | `_build_domain_explanation()` | Hardcoded + conditional LSM section | ~800 tokens |
| `sys_cost_objectives` | `_build_cost_objectives()` | Hardcoded + cost rates JSON | ~600 tokens |
| `sys_policy_architecture` | `_build_policy_tree_architecture()` | Constraint-filtered (allowed trees/actions) | ~400-800 tokens |
| `sys_optimization_process` | `_build_optimization_process()` | Hardcoded | ~300 tokens |
| `sys_pre_gen_checklist` | `_build_pre_generation_checklist()` | Hardcoded | ~200 tokens |
| `sys_policy_schema` | `_build_filtered_schema()` | `get_filtered_policy_schema(constraints)` | ~400 tokens |
| `sys_cost_schema` | `_build_cost_schema()` | `get_filtered_cost_schema(cost_rates)` | ~200 tokens |
| `sys_common_errors` | `_build_common_errors()` | Hardcoded | ~300 tokens |
| `sys_final_instructions` | `_build_final_instructions()` | Hardcoded | ~200 tokens |

### User Prompt Blocks

These come from `SingleAgentContextBuilder` in `single_agent_context.py` + additions in `streaming_optimizer.py`.

| Block ID | Builder Method | Source | Notes |
|----------|---------------|--------|-------|
| `usr_header` | `_build_header()` | Dynamic (agent_id, iteration) | ~150 tokens |
| `usr_current_state` | `_build_current_state_summary()` | Dynamic (metrics, policy params) | ~250 tokens |
| `usr_cost_analysis` | `_build_cost_analysis()` | Dynamic (cost breakdown + rates) | ~500 tokens |
| `usr_optimization_guidance` | `_build_optimization_guidance()` | Dynamic (heuristic from costs/trends) | ~200 tokens |
| `usr_simulation_trace` | `_build_bootstrap_samples_section()` | Dynamic (tick-by-tick events) | **5k-150k tokens** — dominates |
| `usr_iteration_history` | `_build_iteration_history_section()` | Dynamic (grows each round) | 500-10k tokens |
| `usr_parameter_trajectories` | `_build_parameter_trajectory_section()` | Dynamic | ~200 tokens |
| `usr_final_instructions` | `_build_final_instructions()` | Semi-static (rejected count changes) | ~500 tokens |
| `usr_policy_section` | `UserPromptBuilder._build_policy_section()` | Dynamic (current policy JSON) | ~300 tokens |

### Block Options

| Block ID | Option | Type | Default | Description |
|----------|--------|------|---------|-------------|
| `usr_simulation_trace` | `verbosity` | enum | `"full"` | `full` / `decisions_only` / `summary` / `costs_only` |
| `usr_simulation_trace` | `max_tokens` | int | null | Truncate if exceeding |
| `usr_iteration_history` | `format` | enum | `"full"` | `full` / `table_only` / `last_n` |
| `usr_iteration_history` | `last_n` | int | 10 | Only used when format=`last_n` |
| `usr_iteration_history` | `include_policy_json` | bool | true | Include full policy JSON per iteration |
| `usr_cost_analysis` | `include_rates` | bool | true | Include cost rates config JSON |
| `sys_experiment_custom` | `text` | string | `""` | Custom text injected into system prompt |

## Phase 1: Prompt Persistence

### 1.1 Backend Data Model

**New file: `web/backend/app/prompt_blocks.py`**

```python
"""Prompt block registry and structured prompt builder."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class PromptBlock:
    """A named section of the optimization prompt."""
    id: str
    name: str
    category: str          # "system" | "user"
    source: str            # "static" | "dynamic"
    content: str
    token_estimate: int
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self) -> dict[str, Any]:
        """Compact form for storage — truncate large content."""
        d = asdict(self)
        if len(self.content) > 50_000:
            d["content_hash"] = hashlib.sha256(self.content.encode()).hexdigest()
            d["content_length"] = len(self.content)
            d["content"] = self.content[:1000] + f"\n\n... [{len(self.content) - 1000} chars truncated] ..."
            d["truncated"] = True
        return d


@dataclass
class StructuredPrompt:
    """Complete prompt with named blocks + assembled text."""
    blocks: list[PromptBlock]
    system_prompt: str
    user_prompt: str
    total_tokens: int
    profile_hash: str
    llm_response: str | None = None
    llm_response_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocks": [b.to_summary_dict() for b in self.blocks],
            "total_tokens": self.total_tokens,
            "profile_hash": self.profile_hash,
            "llm_response": self.llm_response,
            "llm_response_tokens": self.llm_response_tokens,
        }

    @staticmethod
    def compute_profile_hash(blocks: list[PromptBlock]) -> str:
        """Hash of block IDs + enabled states for reproducibility."""
        config = {b.id: {"enabled": b.enabled, "options": b.options} for b in blocks}
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class PromptProfile:
    """Saved profile for prompt block configuration."""
    id: str
    name: str
    description: str = ""
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)  # block_id → {enabled, options}
    created_at: str = ""
    hash: str = ""
```

### 1.2 Refactor `_build_optimization_prompt()`

**File: `web/backend/app/streaming_optimizer.py`**

Currently returns `(system_prompt, user_prompt, context)`. Refactor to:

1. Build each block individually with its metadata
2. Assemble enabled blocks into system/user prompts
3. Return `StructuredPrompt` alongside the existing tuple (backward compat)

```python
def _build_optimization_prompt(
    agent_id, current_policy, last_day, all_days, raw_yaml,
    constraint_preset="simple",
    prompt_profile: dict[str, dict] | None = None,  # NEW: block overrides
) -> tuple[str, str, dict, StructuredPrompt]:
    """Build optimization prompt with named blocks.
    
    Returns (system_prompt, user_prompt, context, structured_prompt).
    """
    blocks: list[PromptBlock] = []
    
    # --- System prompt blocks ---
    # Each section of SystemPromptBuilder becomes a block
    system_prompt = optimizer.get_system_prompt(cost_rates=cost_rates)
    # For Phase 1, treat entire system prompt as one block
    # Phase 2 will decompose SystemPromptBuilder into individual blocks
    blocks.append(PromptBlock(
        id="sys_full", name="System Prompt", category="system",
        source="static", content=system_prompt,
        token_estimate=len(system_prompt) // 4,
    ))
    
    # --- User prompt blocks ---
    # Build each section separately...
    # (see detailed implementation below)
```

**Key insight:** For Phase 1, we don't need to refactor `SystemPromptBuilder` internally. We can treat the system prompt as a single block and decompose it in Phase 2. The user prompt sections in `SingleAgentContextBuilder` are already separate methods — we just need to call them individually and wrap each in a `PromptBlock`.

### 1.3 Refactor `SingleAgentContextBuilder`

Currently `build()` calls all section methods and joins them. Add a `build_blocks()` method:

```python
def build_blocks(self) -> list[PromptBlock]:
    """Build individual prompt blocks instead of a single string."""
    blocks = []
    section_map = [
        ("usr_header", "Header", self._build_header),
        ("usr_current_state", "Current State", self._build_current_state_summary),
        ("usr_cost_analysis", "Cost Analysis", self._build_cost_analysis),
        ("usr_optimization_guidance", "Optimization Guidance", self._build_optimization_guidance),
        ("usr_simulation_trace", "Simulation Trace", self._build_bootstrap_samples_section),
        ("usr_iteration_history", "Iteration History", self._build_iteration_history_section),
        ("usr_parameter_trajectories", "Parameter Trajectories", self._build_parameter_trajectory_section),
        ("usr_final_instructions", "Final Instructions", self._build_final_instructions),
    ]
    for block_id, name, builder_fn in section_map:
        content = builder_fn()
        if content:
            blocks.append(PromptBlock(
                id=block_id, name=name, category="user",
                source="static" if block_id == "usr_final_instructions" else "dynamic",
                content=content,
                token_estimate=len(content) // 4,
            ))
    return blocks
```

### 1.4 Store in GameDay

Add to `GameDay.__init__()`:
```python
self.optimization_prompts: dict[str, dict] = {}  # agent_id → StructuredPrompt.to_dict()
```

Set after optimization in `_apply_result()` or `optimize_policies_streaming()`.

### 1.5 Store in Checkpoint

In `_day_to_checkpoint()`, add:
```python
"optimization_prompts": day.optimization_prompts,
```

In `from_checkpoint()`, restore:
```python
day.optimization_prompts = day_data.get("optimization_prompts", {})
```

### 1.6 Store in DuckDB

New table created in `GameStorage.create_game_db()`:
```sql
CREATE TABLE IF NOT EXISTS optimization_prompts (
    day_num INTEGER,
    agent_id TEXT,
    block_id TEXT,
    block_name TEXT,
    category TEXT,
    source TEXT,
    content TEXT,
    token_estimate INTEGER,
    enabled BOOLEAN,
    options TEXT,  -- JSON
    PRIMARY KEY (day_num, agent_id, block_id)
);
```

Insert after each optimization round.

### 1.7 New API Endpoint

```python
@app.get("/api/games/{game_id}/prompts/{day_num}/{agent_id}")
def get_prompt(game_id: str, day_num: int, agent_id: str):
    """Get the structured prompt for a specific optimization round."""
    game = game_manager.get(game_id)
    if not game:
        # Try loading from checkpoint
        ...
    day = game.days[day_num - 1]  # 1-indexed
    prompt_data = day.optimization_prompts.get(agent_id)
    if not prompt_data:
        raise HTTPException(404, "No prompt data for this round/agent")
    return prompt_data
```

### 1.8 Token Estimation

Simple heuristic: `len(content) // 4` (chars / 4 ≈ tokens for English text). Good enough for UI display. Exact tokenization per-model is overkill.

---

## Phase 2: Prompt Profiles

### 2.1 Profile Storage

**Firestore collection:** `prompt_profiles/{profile_id}`

```json
{
  "id": "castro-full",
  "name": "Castro Paper (Full)",
  "description": "All blocks enabled, full verbosity",
  "blocks": {
    "usr_simulation_trace": { "enabled": true, "options": { "verbosity": "full" } },
    "usr_iteration_history": { "enabled": true, "options": { "format": "full" } },
    "sys_experiment_custom": { "enabled": true, "options": { "text": "..." } }
  },
  "created_at": "2026-02-21T16:00:00Z",
  "hash": "a1b2c3d4e5f6"
}
```

Blocks not listed in `blocks` use defaults.

### 2.2 API Endpoints

```python
@app.get("/api/prompt-profiles")
def list_profiles(): ...

@app.post("/api/prompt-profiles")
def create_profile(profile: PromptProfile): ...

@app.get("/api/prompt-profiles/{profile_id}")
def get_profile(profile_id: str): ...

@app.delete("/api/prompt-profiles/{profile_id}")
def delete_profile(profile_id: str): ...

@app.get("/api/prompt-blocks")
def get_block_definitions():
    """Return all available blocks with defaults and descriptions."""
    ...
```

### 2.3 Wire Profile into Game Creation

Add to `CreateGameRequest`:
```python
prompt_profile_id: str | None = None
prompt_profile: dict[str, dict] | None = None  # inline override
```

Store in `Game` and pass through to `_build_optimization_prompt()`.

### 2.4 Frontend: Prompt Anatomy Inspector

**New component: `PromptAnatomyPanel.tsx`**

Shown in the game creation flow (below scenario selection, above "Start" button).

```
┌─ Prompt Configuration ─────────────────────────────┐
│ Profile: [Castro Paper (Full) ▼]  [Save] [Reset]   │
│                                                     │
│ System Prompt                           ~3.2k tok   │
│ ├ ✅ Expert Introduction        static   200 tok    │
│ ├ ✅ Experiment Customization   static   450 tok    │
│ │   └ [Edit text...]                                │
│ ├ ✅ Domain Explanation         static   800 tok    │
│ ├ ✅ Cost Objectives            static   600 tok    │
│ ├ ✅ Policy Architecture        static   400 tok    │
│ ├ ✅ Optimization Process       static   300 tok    │
│ ├ ✅ Pre-Gen Checklist          static   200 tok    │
│ ├ ✅ Policy Schema              static   400 tok    │
│ ├ ✅ Cost Schema                static   200 tok    │
│ ├ ✅ Common Errors              static   300 tok    │
│ └ ✅ Final Instructions         static   200 tok    │
│                                                     │
│ User Prompt (per round)                ~varies      │
│ ├ ✅ Header                    dynamic   150 tok    │
│ ├ ✅ Current State             dynamic   250 tok    │
│ ├ ✅ Cost Analysis             dynamic   500 tok    │
│ ├ ✅ Optimization Guidance     dynamic   200 tok    │
│ ├ ✅ Simulation Trace ⚙️       dynamic  5-150k tok  │
│ │   └ Verbosity: [Full ▼] decisions_only|summary    │
│ ├ ✅ Iteration History ⚙️      dynamic  0.5-10k tok │
│ │   └ Format: [Full ▼] table_only|last_10           │
│ ├ ✅ Parameter Trajectories    dynamic   200 tok    │
│ ├ ✅ Final Instructions        static    500 tok    │
│ └ ✅ Current Policy            dynamic   300 tok    │
│                                                     │
│ Estimated total: ~5-155k tokens per round           │
└─────────────────────────────────────────────────────┘
```

Toggle checkboxes enable/disable blocks. ⚙️ opens options popover. Static blocks can be expanded to preview content. Profile dropdown loads/saves named configs.

---

## Phase 3: Prompt Explorer

### 3.1 API

```python
@app.get("/api/games/{game_id}/prompts")
def list_prompts(game_id: str):
    """List all optimization prompts with metadata (no content)."""
    return {
        "prompts": [
            {"day": d.day_num, "agents": list(d.optimization_prompts.keys()),
             "total_tokens": ...}
            for d in game.days if d.optimization_prompts
        ]
    }

@app.get("/api/games/{game_id}/prompts/{day_num}/{agent_id}")
def get_prompt(game_id: str, day_num: int, agent_id: str):
    """Get full structured prompt with all blocks."""
    ...

@app.get("/api/games/{game_id}/prompts/{day_num}/{agent_id}/{block_id}")
def get_prompt_block(game_id: str, day_num: int, agent_id: str, block_id: str):
    """Get a single block's full content (for large blocks stored truncated)."""
    ...
```

### 3.2 Frontend Component: `PromptExplorer.tsx`

**Navigation:** Round selector (1-25) × Agent selector (BANK_A, BANK_B, ...) at bottom.

**Layout:** Accordion of blocks. Each block header shows:
- Checkbox (was it enabled?)
- Name
- Token count
- Badge: `[constant]` if content identical to previous round, `[+Δ]` if changed

**Block content:** Expandable. For large blocks (>5k tokens), show first 500 chars with "Show full" button.

**Diff mode:** Toggle button. When on, shows side-by-side or inline diff of each block vs previous round.

**Response section:** Below all blocks, shows the LLM's output (the generated policy JSON).

**Token breakdown bar:** Horizontal stacked bar chart at top showing relative size of each block.

### 3.3 Integration Point

Add a "🔍 Prompt Explorer" tab/button to the game detail view (`GameView.tsx`), next to the existing panels (Cost Chart, Policy Evolution, etc.).

---

## Phase 4: Smart Defaults

### 4.1 Detection Logic

In `PromptAnatomyPanel.tsx`, when scenario config is loaded:

```typescript
function suggestDefaults(scenario: ScenarioConfig): PromptProfile {
  const isStochastic = scenario.agents?.some(a => a.arrival_config);
  const ticksPerDay = scenario.simulation?.ticks_per_day || 1;
  const numAgents = scenario.agents?.length || 2;
  
  const suggestions: PromptProfile = { blocks: {} };
  
  // Deterministic scenarios: summarize traces
  if (!isStochastic) {
    suggestions.blocks["usr_simulation_trace"] = {
      enabled: true,
      options: { verbosity: "decisions_only" },
    };
  }
  
  // Large tick counts: warn about trace size
  if (ticksPerDay > 50) {
    // Estimated trace size: ~500 tokens per tick per agent
    const estimatedTraceTokens = ticksPerDay * 500;
    if (estimatedTraceTokens > 50000) {
      suggestions.blocks["usr_simulation_trace"] = {
        enabled: true,
        options: { verbosity: "decisions_only", max_tokens: 50000 },
      };
    }
  }
  
  return suggestions;
}
```

### 4.2 UI: Suggestion Banner

When smart defaults differ from current profile:
```
💡 This is a deterministic scenario. Simulation traces are structurally
   identical across rounds. Suggested: use "decisions_only" verbosity
   to reduce trace from ~35k to ~5k tokens.
   [Apply Suggestion] [Dismiss]
```

---

## File Change Summary

### New Files
| File | Description |
|------|-------------|
| `web/backend/app/prompt_blocks.py` | PromptBlock, StructuredPrompt, PromptProfile dataclasses |
| `web/frontend/src/components/PromptAnatomyPanel.tsx` | Pre-run block config UI |
| `web/frontend/src/components/PromptExplorer.tsx` | Post-run prompt inspection UI |
| `web/frontend/src/components/PromptBlockAccordion.tsx` | Shared accordion component for blocks |

### Modified Files
| File | Changes |
|------|---------|
| `web/backend/app/streaming_optimizer.py` | Return `StructuredPrompt` from `_build_optimization_prompt()` |
| `web/backend/app/game.py` | Store `optimization_prompts` on `GameDay`, persist in checkpoint |
| `web/backend/app/main.py` | New API endpoints for prompts and profiles |
| `web/backend/app/storage.py` | DuckDB `optimization_prompts` table |
| `web/frontend/src/views/GameView.tsx` | Add Prompt Explorer tab |
| `web/frontend/src/views/CreateGameView.tsx` | Add Prompt Anatomy panel |
| `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` | Add `build_blocks()` method |
| `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` | Add `build_blocks()` method |

### Unchanged (reused as-is)
| File | Reason |
|------|--------|
| `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py` | Already provides `filter_events_for_agent()` |
| `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` | `SingleAgentContext`, `SingleAgentIterationRecord` already correct |
| `api/payment_simulator/ai_cash_mgmt/prompts/user_prompt_builder.py` | `UserPromptBuilder._build_policy_section()` stays as-is |

---

## Implementation Order

```
Phase 1 (Persistence):
  1. Create prompt_blocks.py with data models
  2. Add build_blocks() to SingleAgentContextBuilder
  3. Refactor _build_optimization_prompt() to produce StructuredPrompt
  4. Store on GameDay + checkpoint + DuckDB
  5. Add GET /api/games/{id}/prompts/{day}/{agent} endpoint
  6. Test: run a game, verify prompts are stored and retrievable

Phase 2 (Profiles):
  7. Add PromptProfile to CreateGameRequest
  8. Wire profile through to _build_optimization_prompt()
  9. Apply block enables/disables and options
  10. Add profile CRUD endpoints
  11. Build PromptAnatomyPanel.tsx
  12. Test: create game with custom profile, verify blocks are filtered

Phase 3 (Explorer):
  13. Build PromptExplorer.tsx with accordion UI
  14. Add round/agent navigation
  15. Add constant/variable badges (compare blocks between rounds)
  16. Add diff mode
  17. Integrate into GameView.tsx
  18. Test: inspect prompts from a completed game

Phase 4 (Smart Defaults):
  19. Implement suggestion logic (deterministic detection, trace size estimation)
  20. Add suggestion banner to PromptAnatomyPanel
  21. Test: create deterministic scenario, verify suggestion appears
```

## Estimated Effort

Total: ~10-12 days of focused implementation across all 4 phases.
