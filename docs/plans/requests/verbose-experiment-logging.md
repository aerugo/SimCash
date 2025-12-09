# Feature Request: Verbose Experiment Logging for Castro Experiments

**Date:** 2025-12-09
**Requested by:** AI Research Assistant (during experiment execution)
**Priority:** High
**Component:** experiments/castro

---

## Problem Statement

During execution of Castro experiments, the current console output provides only high-level summary metrics:

```
Iteration 3
  Total cost: $13466.40
  New best!
  Optimizing BANK_A...
    Policy improved: $6723.20 → $6513.22
  Optimizing BANK_B...
```

This output is insufficient for:
1. **Understanding what the LLM is doing** - No visibility into policy changes
2. **Debugging optimization failures** - Cannot see why policies are rejected
3. **Scientific reproducibility** - Cannot trace cause-and-effect relationships
4. **Real-time monitoring** - Must wait until experiment completes to query DuckDB

---

## Requested Features

### 1. Verbose Policy Change Logging (`--verbose-policy`)

Show before/after policy parameters when policies change:

```
Iteration 3
  Total cost: $13466.40
  New best!

  Optimizing BANK_A...
    Current policy:
      initial_liquidity_fraction: 0.25
      urgency_threshold: 3.0

    LLM proposed:
      initial_liquidity_fraction: 0.18  (-28%)
      urgency_threshold: 2.0  (-33%)

    Evaluation: $6723.20 → $6513.22 (-3.1%)
    Decision: ACCEPTED
```

### 2. Monte Carlo Run Details (`--verbose-monte-carlo`)

Show individual simulation run results:

```
Monte Carlo Evaluation (5 samples):
  Seed 0x7a3b...: cost=$13200, settled=12/12, settlement_rate=100%
  Seed 0x2f1c...: cost=$13800, settled=11/12, settlement_rate=91.7%
  Seed 0x8e4d...: cost=$13400, settled=12/12, settlement_rate=100%
  Seed 0x1a9f...: cost=$13600, settled=12/12, settlement_rate=100%
  Seed 0x5c2e...: cost=$13332, settled=12/12, settlement_rate=100%
  ─────────────────────────────────────────────────────────
  Mean: $13466.40 (std: $223.61)
  Best seed: 0x7a3b... (for debugging)
  Worst seed: 0x2f1c... (for debugging)
```

### 3. LLM Interaction Logging (`--verbose-llm`)

Show prompt and response details:

```
LLM Call for BANK_A:
  Model: gpt-5.1 (reasoning_effort=high)
  Prompt tokens: 2,847
  Completion tokens: 1,203
  Latency: 34.2s

  Key context provided:
    - Performance history (5 iterations)
    - Best/worst seed costs
    - Current cost: $6723.20

  LLM reasoning summary: [if available from model]
```

### 4. Rejection Analysis (`--verbose-rejections`)

When policies are rejected, explain why:

```
Optimizing BANK_B...
  LLM proposed policy:
    initial_liquidity_fraction: -0.05  # INVALID: outside [0.0, 1.0]
    urgency_threshold: 25  # INVALID: outside [0, 20]

  Validation errors:
    1. Parameter 'initial_liquidity_fraction' value -0.05 below minimum 0.0
    2. Parameter 'urgency_threshold' value 25 above maximum 20

  Decision: REJECTED (validation failed)
  Retry: 1/3...
```

---

## Implementation Suggestions

### CLI Flag

Add a `--verbose` flag with optional granularity:

```bash
# All verbose output
castro run exp1 --verbose

# Specific verbose modes
castro run exp1 --verbose-policy --verbose-monte-carlo

# Quiet mode (current behavior)
castro run exp1 --quiet
```

### Code Changes

1. **runner.py**: Add logging calls at key decision points
2. **simulation.py**: Return summary metrics when verbose
3. **llm_client.py**: Log prompt/response metadata
4. **cli.py**: Add `--verbose` flags and pass to runner

### Log Format

Consider structured logging (JSON) for machine parsing alongside human-readable console output:

```python
# Human-readable to console
console.print("[bold]Policy Change:[/bold] BANK_A")

# Machine-readable to file
logger.info("policy_change", agent="BANK_A", old={...}, new={...})
```

---

## Rationale

### Scientific Rigor
Experiments in the Castro paper style require understanding *why* certain equilibria are reached. Without verbose logging, we can only observe *that* costs decreased, not *how* the policy changes achieved this.

### Debugging
When experiments fail to converge or produce unexpected results, the current output provides no diagnostic information. Verbose logging would enable root cause analysis.

### Human Review
The architecture.md protocol requires "AI Reviewer Analysis" followed by "Human Reviewer" chart review. The AI reviewer needs detailed logs to produce meaningful analysis; charts alone cannot capture policy evolution nuances.

### LLM Transparency
When using expensive reasoning models like GPT-5.1, understanding what context the model received and how it responded is crucial for improving prompts and diagnosing poor policy suggestions.

---

## Acceptance Criteria

- [ ] `--verbose` flag produces detailed console output
- [ ] Policy parameter changes shown with before/after/delta
- [ ] Monte Carlo run statistics shown with per-seed breakdown
- [ ] LLM call metadata logged (latency, tokens, model)
- [ ] Rejection reasons clearly explained
- [ ] Optional JSON structured logging to file
- [ ] Backward compatible (default behavior unchanged)

---

## References

- `experiments/castro/architecture.md` - Experiment architecture
- `experiments/castro/README.md` - Research protocol requirements
- `experiments/castro/castro/runner.py` - Current implementation
