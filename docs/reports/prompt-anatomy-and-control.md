# Prompt Anatomy & Control: Design Report

**Date:** 2026-02-21  
**Author:** Nash  
**Status:** Proposal

## Problem Statement

The optimization prompt sent to the LLM between rounds is a ~170k token document assembled from multiple sources. Currently:

1. **No visibility** — You can't see what the LLM actually receives. The prompt is built in Python, sent to pydantic-ai, and discarded. Only the response is shown.

2. **No control** — Every prompt includes the same sections regardless of experiment type. A 2-period deterministic scenario gets the same simulation trace treatment as a 12-period stochastic one, even though the information value differs dramatically.

3. **Wrong content for deterministic repeated scenarios** — When running `exp1_2period.yaml` for 25 rounds, each round replays the same 2-tick deterministic scenario. The `simulation_trace` section contains the full tick-by-tick event log from the *last round only*. But since every round has identical transactions (only the policy changes), including the raw trace adds ~5-15k tokens of near-identical content. What the LLM actually needs is:
   - **Current round trace** (to see what *this* policy did)
   - **Previous round outcomes** (costs, fractions — already included via `iteration_history`)
   - **NOT** raw traces from all prior rounds (redundant for deterministic scenarios)

4. **No reproducibility metadata** — The prompt composition isn't recorded anywhere. If you re-run an experiment, you can't verify the LLM saw the same prompt structure.

### What's Currently in the Prompt

The optimization prompt has two parts:

#### System Prompt (~2-5k tokens)
Built by `SystemPromptBuilder` in `system_prompt_builder.py`:
- Domain explanation (RTGS, liquidity, payment coordination)
- Cost structure documentation
- Filtered policy JSON schema (based on `constraint_preset`)
- Castro paper alignment notes (if `castro_mode=True`)
- JSON examples
- Experiment-specific customization text

#### User Prompt (~10-170k tokens)
Built by `_build_optimization_prompt()` in `streaming_optimizer.py`, calling `build_single_agent_context()`:

| Block | Source | Content | Typical Size |
|-------|--------|---------|-------------|
| **Header** | `_build_header()` | Agent ID, iteration number, table of contents | ~500 chars |
| **Current State** | `_build_current_state_summary()` | Mean cost, std dev, settlement rate, current policy params | ~800 chars |
| **Cost Analysis** | `_build_cost_analysis()` | Cost breakdown table (delay/overdraft/penalty), cost rates JSON | ~1.5k chars |
| **Optimization Guidance** | `_build_optimization_guidance()` | Heuristic advice based on cost proportions and trends | ~500-1k chars |
| **Simulation Trace** | `_build_bootstrap_samples_section()` | Full tick-by-tick event log from representative sample | **5k-150k chars** |
| **Iteration History** | `_build_iteration_history_section()` | Metrics summary table + detailed changes per iteration + policy params | **2k-50k chars** (grows with rounds) |
| **Parameter Trajectories** | `_build_parameter_trajectory_section()` | Per-parameter value table across iterations | ~500-2k chars |
| **Final Instructions** | `_build_final_instructions()` | Output requirements, rejected policy warnings | ~1.5k chars |
| **Policy Section** | `UserPromptBuilder._build_policy_section()` | Current policy JSON + generation instructions | ~1k chars |

The simulation trace dominates. For a 12-tick stochastic scenario with 2 agents and ~24 transactions, the filtered event log can be 10-20k chars. For a 100-tick crisis scenario with 4 agents, it reaches 100k+ chars.

## Design: Prompt Anatomy System

### Core Concept: Named Prompt Blocks

Every piece of the prompt is a **named block** with metadata:

```typescript
interface PromptBlock {
  id: string;                    // e.g. "simulation_trace", "iteration_history"
  name: string;                  // Human-readable: "Simulation Trace"
  category: "system" | "user";   // Which prompt it belongs to
  source: "static" | "dynamic";  // Constant across rounds vs. changes each round
  content: string;               // The actual text
  tokenEstimate: number;         // Approximate token count
  enabled: boolean;              // Whether included in this run
  dependencies: string[];        // Other blocks this requires
}
```

### Prompt Profile

A **PromptProfile** defines which blocks are enabled and any overrides:

