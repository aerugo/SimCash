# Feature Request: Castro Experiment Audit Trail Enhancement

**Requested by:** Research Team
**Priority:** High
**Date:** 2025-12-09

## Summary

Enhance the Castro experiment persistence layer to store complete audit trails for LLM-driven policy optimization. This enables research reproducibility, debugging, and compliance auditing by capturing the full context of every optimization decision.

## Current State

The `policy_iterations` table stores:
- `old_policy_json` / `new_policy_json` - Complete policy snapshots
- `old_cost` / `new_cost` / `cost_improvement` - Cost metrics
- `was_accepted` - Accept/reject decision
- `validation_errors` - Rejection reasons
- `llm_model` / `tokens_used` / `llm_latency_seconds` - LLM metadata

## Requirements

### Must Store

1. **Full LLM interaction** - Complete prompt sent, raw response received, any parsing errors
2. **Policy diffs** - Human-readable diff and structured parameter changes at every iteration
3. **Simulation context** - What the LLM "saw" (best/worst seed verbose output, Monte Carlo seeds)
4. **Policy evolution** - Parameter trajectories across all iterations for trend analysis

### Use Cases

- **Debugging**: Why did the LLM make this change? What context did it have?
- **Research**: How do policies evolve? What parameter patterns emerge?
- **Compliance**: Full audit trail of every decision for regulatory review
- **Reproducibility**: Re-run any iteration with exact same context

## Schema Design

Three new audit tables, foreign-keyed to the existing `policy_iterations` table:

### Table 1: `llm_interaction_log`

Captures the complete LLM request/response cycle.

```sql
CREATE TABLE llm_interaction_log (
    interaction_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Full prompts
    system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,

    -- Full response
    raw_response TEXT NOT NULL,
    parsed_policy_json TEXT,      -- NULL if parsing failed
    parsing_error TEXT,           -- Error message if parsing failed

    -- LLM reasoning (if extractable from response)
    llm_reasoning TEXT,

    -- Timing
    request_timestamp TIMESTAMP NOT NULL,
    response_timestamp TIMESTAMP NOT NULL,

    FOREIGN KEY (game_id, agent_id, iteration_number)
        REFERENCES policy_iterations(game_id, agent_id, iteration_number)
);

CREATE INDEX idx_llm_log_game ON llm_interaction_log(game_id);
CREATE INDEX idx_llm_log_agent ON llm_interaction_log(game_id, agent_id);
CREATE INDEX idx_llm_log_errors ON llm_interaction_log(game_id) WHERE parsing_error IS NOT NULL;
```

### Table 2: `policy_diffs`

Stores computed diffs and parameter snapshots for evolution tracking.

```sql
CREATE TABLE policy_diffs (
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Human-readable diff
    diff_summary TEXT NOT NULL,

    -- Structured changes for programmatic analysis
    parameter_changes_json VARCHAR,   -- [{"param": "x", "old": 1, "new": 2, "delta": 1}]

    -- Tree modification flags
    payment_tree_changed BOOLEAN NOT NULL DEFAULT FALSE,
    collateral_tree_changed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Full parameter snapshot at this iteration (for trajectory queries)
    parameters_snapshot_json VARCHAR NOT NULL,

    PRIMARY KEY (game_id, agent_id, iteration_number),
    FOREIGN KEY (game_id, agent_id, iteration_number)
        REFERENCES policy_iterations(game_id, agent_id, iteration_number)
);

CREATE INDEX idx_diffs_game ON policy_diffs(game_id);
CREATE INDEX idx_diffs_tree_changes ON policy_diffs(game_id, agent_id)
    WHERE payment_tree_changed OR collateral_tree_changed;
```

### Table 3: `iteration_context`

Stores the simulation context provided to the LLM for each optimization.

