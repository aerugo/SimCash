# Time Model Clarification: Ticks, Days, Rounds, and Optimization Intervals

**Date:** 2026-02-21  
**Author:** Nash  
**Status:** Design proposal  

## 1. Problem Statement

The web sandbox conflates three distinct temporal concepts — **scenario days**, **optimization rounds**, and **scenario repetitions** — into a single `max_days` parameter. This creates confusion:

- A "10-day crisis scenario" (`num_days: 10`, `ticks_per_day: 100`) currently maps each scenario-day to one "round" in the UI, with optimization after each. But these are engine days with distinct event schedules (crisis on days 1–3, intervention on day 4, recovery on days 5–10). They are **not** repetitions.

- A "2-bank, 12-tick" experiment (`num_days: 1`, `ticks_per_day: 12`) should be **repeated** across multiple rounds with different seeds — each round is a full re-run of the same 1-day scenario. The paper calls these "iterations."

- The current `Game.run_day()` treats every "day" as a fresh simulation with `seed = base_seed + day_num`, but it always runs the **entire** multi-day scenario (all `num_days * ticks_per_day` ticks) each time. So for a 10-day scenario, each "round" already simulates all 10 days. The `max_days` parameter is really "max rounds."

- Optimization intervals are expressed as "every N rounds" but there's a real use case for intra-day optimization (every N ticks) or per-scenario-day optimization in multi-day scenarios.

## 2. Terminology

We need unambiguous terms. Here's the proposed vocabulary:

| Term | Definition | Example |
|------|-----------|---------|
| **Tick** | Atomic time unit in the engine. One call to `orch.tick()`. | Tick 0, tick 1, ..., tick 99 |
| **Scenario day** | A group of ticks within one engine run. The engine emits `EndOfDay` events at day boundaries. | Day 1 = ticks 0–99, Day 2 = ticks 100–199 |
| **Scenario** | One complete engine run: all scenario days, all ticks. Defined by the YAML config. | `num_days: 10, ticks_per_day: 100` = 1000 ticks |
| **Round** | One complete execution of the scenario with a specific seed. Multiple rounds = scenario repetitions. | Round 1 (seed 42), Round 2 (seed 43), Round 3 (seed 44) |
| **Experiment** | The full sequence of rounds, including policy optimization between them. | 10 rounds with optimization every round |
| **Optimization step** | An LLM policy update. Occurs at configurable intervals. | After round 1, after round 3, etc. |

### Key distinction

- **Scenario days are INSIDE a single round.** A 10-day crisis scenario has 10 scenario days per round.
- **Rounds are REPETITIONS of the scenario.** Each round runs the full scenario with a (possibly different) seed.
- **The current code conflates these.** `max_days` in `Game` actually means "max rounds," and each "day" is a full scenario execution.

## 3. Current Architecture (What Exists)

### 3.1 Rust Engine

The engine is a single-run simulator. One call to `Orchestrator.new(config)` creates a simulation that runs for `num_days * ticks_per_day` total ticks. The engine:

- Manages `TimeManager` with `ticks_per_day` granularity
- Emits `EndOfDay` events at day boundaries
- Supports day-specific `scenario_events` (e.g., crisis triggers, interventions)
- Has no concept of "rounds" — it just runs ticks

### 3.2 Web Backend (`game.py`)

```
Game:
  max_days          # Actually means "max rounds"
  run_day()         # Actually runs one FULL scenario (all num_days * ticks_per_day)
  _base_seed + day_num  # Seed derivation: base + round_index
  optimization_interval  # Every N "days" (actually rounds)
```

Each call to `run_day()`:
1. Creates a fresh `Orchestrator` with the full YAML config
2. Runs ALL ticks (`ticks_per_day * num_days`)
3. Collects ALL events, balances, costs
4. Returns a single `GameDay` (really a `RoundResult`)

### 3.3 Paper's Experiment Runner (`optimization.py`)

The paper's runner uses:
- **"Iterations"** = what we call rounds
- `SeedMatrix` for deterministic per-iteration, per-agent seed derivation
- `max_iterations` for convergence
- Bootstrap evaluation with N samples per iteration
- No concept of intra-scenario optimization

### 3.4 Frontend (`GameView.tsx`)

Uses "Round" in the UI, "day" in the code. The `selectedDay` state variable indexes into `gameState.days[]`, which are actually rounds.

## 4. Proposed Architecture

### 4.1 Rename for Clarity

In `game.py`:

