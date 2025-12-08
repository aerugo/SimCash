# LsmConfig

**Location:** `simulator/src/settlement/lsm.rs:84-107`

Configuration for the Liquidity Saving Mechanism (LSM), which optimizes settlement by finding offsetting payments and cycles to reduce liquidity needs.

---

## Struct Definition

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LsmConfig {
    pub enable_bilateral: bool,
    pub enable_cycles: bool,
    pub max_cycle_length: usize,
    pub max_cycles_per_tick: usize,
}
```

---

## Fields

### `enable_bilateral`

**Type:** `bool`
**Default:** `true`
**Location:** `lsm.rs:85-86`

Enable bilateral offsetting (A↔B netting).

**Description:**
When enabled, the LSM looks for pairs of opposing payments between two agents and settles them simultaneously, requiring only the net difference in liquidity.

**Example:**
```
BANK_A → BANK_B: $100,000
BANK_B → BANK_A: $80,000
```
Without bilateral: Both agents need full amounts
With bilateral: Only $20,000 net flow (A pays B)

**Example:**
```yaml
lsm_config:
  enable_bilateral: true
```

**Related:**
- See [LSM Bilateral](../05-settlement/lsm-bilateral.md)
- See [LsmBilateralOffset Event](../07-events/settlement-events.md#lsmbilateraloffset)

---

### `enable_cycles`

**Type:** `bool`
**Default:** `true`
**Location:** `lsm.rs:88-89`

Enable multilateral cycle detection and settlement.

**Description:**
When enabled, the LSM detects cycles of payments (A→B→C→A) and settles them simultaneously, requiring only the net outflow for each participant.

**Example:**
```
BANK_A → BANK_B: $100,000
BANK_B → BANK_C: $80,000
BANK_C → BANK_A: $90,000
```
Cycle settlement: Each agent only needs their net position

**Example:**
```yaml
lsm_config:
  enable_cycles: true
```

**Related:**
- See [LSM Cycles](../05-settlement/lsm-cycles.md)
- See [LsmCycleSettlement Event](../07-events/settlement-events.md#lsmcyclesettlement)

---

### `max_cycle_length`

**Type:** `usize`
**Default:** `4`
**Location:** `lsm.rs:91-92`

Maximum cycle length to detect.

**Description:**
Limits the complexity of cycle detection. Longer cycles are computationally expensive to find. Real-world systems typically limit to 3-5 agents.

**Valid Values:**
- `3` = Triangles only (A→B→C→A)
- `4` = Up to 4-agent cycles (default, good balance)
- `5` = Up to 5-agent cycles (higher computation)

**Tradeoffs:**
- Higher values find more netting opportunities
- Higher values require more computation per tick
- Diminishing returns above 5

**Example:**
```yaml
lsm_config:
  max_cycle_length: 4
```

---

### `max_cycles_per_tick`

**Type:** `usize`
**Default:** `10`
**Location:** `lsm.rs:94-95`

Maximum cycles to settle per tick (performance limit).

**Description:**
Limits processing time by capping how many cycles can be settled in a single tick. Prevents runaway computation with dense queues.

**Example Values:**
- `10` = Standard limit (default)
- `50` = Higher throughput, more computation
- `100` = Maximum netting, highest computation

**Example:**
```yaml
lsm_config:
  max_cycles_per_tick: 10
```

**Behavior:**
- Cycles are settled until limit reached or no more found
- Remaining cycles processed in subsequent ticks
- Does not affect bilateral offsetting (no limit)

---

## Default Configuration

**Location:** `lsm.rs:98-107`

```rust
impl Default for LsmConfig {
    fn default() -> Self {
        Self {
            enable_bilateral: true,
            enable_cycles: true,
            max_cycle_length: 4,
            max_cycles_per_tick: 10,
        }
    }
}
```

---

## Python Configuration

**Location:** `api/payment_simulator/config/schemas.py`

```python
class LsmConfig(BaseModel):
    enable_bilateral: bool = True
    enable_cycles: bool = True
    max_cycle_length: int = 4
    max_cycles_per_tick: int = 10
```

---

## Example Configurations

### Full LSM (Default)

```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10
```

### Bilateral Only (Simpler)

```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: false
  max_cycle_length: 4      # Ignored when cycles disabled
  max_cycles_per_tick: 10  # Ignored when cycles disabled
```

### Aggressive Netting

```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 5       # Include 5-agent cycles
  max_cycles_per_tick: 50   # More cycles per tick
```

### No LSM (Pure RTGS)

```yaml
lsm_config:
  enable_bilateral: false
  enable_cycles: false
  max_cycle_length: 4
  max_cycles_per_tick: 10
```

---

## LSM Algorithm Overview

### Processing Order (Per Tick)

1. **RTGS Queue Processing** - Try to settle each queued transaction
2. **Bilateral Offsetting** (if enabled) - Find and settle A↔B pairs
3. **Cycle Detection** (if enabled) - Find and settle cycles up to `max_cycle_length`

### Bilateral Offsetting Algorithm

```
For each pair of agents (A, B) in queue:
    Find transactions A→B and B→A
    If both exist:
        Settle the minimum of opposing amounts
        Net flow = max(A→B, B→A) - min(A→B, B→A)
        Only net flow requires liquidity
```

### Cycle Detection Algorithm

```
Build directed graph from queued transactions
Use Tarjan's SCC + triangle enumeration
For each cycle found (up to max_length):
    Calculate net positions for each participant
    If all participants have sufficient liquidity for net:
        Settle all transactions in cycle
```

### Performance Characteristics

| Setting | Time Complexity | Space Complexity |
|---------|-----------------|------------------|
| Bilateral only | O(agents²) | O(agents) |
| Cycles (length 3) | O(agents³) | O(agents²) |
| Cycles (length 4) | O(agents⁴) | O(agents²) |
| Cycles (length 5) | O(agents⁵) | O(agents²) |

---

## Related Events

| Event | Description |
|-------|-------------|
| `LsmBilateralOffset` | Emitted when bilateral pair settled |
| `LsmCycleSettlement` | Emitted when cycle settled |
| `EntryDispositionOffset` | Emitted for entry-time bilateral (if enabled) |
| `AlgorithmExecution` | Emitted for LSM pass (if algorithm_sequencing enabled) |

---

## See Also

- [LSM Bilateral](../05-settlement/lsm-bilateral.md) - Bilateral algorithm details
- [LSM Cycles](../05-settlement/lsm-cycles.md) - Cycle algorithm details
- [Settlement Engine](../05-settlement/rtgs-engine.md) - Overall settlement
- [OrchestratorConfig](orchestrator-config.md) - Parent configuration
- [entry_disposition_offsetting](orchestrator-config.md#entry_disposition_offsetting) - Entry-time bilateral

---

*Last Updated: 2025-11-28*
