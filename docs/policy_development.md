# Payment Simulator - Multi-Agent Payment System

## Quick Context for Claude Code

This is a **high-performance payment simulator** modeling real-time settlement between banks. It's a hybrid Rust-Python system where performance-critical code lives in Rust, while Python provides developer ergonomics.

**Your role**: You're an expert systems programmer who understands both high-performance computing and developer experience. You write correct, maintainable code that follows the project's strict invariants.

---

## A Guide to Developing New Policies

Policies are the "brains" of your banking agents. They control the strategic decisions an agent makes about its internal payment queue (**Queue 1**), specifically:

  * **When** to submit a payment to the central RTGS system (**Queue 2**).
  * **How** to submit it (e.g., in full, or split into smaller pieces).
  * **How** to manage liquidity (e.g., by posting or withdrawing collateral).

These decisions are critical for balancing settlement speed, liquidity costs (like overdraft fees), and deadline penalties.

The system provides two primary methods for developing new policies, each with different trade-offs:

1.  **JSON DSL (Decision Trees):** The recommended and most flexible method. You define logic in a JSON file without recompiling the Rust core. This is ideal for rapid iteration, configuration, and even for an AI (like me) to safely edit.
2.  **Rust Trait (`CashManagerPolicy`):** A compiled, high-performance method. You write native Rust code by implementing a trait. This is best for complex, computationally-heavy logic that won't change often.

-----

### Method 1: JSON DSL (Decision Tree) Policies

This is the preferred method for most policies. You create a `.json` file in the `backend/policies/` directory and the system's policy factory (`backend/src/policy/tree/factory.rs`) will load it.

#### 1. Core Syntax (The JSON Schema)

The JSON file defines a `DecisionTreeDef` (see `backend/src/policy/tree/types.rs`). Here are the key components:

  * **Root Object:** The main JSON object.

      * `version`: (string) The schema version, e.g., `"1.0"`.
      * `policy_id`: (string) A unique name, e.g., `"my_custom_policy"`.
      * `description`: (string, optional) What this policy does.
      * `parameters`: (object) A key-value map of default values (e.g., thresholds) that your tree can reference. These can be overridden by the simulation config.
      * `payment_tree`: (object) The root `TreeNode` for payment release decisions.
      * `strategic_collateral_tree`: (object, optional) The root `TreeNode` for deciding to post/withdraw collateral *before* settlements (Step 1.5 in the tick loop).
      * `end_of_tick_collateral_tree`: (object, optional) The root `TreeNode` for collateral decisions *after* all settlements (Step 5.5 in the tick loop).

  * **`TreeNode`:** The building block of your logic, which has two types:

    1.  **`condition` Node:** An `if/then/else` block.
        ```json
        {
          "type": "condition",
          "node_id": "N1",
          "condition": { ...expression... },
          "on_true": { ...tree_node... },
          "on_false": { ...tree_node... }
        }
        ```
    2.  **`action` Node:** A terminal leaf that returns a final decision.
        ```json
        {
          "type": "action",
          "node_id": "A1",
          "action": "Release"
        }
        ```

  * **`Expression`:** The "if" part of a condition.

      * `"op"`: `"=="`, `"!="`, `"<"`, `"<="`, `">"`, `">="`, `"and"`, `"or"`, `"not"`.
      * `"left"`, `"right"`: The `Value`s to compare.
      * `"conditions"`: An array of `Expression`s for `and`/`or`.

  * **`Value`:** How you get data to compare.

      * `{"field": "balance"}`: Gets a value from the simulation context (see list below).
      * `{"param": "my_threshold"}`: Gets a value from the root `parameters` object.
      * `{"value": 1000.0}`: A literal number.
      * `{"compute": {...}}`: Performs arithmetic.

  * **`Computation`:** Arithmetic operations.

      * `"op"`: `"+"`, `"-"`, `"*"`, `"/"`, `"max"`, `"min"`.
      * Example: `{"op": "+", "left": {"field": "balance"}, "right": {"field": "credit_limit"}}`

  * **`ActionType`:** The final decision from an `action` node.

      * `"Release"`: Submits the transaction to Queue 2 (RTGS).
      * `"Hold"`: Keeps the transaction in Queue 1 to be re-evaluated next tick.
      * `"Drop"`: Removes the transaction from the simulation (e.g., if expired).
      * `"Split"` / `"PaceAndRelease"`: Submits the transaction as *N* smaller "child" transactions. Requires a `num_splits` parameter.
      * `"PostCollateral"`: (In collateral trees only) Post collateral. Requires `amount` and `reason` parameters.
      * `"WithdrawCollateral"`: (In collateral trees only) Withdraw collateral. Requires `amount` and `reason`.
      * `"HoldCollateral"`: (In collateral trees only) Do nothing.

