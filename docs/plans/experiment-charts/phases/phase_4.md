# Phase 4: Documentation

**Status**: Pending
**Started**: -

---

## Objective

Update CLI documentation to include the new `chart` command with examples and output samples.

---

## Documentation to Update

### `docs/reference/cli/commands/experiment.md`

Add new section after `policy-evolution`:

```markdown
## chart

Generate convergence charts for experiment runs.

### Synopsis

```bash
payment-sim experiment chart <run-id> [OPTIONS]
```

### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `run-id` | String | Run ID to visualize (e.g., `exp1-20251209-143022-a1b2c3`) |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--db` | `-d` | Path | `results/experiments.db` | Path to database file |
| `--agent` | `-a` | String | `null` | Filter to specific agent's costs |
| `--parameter` | `-p` | String | `null` | Show parameter value at each iteration (requires `--agent`) |
| `--output` | `-o` | Path | `<run-id>.png` | Output file path |

### Description

The `chart` command generates a convergence visualization showing how costs evolved over experiment iterations. The chart displays:

**Primary Line (Accepted Policies)**: A prominent line showing the cost trajectory when only accepted policy changes are applied. This shows the optimization convergence path.

**Secondary Line (All Policies)**: A subtle, dashed line showing the cost of every tested policy, including rejected ones. This shows the exploration space.

When `--parameter` is specified with `--agent`, the chart annotates each data point with the parameter value at that iteration, useful for understanding how specific parameters (like `initial_liquidity_fraction`) evolved during optimization.

### Examples

```bash
# Basic chart for all agents (system total cost)
payment-sim experiment chart exp1-20251215-084901-866d63

# Chart for specific agent
payment-sim experiment chart exp1-20251215-084901-866d63 --agent BANK_A

# Chart with parameter value annotations
payment-sim experiment chart exp1-20251215-084901-866d63 \
    --agent BANK_A --parameter initial_liquidity_fraction

# Custom output path
payment-sim experiment chart exp1-20251215-084901-866d63 --output results/exp1_chart.png

# From specific database
payment-sim experiment chart exp1-20251215-084901-866d63 --db results/custom.db

# Generate PDF for publication
payment-sim experiment chart exp1-20251215-084901-866d63 --output paper/fig1.pdf
```

### Output Example

The chart displays:

```
              Cost Convergence - exp1-20251215-084901-866d63
    Cost ($)
      │
  $80 ┤  ·                          ·
      │    ·  ·  ·                ·
  $60 ┤        ●────●───●───●───●───●  ◄── Accepted Policies (blue)
      │      ·       ·     ·   ·       ◄── All Policies (gray, dashed)
  $40 ┤
      │
  $20 ┤
      │
   $0 ┼────┬────┬────┬────┬────┬────┬
          1    2    3    4    5    6
                    Iteration
```

With `--parameter initial_liquidity_fraction`:
```
              Cost Convergence - exp1-20251215-084901-866d63 (BANK_A)
    Cost ($)
      │       0.50
  $80 ┤  ·     │
      │    ·  ·│·
  $60 ┤        ●   0.40            0.20
      │        ·    │    0.30  0.25 │
  $40 ┤             ●────●───●───●───●
      │
   $0 ┼────┬────┬────┬────┬────┬────┬
          1    2    3    4    5    6
                    Iteration
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Database not found, run not found, or invalid options |

---
```

### Commands Table Update

Update the commands table at the top of the file:

```markdown
| Command | Description |
|---------|-------------|
| `validate` | Validate an experiment configuration file |
| `info` | Show detailed experiment information |
| `template` | Generate an experiment configuration template |
| `list` | List experiments in a directory |
| `run` | Run an experiment from configuration |
| `replay` | Replay experiment output from database |
| `results` | List experiment runs from database |
| `policy-evolution` | Extract policy evolution data as JSON |
| `chart` | Generate convergence charts for experiment runs |
```

---

## Files

| File | Action |
|------|--------|
| `docs/reference/cli/commands/experiment.md` | MODIFY |

---

## Completion Criteria

- [ ] Synopsis with all options documented
- [ ] Description explains both chart lines
- [ ] Examples cover common use cases
- [ ] Output examples show expected chart appearance
- [ ] Exit codes documented
- [ ] Commands table updated
