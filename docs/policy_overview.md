### Executive Report: Policy Decision Variables and Parameters in the Payment Simulator

This report provides a comprehensive overview of the variables (fields) and configurable parameters that can be utilized within the four distinct policy decision trees of the payment simulator. These trees—`payment_tree`, `bank_tree`, `strategic_collateral_tree`, and `end_of_tick_collateral_tree`—form the strategic core of an agent's behavior, allowing for sophisticated, state-aware decision-making.

The system's design is centered around a JSON-based Domain-Specific Language (DSL) where policies are constructed as trees of conditions and actions. The outcome of any path through a tree is determined by evaluating boolean expressions against a rich set of real-time data from the simulation, known as the **Evaluation Context**.

This report categorizes and explains each available variable and parameter, clarifying its meaning, how it can be used, and in which policy tree it is accessible.

---

### 1. The Four Policy Trees and Their Contexts

An agent's strategy is partitioned into four specialized decision trees, each evaluated at a specific point in the simulation tick:

1.  **`bank_tree` (Bank-Level Strategy):** Evaluated **once per agent at the start of a tick**. It makes high-level decisions, such as setting a payment release budget for the current tick, without considering any single transaction.
2.  **`strategic_collateral_tree` (Proactive Collateral):** Evaluated **after the `bank_tree` but before payment decisions**. It allows an agent to proactively post or withdraw collateral based on its overall financial state and anticipated needs for the upcoming settlement cycle.
3.  **`payment_tree` (Payment Release Decisions):** This is the primary tree for payment-by-payment decisions. It is evaluated **for each transaction** in an agent's internal queue (Queue 1) to decide whether to release, hold, split, or reprioritize it.
4.  **`end_of_tick_collateral_tree` (Reactive Collateral):** Evaluated **once per agent at the end of a tick**, after all settlement activities have concluded. It is used for reactive collateral management, such as withdrawing excess collateral that was not needed.

These trees operate within two distinct evaluation contexts:
*   **Bank-Level Context:** Used by `bank_tree`, `strategic_collateral_tree`, and `end_of_tick_collateral_tree`. It has access to agent-wide and system-wide variables.
*   **Transaction-Level Context:** Used exclusively by `payment_tree`. It has access to all bank-level and system-level variables, **plus** detailed variables specific to the individual transaction being evaluated.

---

### 2. Decision Variables (Fields)

Fields are dynamic variables from the simulation state that can be used in policy expressions. They are the primary inputs for decision-making.

#### 2.1. Transaction-Specific Fields
These fields are **only available in the `payment_tree`**, as they relate to a specific transaction being evaluated.

| Field Name | Description & Data Type | Example Use Case |
| :--- | :--- | :--- |
| `amount` | The original total amount of the transaction. (Integer cents) | Decide whether to split a payment if `amount` > a certain threshold. |
| `remaining_amount` | The portion of the transaction amount that is not yet settled. (Integer cents) | Check if a partially settled transaction still requires action. |
| `settled_amount` | The portion of the transaction amount that has already been settled. (Integer cents) | Monitor the progress of a divisible payment. |
| `arrival_tick` | The simulation tick when the transaction was created. (Integer) | Calculate how long a payment has been waiting in the queue. |
| `deadline_tick` | The simulation tick by which the transaction must be settled. (Integer) | Prioritize payments with an imminent deadline. |
| `priority` | The priority level of the transaction (0-10). (Integer) | Release high-priority payments before low-priority ones. |
| `is_split` | Whether the transaction is a child of a larger, split payment. (Boolean: 1.0/0.0) | Apply different logic to child transactions versus original parent transactions. |
| `is_past_deadline` | Whether the current tick is after the transaction's `deadline_tick`. (Boolean: 1.0/0.0) | Immediately reprioritize any transaction that has missed its deadline. |
| `is_overdue` | Whether the transaction has been officially marked as overdue. (Boolean: 1.0/0.0) | Trigger emergency settlement strategies for overdue payments. |
| `overdue_duration` | The number of ticks that have passed since the transaction became overdue. (Integer) | Escalate actions based on how long a payment has been overdue. |
| `ticks_to_deadline` | The number of ticks remaining until the deadline (`deadline_tick` - `current_tick`). Can be negative. (Integer) | Trigger urgent actions when `ticks_to_deadline` is less than a threshold. |
| `queue_age` | The number of ticks the transaction has been in the system (`current_tick` - `arrival_tick`). (Integer) | Prevent transactions from languishing by releasing them after a certain age. |
| `tx_counterparty_id`| A hash of the receiving agent's ID for this transaction. (Integer) | Identify and apply special logic for payments to specific counterparties. |
| `tx_is_top_counterparty`| Whether the receiver is one of the agent's top 5 trading partners by historical volume. (Boolean: 1.0/0.0) | Prioritize payments to key business partners to maintain relationships. |