```python
class RoundResult:  # Was: GameDay
    round_num: int          # Was: day_num
    seed: int
    scenario_days: int      # NEW: how many engine days were in this round
    ticks_per_day: int      # NEW: for display
    ...

class Game:
    max_rounds: int         # Was: max_days
    rounds: list[RoundResult]  # Was: days
    current_round: int      # Was: current_day
```

### 4.2 Seed Derivation

Current: `seed = base_seed + round_index` (simple increment, not great).

Proposed: Use the paper's `SeedMatrix` approach:

```python
def round_seed(master_seed: int, round_index: int) -> int:
    """Deterministic seed for a round, derived from master seed."""
    # Same approach as SeedMatrix._derive_iteration_seed
    import hashlib
    h = hashlib.sha256(f"{master_seed}:round:{round_index}".encode())
    return int.from_bytes(h.digest()[:8], 'big') % (2**63)
```

This ensures:
- Determinism: same master seed → same round seeds
- Independence: round seeds don't collide or correlate
- Consistency with the paper's methodology

### 4.3 Optimization Interval Options

Currently: `optimization_interval: int` = "every N rounds."

Proposed: A richer configuration:

```python
@dataclass
class OptimizationSchedule:
    kind: Literal["every_round", "every_n_rounds", "every_scenario_day", "every_n_ticks"]
    n: int = 1  # Used for every_n_rounds and every_n_ticks
```

#### Option A: `every_round` (default, current behavior)
Optimize after each complete scenario run. This is the paper's approach.

```
Round 1: [run full scenario] → optimize → Round 2: [run full scenario] → optimize → ...
```

#### Option B: `every_n_rounds`
Optimize every N rounds. Useful for seeing policy drift before correction.

```
Round 1 → Round 2 → optimize → Round 3 → Round 4 → optimize → ...
```

#### Option C: `every_scenario_day`
For multi-day scenarios: pause at each `EndOfDay` boundary within a single round, optimize, then continue. This is the most realistic model — a bank's cash manager reviews EOD results and adjusts for tomorrow.

```
Round 1: [day 1] → optimize → [day 2] → optimize → [day 3] → optimize → ... → [day 10]
         Then: Round 2: [day 1] → optimize → [day 2] → ...
```

**Implementation:** Instead of running all ticks in one `Orchestrator` call, run `ticks_per_day` ticks, pause, optimize, inject new policies, then continue. This requires either:
- (a) Keeping the `Orchestrator` alive between days and updating policies mid-run (needs Rust FFI support for mid-run policy changes), OR
- (b) Running each scenario-day as a separate `Orchestrator` run, carrying forward balances/state (complex, fragile)

**Recommendation:** Option (a) is the clean path. Add `orch.update_agent_policy(agent_id, policy_json)` to the Rust FFI. The engine already tracks per-day state via `TimeManager`.

#### Option D: `every_n_ticks`
Optimize every N ticks within a scenario. This enables intra-day optimization — multiple policy updates per day. Most aggressive and least realistic, but interesting for research.

**Implementation:** Same as Option C but at tick granularity instead of day boundaries.

### 4.4 Intra-Scenario Optimization: Engine Requirements

For Options C and D, the Rust engine needs a new FFI method:

```rust
impl Orchestrator {
    /// Update an agent's policy mid-simulation (between ticks).
    /// The new policy takes effect from the next tick.
    pub fn update_agent_policy(&self, agent_id: &str, policy_json: &str) -> PyResult<()> {
        // Parse policy JSON, update agent's PolicyTree in-place
    }
}
```

This is a significant but well-scoped change:
1. Parse `policy_json` into a `PolicyTree` (already exists: `FromJson` policy type does this)
2. Look up the agent by ID in the orchestrator's state
3. Replace their `PolicyTree` reference
4. The next `tick()` call uses the new policy

**No balance or state reset** — the simulation continues seamlessly with the new policy.

### 4.5 Multi-Round with Same Seed vs Different Seeds

Two valid modes:

1. **Different seed per round** (default): Each round uses a unique seed derived from the master seed. This tests policy robustness across stochastic variations. The paper uses this.

2. **Same seed every round**: All rounds use the same seed. This isolates the effect of policy changes — the only variable is the policy, not the randomness. Useful for debugging and deterministic analysis.

Configuration:
```python
seed_mode: Literal["vary", "fixed"] = "vary"
```

### 4.6 What the LLM Sees Between Rounds

The optimization context should be clear about what happened:

- **For `every_round`:** "You just completed Round N (a full run of the X-day scenario). Here are your costs..."
- **For `every_scenario_day`:** "Day 3 of Round 1 just ended. You've seen 3 of 10 days so far. Here are your costs for today..."
- **For `every_n_ticks`:** "Ticks 48-60 of Day 1 just completed. Here's what happened..."

