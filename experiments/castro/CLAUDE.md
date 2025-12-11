# Castro Experiments - Claude Code Guide

## You Are Here: `/experiments/castro`

This directory contains **YAML-only experiment configurations** for replicating Castro et al. (2025) research on liquidity management in high-value payment systems. No Python code lives here—all execution happens via the core `payment-sim experiment` CLI.

**Your role**: Help users configure, run, and analyze Castro experiments. Point them to documentation rather than explaining concepts directly.

---

## 🎯 Proactive Agent Delegation (MANDATORY)

**IMPORTANT**: Before answering questions directly, check if a specialized agent should handle the task.

### docs-navigator — DELEGATE FIRST for Documentation Questions

**Trigger immediately when user asks:**
- "Where is X documented?" or "How do I use X?"
- "How do I run an experiment?" → Point to CLI docs
- "What's the experiment YAML schema?" → Point to experiments docs
- "How does LLM configuration work?" → Point to LLM docs
- Questions about verbose output, replay, or debugging

**Agent file**: `.claude/agents/docs-navigator.md`

### Key Documentation References

| Topic | Documentation |
|-------|---------------|
| **Experiment CLI** | `docs/reference/cli/commands/experiment.md` |
| **Experiment YAML Schema** | `docs/reference/experiments/configuration.md` |
| **LLM Configuration** | `docs/reference/llm/configuration.md` |
| **Castro Overview** | `docs/reference/castro/index.md` |
| **Verbose Output Flags** | `docs/reference/experiments/runner.md` |

---

## Quick Reference

### Directory Structure

```
experiments/castro/
├── experiments/           # Experiment YAML configurations
│   ├── exp1.yaml         # 2-Period Deterministic Nash Equilibrium
│   ├── exp2.yaml         # 12-Period Stochastic LVTS-Style
│   └── exp3.yaml         # Joint Liquidity & Timing Optimization
├── configs/               # Scenario YAML configurations
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_joint.yaml
├── papers/                # Reference paper
│   └── castro_et_al.md
├── CLAUDE.md              # This file
└── README.md              # Quick start guide
```

### Essential CLI Commands

```bash
# List available experiments
payment-sim experiment list experiments/castro/experiments/

# Show experiment details
payment-sim experiment info experiments/castro/experiments/exp1.yaml

# Validate configuration
payment-sim experiment validate experiments/castro/experiments/exp1.yaml

# Run experiment (basic)
payment-sim experiment run experiments/castro/experiments/exp1.yaml

# Run with full verbose output
payment-sim experiment run experiments/castro/experiments/exp1.yaml --verbose

# Run with debug logging
payment-sim experiment run experiments/castro/experiments/exp1.yaml --verbose --debug

# Run with selective verbose flags
payment-sim experiment run experiments/castro/experiments/exp1.yaml \
  --verbose-iterations \
  --verbose-policy \
  --verbose-llm

# Dry run (validate without executing)
payment-sim experiment run experiments/castro/experiments/exp1.yaml --dry-run

# Replay a past run
payment-sim experiment replay <run_id> --db results/exp1.db --verbose

# Replay with audit trail (detailed LLM logs)
payment-sim experiment replay <run_id> --db results/exp1.db --audit --start 1 --end 5
```

### Verbose Output Flags

| Flag | Shows |
|------|-------|
| `--verbose` | All verbose categories enabled |
| `--verbose-iterations` | Iteration start/end messages |
| `--verbose-policy` | Policy parameter changes (before/after) |
| `--verbose-bootstrap` | Per-sample bootstrap evaluation results |
| `--verbose-llm` | LLM call metadata (model, tokens, latency) |
| `--debug` | Validation errors, retry attempts, request/response progress |

---

## Three Experiments

| Experiment | Mode | Description |
|------------|------|-------------|
| **exp1** | deterministic | 2-Period Nash Equilibrium validation |
| **exp2** | bootstrap (10 samples) | 12-Period LVTS-style with Poisson arrivals |
| **exp3** | bootstrap (10 samples) | Joint liquidity & timing optimization |

### Expected Outcomes

**Experiment 1 (Nash Equilibrium):**
- Bank A: 0% initial liquidity (free-rides on B's payment)
- Bank B: 20% initial liquidity (covers period-1 demand)
- Pass criteria: Nash gap < 0.02

**Experiment 2 (Learning Curve):**
- Total costs decrease monotonically
- Cost reduction > 30% from initial to final
- Higher-demand agent posts more collateral

---

## 🔴 Critical Rules

### 1. YAML-Only Configuration

**No Python code in this directory.** All experiments run via the core CLI:

```bash
# ✅ CORRECT - Use CLI
payment-sim experiment run experiments/castro/experiments/exp1.yaml

# ❌ WRONG - No custom Python scripts
python run_castro.py  # This doesn't exist!
```

### 2. API Keys Required

Set environment variables before running:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # For Claude models
export OPENAI_API_KEY=sk-...          # For GPT models
export GOOGLE_API_KEY=...             # For Gemini models
```

### 3. LLM Model Format

Use `provider:model` format in YAML:

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"  # ✅ Correct
  # model: "claude-sonnet-4-5"           # ❌ Missing provider
```

### 4. Determinism

Same `master_seed` produces identical results:

```yaml
master_seed: 42  # Change this to get different runs
```

---

## Modifying Experiments

### Adding a New Experiment

1. Create scenario config in `configs/`:
   ```yaml
   # configs/exp4_custom.yaml
   ticks_per_day: 20
   seed: 12345
   agent_configs:
     - id: BANK_A
       opening_balance: 1000000
       # ...
   ```

2. Create experiment config in `experiments/`:
   ```yaml
   # experiments/exp4.yaml
   name: exp4
   description: "Custom experiment"
   scenario: configs/exp4_custom.yaml
   # ... rest of configuration
   ```

3. Validate before running:
   ```bash
   payment-sim experiment validate experiments/castro/experiments/exp4.yaml
   ```

### Modifying LLM Prompts

Edit the `system_prompt` field in the experiment YAML. The prompt is **inline** (no external files):

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.

    # Your custom instructions here...
```

### Modifying Policy Constraints

Edit `policy_constraints` to change what the LLM can generate:

```yaml
policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
  allowed_fields:
    - system_tick_in_day
    - balance
    - ticks_to_deadline
  allowed_actions:
    payment_tree:
      - Release
      - Hold
```

---

## Troubleshooting

### "API key not set"

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

### "Scenario file not found"

Scenario paths are relative to the experiment file:

```yaml
# In experiments/exp1.yaml
scenario: configs/exp1_2period.yaml  # Relative to experiments/castro/
```

### "LLM validation failed"

Check the `--debug` output for specific validation errors:

```bash
payment-sim experiment run exp1.yaml --verbose --debug
```

### "Replay output differs from run"

This violates the replay identity invariant. Check:
1. Events are complete (all fields serialized)
2. No legacy table queries in replay code
3. Same verbose flags used for both run and replay

---

## When to Ask for Help

1. **Documentation question?** → Use `docs-navigator` agent FIRST
2. **LLM prompt not working?** → Check `docs/reference/experiments/configuration.md`
3. **Policy validation failing?** → Check `policy_constraints` in YAML
4. **Replay not matching run?** → Check replay identity section in root `CLAUDE.md`

---

*Last updated: 2025-12-11*
*For documentation questions, use `.claude/agents/docs-navigator.md`*
*For experiment framework docs, see `docs/reference/experiments/index.md`*
*For project overview, see root `/CLAUDE.md`*