```sql
CREATE TABLE iteration_context (
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Monte Carlo evaluation details
    monte_carlo_seeds VARCHAR NOT NULL,   -- JSON array: [123, 456, 789]
    num_samples INTEGER NOT NULL,

    -- Best/worst seed identification
    best_seed INTEGER NOT NULL,
    worst_seed INTEGER NOT NULL,
    best_seed_cost DOUBLE NOT NULL,
    worst_seed_cost DOUBLE NOT NULL,

    -- Verbose output provided to LLM (can be large)
    best_seed_verbose_output TEXT,
    worst_seed_verbose_output TEXT,

    -- Aggregated metrics shown to LLM
    cost_mean DOUBLE NOT NULL,
    cost_std DOUBLE NOT NULL,
    settlement_rate_mean DOUBLE NOT NULL,

    PRIMARY KEY (game_id, agent_id, iteration_number),
    FOREIGN KEY (game_id, agent_id, iteration_number)
        REFERENCES policy_iterations(game_id, agent_id, iteration_number)
);

CREATE INDEX idx_context_game ON iteration_context(game_id);
```

## Pydantic Models

Add to `api/payment_simulator/ai_cash_mgmt/persistence/models.py`:

```python
class LLMInteractionRecord(BaseModel):
    """Full LLM interaction for audit trail."""

    model_config = ConfigDict(
        table_name="llm_interaction_log",
        primary_key=["interaction_id"],
    )

    interaction_id: str = Field(..., description="Unique interaction ID")
    game_id: str = Field(..., description="Foreign key to game_sessions")
    agent_id: str = Field(..., description="Agent being optimized")
    iteration_number: int = Field(..., description="Iteration number")

    system_prompt: str = Field(..., description="System prompt sent to LLM")
    user_prompt: str = Field(..., description="User prompt sent to LLM")
    raw_response: str = Field(..., description="Raw LLM response text")
    parsed_policy_json: str | None = Field(None, description="Parsed policy if successful")
    parsing_error: str | None = Field(None, description="Error if parsing failed")
    llm_reasoning: str | None = Field(None, description="Extracted LLM reasoning")

    request_timestamp: datetime = Field(..., description="When request was sent")
    response_timestamp: datetime = Field(..., description="When response was received")


class PolicyDiffRecord(BaseModel):
    """Policy diff for evolution tracking."""

    model_config = ConfigDict(
        table_name="policy_diffs",
        primary_key=["game_id", "agent_id", "iteration_number"],
    )

    game_id: str = Field(..., description="Foreign key to game_sessions")
    agent_id: str = Field(..., description="Agent being optimized")
    iteration_number: int = Field(..., description="Iteration number")

    diff_summary: str = Field(..., description="Human-readable diff summary")
    parameter_changes_json: str | None = Field(None, description="Structured parameter changes")
    payment_tree_changed: bool = Field(False, description="Whether payment tree was modified")
    collateral_tree_changed: bool = Field(False, description="Whether collateral tree was modified")
    parameters_snapshot_json: str = Field(..., description="All parameters at this iteration")


class IterationContextRecord(BaseModel):
    """Simulation context provided to LLM."""

    model_config = ConfigDict(
        table_name="iteration_context",
        primary_key=["game_id", "agent_id", "iteration_number"],
    )

    game_id: str = Field(..., description="Foreign key to game_sessions")
    agent_id: str = Field(..., description="Agent being optimized")
    iteration_number: int = Field(..., description="Iteration number")

    monte_carlo_seeds: list[int] = Field(..., description="Seeds used in Monte Carlo evaluation")
    num_samples: int = Field(..., description="Number of Monte Carlo samples")

    best_seed: int = Field(..., description="Seed with lowest cost for this agent")
    worst_seed: int = Field(..., description="Seed with highest cost for this agent")
    best_seed_cost: float = Field(..., description="Cost at best seed")
    worst_seed_cost: float = Field(..., description="Cost at worst seed")

    best_seed_verbose_output: str | None = Field(None, description="Verbose output from best seed")
    worst_seed_verbose_output: str | None = Field(None, description="Verbose output from worst seed")

    cost_mean: float = Field(..., description="Mean cost across samples")
    cost_std: float = Field(..., description="Std dev of cost across samples")
    settlement_rate_mean: float = Field(..., description="Mean settlement rate")
```

## Repository Methods

Add to `GameRepository`:

```python
# Save methods
def save_llm_interaction(self, record: LLMInteractionRecord) -> None: ...
def save_policy_diff(self, record: PolicyDiffRecord) -> None: ...
def save_iteration_context(self, record: IterationContextRecord) -> None: ...

# Query methods for analysis
def get_llm_interactions(
    self, game_id: str, agent_id: str | None = None
) -> list[LLMInteractionRecord]: ...

def get_policy_diffs(
    self, game_id: str, agent_id: str | None = None
) -> list[PolicyDiffRecord]: ...

def get_iteration_contexts(
    self, game_id: str, agent_id: str | None = None
) -> list[IterationContextRecord]: ...

def get_parameter_trajectory(
    self, game_id: str, agent_id: str, param_name: str
) -> list[tuple[int, float]]:
    """Extract parameter values across iterations for trend analysis."""
    ...

def get_failed_parsing_attempts(
    self, game_id: str | None = None
) -> list[LLMInteractionRecord]:
    """Get all iterations where LLM response failed to parse."""
    ...
```

## Integration Points

### 1. `CastroLLMClient` (castro/llm_client.py)

Modify to return raw response alongside parsed policy:

```python
@dataclass
class LLMResponse:
    """Full LLM response for audit."""
    raw_response: str
    parsed_policy: dict[str, Any] | None
    parsing_error: str | None
    request_timestamp: datetime
    response_timestamp: datetime

async def generate_policy_with_audit(
    self,
    prompt: str,
    current_policy: dict[str, Any],
    context: dict[str, Any],
) -> LLMResponse:
    """Generate policy with full audit information."""
    ...
```

### 2. `ExperimentRunner` (castro/runner.py)

After each optimization iteration:

```python
# After LLM call
llm_interaction = LLMInteractionRecord(
    interaction_id=f"{game_id}_{agent_id}_{iteration}",
    game_id=game_id,
    agent_id=agent_id,
    iteration_number=iteration,
    system_prompt=SYSTEM_PROMPT,
    user_prompt=user_prompt,
    raw_response=llm_response.raw_response,
    parsed_policy_json=json.dumps(llm_response.parsed_policy) if llm_response.parsed_policy else None,
    parsing_error=llm_response.parsing_error,
    request_timestamp=llm_response.request_timestamp,
    response_timestamp=llm_response.response_timestamp,
)
repo.save_llm_interaction(llm_interaction)

# After policy evaluation
diff_record = PolicyDiffRecord(
    game_id=game_id,
    agent_id=agent_id,
    iteration_number=iteration,
    diff_summary="\n".join(compute_policy_diff(old_policy, new_policy)),
    parameter_changes_json=json.dumps(compute_parameter_changes(old_policy, new_policy)),
    payment_tree_changed=old_policy.get("payment_tree") != new_policy.get("payment_tree"),
    collateral_tree_changed=old_policy.get("strategic_collateral_tree") != new_policy.get("strategic_collateral_tree"),
    parameters_snapshot_json=json.dumps(new_policy.get("parameters", {})),
)
repo.save_policy_diff(diff_record)

# Save context
context_record = IterationContextRecord(
    game_id=game_id,
    agent_id=agent_id,
    iteration_number=iteration,
    monte_carlo_seeds=seeds,
    num_samples=len(seeds),
    best_seed=agent_context.best_seed,
    worst_seed=agent_context.worst_seed,
    best_seed_cost=agent_context.best_seed_cost,
    worst_seed_cost=agent_context.worst_seed_cost,
    best_seed_verbose_output=agent_context.best_seed_output,
    worst_seed_verbose_output=agent_context.worst_seed_output,
    cost_mean=agent_context.mean_cost,
    cost_std=agent_context.cost_std,
    settlement_rate_mean=settlement_rate,
)
repo.save_iteration_context(context_record)
```

## Example Queries

### Policy Evolution Report

```sql
SELECT
    pi.iteration_number,
    pd.diff_summary,
    pi.old_cost,
    pi.new_cost,
    pi.was_accepted,
    ic.best_seed,
    ic.worst_seed
FROM policy_iterations pi
JOIN policy_diffs pd USING (game_id, agent_id, iteration_number)
JOIN iteration_context ic USING (game_id, agent_id, iteration_number)
WHERE pi.game_id = ? AND pi.agent_id = ?
ORDER BY pi.iteration_number;
```

### Parameter Trajectory

```sql
SELECT
    iteration_number,
    json_extract(parameters_snapshot_json, '$.urgency_threshold') as urgency_threshold,
    json_extract(parameters_snapshot_json, '$.liquidity_buffer_factor') as liquidity_buffer
FROM policy_diffs
WHERE game_id = ? AND agent_id = ?
ORDER BY iteration_number;
```