#### 2.2. Agent & System Fields
These fields are available in **all four policy trees**.

| Field Name | Description & Data Type | Example Use Case |
| :--- | :--- | :--- |
| **Agent State** | | |
| `balance` | The agent's current balance in its settlement account. Can be negative (overdraft). (Integer cents) | Hold payments if `balance` is below a certain buffer. |
| `unsecured_cap` | The agent's unsecured overdraft capacity (daylight credit limit). (Integer cents) | Determine the baseline credit available before needing collateral. |
| `credit_used` | The amount of overdraft credit the agent is currently using. (Integer cents, always >= 0) | Post more collateral if `credit_used` exceeds a certain percentage of the limit. |
| `allowed_overdraft_limit` | The total overdraft an agent can have, from both unsecured capacity and collateral. (Integer cents) | Calculate the agent's absolute maximum spending power. |
| `overdraft_headroom` | The remaining credit capacity an agent has (`allowed_overdraft_limit` - `credit_used`). (Integer cents) | Release payments only if they do not exhaust the `overdraft_headroom`. |
| `available_liquidity`| The total funds an agent can use for payments (`balance` + `overdraft_headroom`). (Integer cents) | The primary variable for checking if a payment can be afforded. |
| `effective_liquidity`| The sum of the agent's balance and any *unused* credit capacity. (Integer cents) | A corrected liquidity measure that accurately reflects spending power, especially when in overdraft. |
| `liquidity_pressure`| A ratio (0.0-1.0) indicating how much of the total available liquidity is being used. (Float) | Become more conservative (hold payments) as `liquidity_pressure` increases. |
| `is_using_credit`| Whether the agent's balance is currently negative. (Boolean: 1.0/0.0) | Trigger a strategic collateral review if the agent enters an overdraft state. |
| `liquidity_buffer`| A configurable parameter specifying a target minimum balance to maintain. (Integer cents) | Hold a payment if `balance` - `amount` < `liquidity_buffer`. |
| `outgoing_queue_size`| The number of transactions currently in the agent's internal queue (Queue 1). (Integer) | Post more collateral if the queue size grows too large. |
| `queue1_total_value`| The total monetary value of all transactions in Queue 1. (Integer cents) | Use this to estimate the total liquidity required to clear the internal queue. |
| `queue1_liquidity_gap`| The shortfall between `available_liquidity` and `queue1_total_value`. (Integer cents, >= 0) | Post collateral equal to the `queue1_liquidity_gap` to clear the entire queue. |
| `incoming_expected_count`| The number of payments currently en route to this agent. (Integer) | Be more aggressive with releases if a high number of incoming payments is expected. |
| **System State** | | |
| `current_tick` | The current simulation tick number. (Integer) | Trigger time-based strategies, such as an "end-of-day rush". |
| `rtgs_queue_size`| The total number of transactions in the central RTGS queue (Queue 2). (Integer) | Hold payments to avoid adding to a congested system if `rtgs_queue_size` is high. |
| `rtgs_queue_value`| The total monetary value of all transactions in Queue 2. (Integer cents) | Gauge the severity of system-wide gridlock. |
| `total_agents` | The total number of agents in the simulation. (Integer) | Normalize system-wide metrics on a per-agent basis. |
| `system_queue2_pressure_index`| A ratio (0.0-1.0) indicating the current level of system-wide gridlock in Queue 2. (Float) | Reduce payment releases if system pressure is high to avoid contributing to gridlock. |
| **Time & Day** | | |
| `system_ticks_per_day`| The total number of ticks in a simulation day. (Integer) | Used to calculate progress through the day. |
| `system_current_day`| The current simulation day number (0-indexed). (Integer) | Adapt strategies for multi-day simulations. |
| `system_tick_in_day`| The current tick within the day (0 to `ticks_per_day`-1). (Integer) | Implement time-of-day based logic. |
| `day_progress_fraction`| The progress through the current day (0.0 to 1.0). (Float) | Gradually increase urgency as the day progresses. |
| `is_eod_rush`| Whether the simulation is in the "end-of-day rush" period (e.g., last 20% of the day). (Boolean: 1.0/0.0) | Switch to an aggressive "settle at all costs" strategy during the EOD rush. |
| **Collateral State**| | |
| `posted_collateral` | The amount of collateral the agent has currently posted. (Integer cents) | Withdraw collateral if `posted_collateral` is high and liquidity needs are low. |
| `max_collateral_capacity`| The theoretical maximum amount of collateral the agent could post. (Integer cents) | Check if it's even possible to post the required amount of collateral. |
| `remaining_collateral_capacity`| How much more collateral the agent can post (`max_collateral_capacity` - `posted_collateral`). (Integer cents) | Ensure a `PostCollateral` action does not exceed remaining capacity. |
| `collateral_utilization`| The ratio of `posted_collateral` to `max_collateral_capacity`. (Float) | Monitor how heavily the agent relies on collateral. |
| `excess_collateral` | The amount of collateral that can be safely withdrawn without violating overdraft coverage. (Integer cents) | Withdraw `excess_collateral` at the end of the tick to minimize costs. |
| **Throughput & Progress** | | |
| `my_throughput_fraction_today`| The agent's settlement progress for the day (settled value / total value). (Float) | Release more payments if throughput is lagging behind the expected pace. |
| `expected_throughput_fraction_by_now`| The expected settlement progress based on a system-wide guidance curve. (Float) | A benchmark to compare the agent's own progress against. |
| `throughput_gap`| The difference between actual and expected throughput. (Float, negative if lagging) | A key indicator for a policy to decide whether to speed up or slow down. |