#### 2. Available Data (The `EvalContext`)

When your `payment_tree` is evaluated for a specific transaction, you have access to the following fields (from `backend/src/policy/tree/context.rs`):

| Category | Field Name | Type | Description |
| :--- | :--- | :--- | :--- |
| **Transaction** | `amount` | `f64` (cents) | Original transaction amount. |
| | `remaining_amount` | `f64` (cents) | Amount left to settle (for splits). |
| | `settled_amount` | `f64` (cents) | Amount already settled. |
| | `arrival_tick` | `f64` | Tick the transaction arrived in Queue 1. |
| | `deadline_tick` | `f64` | Tick by which it *must* be settled. |
| | `priority` | `f64` | Priority level (0-10). |
| | `is_split` | `f64` (bool) | `1.0` if this is a child of a split, `0.0` otherwise. |
| | `is_past_deadline`| `f64` (bool) | `1.0` if `current_tick > deadline_tick`, `0.0` otherwise. |
| **Derived** | `ticks_to_deadline`| `f64` | `deadline_tick - current_tick` (can be negative). |
| | `queue_age` | `f64` | `current_tick - arrival_tick`. |
| **Agent** | `balance` | `f64` (cents) | Agent's current balance at the central bank. |
| | `credit_limit` | `f64` (cents) | Agent's overdraft limit. |
| | `available_liquidity`| `f64` (cents) | `balance + credit_limit + posted_collateral`. |
| | `credit_used` | `f64` (cents) | Amount of overdraft currently used. |
| | `is_using_credit` | `f64` (bool) | `1.0` if `balance < 0`, `0.0` otherwise. |
| | `liquidity_buffer` | `f64` (cents) | Configured soft target for minimum balance. |
| | `outgoing_queue_size`| `f64` | Number of items in *this agent's* Queue 1. |
| | `incoming_expected_count`| `f64` | Number of *incoming* payments expected. |
| | `liquidity_pressure`| `f64` (0-1) | `1.0` = max stress, `0.0` = comfortable. |
| **Collateral** | `posted_collateral`| `f64` (cents) | Collateral currently posted. |
| | `max_collateral_capacity`| `f64` (cents) | Max collateral agent *can* post. |
| | `remaining_collateral_capacity`| `f64` (cents) | `max_capacity - posted_collateral`. |
| | `collateral_utilization`| `f64` (0-1) | `posted_collateral / max_collateral_capacity`. |
| | `queue1_total_value`| `f64` (cents) | Total value of all items in Queue 1. |
| | `queue1_liquidity_gap`| `f64` (cents) | `queue1_total_value - available_liquidity` (min 0). |
| **System** | `current_tick` | `f64` | The current simulation tick. |
| | `rtgs_queue_size` | `f64` | Total items in the central **Queue 2** (all agents). |
| | `rtgs_queue_value` | `f64` (cents) | Total value in the central **Queue 2**. |
| | `queue2_count_for_agent`| `f64` | Number of *this agent's* items in **Queue 2**. |

#### 3. Example: `liquidity_aware.json` Walkthrough

Let's break down `backend/policies/liquidity_aware.json`. This policy tries to keep a `target_buffer` of cash but will ignore the buffer if a payment is `urgent`.

```json
{
  "version": "1.0",
  "policy_id": "liquidity_aware_policy",
  "description": "Releases if urgent or if balance remains above target buffer.",
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_IsUrgent",
    "description": "Check if transaction is urgent (near deadline)",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A1_ReleaseUrgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2_CheckBuffer",
      "description": "Not urgent. Check if we have enough liquidity (balance >= amount + buffer)",
      "condition": {
        "op": ">=",
        "left": {"field": "available_liquidity"},
        "right": {
          "compute": {
            "op": "+",
            "left": {"field": "amount"},
            "right": {"param": "target_buffer"}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "A2_ReleaseSafe",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "A3_Hold",
        "action": "Hold",
        "parameters": {
          "reason": {"value": "InsufficientLiquidity"}
        }
      }
    }
  },
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  }
}
```

**Translation to Logic:**

This JSON tree translates to the following pseudo-code:

```
// Get default parameters
urgency_threshold = 5.0
target_buffer = 100000.0
// Note: These can be overridden by simulation config.

function evaluate_policy(transaction, agent, system_state):
    // N1_IsUrgent
    if transaction.ticks_to_deadline <= urgency_threshold:
        // A1_ReleaseUrgent
        return Release
    else:
        // N2_CheckBuffer
        required_liquidity = transaction.amount + target_buffer
        if agent.available_liquidity >= required_liquidity:
            // A2_ReleaseSafe
            return Release
        else:
            // A3_Hold
            return Hold(reason="InsufficientLiquidity")
```