The LLM prompt builder needs to know which granularity it's operating at.

## 5. Implementation Plan

### Phase 1: Rename and Clarify (No Behavior Change)

1. Rename `GameDay` → `RoundResult` in `game.py`
2. Rename `max_days` → `max_rounds` everywhere (backend, frontend, API, checkpoints)
3. Rename `days[]` → `rounds[]` in game state
4. Update frontend to consistently use "Round" (already mostly does)
5. Update checkpoint schema (with migration for existing checkpoints)
6. **Backward compat:** Accept both `max_days` and `max_rounds` in API, prefer new name

**Estimated effort:** 2–3 hours, purely mechanical.

### Phase 2: Proper Seed Derivation

1. Replace `seed = base_seed + day_num` with hash-based derivation
2. Add `seed_mode: "vary" | "fixed"` config option
3. Expose in frontend launch configuration
4. Update LLM prompts to include seed information

**Estimated effort:** 1 hour.

### Phase 3: Intra-Scenario Optimization (Engine Work)

1. Add `Orchestrator.update_agent_policy(agent_id, policy_json)` to Rust FFI
2. Modify `Game.run_round()` to support pause-at-day-boundary mode
3. Add `OptimizationSchedule` config with `every_round` / `every_scenario_day` modes
4. Update frontend to show scenario-day progress within a round
5. Update LLM prompt builder for intra-scenario context

**Estimated effort:** 1–2 days (mostly Rust FFI + careful state management).

### Phase 4: Arbitrary Tick-Level Optimization

1. Extend pause-and-optimize to work at tick granularity
2. Add `every_n_ticks` optimization mode
3. Update UI with tick-level progress indicators

**Estimated effort:** 4–8 hours (builds on Phase 3).

## 6. Migration and Compatibility

### Checkpoint Schema

Existing checkpoints use `days[]` and `max_days`. Migration:

```python
# In Game.from_checkpoint():
max_rounds = data["config"].get("max_rounds") or data["config"].get("max_days", 10)
rounds = data["progress"].get("rounds") or data["progress"].get("days", [])
```

### API Endpoints

- `/api/games/{id}` response: add `max_rounds`, keep `max_days` as alias
- `/api/games/{id}/days/{n}` → `/api/games/{id}/rounds/{n}` (keep old path as redirect)
- Launch config: accept both `max_days` and `max_rounds`

### Frontend

The frontend already says "Round" in most places. The main changes:
- `gameState.days` → `gameState.rounds` in TypeScript types
- `selectedDay` → `selectedRound` in state
- API calls update to new endpoints (with fallback)

## 7. Interaction with Eval Samples

Currently, `num_eval_samples` runs N additional seeds per round for cost averaging. This is orthogonal to rounds:

- **Eval samples** = parallel seeds within one round for statistical robustness of the cost signal
- **Rounds** = sequential repetitions with policy optimization between them

These remain independent. Eval samples use seeds derived from the round seed (matching the paper's `SeedMatrix` bootstrap approach).

## 8. Summary of Terminology Mapping

| Current Code | Proposed Code | UI Label | Paper Term |
|---|---|---|---|
| `max_days` | `max_rounds` | "Rounds" | `max_iterations` |
| `GameDay` | `RoundResult` | "Round N Results" | iteration result |
| `days[]` | `rounds[]` | Round Timeline | iteration history |
| `day_num` | `round_num` | "Round 1" | iteration index |
| `run_day()` | `run_round()` | — | run iteration |
| `optimization_interval` | `optimization_schedule` | "Optimize every..." | — |
| (implicit) | `scenario_days` | "Day 3/10" within round | — |
| (implicit) | `ticks_per_day` | tick progress | — |

## 9. Open Questions

1. **Should we show scenario-day boundaries in the current UI?** Even without intra-scenario optimization, showing "Day 3/10 within Round 1" would help users understand multi-day scenarios. Low effort, high clarity.

2. **Should the default crisis scenario use intra-scenario optimization?** The crisis scenario has day-specific events (intervention on day 4). Optimizing between scenario-days would be more realistic than optimizing between full scenario repetitions. But it requires Phase 3 (Rust FFI changes).

3. **How should the eval samples interact with intra-scenario optimization?** If optimizing at day boundaries, do we re-run just the next day with N seeds, or the remainder of the scenario? Recommendation: just the next day (cheaper, faster, more focused signal).

4. **Backward compatibility window:** How long do we support `max_days` in the API? Recommendation: indefinitely as an alias — it's cheap and avoids breaking existing links/bookmarks.
