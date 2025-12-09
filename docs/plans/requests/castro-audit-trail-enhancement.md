# Feature Request: Castro Experiment Audit Trail Enhancement

**Requested by:** Research Team
**Priority:** High
**Date:** 2025-12-09

## Summary

Enhance the Castro experiment persistence layer to store complete audit trails for LLM-driven policy optimization. Currently, only the final parsed policies are stored. We need full traceability of the optimization process for research reproducibility, debugging, and compliance auditing.

## Current State

The `policy_iterations` table stores:
- `old_policy_json` / `new_policy_json` - Complete policy snapshots
- `old_cost` / `new_cost` / `cost_improvement` - Cost metrics
- `was_accepted` - Accept/reject decision
- `validation_errors` - Rejection reasons
- `llm_model` / `tokens_used` / `llm_latency_seconds` - LLM metadata

## What's Missing

### 1. LLM Interaction Audit Trail

| Field | Description | Use Case |
|-------|-------------|----------|
| `prompt_sent` | Full prompt sent to LLM | Debug prompt engineering, reproduce results |
| `raw_llm_response` | Complete LLM response before parsing | Debug parsing failures, analyze LLM behavior |
| `llm_reasoning` | LLM's explanation for changes (if provided) | Understand optimization decisions |

### 2. Policy Diff Persistence

| Field | Description | Use Case |
|-------|-------------|----------|
| `policy_diff` | Human-readable diff between old/new policy | Quick audit without recomputing |
| `parameter_changes` | Structured list of parameter changes | Trend analysis, visualization |
| `tree_structure_changed` | Boolean flags for tree modifications | Filter structural vs. parameter changes |

### 3. Simulation Context

| Field | Description | Use Case |
|-------|-------------|----------|
| `best_seed_verbose_output` | Verbose output from best-performing seed | Understand what LLM saw |
| `worst_seed_verbose_output` | Verbose output from worst-performing seed | Understand failure modes |
| `monte_carlo_seeds` | List of seeds used in evaluation | Full reproducibility |

## Proposed Schema Changes

### Option A: Extend `policy_iterations` Table

```sql
ALTER TABLE policy_iterations ADD COLUMN prompt_sent TEXT;
ALTER TABLE policy_iterations ADD COLUMN raw_llm_response TEXT;
ALTER TABLE policy_iterations ADD COLUMN llm_reasoning TEXT;
ALTER TABLE policy_iterations ADD COLUMN policy_diff_json VARCHAR;  -- JSON array of change descriptions
ALTER TABLE policy_iterations ADD COLUMN best_seed_context TEXT;
ALTER TABLE policy_iterations ADD COLUMN worst_seed_context TEXT;
ALTER TABLE policy_iterations ADD COLUMN monte_carlo_seeds VARCHAR;  -- JSON array
```

### Option B: Separate Audit Tables (Recommended)

Better for query performance and storage management:

```sql
-- Detailed LLM interaction log
CREATE TABLE llm_interaction_log (
    interaction_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Full LLM context
    system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    parsed_policy_json TEXT,  -- NULL if parsing failed
    parsing_error TEXT,       -- Error message if parsing failed

    -- LLM reasoning (extracted or explicit)
    llm_reasoning TEXT,

    -- Timing
    request_timestamp TIMESTAMP NOT NULL,
    response_timestamp TIMESTAMP NOT NULL,

    FOREIGN KEY (game_id, agent_id, iteration_number)
        REFERENCES policy_iterations(game_id, agent_id, iteration_number)
);

-- Policy evolution tracking
CREATE TABLE policy_diffs (
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Computed diff
    diff_summary TEXT NOT NULL,           -- Human-readable summary
    parameter_changes_json VARCHAR,       -- Structured parameter changes
    payment_tree_changed BOOLEAN,
    collateral_tree_changed BOOLEAN,

    -- For trend analysis
    parameters_snapshot_json VARCHAR,     -- All parameter values at this iteration

    PRIMARY KEY (game_id, agent_id, iteration_number),
    FOREIGN KEY (game_id, agent_id, iteration_number)
        REFERENCES policy_iterations(game_id, agent_id, iteration_number)
);

-- Simulation context provided to LLM
CREATE TABLE iteration_context (
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Monte Carlo context
    monte_carlo_seeds VARCHAR NOT NULL,   -- JSON array of seeds
    best_seed INTEGER NOT NULL,
    worst_seed INTEGER NOT NULL,
    best_seed_cost DOUBLE NOT NULL,
    worst_seed_cost DOUBLE NOT NULL,

    -- Verbose output provided to LLM
    best_seed_verbose_output TEXT,
    worst_seed_verbose_output TEXT,

    -- Aggregated metrics
    cost_mean DOUBLE NOT NULL,
    cost_std DOUBLE NOT NULL,
    settlement_rate_mean DOUBLE NOT NULL,

    PRIMARY KEY (game_id, agent_id, iteration_number),
    FOREIGN KEY (game_id, agent_id, iteration_number)
        REFERENCES policy_iterations(game_id, agent_id, iteration_number)
);
```