-----

### Method 2: Rust Trait (`CashManagerPolicy`) Policies

This method is for policies that require complex logic, state, or maximum performance that is difficult to express in JSON.

#### 1. The `CashManagerPolicy` Trait

You must implement the `CashManagerPolicy` trait (defined in `backend/src/policy/mod.rs`) for your struct.

```rust
use crate::policy::{CashManagerPolicy, ReleaseDecision, CollateralDecision};
use crate::{Agent, SimulationState, CostRates};
use std::any::Any;

pub trait CashManagerPolicy: Send + Sync {
    /// Evaluate the agent's internal queue (Queue 1).
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates, // Read-only access to costs
    ) -> Vec<ReleaseDecision>;

    /// Evaluate strategic collateral decisions (optional).
    fn evaluate_collateral(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
    ) -> CollateralDecision {
        CollateralDecision::Hold // Default is to do nothing
    }

    /// Required for downcasting to access TreePolicy-specific methods.
    fn as_any_mut(&mut self) -> &mut dyn Any;
}
```

#### 2. The `ReleaseDecision` Enum

Your `evaluate_queue` function must return a `Vec<ReleaseDecision>`. The possible decisions are:

  * `ReleaseDecision::SubmitFull { tx_id: String }`: Submits the *entire* transaction to Queue 2.
  * `ReleaseDecision::SubmitPartial { tx_id: String, num_splits: usize }`: Splits the transaction into `num_splits` children and submits them all to Queue 2 (as seen in `liquidity_splitting.json`).
  * `ReleaseDecision::Hold { tx_id: String, reason: HoldReason }`: Keeps the transaction in Queue 1.
  * `ReleaseDecision::Drop { tx_id: String }`: Drops the transaction (e.g., if expired).

#### 3. Example: `CostOptimizingPolicy`

Here is a complete, compile-ready example (from `backend/CLAUDE.md`) of a custom Rust policy. This policy holds a payment if the cost of waiting one tick (`delay_cost`) is less than the cost of using overdraft to send it now (`credit_cost`).

```rust
use payment_simulator_core_rs::policy::{CashManagerPolicy, ReleaseDecision, HoldReason};
use payment_simulator_core_rs::{Agent, SimulationState, CostRates};
use std::any::Any;

// 1. Define your policy's struct (can hold its own state)
pub struct CostOptimizingPolicy {
    // Parameters can be set during initialization
    credit_rate: f64,  // Overdraft cost per tick
    delay_penalty: f64, // Delay cost per tick
}

// 2. Implement the trait
impl CashManagerPolicy for CostOptimizingPolicy {

    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates, // You can also use the global cost_rates
    ) -> Vec<ReleaseDecision> {

        let mut decisions = Vec::new();

        // 3. Iterate over the agent's internal queue
        for tx_id in agent.outgoing_queue() {
            let tx = match state.get_transaction(tx_id) {
                Some(tx) => tx,
                None => continue, // Should not happen
            };

            let amount = tx.remaining_amount();

            // 4. Access agent and transaction data for logic
            let liquidity_shortfall = (amount - agent.balance()).max(0);

            // 5. Implement custom logic
            // Note: Using internal rates, but could also use cost_rates.overdraft_bps_per_tick
            let credit_cost = liquidity_shortfall as f64 * self.credit_rate;
            let delay_cost = self.delay_penalty; // A simple flat penalty for this example

            // 6. Return a decision
            if credit_cost < delay_cost {
                // Cheaper to draw credit and send
                decisions.push(ReleaseDecision::SubmitFull {
                    tx_id: tx_id.clone(),
                });
            } else {
                // Cheaper to wait (re-evaluate next tick)
                decisions.push(ReleaseDecision::Hold {
                    tx_id: tx_id.clone(),
                    reason: HoldReason::Custom("Awaiting better liquidity".to_string()),
                });
            }
        }

        decisions
    }

    fn as_any_mut(&mut self) -> &mut dyn Any {
        self
    }
}
```

To use this Rust-based policy, you would need to modify the `PolicyConfig` enum and the policy factory (`backend/src/policy/tree/factory.rs`) to add a new variant, which is more involved than simply adding a new JSON file.

---

## Summary

**For most use cases, use the JSON DSL approach:**
- Rapid iteration without recompiling Rust
- Safe for LLM/AI editing
- Clear, declarative logic
- Easy parameter overrides

**Use Rust trait implementation only when:**
- You need complex algorithmic logic
- Performance is absolutely critical
- You need to maintain internal state across ticks
- JSON DSL is too limiting

The JSON DSL provides excellent expressiveness for the vast majority of payment release policies while maintaining safety and debuggability.
