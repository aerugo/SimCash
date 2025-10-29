# Payment Simulator - Examples

This directory contains example configurations and demonstration scripts for the Payment Simulator CLI tool.

## Directory Structure

```
examples/
├── README.md          # This file
├── cli/               # Executable demo scripts
│   ├── demo_ai_integration.sh
│   ├── demo_comparison.sh
│   ├── demo_large_scale.sh
│   ├── demo_realistic_scenario.sh
│   └── demo_verbose_mode.sh
└── configs/           # Example configuration files
    └── minimal.yaml   # Minimal 2-bank setup for testing
```

## Demo Scripts

All demo scripts are self-contained and include detailed output showing what the simulator can do.

### Prerequisites

Before running any demos:

```bash
# 1. Activate the Python virtual environment
cd api
source .venv/bin/activate

# 2. Ensure payment-sim CLI is installed
which payment-sim  # Should show: api/.venv/bin/payment-sim

# 3. Run demos from the examples/cli/ directory
cd ../examples/cli
```

### Available Demos

#### 1. AI Integration Patterns (`demo_ai_integration.sh`)

**Purpose:** Shows how AI models can programmatically interact with the simulator.

**Demonstrates:**
- Extracting metrics from JSON output (using `jq`)
- Batch experiments with multiple seeds
- Parameter sweeps (varying tick counts)
- Streaming mode for real-time monitoring

**Use Case:** ML researchers building reinforcement learning agents or policy optimizers.

```bash
./demo_ai_integration.sh
```

**Example Output:**
```
Pattern 1: Extract settlement rate
0.98

Pattern 2: Test multiple seeds (batch experiment)
Seed | Ticks/Second
-----|-------------
42   | 403298.46
123  | 388361.48
...
```

---

#### 2. Realistic Scenario (`demo_realistic_scenario.sh`)

**Purpose:** Demonstrates a complete RTGS simulation with transaction arrivals, settlements, and costs.

**Demonstrates:**
- Full simulation run with 4 banks
- ~150 transactions over 100 ticks
- Bank balance tracking
- Cost accrual (overdraft, delay penalties)
- Determinism verification (same seed = same results)

**Use Case:** Understanding how the simulator models real-world payment systems.

```bash
./demo_realistic_scenario.sh
```

**Example Output:**
```
📊 Running full simulation...

📈 SIMULATION RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️  Configuration:
  Seed: 42
  Ticks: 100
  Performance: 63005 ticks/s

💸 Transaction Activity:
  Arrivals: 128
  Settlements: 128
  LSM Releases: 0
  Settlement Rate: 100%
...
```

---

#### 3. Scenario Comparison (`demo_comparison.sh`)

**Purpose:** Compares normal liquidity vs. high-stress scenarios side-by-side.

**Demonstrates:**
- Normal liquidity scenario (well-capitalized banks)
- High-stress scenario (low liquidity, gridlock risk)
- LSM (Liquidity-Saving Mechanism) effectiveness
- Cost comparison between scenarios

**Use Case:** Policy researchers studying liquidity management strategies.

```bash
./demo_comparison.sh
```

**Example Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCENARIO 1: Normal Liquidity (realistic_demo.yaml)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Results:
  Settlement Rate: 100%
  Total Costs: $295.80

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCENARIO 2: High-Stress Gridlock (high_stress_gridlock.yaml)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Results:
  Settlement Rate: 87%
  LSM Releases: 34 ← LSM ACTIVE!
  Total Costs: $1,248.00 ← High penalties!
...
```

---

#### 4. Large-Scale Performance (`demo_large_scale.sh`)

**Purpose:** Tests simulator performance with 200 agents over 10 simulated days.

**Demonstrates:**
- Large-scale system behavior
- Performance benchmarking (ticks/second)
- Memory efficiency
- Realistic multi-day simulations

**Use Case:** Scalability testing and performance validation.

**Note:** This demo takes 30-60 seconds to run (2,000 ticks).

```bash
./demo_large_scale.sh
```

**Example Output:**
```
╔═══════════════════════════════════════════════════════════════╗
║   Payment Simulator - Large-Scale Demo                       ║
║   200 Agents • 2000 Ticks • 10 Days                          ║
╚═══════════════════════════════════════════════════════════════╝

⏱️  Running simulation (this will take 30-60 seconds)...

Results:
  Ticks executed: 2000
  Duration: 0.98 seconds
  Performance: 2040 ticks/second
  Total transactions: 21,345
  Settlement rate: 94.2%
...
```

---

#### 5. Verbose Mode (`demo_verbose_mode.sh`)

**Purpose:** Shows detailed real-time event logging.

**Demonstrates:**
- Tick-by-tick event logging
- Transaction lifecycle visibility
- Queue dynamics
- LSM intervention points

**Use Case:** Debugging simulations or understanding internal mechanics.

```bash
./demo_verbose_mode.sh
```

**Example Output:**
```
Tick 0:
  [ARRIVAL] TX-001: BANK_A → BANK_B ($5,000.00)
  [SETTLE]  TX-001: Immediate settlement (balance: $495,000)
  [ARRIVAL] TX-002: BANK_C → BANK_D ($12,500.00)
  [QUEUE]   TX-002: Insufficient liquidity (queue: 1)