## Implementation Requirements

### 1. Model Updates

Add new Pydantic models in `api/payment_simulator/ai_cash_mgmt/persistence/models.py`:

```python
class LLMInteractionRecord(BaseModel):
    """Full LLM interaction for audit trail."""
    interaction_id: str
    game_id: str
    agent_id: str
    iteration_number: int
    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy_json: str | None
    parsing_error: str | None
    llm_reasoning: str | None
    request_timestamp: datetime
    response_timestamp: datetime

class PolicyDiffRecord(BaseModel):
    """Policy diff for evolution tracking."""
    game_id: str
    agent_id: str
    iteration_number: int
    diff_summary: str
    parameter_changes_json: str | None
    payment_tree_changed: bool
    collateral_tree_changed: bool
    parameters_snapshot_json: str | None

class IterationContextRecord(BaseModel):
    """Simulation context provided to LLM."""
    game_id: str
    agent_id: str
    iteration_number: int
    monte_carlo_seeds: list[int]
    best_seed: int
    worst_seed: int
    best_seed_cost: float
    worst_seed_cost: float
    best_seed_verbose_output: str | None
    worst_seed_verbose_output: str | None
    cost_mean: float
    cost_std: float
    settlement_rate_mean: float
```

### 2. Repository Updates

Add methods to `GameRepository`:

```python
def save_llm_interaction(self, record: LLMInteractionRecord) -> None: ...
def save_policy_diff(self, record: PolicyDiffRecord) -> None: ...
def save_iteration_context(self, record: IterationContextRecord) -> None: ...

# Query methods for analysis
def get_policy_evolution(self, game_id: str, agent_id: str) -> list[PolicyDiffRecord]: ...
def get_parameter_trajectory(self, game_id: str, agent_id: str, param: str) -> list[tuple[int, float]]: ...
def get_llm_interactions(self, game_id: str) -> list[LLMInteractionRecord]: ...
```

### 3. Integration Points

Update `ExperimentRunner` and `PolicyOptimizer` to capture and persist:

1. **Before LLM call**: Capture full prompt (system + user)
2. **After LLM call**: Capture raw response, timing
3. **After parsing**: Capture parsed policy or error
4. **After evaluation**: Capture diff, context

### 4. Castro-Specific Updates

In `experiments/castro/castro/`:

- `runner.py`: Persist iteration context after each Monte Carlo evaluation
- `llm_client.py`: Return raw response alongside parsed policy
- New `audit.py`: Centralize audit record creation

## Query Examples

### Policy Evolution Report

```sql
SELECT
    pi.iteration_number,
    pd.diff_summary,
    pi.old_cost,
    pi.new_cost,
    pi.was_accepted
FROM policy_iterations pi
JOIN policy_diffs pd USING (game_id, agent_id, iteration_number)
WHERE pi.game_id = ? AND pi.agent_id = ?
ORDER BY pi.iteration_number;
```

### Parameter Trajectory

```sql
SELECT
    iteration_number,
    json_extract(parameters_snapshot_json, '$.urgency_threshold') as urgency_threshold
FROM policy_diffs
WHERE game_id = ? AND agent_id = ?
ORDER BY iteration_number;
```

### Failed Parsing Analysis

```sql
SELECT
    game_id,
    iteration_number,
    parsing_error,
    raw_response
FROM llm_interaction_log
WHERE parsing_error IS NOT NULL;
```

## Storage Considerations

- **Verbose output**: Can be large (10-100KB per seed). Consider compression or separate blob storage for production.
- **Retention policy**: Define how long to keep detailed audit logs vs. summary data.
- **Indexing**: Index on `(game_id, agent_id)` for evolution queries.

## Acceptance Criteria

1. Every LLM interaction is logged with full prompt and response
2. Policy diffs are computed and persisted at each iteration
3. Simulation context (best/worst seed output) is persisted
4. Query API exists for policy evolution analysis
5. Existing `policy_iterations` functionality unchanged
6. Migration script for schema changes
7. Unit tests for new persistence methods

## Open Questions

1. Should we store the verbose output compressed (gzip)?
2. What's the retention policy for detailed audit data?
3. Should we add a CLI command to export policy evolution as a report?
4. Do we need real-time streaming of audit data, or batch persistence is sufficient?

## Related Files

- `api/payment_simulator/ai_cash_mgmt/persistence/models.py` - Current models
- `api/payment_simulator/ai_cash_mgmt/persistence/repository.py` - Current repository
- `api/payment_simulator/ai_cash_mgmt/prompts/policy_diff.py` - Diff computation (runtime only)
- `experiments/castro/castro/runner.py` - Main experiment runner
- `experiments/castro/castro/llm_client.py` - LLM interaction