```typescript
interface PromptProfile {
  id: string;
  name: string;                  // e.g. "Paper Reproduction (Full)"
  description: string;
  blocks: {
    [blockId: string]: {
      enabled: boolean;
      maxTokens?: number;        // Truncate if exceeding
      options?: Record<string, any>;  // Block-specific settings
    };
  };
  // Saved with experiment for reproducibility
  createdAt: string;
  hash: string;                  // SHA-256 of block config for integrity
}
```

### Default Blocks

| Block ID | Category | Source | Default | Description |
|----------|----------|--------|---------|-------------|
| `domain_explanation` | system | static | ✅ | RTGS/LSM domain context |
| `cost_structure` | system | static | ✅ | Cost rate documentation |
| `policy_schema` | system | static | ✅ | Filtered JSON schema |
| `json_examples` | system | static | ✅ | Policy JSON examples |
| `castro_alignment` | system | static | ❌ | Castro paper references |
| `experiment_custom` | system | static | ✅ | Per-experiment customization |
| `current_state` | user | dynamic | ✅ | Current metrics summary |
| `cost_analysis` | user | dynamic | ✅ | Cost breakdown |
| `optimization_guidance` | user | dynamic | ✅ | Heuristic advice |
| `simulation_trace` | user | dynamic | ✅ | Tick-by-tick event log |
| `iteration_history` | user | dynamic | ✅ | Full round history |
| `parameter_trajectories` | user | dynamic | ✅ | Parameter evolution |
| `final_instructions` | user | static | ✅ | Output format requirements |
| `current_policy` | user | dynamic | ✅ | Current policy JSON |

### Block Options

Some blocks have configurable options:

- **`simulation_trace`**: `{ include_current: true, include_previous: false, max_traces: 1, verbosity: "full" | "decisions_only" | "summary" | "costs_only" }`
  - `decisions_only`: Show only ticks where the policy made an active decision (Release/Hold/Split) plus any penalty events, dropping mechanical arrival/settlement ticks that are identical across rounds. Preserves temporal reasoning ("held at tick 3, penalty at tick 10") without redundant arrivals.
- **`iteration_history`**: `{ format: "full" | "table_only" | "last_n", last_n: 5, include_policy_json: true }`
- **`cost_analysis`**: `{ include_rates: true, include_guidance: true }`

### Pre-Run UI: Prompt Anatomy Inspector

Before starting an experiment, users can examine and configure the prompt:

```
┌─────────────────────────────────────────────────────┐
│ Prompt Anatomy                            ~45k tokens│
├─────────────────────────────────────────────────────┤
│ SYSTEM PROMPT                              ~3.2k tok│
│ ┌ ✅ Domain Explanation          static    1.2k tok ┐│
│ │ ✅ Cost Structure              static    0.8k tok ││
│ │ ✅ Policy Schema               static    0.6k tok ││
│ │ ✅ JSON Examples               static    0.4k tok ││
│ │ ❌ Castro Alignment            static    0.2k tok ││
│ └ ✅ Experiment Customization    static    0.1k tok ┘│
│                                                     │
│ USER PROMPT (Round 1 preview)             ~42k tok  │
│ ┌ ✅ Current State Summary       dynamic   0.8k tok ┐│
│ │ ✅ Cost Analysis               dynamic   1.5k tok ││
│ │ ✅ Optimization Guidance       dynamic   0.5k tok ││
│ │ ✅ Simulation Trace ⚙️          dynamic  35.0k tok ││
│ │    └ Options: current only, full verbosity        ││
│ │ ✅ Iteration History ⚙️         dynamic   2.0k tok ││
│ │    └ Options: full format, include policy JSON    ││
│ │ ✅ Parameter Trajectories      dynamic   0.5k tok ││
│ │ ✅ Final Instructions          static    1.5k tok ││
│ └ ✅ Current Policy              dynamic   0.2k tok ┘│
│                                                     │
│ 💡 Tip: Simulation trace for deterministic          │
│    scenarios is identical across rounds.             │
│    Consider: costs_only verbosity.                   │
│                                                     │
│ [Save Profile] [Load Profile] [Reset Defaults]      │
└─────────────────────────────────────────────────────┘
```

Each block is a clickable accordion — expand to see the actual content (or a preview for dynamic blocks showing "will contain X based on round results").

Static blocks show their exact content. Dynamic blocks show a template/preview.