### Failed Parsing Analysis

```sql
SELECT
    game_id,
    agent_id,
    iteration_number,
    parsing_error,
    LEFT(raw_response, 500) as response_preview
FROM llm_interaction_log
WHERE parsing_error IS NOT NULL
ORDER BY request_timestamp DESC;
```

### LLM Reasoning Review

```sql
SELECT
    iteration_number,
    llm_reasoning,
    pd.diff_summary,
    pi.was_accepted
FROM llm_interaction_log lil
JOIN policy_diffs pd USING (game_id, agent_id, iteration_number)
JOIN policy_iterations pi USING (game_id, agent_id, iteration_number)
WHERE lil.game_id = ? AND lil.agent_id = ?
ORDER BY iteration_number;
```

## Storage Considerations

| Table | Estimated Row Size | Notes |
|-------|-------------------|-------|
| `llm_interaction_log` | 10-50 KB | Prompts and responses can be large |
| `policy_diffs` | 1-5 KB | Mostly small JSON |
| `iteration_context` | 10-100 KB | Verbose output can be large |

**Recommendations:**
- Consider TEXT compression for verbose output columns
- Implement retention policy (e.g., keep detailed audit for 90 days, then archive)
- Index only necessary columns to balance write performance

## Migration

```sql
-- Migration: 004_add_audit_tables.sql

-- Table 1: LLM Interaction Log
CREATE TABLE IF NOT EXISTS llm_interaction_log (
    interaction_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    parsed_policy_json TEXT,
    parsing_error TEXT,
    llm_reasoning TEXT,
    request_timestamp TIMESTAMP NOT NULL,
    response_timestamp TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_log_game ON llm_interaction_log(game_id);
CREATE INDEX IF NOT EXISTS idx_llm_log_agent ON llm_interaction_log(game_id, agent_id);

-- Table 2: Policy Diffs
CREATE TABLE IF NOT EXISTS policy_diffs (
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    diff_summary TEXT NOT NULL,
    parameter_changes_json VARCHAR,
    payment_tree_changed BOOLEAN NOT NULL DEFAULT FALSE,
    collateral_tree_changed BOOLEAN NOT NULL DEFAULT FALSE,
    parameters_snapshot_json VARCHAR NOT NULL,
    PRIMARY KEY (game_id, agent_id, iteration_number)
);

CREATE INDEX IF NOT EXISTS idx_diffs_game ON policy_diffs(game_id);

-- Table 3: Iteration Context
CREATE TABLE IF NOT EXISTS iteration_context (
    game_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    monte_carlo_seeds VARCHAR NOT NULL,
    num_samples INTEGER NOT NULL,
    best_seed INTEGER NOT NULL,
    worst_seed INTEGER NOT NULL,
    best_seed_cost DOUBLE NOT NULL,
    worst_seed_cost DOUBLE NOT NULL,
    best_seed_verbose_output TEXT,
    worst_seed_verbose_output TEXT,
    cost_mean DOUBLE NOT NULL,
    cost_std DOUBLE NOT NULL,
    settlement_rate_mean DOUBLE NOT NULL,
    PRIMARY KEY (game_id, agent_id, iteration_number)
);

CREATE INDEX IF NOT EXISTS idx_context_game ON iteration_context(game_id);
```

## Acceptance Criteria

- [ ] All three audit tables created with proper indexes
- [ ] Every LLM call logs full prompt/response to `llm_interaction_log`
- [ ] Every iteration stores diff in `policy_diffs`
- [ ] Every iteration stores context in `iteration_context`
- [ ] Repository methods for saving and querying audit data
- [ ] Parameter trajectory query works correctly
- [ ] Migration script tested and documented
- [ ] Unit tests for all new persistence methods
- [ ] Existing `policy_iterations` functionality unchanged

## Files to Modify

- `api/payment_simulator/ai_cash_mgmt/persistence/models.py` - Add new models
- `api/payment_simulator/ai_cash_mgmt/persistence/repository.py` - Add save/query methods
- `api/migrations/004_add_audit_tables.sql` - Migration script
- `experiments/castro/castro/llm_client.py` - Return full response for audit
- `experiments/castro/castro/runner.py` - Persist audit records after each iteration
- `api/payment_simulator/ai_cash_mgmt/prompts/policy_diff.py` - Add structured diff output
