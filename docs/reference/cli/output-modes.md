# Output Modes

The CLI supports multiple output modes for different use cases. This document describes each mode, its format, and when to use it.

## Mode Overview

| Mode | Flag | Use Case |
|------|------|----------|
| [Normal](#normal-mode) | (default) | Final summary for scripts/automation |
| [Verbose](#verbose-mode) | `--verbose` | Real-time debugging and analysis |
| [Stream](#stream-mode) | `--stream` | Processing long simulations incrementally |
| [Event Stream](#event-stream-mode) | `--event-stream` | Machine-readable event processing |
| [Quiet](#quiet-mode) | `--quiet` | AI-friendly, stdout-only output |

## Normal Mode

**Default mode** - produces a single JSON summary at simulation end.

### Usage

```bash
payment-sim run --config scenario.yaml
```

### Output Format

```json
{
  "simulation": {
    "config_file": "/path/to/scenario.yaml",
    "seed": 42,
    "simulation_id": "sim-abc123",
    "database": "simulation_data.db",
    "ticks_executed": 300,
    "duration_seconds": 1.234,
    "ticks_per_second": 243.41
  },
  "metrics": {
    "total_arrivals": 450,
    "total_settlements": 405,
    "total_lsm_releases": 12,
    "settlement_rate": 0.9
  },
  "agents": [
    {
      "id": "BANK_A",
      "final_balance": 950000,
      "queue1_size": 5
    },
    {
      "id": "BANK_B",
      "final_balance": 1050000,
      "queue1_size": 2
    }
  ],
  "costs": {
    "total_cost": 125000
  },
  "performance": {
    "ticks_per_second": 243.41
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `simulation.config_file` | String | Path to configuration file |
| `simulation.seed` | Integer | RNG seed used |
| `simulation.simulation_id` | String | Simulation ID (if persisted) |
| `simulation.database` | String | Database path (if persisted) |
| `simulation.ticks_executed` | Integer | Total ticks run |
| `simulation.duration_seconds` | Float | Wall-clock time |
| `simulation.ticks_per_second` | Float | Performance metric |
| `metrics.total_arrivals` | Integer | Total transaction arrivals |
| `metrics.total_settlements` | Integer | Total settlements |
| `metrics.total_lsm_releases` | Integer | LSM settlements |
| `metrics.settlement_rate` | Float | Settlement ratio (0-1) |
| `agents[].id` | String | Agent ID |
| `agents[].final_balance` | Integer | Final balance in cents |
| `agents[].queue1_size` | Integer | Pending transactions |
| `costs.total_cost` | Integer | Total costs in cents |
| `performance.ticks_per_second` | Float | Performance metric |

### Best For

- CI/CD pipelines
- Scripted automation
- Quick summary checks
- JSON parsing by external tools

---

## Verbose Mode

**Real-time detailed output** - displays tick-by-tick events grouped by category.

### Usage

```bash
payment-sim run --config scenario.yaml --verbose
```

### Output Format

```
═══════════════════════════════════════════════════════════════════
                            TICK 0 (Day 0)
═══════════════════════════════════════════════════════════════════

📥 ARRIVALS (3)
┌──────────────────┬────────────┬────────────┬──────────────┬──────────┬────────┐
│ Transaction      │ Sender     │ Receiver   │ Amount       │ Priority │ Deadline│
├──────────────────┼────────────┼────────────┼──────────────┼──────────┼────────┤
│ tx-abc123        │ BANK_A     │ BANK_B     │   $1,500.00  │ 5        │ 50     │
│ tx-def456        │ BANK_B     │ BANK_C     │   $2,250.00  │ 7        │ 75     │
│ tx-ghi789        │ BANK_C     │ BANK_A     │     $800.00  │ 3        │ 30     │
└──────────────────┴────────────┴────────────┴──────────────┴──────────┴────────┘

✅ RTGS IMMEDIATE SETTLEMENTS (2)
┌──────────────────┬────────────┬────────────┬──────────────┬──────────────────┐
│ Transaction      │ Sender     │ Receiver   │ Amount       │ Balance After    │
├──────────────────┼────────────┼────────────┼──────────────┼──────────────────┤
│ tx-abc123        │ BANK_A     │ BANK_B     │   $1,500.00  │   $998,500.00    │
│ tx-def456        │ BANK_B     │ BANK_C     │   $2,250.00  │   $997,750.00    │
└──────────────────┴────────────┴────────────┴──────────────┴──────────────────┘

⏳ QUEUED RTGS (1)
┌──────────────────┬────────────┬────────────┬──────────────┬──────────────────┐
│ Transaction      │ Sender     │ Reason     │ Amount       │ Queue Position   │
├──────────────────┼────────────┼────────────┼──────────────┼──────────────────┤
│ tx-ghi789        │ BANK_C     │ Insufficient│     $800.00 │ 1               │
└──────────────────┴────────────┴────────────┴──────────────┴──────────────────┘

💰 COST BREAKDOWN
┌────────────┬──────────────┬──────────────┬──────────────┬──────────────────┐
│ Agent      │ Liquidity    │ Delay        │ Collateral   │ Total            │
├────────────┼──────────────┼──────────────┼──────────────┼──────────────────┤
│ BANK_A     │       $0.00  │       $5.00  │       $0.00  │          $5.00   │
│ BANK_B     │       $0.00  │       $0.00  │       $0.00  │          $0.00   │
│ BANK_C     │       $0.00  │      $10.00  │       $0.00  │         $10.00   │
└────────────┴──────────────┴──────────────┴──────────────┴──────────────────┘

📊 TICK SUMMARY: 3 arrivals, 2 settlements, 0 LSM
═══════════════════════════════════════════════════════════════════
```

### Event Categories Displayed

| Category | Icon | Description |
|----------|------|-------------|
| Arrivals | 📥 | New transactions entering the system |
| RTGS Immediate | ✅ | Immediate settlements via RTGS |
| Queued RTGS | ⏳ | Transactions queued for later settlement |
| Queue-2 Releases | 🔓 | Queue-2 liquidity releases |
| LSM Bilateral | 🔄 | Two-party LSM offsets |
| LSM Cycles | 🔃 | Multi-party LSM cycles |
| Policy Decisions | 🎯 | Policy tree decisions |
| Collateral Activity | 💎 | Collateral posts/withdrawals |
| Cost Breakdown | 💰 | Per-agent cost accrual |
| End of Day | 📅 | Daily summary statistics |

### Debug Mode

Add `--debug` for performance diagnostics:

```bash
payment-sim run --config scenario.yaml --verbose --debug
```

### Best For

- Debugging simulation behavior
- Understanding tick-by-tick flow
- Visual inspection during development
- Interactive analysis sessions

---

## Stream Mode

**JSONL streaming output** - emits one JSON object per tick during simulation.

### Usage

```bash
payment-sim run --config scenario.yaml --stream
```

### Output Format

Each line is a complete JSON object:

```
{"tick":0,"day":0,"arrivals":5,"settlements":3,"lsm":0,"costs":1500}
{"tick":1,"day":0,"arrivals":3,"settlements":2,"lsm":0,"costs":1200}
{"tick":2,"day":0,"arrivals":4,"settlements":3,"lsm":1,"costs":1800}
{"tick":3,"day":0,"arrivals":2,"settlements":1,"lsm":0,"costs":900}
```

### Fields Per Line

| Field | Type | Description |
|-------|------|-------------|
| `tick` | Integer | Current tick number |
| `day` | Integer | Current day number |
| `arrivals` | Integer | Arrivals this tick |
| `settlements` | Integer | Settlements this tick |
| `lsm` | Integer | LSM settlements this tick |
| `costs` | Integer | Costs accrued this tick (cents) |

### Processing Example

```bash
# Filter high-cost ticks
payment-sim run --config large.yaml --stream | jq 'select(.costs > 10000)'

# Count arrivals
payment-sim run --config scenario.yaml --stream | jq -s 'map(.arrivals) | add'

# Real-time monitoring
payment-sim run --config long.yaml --stream | while read line; do
  echo "$line" | jq '.tick, .settlements'
done
```

### Best For

- Long-running simulations
- Real-time monitoring
- Incremental processing
- Piping to analysis tools

---

## Event Stream Mode

**Individual events as JSONL** - emits each event as a separate JSON line.

### Usage

```bash
payment-sim run --config scenario.yaml --event-stream
```

### Output Format

```json
{"tick":0,"event_type":"Arrival","tx_id":"tx-001","sender_id":"BANK_A","receiver_id":"BANK_B","amount":150000,"priority":5,"deadline_tick":50}
{"tick":0,"event_type":"RtgsImmediateSettlement","tx_id":"tx-001","sender":"BANK_A","receiver":"BANK_B","amount":150000}
{"tick":0,"event_type":"Arrival","tx_id":"tx-002","sender_id":"BANK_B","receiver_id":"BANK_C","amount":225000,"priority":7,"deadline_tick":75}
{"tick":0,"event_type":"CostAccrual","agent_id":"BANK_A","costs":{"liquidity":0,"delay":500,"collateral":0,"total":500}}
```

### Event Types

| Event Type | Description |
|------------|-------------|
| `Arrival` | Transaction entered system |
| `RtgsImmediateSettlement` | RTGS immediate settlement |
| `Queue2LiquidityRelease` | Queue-2 release |
| `LsmBilateralOffset` | LSM bilateral offset |
| `LsmCycleSettlement` | LSM multi-party cycle |
| `TransactionWentOverdue` | Deadline exceeded |
| `CostAccrual` | Cost accrual event |
| `PolicySubmit` | Policy: submit action |
| `PolicyHold` | Policy: hold action |
| `PolicyDrop` | Policy: drop action |
| `PolicySplit` | Policy: split action |
| `CollateralPost` | Collateral posted |
| `CollateralWithdraw` | Collateral withdrawn |
| `EndOfDay` | End of day marker |

### Processing Examples

```bash
# Filter for LSM events
payment-sim run --config scenario.yaml --event-stream | \
  jq 'select(.event_type | startswith("Lsm"))'

# Count events by type
payment-sim run --config scenario.yaml --event-stream | \
  jq -s 'group_by(.event_type) | map({type: .[0].event_type, count: length})'

# Extract all settlements
payment-sim run --config scenario.yaml --event-stream | \
  jq 'select(.event_type | test("Settlement|Release"))'
```

### Best For

- Event-driven processing
- Detailed audit trails
- Building custom visualizations
- Integration with event processing systems

---

## Quiet Mode

**AI-friendly mode** - suppresses stderr logs, outputs only to stdout.

### Usage

```bash
payment-sim run --config scenario.yaml --quiet
```

### Behavior

- Suppresses progress messages
- Suppresses informational logs
- Only outputs final JSON to stdout
- Error messages still go to stderr

### Combined with Other Modes

```bash
# Quiet + normal (JSON only)
payment-sim run --config scenario.yaml --quiet

# Quiet + stream (JSONL only)
payment-sim run --config scenario.yaml --quiet --stream

# Note: --quiet is ignored with --verbose (verbose needs output)
```

### Best For

- AI/LLM integrations
- Script automation
- Clean pipe chains
- Machine parsing

---

## Mode Comparison

| Feature | Normal | Verbose | Stream | Event Stream |
|---------|--------|---------|--------|--------------|
| Format | JSON | Text tables | JSONL | JSONL |
| Timing | End only | Real-time | Real-time | Real-time |
| Granularity | Summary | Tick-level | Tick-level | Event-level |
| Human readable | No | Yes | No | No |
| Filtering | No | Yes | No | Yes |
| Memory usage | Low | Higher | Low | Low |
| Best for | Automation | Debug | Long sims | Analysis |

---

## Output Destinations

### Standard Output (stdout)

All modes output primary data to stdout:

```bash
# Redirect to file
payment-sim run --config scenario.yaml > output.json

# Pipe to processor
payment-sim run --config scenario.yaml --stream | processor.py
```

### Standard Error (stderr)

Progress and informational messages go to stderr:

```bash
# Capture only data, not logs
payment-sim run --config scenario.yaml 2>/dev/null

# Capture logs separately
payment-sim run --config scenario.yaml 2>logs.txt >output.json
```

### Using `--quiet`

```bash
# Clean stdout only
payment-sim run --config scenario.yaml --quiet | jq .
```

---

## Related Documentation

- [run Command](commands/run.md) - Full `run` command reference
- [Event Filtering](filtering.md) - Filter events in verbose/event-stream modes
- [replay Command](commands/replay.md) - Replay modes
