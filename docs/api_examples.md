# Payment Simulator API Examples

> **Practical examples and patterns for using the Payment Simulator API**

This guide provides production-ready code examples for common use cases, research patterns, and integration scenarios.

---

## Table of Contents

1. [Basic Operations](#basic-operations)
2. [Simulation Lifecycle Management](#simulation-lifecycle-management)
3. [Transaction Patterns](#transaction-patterns)
4. [Policy Comparison Studies](#policy-comparison-studies)
5. [Stress Testing](#stress-testing)
6. [Integration Patterns](#integration-patterns)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## Basic Operations

### Simple Client Class

Create a reusable client for the Payment Simulator API:

```python
import requests
from typing import Dict, List, Optional

class PaymentSimulatorClient:
    """Client for Payment Simulator API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def create_simulation(self, config: Dict) -> str:
        """Create a new simulation and return its ID."""
        response = self.session.post(
            f"{self.base_url}/simulations",
            json=config
        )
        response.raise_for_status()
        return response.json()["simulation_id"]

    def get_state(self, sim_id: str) -> Dict:
        """Get current simulation state."""
        response = self.session.get(
            f"{self.base_url}/simulations/{sim_id}/state"
        )
        response.raise_for_status()
        return response.json()

    def tick(self, sim_id: str, count: int = 1) -> Dict:
        """Advance simulation by one or more ticks."""
        response = self.session.post(
            f"{self.base_url}/simulations/{sim_id}/tick",
            params={"count": count}
        )
        response.raise_for_status()
        return response.json()

    def submit_transaction(self, sim_id: str, tx_data: Dict) -> str:
        """Submit a transaction and return its ID."""
        response = self.session.post(
            f"{self.base_url}/simulations/{sim_id}/transactions",
            json=tx_data
        )
        response.raise_for_status()
        return response.json()["transaction_id"]

    def get_transaction(self, sim_id: str, tx_id: str) -> Dict:
        """Get transaction status and details."""
        response = self.session.get(
            f"{self.base_url}/simulations/{sim_id}/transactions/{tx_id}"
        )
        response.raise_for_status()
        return response.json()

    def list_transactions(
        self,
        sim_id: str,
        status: Optional[str] = None,
        agent: Optional[str] = None
    ) -> List[Dict]:
        """List transactions with optional filtering."""
        params = {}
        if status:
            params["status"] = status
        if agent:
            params["agent"] = agent

        response = self.session.get(
            f"{self.base_url}/simulations/{sim_id}/transactions",
            params=params
        )
        response.raise_for_status()
        return response.json()["transactions"]

    def delete_simulation(self, sim_id: str):
        """Delete a simulation."""
        response = self.session.delete(
            f"{self.base_url}/simulations/{sim_id}"
        )
        response.raise_for_status()

    def health_check(self) -> Dict:
        """Check API health."""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
```

**Usage:**

```python
client = PaymentSimulatorClient()

# Create simulation
config = {
    "simulation": {"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
    "agents": [
        {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 500_000,
         "policy": {"type": "Fifo"}},
        {"id": "BANK_B", "opening_balance": 1_000_000, "credit_limit": 500_000,
         "policy": {"type": "Fifo"}},
    ]
}

sim_id = client.create_simulation(config)

# Submit transaction
tx_id = client.submit_transaction(sim_id, {
    "sender": "BANK_A",
    "receiver": "BANK_B",
    "amount": 100_000,
    "deadline_tick": 50,
    "priority": 5,
    "divisible": False,
})

# Advance and check status
client.tick(sim_id, count=10)
tx = client.get_transaction(sim_id, tx_id)
print(f"Status: {tx['status']}")

# Cleanup
client.delete_simulation(sim_id)
```

---

## Simulation Lifecycle Management

### Context Manager for Automatic Cleanup

```python
from contextlib import contextmanager

@contextmanager
def simulation_context(client: PaymentSimulatorClient, config: Dict):
    """Context manager for automatic simulation cleanup."""
    sim_id = client.create_simulation(config)
    try:
        yield sim_id
    finally:
        client.delete_simulation(sim_id)


# Usage
client = PaymentSimulatorClient()

with simulation_context(client, my_config) as sim_id:
    # Do work with simulation
    client.tick(sim_id, count=100)
    state = client.get_state(sim_id)
    print(f"Final balances: {state['agents']}")
    # Automatically deleted when context exits
```

### Running Multiple Simulations Concurrently

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_simulation_trial(trial_num: int, config: Dict) -> Dict:
    """Run a single simulation trial."""
    client = PaymentSimulatorClient()

    # Use different seed for each trial
    config["simulation"]["rng_seed"] = 42 + trial_num

    sim_id = client.create_simulation(config)

    try:
        # Run simulation
        for _ in range(100):  # 100 ticks
            result = client.tick(sim_id)

        # Collect final state
        final_state = client.get_state(sim_id)

        return {
            "trial": trial_num,
            "seed": config["simulation"]["rng_seed"],
            "final_state": final_state,
        }

    finally:
        client.delete_simulation(sim_id)


# Run 10 trials in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [
        executor.submit(run_simulation_trial, i, base_config)
        for i in range(10)
    ]

    results = []
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        print(f"Trial {result['trial']} completed")

# Analyze results
avg_balance = sum(
    r["final_state"]["agents"]["BANK_A"]["balance"]
    for r in results
) / len(results)

print(f"Average final balance: ${avg_balance / 100:,.2f}")
```

---

## Transaction Patterns

### Batch Transaction Submission

```python
def submit_batch_transactions(
    client: PaymentSimulatorClient,
    sim_id: str,
    transactions: List[Dict]
) -> List[str]:
    """Submit multiple transactions efficiently."""
    tx_ids = []

    for tx_data in transactions:
        tx_id = client.submit_transaction(sim_id, tx_data)
        tx_ids.append(tx_id)

    return tx_ids


# Create payment schedule
payment_schedule = [
    {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 50_000,
        "deadline_tick": 10,
        "priority": 8,
        "divisible": False,
    },
    {
        "sender": "BANK_B",
        "receiver": "BANK_C",
        "amount": 75_000,
        "deadline_tick": 20,
        "priority": 5,
        "divisible": True,
    },
    # ... more transactions
]

tx_ids = submit_batch_transactions(client, sim_id, payment_schedule)
print(f"Submitted {len(tx_ids)} transactions")
```

### Monitoring Transaction Settlement

```python
def wait_for_settlement(
    client: PaymentSimulatorClient,
    sim_id: str,
    tx_id: str,
    max_ticks: int = 100,
    tick_increment: int = 1
) -> Dict:
    """Wait for transaction to settle or timeout."""
    for tick in range(0, max_ticks, tick_increment):
        # Check status
        tx = client.get_transaction(sim_id, tx_id)

        if tx["status"] == "settled":
            return {
                "settled": True,
                "ticks_elapsed": tick,
                "transaction": tx,
            }

        # Advance simulation
        client.tick(sim_id, count=tick_increment)

    # Timeout
    return {
        "settled": False,
        "ticks_elapsed": max_ticks,
        "transaction": client.get_transaction(sim_id, tx_id),
    }


# Usage
result = wait_for_settlement(client, sim_id, tx_id, max_ticks=50)

if result["settled"]:
    print(f"Settled in {result['ticks_elapsed']} ticks")
else:
    print(f"Timeout after {result['ticks_elapsed']} ticks")
```

### Transaction Analytics

```python
def analyze_transactions(
    client: PaymentSimulatorClient,
    sim_id: str
) -> Dict:
    """Compute transaction statistics."""
    all_transactions = client.list_transactions(sim_id)

    total = len(all_transactions)
    settled = sum(1 for tx in all_transactions if tx["status"] == "settled")
    pending = sum(1 for tx in all_transactions if tx["status"] == "pending")

    total_value = sum(tx["amount"] for tx in all_transactions)
    settled_value = sum(
        tx["amount"]
        for tx in all_transactions
        if tx["status"] == "settled"
    )

    return {
        "total_transactions": total,
        "settled_count": settled,
        "pending_count": pending,
        "settlement_rate": settled / total if total > 0 else 0,
        "total_value": total_value,
        "settled_value": settled_value,
        "value_settled_rate": settled_value / total_value if total_value > 0 else 0,
    }


# Usage
stats = analyze_transactions(client, sim_id)
print(f"Settlement Rate: {stats['settlement_rate']:.2%}")
print(f"Value Settled: ${stats['settled_value'] / 100:,.2f}")
```

---

## Policy Comparison Studies

### Comparing Policies on Same Scenario

```python
import copy
from dataclasses import dataclass
from typing import List

@dataclass
class PolicyResult:
    """Results from running a policy."""
    policy_name: str
    settlement_rate: float
    avg_settlement_time: float
    total_cost: int
    final_balances: Dict[str, int]


def evaluate_policy(
    client: PaymentSimulatorClient,
    base_config: Dict,
    policy_name: str,
    policy_config: Dict,
    num_ticks: int = 1000
) -> PolicyResult:
    """Evaluate a policy on a scenario."""
    # Create config with this policy
    config = copy.deepcopy(base_config)

    for agent in config["agents"]:
        agent["policy"] = policy_config

    sim_id = client.create_simulation(config)

    try:
        # Run simulation
        for _ in range(num_ticks):
            client.tick(sim_id)

        # Collect metrics
        final_state = client.get_state(sim_id)
        transactions = client.list_transactions(sim_id)

        # Calculate metrics
        settled = [tx for tx in transactions if tx["status"] == "settled"]
        settlement_rate = len(settled) / len(transactions) if transactions else 0

        # Note: This is placeholder logic - actual implementation would need
        # to track settlement times and costs from the simulation
        avg_settlement_time = 10.0  # Placeholder
        total_cost = 0  # Placeholder

        return PolicyResult(
            policy_name=policy_name,
            settlement_rate=settlement_rate,
            avg_settlement_time=avg_settlement_time,
            total_cost=total_cost,
            final_balances={
                agent_id: data["balance"]
                for agent_id, data in final_state["agents"].items()
            },
        )

    finally:
        client.delete_simulation(sim_id)


# Compare three policies
policies = [
    ("FIFO", {"type": "Fifo"}),
    ("Deadline", {"type": "Deadline", "urgency_threshold": 10}),
    ("LiquidityAware", {"type": "LiquidityAware", "buffer_target": 100_000}),
]

results: List[PolicyResult] = []

for policy_name, policy_config in policies:
    print(f"Evaluating {policy_name}...")
    result = evaluate_policy(client, base_config, policy_name, policy_config)
    results.append(result)

# Print comparison
print("\n" + "=" * 70)
print(f"{'Policy':<20} {'Settlement Rate':<20} {'Avg Time':<15}")
print("=" * 70)

for result in results:
    print(
        f"{result.policy_name:<20} "
        f"{result.settlement_rate:<20.2%} "
        f"{result.avg_settlement_time:<15.1f}"
    )

# Find best policy
best = max(results, key=lambda r: r.settlement_rate)
print(f"\n✅ Best policy: {best.policy_name} ({best.settlement_rate:.2%} settled)")
```

### Monte Carlo Policy Optimization

```python
import random
from typing import Tuple

def random_policy_parameters() -> Dict:
    """Generate random policy parameters for exploration."""
    policy_type = random.choice(["Deadline", "LiquidityAware"])

    if policy_type == "Deadline":
        return {
            "type": "Deadline",
            "urgency_threshold": random.randint(3, 20),
        }
    else:
        return {
            "type": "LiquidityAware",
            "buffer_target": random.randint(50_000, 500_000),
        }


def monte_carlo_optimization(
    client: PaymentSimulatorClient,
    base_config: Dict,
    num_trials: int = 100,
    num_ticks: int = 1000
) -> Tuple[Dict, float]:
    """Find best policy parameters via random search."""
    best_policy = None
    best_score = -float("inf")

    for trial in range(num_trials):
        # Generate random policy
        policy_config = random_policy_parameters()

        # Evaluate
        result = evaluate_policy(
            client,
            base_config,
            f"Trial_{trial}",
            policy_config,
            num_ticks
        )

        # Score (maximize settlement rate, minimize cost)
        score = result.settlement_rate - (result.total_cost / 1_000_000)

        if score > best_score:
            best_score = score
            best_policy = policy_config
            print(f"✨ New best: {policy_config} (score: {score:.4f})")

    return best_policy, best_score


# Run optimization
best_policy, score = monte_carlo_optimization(
    client,
    base_config,
    num_trials=50
)

print(f"\n🏆 Optimal policy found: {best_policy}")
print(f"Score: {score:.4f}")
```

---

## Stress Testing

### High-Volume Simulation

```python
def stress_test_high_volume(
    client: PaymentSimulatorClient,
    num_agents: int = 50,
    num_ticks: int = 1000,
    arrival_rate: float = 5.0
) -> Dict:
    """Stress test with many agents and high transaction volume."""
    import time

    # Generate configuration
    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 10,
            "rng_seed": 42,
        },
        "agents": [],
        "lsm_config": {
            "bilateral_offsetting": True,
            "cycle_detection": True,
            "max_iterations": 3,
        },
    }

    # Create many agents
    for i in range(num_agents):
        config["agents"].append({
            "id": f"BANK_{i:03d}",
            "opening_balance": 10_000_000,  # $100k
            "credit_limit": 5_000_000,      # $50k
            "policy": {"type": "Fifo"},
            "arrival_config": {
                "rate_per_tick": arrival_rate,
                "distribution": {
                    "type": "LogNormal",
                    "mean_log": 11.5,
                    "std_dev_log": 1.2,
                },
                "counterparty_weights": {
                    # Uniform distribution to all other banks
                    f"BANK_{j:03d}": 1.0
                    for j in range(num_agents)
                    if j != i
                },
                "deadline_offset": 50,
            },
        })

    print(f"Creating simulation with {num_agents} agents...")
    start_time = time.time()

    sim_id = client.create_simulation(config)
    create_time = time.time() - start_time

    print(f"✅ Created in {create_time:.2f}s")

    # Run simulation
    print(f"Running {num_ticks} ticks...")
    tick_times = []

    for tick in range(num_ticks):
        tick_start = time.time()
        result = client.tick(sim_id)
        tick_time = time.time() - tick_start
        tick_times.append(tick_time)

        if tick % 100 == 0:
            print(f"  Tick {tick}: {result['num_arrivals']} arrivals, "
                  f"{result['num_settlements']} settlements "
                  f"({tick_time * 1000:.1f}ms)")

    # Collect results
    final_state = client.get_state(sim_id)
    client.delete_simulation(sim_id)

    avg_tick_time = sum(tick_times) / len(tick_times)
    max_tick_time = max(tick_times)

    return {
        "num_agents": num_agents,
        "num_ticks": num_ticks,
        "create_time": create_time,
        "avg_tick_time": avg_tick_time,
        "max_tick_time": max_tick_time,
        "ticks_per_second": 1.0 / avg_tick_time,
        "final_state": final_state,
    }


# Run stress test
results = stress_test_high_volume(
    client,
    num_agents=50,
    num_ticks=1000,
    arrival_rate=5.0
)

print("\n" + "=" * 50)
print("STRESS TEST RESULTS")
print("=" * 50)
print(f"Agents:           {results['num_agents']}")
print(f"Ticks:            {results['num_ticks']}")
print(f"Create Time:      {results['create_time']:.2f}s")
print(f"Avg Tick Time:    {results['avg_tick_time'] * 1000:.1f}ms")
print(f"Max Tick Time:    {results['max_tick_time'] * 1000:.1f}ms")
print(f"Ticks/Second:     {results['ticks_per_second']:.1f}")
```

---

## Integration Patterns

### Webhook Notifications (Future Enhancement)

```python
# This is a conceptual example - actual implementation would require
# extending the API to support webhooks

from flask import Flask, request
import threading

app = Flask(__name__)

# Store simulation events
events = []

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Receive simulation events."""
    event = request.json
    events.append(event)
    print(f"Event received: {event['type']} at tick {event['tick']}")
    return {"status": "ok"}


def start_webhook_server():
    """Start webhook server in background."""
    app.run(port=5000, debug=False, use_reloader=False)


# Start webhook server
thread = threading.Thread(target=start_webhook_server, daemon=True)
thread.start()

# Register webhook with simulator (hypothetical API)
# client.register_webhook(sim_id, "http://localhost:5000/webhook")
```

### Data Export to Pandas

```python
import pandas as pd

def export_simulation_to_dataframe(
    client: PaymentSimulatorClient,
    sim_id: str
) -> Dict[str, pd.DataFrame]:
    """Export simulation data to Pandas DataFrames."""
    # Get final state
    state = client.get_state(sim_id)

    # Agents DataFrame
    agents_data = []
    for agent_id, agent_data in state["agents"].items():
        agents_data.append({
            "agent_id": agent_id,
            "balance": agent_data["balance"],
            "queue_size": agent_data["queue1_size"],
        })

    agents_df = pd.DataFrame(agents_data)

    # Transactions DataFrame
    transactions = client.list_transactions(sim_id)
    transactions_df = pd.DataFrame(transactions)

    return {
        "agents": agents_df,
        "transactions": transactions_df,
    }


# Usage
dfs = export_simulation_to_dataframe(client, sim_id)

# Analyze
print(dfs["agents"].describe())
print(f"\nSettlement rate: "
      f"{(dfs['transactions']['status'] == 'settled').mean():.2%}")

# Export to CSV
dfs["agents"].to_csv("agents.csv", index=False)
dfs["transactions"].to_csv("transactions.csv", index=False)
```

---

## Error Handling

### Robust Error Handling

```python
from requests.exceptions import RequestException, HTTPError, Timeout

class SimulationError(Exception):
    """Base exception for simulation errors."""
    pass


class SimulationNotFoundError(SimulationError):
    """Simulation does not exist."""
    pass


class TransactionError(SimulationError):
    """Transaction-related error."""
    pass


def safe_api_call(func):
    """Decorator for safe API calls with retry logic."""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)

            except HTTPError as e:
                if e.response.status_code == 404:
                    raise SimulationNotFoundError(
                        f"Simulation not found: {e.response.text}"
                    )
                elif e.response.status_code >= 500:
                    # Server error - retry
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    else:
                        raise SimulationError(f"Server error: {e.response.text}")
                else:
                    # Client error - don't retry
                    raise TransactionError(f"Request failed: {e.response.text}")

            except Timeout:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    raise SimulationError("Request timeout after retries")

            except RequestException as e:
                raise SimulationError(f"Network error: {e}")

    return wrapper


# Apply to client methods
class RobustPaymentSimulatorClient(PaymentSimulatorClient):
    """Client with robust error handling."""

    @safe_api_call
    def create_simulation(self, config: Dict) -> str:
        return super().create_simulation(config)

    @safe_api_call
    def tick(self, sim_id: str, count: int = 1) -> Dict:
        return super().tick(sim_id, count)

    # ... apply to other methods


# Usage
client = RobustPaymentSimulatorClient()

try:
    sim_id = client.create_simulation(config)
    client.tick(sim_id, count=100)

except SimulationNotFoundError as e:
    print(f"Simulation not found: {e}")
except TransactionError as e:
    print(f"Transaction failed: {e}")
except SimulationError as e:
    print(f"Simulation error: {e}")
```

---

## Best Practices

### 1. Always Use Context Managers

```python
with simulation_context(client, config) as sim_id:
    # Work is automatically cleaned up
    pass
```

### 2. Validate Configuration Before Submission

```python
from pydantic import ValidationError
from payment_simulator.config import SimulationConfig

def validate_config(config_dict: Dict) -> bool:
    """Validate configuration before sending to API."""
    try:
        SimulationConfig.from_dict(config_dict)
        return True
    except ValidationError as e:
        print(f"Invalid configuration: {e}")
        return False


if validate_config(my_config):
    sim_id = client.create_simulation(my_config)
```

### 3. Use Deterministic Seeds for Reproducibility

```python
# For production research
config["simulation"]["rng_seed"] = 42  # Fixed seed

# For exploration
import random
config["simulation"]["rng_seed"] = random.randint(1, 1_000_000)
```

### 4. Monitor Performance

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    """Time a block of code."""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"{name}: {elapsed:.3f}s")


with timer("Simulation setup"):
    sim_id = client.create_simulation(large_config)

with timer("1000 ticks"):
    client.tick(sim_id, count=1000)
```

### 5. Batch Operations When Possible

```python
# Bad: Multiple API calls
for i in range(100):
    client.tick(sim_id)  # 100 HTTP requests!

# Good: Single batched call
client.tick(sim_id, count=100)  # 1 HTTP request
```

---

## Complete Example: Research Study

Here's a complete example of a research study comparing policies:

```python
#!/usr/bin/env python3
"""
Research Study: Policy Performance Under Liquidity Stress

Compares FIFO, Deadline, and LiquidityAware policies under
various liquidity constraints.
"""

import pandas as pd
import matplotlib.pyplot as plt
from payment_simulator_client import PaymentSimulatorClient
from typing import List, Dict

def run_experiment(
    client: PaymentSimulatorClient,
    policy_name: str,
    policy_config: Dict,
    liquidity_level: float,  # 0.5 = 50% of required liquidity
    num_replications: int = 10
) -> pd.DataFrame:
    """Run experiment with replications."""
    results = []

    for rep in range(num_replications):
        # Create config
        config = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 5,
                "rng_seed": 1000 + rep,  # Different seed per replication
            },
            "agents": [
                {
                    "id": f"BANK_{i}",
                    "opening_balance": int(1_000_000 * liquidity_level),
                    "credit_limit": 500_000,
                    "policy": policy_config,
                    "arrival_config": {
                        "rate_per_tick": 3.0,
                        "distribution": {
                            "type": "LogNormal",
                            "mean_log": 11.5,
                            "std_dev_log": 1.2,
                        },
                        "counterparty_weights": {
                            f"BANK_{j}": 1.0 for j in range(4) if j != i
                        },
                        "deadline_offset": 50,
                    },
                }
                for i in range(4)
            ],
        }

        # Run simulation
        sim_id = client.create_simulation(config)
        client.tick(sim_id, count=500)  # 5 days

        # Collect results
        transactions = client.list_transactions(sim_id)
        settled = sum(1 for tx in transactions if tx["status"] == "settled")
        settlement_rate = settled / len(transactions) if transactions else 0

        results.append({
            "policy": policy_name,
            "liquidity_level": liquidity_level,
            "replication": rep,
            "settlement_rate": settlement_rate,
            "total_transactions": len(transactions),
        })

        client.delete_simulation(sim_id)

    return pd.DataFrame(results)


def main():
    """Run complete research study."""
    client = PaymentSimulatorClient()

    # Experimental design
    policies = [
        ("FIFO", {"type": "Fifo"}),
        ("Deadline", {"type": "Deadline", "urgency_threshold": 10}),
        ("LiquidityAware", {"type": "LiquidityAware", "buffer_target": 100_000}),
    ]

    liquidity_levels = [0.5, 0.75, 1.0, 1.5, 2.0]

    # Run experiments
    all_results = []

    for policy_name, policy_config in policies:
        for liquidity_level in liquidity_levels:
            print(f"Running: {policy_name} @ {liquidity_level:.0%} liquidity...")

            df = run_experiment(
                client,
                policy_name,
                policy_config,
                liquidity_level,
                num_replications=10
            )

            all_results.append(df)

    # Combine results
    results_df = pd.concat(all_results, ignore_index=True)

    # Save raw data
    results_df.to_csv("research_results.csv", index=False)

    # Analyze
    summary = results_df.groupby(["policy", "liquidity_level"]).agg({
        "settlement_rate": ["mean", "std"],
    }).round(4)

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(summary)

    # Visualize
    pivot = results_df.pivot_table(
        values="settlement_rate",
        index="liquidity_level",
        columns="policy",
        aggfunc="mean"
    )

    pivot.plot(kind="line", marker="o", figsize=(10, 6))
    plt.title("Settlement Rate vs Liquidity Level by Policy")
    plt.xlabel("Liquidity Level (fraction of required)")
    plt.ylabel("Settlement Rate")
    plt.grid(True, alpha=0.3)
    plt.legend(title="Policy")
    plt.savefig("settlement_rate_comparison.png", dpi=300, bbox_inches="tight")
    plt.show()

    print("\n✅ Study complete! Results saved to research_results.csv")


if __name__ == "__main__":
    main()
```

---

*For more examples, see the test files in `/api/tests/integration/`*

*Last updated: 2025-10-28*