#### 2.3. Agent State Registers
State registers are a key-value store (like a simple "memory") for each agent, allowing for stateful policies that evolve over time.

| Field Name | Description & Data Type | Available in Trees | Example Use Case |
| :--- | :--- | :--- | :--- |
| `bank_state_*` | A custom, user-defined variable. Keys must be prefixed with `bank_state_`. (Float) | `bank_tree`, `payment_tree` | Implement a cooldown period after a large release by setting `bank_state_cooldown_timer` to the current tick and holding payments until `current_tick` > `bank_state_cooldown_timer`. |

---

### 3. Configurable Parameters

Parameters are named constants defined in the `parameters` section of a policy's JSON file. They are used to make policies tunable and reusable. Their values can be **overridden on a per-agent basis** in the main simulation YAML configuration, allowing different agents to use the same policy logic but with different thresholds.

| Parameter Role | Example |
| :--- | :--- |
| **Thresholds** | A `liquidity_aware` policy might use a `target_buffer` parameter to define the minimum balance it tries to maintain. An agent can be configured with a high `target_buffer` to be conservative, while another uses a low value to be more aggressive. |
| **Switches** | A parameter like `enable_splitting` could be set to 1.0 or 0.0 to turn a splitting behavior on or off for a specific agent without changing the policy logic. |
| **Weights** | In a complex policy, parameters could be used as weights in a scoring function to balance competing priorities like liquidity cost versus settlement delay. |

In an expression, a parameter is referenced by name, like `{"param": "my_threshold"}`.

---

### 4. Policy Actions and Outcomes

The ultimate outcome of a policy tree evaluation is an **action**. The set of available actions is specific to the tree being evaluated.

