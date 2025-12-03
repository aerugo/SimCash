# Castro Experiments - Research Environment

## Overview

This directory contains **research experiments** replicating and extending Castro et al. (2025) "Strategic Payment Timing" using LLM-based policy optimization. This is a **research environment** separate from the main simulation engine.

**Key Principle**: Research code prioritizes reproducibility and experimentation over production robustness. However, type safety and documentation standards still apply.

> 📖 **Essential Reading**: Before working here, read the main [`/CLAUDE.md`](/CLAUDE.md) for project-wide invariants (money as i64, determinism, etc.).

---

## 🔴 Critical Research Invariants

### 1. Reproducibility is Mandatory

Every experiment must be fully reproducible from recorded artifacts.

```python
# ✅ CORRECT - Store all inputs for reproducibility
experiment_db.store_policy_iteration(
    iteration_id=uuid.uuid4(),
    policy_json=json.dumps(policy),
    policy_hash=hashlib.sha256(json.dumps(policy).encode()).hexdigest(),
    llm_prompt=prompt,
    llm_response=response,
    created_at=datetime.utcnow(),
)

# ❌ NEVER DO THIS - Untraceable experiment
new_policy = llm.optimize(current_policy)  # Lost forever!
```

### 2. Money Values Follow Project Convention

All money values are **i64 cents**, even in research scripts.

```python
# ✅ CORRECT - Integer cents
collateral_amount: int = 25_000_000  # $250,000.00

# ❌ NEVER DO THIS
collateral_amount: float = 250000.00  # NO FLOATS FOR MONEY
```

### 3. LLM Interactions Must Be Logged

Every LLM call must be recorded in the experiment database.

```python
# ✅ CORRECT - Full logging
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
)
db.store_llm_interaction(
    prompt=json.dumps(messages),
    response=response.choices[0].message.content,
    model=response.model,
    tokens_used=response.usage.total_tokens,
)

# ❌ NEVER DO THIS - Unreproducible
policy = llm.get_policy()  # Where did this come from?
```

---

## Python Style Guide

This environment follows the same strict typing conventions as [`/api/CLAUDE.md`](/api/CLAUDE.md).

### Type System Requirements

```python
# ✅ CORRECT - Complete type annotations
def run_simulation(
    config_path: Path,
    seed: int,
    simcash_root: Path,
) -> dict[str, int | float | str]:
    """Run a single simulation and return results."""
    ...

# ✅ CORRECT - Dataclasses for structured data
@dataclass
class SimulationResult:
    seed: int
    bank_a_cost: int  # cents
    bank_b_cost: int  # cents
    total_cost: int   # cents
    settlement_rate: float

# ❌ WRONG - Missing types
def run_simulation(config_path, seed, simcash_root):  # Missing annotations!
    ...
```

### Use Native Python Types

```python
# ✅ CORRECT - Python 3.11+ syntax
def aggregate_results(results: list[SimulationResult]) -> dict[str, float]:
    ...

def find_best_policy(policies: dict[str, PolicyConfig]) -> str | None:
    ...

# ❌ WRONG - Legacy typing imports
from typing import List, Dict, Optional  # Don't do this
```

### LLM Response Handling

LLM responses are inherently untyped. Use proper parsing:

```python
# ✅ CORRECT - Parse and validate LLM output
def parse_policy_response(response: str) -> dict[str, int | float | str]:
    """Parse LLM response into policy dict."""
    try:
        policy = json.loads(response)
        # Validate required fields
        if "action" not in policy:
            raise ValueError("Missing 'action' field")
        return policy
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}") from e

# ❌ WRONG - Trust LLM output blindly
policy = json.loads(llm_response)  # May fail or return unexpected types
```

---

## Project Structure