...
```

---

## Configuration Files

### `configs/minimal.yaml`

A minimal configuration for quick testing:

```yaml
simulation:
  ticks_per_day: 10
  num_days: 1
  rng_seed: 42

agents:
  - id: "BANK_A"
    opening_balance: 1000000  # $10,000 in cents
    credit_limit: 500000      # $5,000 overdraft
    policy:
      type: "Fifo"

  - id: "BANK_B"
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: "Fifo"

lsm_config:
  bilateral_offsetting: true
  cycle_detection: true
  max_iterations: 3
```

**Use this when:**
- Testing new features
- Debugging policy logic
- Quick smoke tests

For more complex scenarios, see [/scenarios/](../../scenarios/).

---

## CLI Tool Reference

### Basic Usage

```bash
# Run a simulation
payment-sim run --config ../configs/minimal.yaml

# JSON output (quiet mode)
payment-sim run --config ../configs/minimal.yaml --quiet

# Override seed
payment-sim run --config ../configs/minimal.yaml --seed 12345

# Override tick count
payment-sim run --config ../configs/minimal.yaml --ticks 500

# Streaming mode (real-time tick events)
payment-sim run --config ../configs/minimal.yaml --stream

# Get help
payment-sim --help
payment-sim run --help
```

### Output Formats

**Standard Output:** Human-readable tables and summaries

**Quiet Mode (`--quiet`):** Machine-parseable JSON

**Streaming Mode (`--stream`):** NDJSON (newline-delimited JSON) for real-time processing

### JSON Output Schema

```json
{
  "simulation": {
    "config_file": "minimal.yaml",
    "seed": 42,
    "ticks_executed": 10,
    "duration_seconds": 0.001,
    "ticks_per_second": 10000.0
  },
  "metrics": {
    "total_arrivals": 15,
    "total_settlements": 14,
    "total_lsm_releases": 0,
    "settlement_rate": 0.9333
  },
  "agents": [
    {
      "id": "BANK_A",
      "final_balance": 1050000,
      "queue1_size": 1
    }
  ],
  "costs": {
    "total_cost": 12000
  }
}
```

---

## Integration Patterns

### Python Integration

```python
import subprocess
import json

# Run simulation and capture output
result = subprocess.run(
    ["payment-sim", "run", "--config", "minimal.yaml", "--quiet"],
    capture_output=True,
    text=True
)

data = json.loads(result.stdout)
settlement_rate = data["metrics"]["settlement_rate"]

print(f"Settlement rate: {settlement_rate:.2%}")
```

### Bash Scripting

```bash
# Extract settlement rate
settlement_rate=$(payment-sim run --config minimal.yaml --quiet | \
    jq -r '.metrics.settlement_rate')

echo "Settlement rate: $settlement_rate"

# Batch experiments
for seed in {1..10}; do
    result=$(payment-sim run --config minimal.yaml --seed $seed --quiet)
    echo "Seed $seed: $(echo $result | jq -r '.metrics.settlement_rate')"
done
```

### RL Agent Integration

```python
import gymnasium as gym
from payment_simulator import PaymentSimEnv

# Custom Gym environment (example - not yet implemented)
env = PaymentSimEnv(config_path="minimal.yaml")

for episode in range(100):
    obs, info = env.reset(seed=episode)
    done = False

    while not done:
        # Agent chooses action (e.g., submit/delay transaction)
        action = agent.predict(obs)
        obs, reward, done, truncated, info = env.step(action)

    print(f"Episode {episode}: Settlement rate = {info['settlement_rate']}")
```

---

## Next Steps

1. **Run the demos** to see the simulator in action
2. **Read the scenario documentation** in [/scenarios/README.md](../../scenarios/README.md)
3. **Explore the API** at [/docs/api.md](../../docs/api.md)
4. **Study the architecture** at [/docs/architecture.md](../../docs/architecture.md)
5. **Write your own scenarios** by copying and modifying configs

---

## Troubleshooting

### Demo Script Fails: "command not found: payment-sim"

**Solution:** Activate the virtual environment first:

```bash
cd api
source .venv/bin/activate
cd ../examples/cli
```

### Demo Script Fails: "No such file or directory: scenarios/..."

**Solution:** Run demos from the `examples/cli/` directory:

```bash
cd examples/cli
./demo_realistic_scenario.sh
```

### "jq: command not found"

**Solution:** Install jq (used for JSON parsing):

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Or parse JSON with Python instead:
payment-sim run --config minimal.yaml --quiet | python3 -m json.tool
```

---

*For more information, see the main [project documentation](../../docs/).*