*   **`payment_tree` Actions:** These directly control the fate of a single transaction (e.g., `Release`, `Hold`, `Split`). The parameters for these actions, such as the number of splits in a `Split` action, can themselves be determined by expressions, enabling highly dynamic outcomes.
*   **`bank_tree` Actions:** These set agent-wide conditions for the tick. The main action is `SetReleaseBudget`, which imposes constraints on the subsequent `payment_tree` evaluations. The `SetState` and `AddState` actions modify the agent's memory for future ticks.
*   **Collateral Tree Actions:** These determine the agent's collateral posture. `PostCollateral` and `WithdrawCollateral` actions can have their `amount` determined dynamically by evaluating expressions, allowing an agent to, for example, post exactly enough collateral to cover its `queue1_liquidity_gap`.

By combining the rich set of available fields with configurable parameters and dynamic action properties, the policy system provides a vast and expressive framework for designing and testing sophisticated, autonomous agent behaviors in a complex payment ecosystem.

---

### 5. Priority System Configuration **✨ NEW**

The priority system enables realistic transaction prioritization through four complementary features that work together to model T2-style payment handling.

#### 5.1. Priority Distributions

Instead of fixed per-agent priorities, transactions can have varying priorities via distributions:

| Distribution Type | Configuration Example | Use Case |
| :--- | :--- | :--- |
| **Fixed** | `priority: 5` | Backward compatible, all transactions same priority |
| **Categorical** | `priority_distribution: {type: Categorical, values: [3, 5, 7, 9], weights: [0.2, 0.5, 0.2, 0.1]}` | Realistic mix of urgent/normal/low priority |
| **Uniform** | `priority_distribution: {type: Uniform, min: 2, max: 8}` | Random priority within range |

**Key benefit:** Transactions from the same agent now have naturally different priorities, enabling meaningful intra-agent ordering decisions.

#### 5.2. Queue 1 Priority Ordering

Enable priority-based ordering for the internal bank queue:

```yaml
queue_config:
  queue1_ordering: "priority_deadline"  # or "fifo" (default)
```

When enabled, Queue 1 is sorted by:
1. **Priority** (descending) - higher priority first
2. **Deadline** (ascending) - sooner deadline first
3. **Arrival tick** (FIFO tiebreaker)

**Impact on policy:** The `payment_tree` evaluates transactions in sorted order, so high-priority transactions are considered for release first.

#### 5.3. T2 Priority Mode for Queue 2

Enable T2-style priority band processing at the RTGS level:

```yaml
rtgs_config:
  priority_mode: true  # Default: false
```

**Priority Bands:**
| Band | Priority Range | Description |
| :--- | :--- | :--- |
| Urgent | 8-10 | Central bank operations, securities settlement, CLS |
| Normal | 4-7 | Standard interbank payments |
| Low | 0-3 | Discretionary payments |

Queue 2 processes all Urgent transactions before Normal before Low, with FIFO preserved within each band.

#### 5.4. Dynamic Priority Escalation

Automatically boost priority as deadlines approach (prevents priority starvation):

```yaml
priority_escalation:
  enabled: true
  curve: "linear"
  start_escalating_at_ticks: 20
  max_boost: 3
```

**Escalation formula:** `boost = max_boost × (1 - ticks_remaining / start_at_ticks)`

Example with start=20, max_boost=3:
- 20 ticks remaining: +0 boost
- 10 ticks remaining: +1.5 boost
- 1 tick remaining: +3 boost (capped)

**Events:** `PriorityEscalated` events are logged and visible in verbose CLI output.

#### 5.5. Priority Fields in Policy Trees

The following priority-related fields are available in policy expressions:

| Field | Description | Available In |
| :--- | :--- | :--- |
| `priority` | Current transaction priority (0-10, may be escalated) | `payment_tree` |
| `original_priority` | Initial priority before escalation | `payment_tree` |

**Example policy pattern - Priority-based release:**
```json
{
  "type": "condition",
  "condition": {
    "op": ">=",
    "left": {"field": "priority"},
    "right": {"value": 8.0}
  },
  "on_true": {
    "type": "action",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "action": "Hold"
  }
}
```