```
experiments/castro/
├── CLAUDE.md                 ← You are here
├── HANDOVER.md               ← Current status and next steps
├── LAB_NOTES.md              ← Detailed research log
├── RESEARCH_PAPER.md         ← Draft paper
├── pyproject.toml            ← UV/pip configuration
│
├── configs/                  ← Experiment configurations
│   ├── castro_2period_aligned.yaml
│   ├── castro_12period_aligned.yaml
│   └── castro_joint_aligned.yaml
│
├── policies/                 ← Policy definitions
│   └── seed_policy.json      ← Starting policy for optimization
│
├── scripts/                  ← Experiment scripts
│   ├── optimizer.py          ← LLM policy optimizer
│   ├── optimizer_v2.py       ← Improved optimizer
│   ├── optimizer_v3.py       ← Latest optimizer version
│   └── reproducible_experiment.py  ← Full experiment runner
│
├── results/                  ← Output databases
│   └── *.db                  ← DuckDB experiment results
│
├── papers/                   ← Reference papers
│   └── castro_et_al.md       ← Original paper
│
└── archive/                  ← Deprecated experiments
    └── pre-castro-alignment/ ← Old configs (don't use)
```

---

## Development Setup

### Initial Setup

```bash
# From experiments/castro directory
cd experiments/castro

# Create virtual environment and install dependencies
uv sync --extra dev

# This installs:
# - Research dependencies (openai, duckdb, matplotlib, seaborn)
# - payment-simulator package from ../../api (with Rust backend)
# - Dev tools (mypy, ruff, pytest)
```

### After Rust Backend Changes

If you modify the Rust code in `/backend/`, rebuild:

```bash
# From experiments/castro directory
uv sync --extra dev --reinstall-package payment-simulator
```

### Running Experiments

```bash
# Set OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Run experiment
.venv/bin/python scripts/reproducible_experiment.py \
    --experiment exp1 \
    --output results/exp1.db

# Replay experiment from database
.venv/bin/python scripts/reproducible_experiment.py \
    --replay results/exp1.db
```

---

## Type Checking & Linting

```bash
# From experiments/castro directory

# Type checking (MUST pass before committing)
.venv/bin/python -m mypy scripts/

# Linting (MUST pass before committing)
.venv/bin/python -m ruff check scripts/

# Format code
.venv/bin/python -m ruff format scripts/
```

---

## Experiment Workflow

### 1. Before Starting an Experiment

1. Read `LAB_NOTES.md` for context on previous experiments
2. Verify configuration alignment with Castro paper
3. Check that `deferred_crediting: true` and `deadline_cap_at_eod: true` are set

### 2. During an Experiment

1. **Log everything** to the experiment database
2. Use deterministic seeds for reproducibility
3. Document observations in `LAB_NOTES.md`

### 3. After an Experiment

1. Export results for analysis
2. Update `RESEARCH_PAPER.md` with findings
3. Archive raw data in `results/`

---

## Configuration Requirements

### Castro-Aligned Settings

All experiments must use these settings for Castro paper alignment:

```yaml
# Required for Castro model alignment
deferred_crediting: true      # Credits applied at end of tick
deadline_cap_at_eod: true     # All deadlines capped at day end
```

### Cost Model Parameters

```yaml
costs:
  collateral_cost_per_tick_bps: 83  # 10%/year ÷ 12 ticks
  overdraft_cost_per_tick_bps: 500  # 60%/year ÷ 12 ticks (penalty rate)
  delay_penalty_per_tick: 100       # $1 per tick delay
  eod_penalty: 1000000              # $10k EOD failure penalty
```

---

## Database Schema

Experiments store results in DuckDB:

```sql
-- Policy iterations
CREATE TABLE policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    policy_json TEXT NOT NULL,
    policy_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

-- LLM interactions
CREATE TABLE llm_interactions (
    interaction_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    model VARCHAR NOT NULL,
    tokens_used INTEGER,
    created_at TIMESTAMP NOT NULL
);

-- Simulation runs
CREATE TABLE simulation_runs (
    run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    bank_a_cost BIGINT NOT NULL,  -- cents
    bank_b_cost BIGINT NOT NULL,  -- cents
    total_cost BIGINT NOT NULL,   -- cents
    settlement_rate DOUBLE NOT NULL
);
```

---

## 🔴 Debugging LLM-Generated Policy Failures

When the LLM generates policies that fail validation or simulation, follow this systematic approach:

### NEVER Post-Process or Retrofit

```python
# ❌ NEVER DO THIS
def fix_policy(policy: dict) -> dict:
    """Manually fix LLM output."""
    # Replace wrong actions with correct ones
    policy["strategic_collateral_tree"]["action"] = "HoldCollateral"  # NO!
    return policy

# ✅ CORRECT - Find and fix the root cause
# 1. Investigate why LLM generated wrong output
# 2. Fix the prompt, schema, or validation
# 3. Let the retry mechanism work
```

### Systematic Debugging Checklist

When LLM policies fail, investigate in this order:

1. **Check the prompt** (`generator/robust_policy_agent.py`)
   - Does it explain ALL tree types and their valid actions?
   - Are examples complete and correct?
   - Is the vocabulary clear and unambiguous?

2. **Check Pydantic schema** (`schemas/dynamic.py`)
   - Does validation distinguish between tree types?
   - Are action types properly constrained per tree?
   - Look for `create_constrained_policy_model()`

3. **Check CLI validation** (`payment-sim validate-policy`)
   - Use `--functional-tests` flag to catch runtime errors
   - Basic validation may pass but simulation may fail

4. **Verify retry mechanism** (`scripts/reproducible_experiment.py`)
   - Is `validate_and_fix_policy()` being called?
   - Does error message reach the LLM for fixing?
   - Check `MAX_VALIDATION_RETRIES`

### Current Known Issues (2025-12-03)

**Issue**: LLM uses payment actions (`Hold`) in collateral trees instead of collateral actions (`HoldCollateral`)

**Root Causes Identified**:
1. Prompt only shows payment_tree examples (no collateral tree examples)
2. Pydantic schema uses same `ActionLiteral` for all tree types
3. Experiment doesn't use `--functional-tests` in validation

**Required Fixes**:
1. Add per-tree-type action sets to the prompt
2. Update `create_constrained_policy_model()` to use tree-specific actions
3. Enable `--functional-tests` in experiment validation

---

## Anti-Patterns

### Unreproducible Experiments

```python
# ❌ WRONG - No logging
policy = llm.optimize(current_policy)
result = run_simulation(policy)
print(f"Cost: {result}")  # Lost forever!

# ✅ CORRECT - Full logging
policy, llm_log = llm.optimize_with_log(current_policy)
db.store_iteration(policy, llm_log)
result = run_simulation(policy)
db.store_result(result)
```

### Float Money

```python
# ❌ WRONG
cost = 250000.50  # Float dollars

# ✅ CORRECT
cost = 25_000_050  # Integer cents ($250,000.50)
```

### Unvalidated LLM Output

```python
# ❌ WRONG - Trust LLM blindly
policy = json.loads(llm_response)
run_with_policy(policy)

# ✅ CORRECT - Validate structure
policy = parse_and_validate_policy(llm_response)
if not is_valid_policy(policy):
    raise ValueError("LLM produced invalid policy")
run_with_policy(policy)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `LAB_NOTES.md` | Detailed research log (read first!) |
| `HANDOVER.md` | Current status and next steps |
| `RESEARCH_PAPER.md` | Draft paper with results |
| `configs/castro_*_aligned.yaml` | Castro-aligned experiment configs |
| `scripts/reproducible_experiment.py` | Main experiment runner |
| `policies/seed_policy.json` | Starting policy for optimization |

---

## Checklist Before Committing

### Research Integrity
- [ ] All LLM interactions logged to database
- [ ] All simulation results stored with seeds
- [ ] Experiment is reproducible from database

### Code Quality
- [ ] All functions have type annotations
- [ ] mypy passes: `.venv/bin/python -m mypy scripts/`
- [ ] ruff passes: `.venv/bin/python -m ruff check scripts/`
- [ ] Money values are integer cents

### Documentation
- [ ] `LAB_NOTES.md` updated with observations
- [ ] `HANDOVER.md` updated if status changed
- [ ] Config files documented with purpose

---

*Last updated: 2025-12-03*
*For project-wide patterns, see root `/CLAUDE.md`*
*For API patterns, see `/api/CLAUDE.md`*