The ⚙️ icon opens block-specific options.

### Post-Run UI: Prompt Explorer

After a game completes (or while it's running), each optimization round can be inspected:

```
┌─────────────────────────────────────────────────────┐
│ Round 7 · BANK_A Optimization Prompt     148.2k tok │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ▸ System Prompt                           3.2k tok  │ ← collapsed
│                                                     │
│ ▾ Current State Summary                   0.8k tok  │ ← expanded
│ │ Mean Total Cost: $12,500 (↓ 8.2%)               │
│ │ Settlement Rate: 100%                             │
│ │ Current Policy: { initial_liquidity_fraction: ... │
│                                                     │
│ ▸ Cost Analysis                           1.5k tok  │
│ ▸ Optimization Guidance                   0.5k tok  │
│                                                     │
│ ▾ Simulation Trace                      138.0k tok  │ ← expanded
│ │ [constant] ← badge if identical to prior round   │
│ │ === Tick 0 ===                                    │
│ │ Arrival: $150.00 from BANK_B ...                  │
│ │ ...                                               │
│                                                     │
│ ▸ Iteration History (7 rounds)           3.2k tok   │
│ ▸ Parameter Trajectories                  0.5k tok  │
│ ▸ Final Instructions                      1.5k tok  │
│ ▸ Current Policy                          0.2k tok  │
│                                                     │
│ ── Response ──────────────────────────────────────  │
│ ▾ LLM Output                             0.8k tok  │
│ │ { "version": "2.0", "policy_id": "bank_a_v8",   │
│ │   "parameters": { "initial_liquidity_fraction"...│
│                                                     │
│ [◀ BANK_A] [BANK_B ▶]    [◀ Round 6] [Round 8 ▶]  │
└─────────────────────────────────────────────────────┘
```

Key features:
- **Constant vs. variable badges**: Blocks that didn't change from the previous round get a `[constant]` tag. For deterministic scenarios, the simulation trace is always constant (same transactions, different policy → different events, but identical arrivals).
- **Diff view**: Click a block to see what changed from the previous round (especially useful for iteration history which grows each round).
- **Token breakdown**: Each block shows its token count. The total is shown at the top.
- **Copy prompt**: Button to copy the full prompt to clipboard for manual inspection.
- **Navigate by agent and round**: Bottom nav switches between agents and rounds.

## Implementation Plan

### Phase 1: Prompt Persistence (Backend)

**Goal:** Record every prompt sent to the LLM.

Currently, `_build_optimization_prompt()` returns `(system_prompt, user_prompt, context)`. The prompts are passed to pydantic-ai and then discarded.

**Changes:**

1. **Refactor `_build_optimization_prompt()` to return structured blocks:**

```python
@dataclass
class PromptBlock:
    id: str
    name: str
    category: str  # "system" | "user"
    source: str    # "static" | "dynamic"
    content: str
    token_estimate: int
    enabled: bool

@dataclass  
class StructuredPrompt:
    blocks: list[PromptBlock]
    system_prompt: str      # Assembled from system blocks
    user_prompt: str        # Assembled from user blocks
    total_tokens: int
    profile_hash: str       # Hash of block config
```

2. **Store in `GameDay` / checkpoint:**

```python
class GameDay:
    # ... existing fields ...
    optimization_prompts: dict[str, StructuredPrompt]  # agent_id → prompt
```

Persist in Firestore checkpoint under `optimization_prompts.{agent_id}.blocks` (store block id + content + token_estimate). Skip full content for blocks > 50k chars — store a hash + token count instead, with the full content available via a dedicated API endpoint that reads from the in-memory game or reconstructs from checkpoint data.

3. **Store in DuckDB:**

New table `optimization_prompts`:
```sql
CREATE TABLE optimization_prompts (
    day_num INTEGER,
    agent_id TEXT,
    block_id TEXT,
    block_name TEXT,
    category TEXT,
    source TEXT,
    content TEXT,
    token_estimate INTEGER,
    enabled BOOLEAN,
    PRIMARY KEY (day_num, agent_id, block_id)
);
```

### Phase 2: Prompt Profile (Backend + Frontend)

**Goal:** Let users configure which blocks are included before running.

1. **Add `PromptProfile` to `CreateGameRequest`:**

```python
class PromptProfileConfig(BaseModel):
    blocks: dict[str, BlockOverride] = {}  # block_id → override

class BlockOverride(BaseModel):
    enabled: bool = True
    max_tokens: int | None = None
    options: dict[str, Any] = {}
```

2. **Pass profile through to `_build_optimization_prompt()`** which applies enables/disables and options.

3. **Frontend: Prompt Anatomy Inspector** — new panel in the game creation flow. Fetches block definitions from a new `GET /api/prompt-blocks` endpoint that returns the block list with default states and descriptions. User toggles blocks, saves as profile.

4. **Profile persistence:** Store the profile config in the game checkpoint. Display it in the game detail view.

### Phase 3: Prompt Explorer (Frontend)

**Goal:** Post-run prompt inspection.

1. **New API:** `GET /api/games/{id}/prompts/{day}/{agent}` returns the structured prompt with all blocks.

2. **Frontend component:** `PromptExplorer.tsx` — accordion view of blocks with expand/collapse, token counts, constant/variable badges, agent/round navigation.

3. **Diff mode:** Compare blocks between consecutive rounds. Highlight what changed.

### Phase 4: Smart Defaults

**Goal:** Automatically suggest optimal block configurations.

- Deterministic scenarios: Auto-suggest `simulation_trace.verbosity = "summary"` after round 1 (since arrivals are identical).
- Stochastic scenarios: Keep full trace (different arrivals each round).
- Large iteration counts (>15): Auto-suggest `iteration_history.format = "last_n"` with `last_n = 10`.
- When total tokens > 150k: Show warning, suggest disabling or truncating largest blocks.

## Priority & Effort

| Phase | Effort | Value | Priority |
|-------|--------|-------|----------|
| Phase 1: Persistence | 2-3 days | High (enables everything else) | P0 |
| Phase 2: Profile | 3-4 days | High (experiment control) | P0 |
| Phase 3: Explorer | 2-3 days | High (debugging & understanding) | P0 |
| Phase 4: Smart Defaults | 1-2 days | High (convenience) | P0 |

All phases are equally important. Persistence enables the rest, but the explorer UI and profiles are not polish — they're core to the research workflow. You can't iterate on prompt composition without seeing what you're sending, and you can't reproduce results without saved profiles.

## Impact on Current Experiments

The three paper reproduction runs (`exp1`, `exp2`, `exp3`) currently in progress on Cloud Run rev 99 use the existing prompt construction without block control. Once the Prompt Anatomy system is implemented, we can:

1. **Verify** what the LLM saw in each round by inspecting stored prompts
2. **Compare** prompt composition between experiments
3. **Optimize** token usage — e.g., exp1 (deterministic, 2 ticks) probably wastes tokens on full simulation traces that are nearly identical across rounds
4. **Reproduce** by loading the same prompt profile

## Open Questions

1. **Should we store full prompt content or reconstruct on demand?** Full storage is simpler but Firestore has 1MB document limits. Recommendation: Store blocks < 50k chars directly, larger blocks store hash + reconstruct from game state.

2. **Should profiles be global (saved across games) or per-game?** Both — save named profiles that can be selected when creating a new game, but each game records its specific profile at creation time.

3. **How granular should block options be?** Start simple (enable/disable + a few options per block), expand based on usage. Over-engineering the options system before we know what matters is a trap.

## Dennis's Feedback (2026-02-21)

**On trace redundancy:** Confirmed that in deterministic scenarios, arrival events are byte-identical every round (INV-2). Only policy-driven events differ. Added `decisions_only` verbosity level as a middle ground — shows ticks where the policy made a decision + penalty events, drops mechanical arrivals/settlements.

**On "costs_only" risk:** Dennis correctly noted that pure aggregate costs lose temporal reasoning. A deadline penalty at tick 80 vs tick 20 implies different policy failures. The `decisions_only` mode preserves this causal chain.

**On storing prompts as engine events:** Considered and rejected. Engine events are per-tick simulation data; prompt blocks are per-round-per-agent orchestrator data. Different granularities. A separate `optimization_prompts` table with `(day_num, agent_id, block_id)` PK is cleaner — still co-located in the per-game DuckDB, joinable via `day_num`.

**On Phase 3 priority:** Hugi overruled — all phases are equally important. The explorer UI is core to the research workflow, not polish.
