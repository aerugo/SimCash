# Appendix B: Event Catalog

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Event Types Summary

| Category | Count | Events |
|----------|-------|--------|
| Arrival | 1 | Arrival |
| Policy | 8 | PolicySubmit, PolicyHold, PolicyDrop, PolicySplit, TransactionReprioritized, PriorityEscalated, BankBudgetSet, StateRegisterSet |
| Settlement | 7 | RtgsImmediateSettlement, QueuedRtgs, Queue2LiquidityRelease, RtgsSubmission, RtgsWithdrawal, RtgsResubmission, DeferredCreditApplied |
| LSM | 6 | LsmBilateralOffset, LsmCycleSettlement, BilateralLimitExceeded, MultilateralLimitExceeded, AlgorithmExecution, EntryDispositionOffset |
| Cost | 3 | CostAccrual, TransactionWentOverdue, OverdueTransactionSettled |
| Collateral | 4 | CollateralPost, CollateralWithdraw, CollateralTimerWithdrawn, CollateralTimerBlocked |
| System | 2 | EndOfDay, ScenarioEventExecuted |

---

## Arrival Events

### Arrival

Transaction arrives at bank.

```json
{
  "event_type": "Arrival",
  "tick": 42,
  "tx_id": "tx-abc-123",
  "sender_id": "BANK_A",
  "receiver_id": "BANK_B",
  "amount": 100000,
  "priority": 5,
  "deadline_tick": 142,
  "divisible": true
}
```

---

## Policy Events

### PolicySubmit

Transaction released to RTGS.

```json
{
  "event_type": "PolicySubmit",
  "tick": 43,
  "tx_id": "tx-abc-123",
  "agent_id": "BANK_A"
}
```

### PolicyHold

Transaction held in Queue 1.

```json
{
  "event_type": "PolicyHold",
  "tick": 43,
  "tx_id": "tx-abc-123",
  "agent_id": "BANK_A",
  "reason": "insufficient_liquidity"
}
```

### PolicySplit

Transaction split into parts.

```json
{
  "event_type": "PolicySplit",
  "tick": 43,
  "original_tx_id": "tx-abc-123",
  "child_tx_ids": ["tx-abc-123-1", "tx-abc-123-2"],
  "num_splits": 2,
  "agent_id": "BANK_A"
}
```

### TransactionReprioritized

Priority manually changed.

```json
{
  "event_type": "TransactionReprioritized",
  "tick": 43,
  "tx_id": "tx-abc-123",
  "old_priority": 5,
  "new_priority": 8
}
```

### PriorityEscalated

Auto-escalation due to deadline.

```json
{
  "event_type": "PriorityEscalated",
  "tick": 90,
  "tx_id": "tx-abc-123",
  "old_priority": 5,
  "new_priority": 7,
  "ticks_until_deadline": 10
}
```

### BankBudgetSet

Release budget configured.

```json
{
  "event_type": "BankBudgetSet",
  "tick": 43,
  "agent_id": "BANK_A",
  "budget_max": 1000000,
  "focus_counterparties": ["BANK_B", "BANK_C"]
}
```

### StateRegisterSet

Policy state updated.

```json
{
  "event_type": "StateRegisterSet",
  "tick": 43,
  "agent_id": "BANK_A",
  "register_name": "hold_count",
  "value": 3.0
}
```

---

## Settlement Events

### RtgsImmediateSettlement

Settled immediately on submission.

```json
{
  "event_type": "RtgsImmediateSettlement",
  "tick": 43,
  "tx_id": "tx-abc-123",
  "amount": 100000,
  "sender_id": "BANK_A",
  "receiver_id": "BANK_B",
  "sender_balance_before": 500000,
  "sender_balance_after": 400000
}
```

### QueuedRtgs

Queued due to insufficient liquidity.

```json
{
  "event_type": "QueuedRtgs",
  "tick": 43,
  "tx_id": "tx-abc-123",
  "queue_position": 5
}
```

### Queue2LiquidityRelease

Settled from Queue 2.

```json
{
  "event_type": "Queue2LiquidityRelease",
  "tick": 50,
  "tx_id": "tx-abc-123",
  "queue_wait_ticks": 7,
  "release_reason": "liquidity_available"
}
```

### RtgsSubmission

Submitted to Queue 2.

```json
{
  "event_type": "RtgsSubmission",
  "tick": 43,
  "tx_id": "tx-abc-123",
  "declared_priority": "Normal"
}
```

### RtgsWithdrawal

Withdrawn from Queue 2.

```json
{
  "event_type": "RtgsWithdrawal",
  "tick": 45,
  "tx_id": "tx-abc-123",
  "reason": "priority_change"
}
```

### RtgsResubmission

Resubmitted with new priority.

```json
{
  "event_type": "RtgsResubmission",
  "tick": 45,
  "tx_id": "tx-abc-123",
  "new_priority": "Urgent"
}
```

### DeferredCreditApplied

Credit applied at end of tick (deferred crediting mode only).

```json
{
  "event_type": "DeferredCreditApplied",
  "tick": 42,
  "agent_id": "BANK_B",
  "amount": 150000,
  "source_transactions": ["tx-001", "tx-002"]
}
```

**Fields**:
- `tick`: Tick when credit was applied
- `agent_id`: Receiving agent ID
- `amount`: Total credit amount (cents)
- `source_transactions`: List of transaction IDs that contributed to this credit

**When Emitted**: End of tick (step 5.7), only when `deferred_crediting: true` is configured.

**Use Case**: Castro model alignment where incoming payments are not available until the next tick. See [06-settlement-engines.md](./06-settlement-engines.md#8-deferred-crediting-mode).

---

## LSM Events

### LsmBilateralOffset

Bilateral netting settlement.

```json
{
  "event_type": "LsmBilateralOffset",
  "tick": 50,
  "agent_a": "BANK_A",
  "agent_b": "BANK_B",
  "amount_a": 100000,
  "amount_b": 80000,
  "net_amount": 20000,
  "tx_ids": ["tx-1", "tx-2"]
}
```

### LsmCycleSettlement

Multilateral cycle settlement.

```json
{
  "event_type": "LsmCycleSettlement",
  "tick": 50,
  "agents": ["BANK_A", "BANK_B", "BANK_C"],
  "tx_ids": ["tx-1", "tx-2", "tx-3"],
  "tx_amounts": [100000, 120000, 80000],
  "net_positions": [20000, -20000, 0],
  "max_net_outflow": 20000,
  "max_net_outflow_agent": "BANK_A",
  "total_value": 300000
}
```

### AlgorithmExecution

LSM algorithm completed.

```json
{
  "event_type": "AlgorithmExecution",
  "tick": 50,
  "algorithm_number": 2,
  "settled_count": 4,
  "settled_value": 500000
}
```

### BilateralLimitExceeded

Bilateral limit blocked settlement.

```json
{
  "event_type": "BilateralLimitExceeded",
  "tick": 50,
  "agent_id": "BANK_A",
  "counterparty_id": "BANK_B",
  "limit": 100000,
  "attempted_outflow": 150000
}
```

### EntryDispositionOffset

Offset at entry time.

```json
{
  "event_type": "EntryDispositionOffset",
  "tick": 43,
  "submitted_tx_id": "tx-new",
  "offset_tx_id": "tx-existing",
  "net_amount": 20000
}
```

---

## Cost Events

### CostAccrual

Cost charged.

```json
{
  "event_type": "CostAccrual",
  "tick": 43,
  "agent_id": "BANK_A",
  "cost_type": "liquidity",
  "amount": 100,
  "tx_id": null
}
```

### TransactionWentOverdue

Deadline passed.

```json
{
  "event_type": "TransactionWentOverdue",
  "tick": 143,
  "tx_id": "tx-abc-123",
  "deadline_tick": 142,
  "penalty_amount": 10000
}
```

### OverdueTransactionSettled

Late settlement.

```json
{
  "event_type": "OverdueTransactionSettled",
  "tick": 150,
  "tx_id": "tx-abc-123",
  "ticks_overdue": 8,
  "total_overdue_cost": 40000
}
```

---

## Collateral Events

### CollateralPost

Collateral posted.

```json
{
  "event_type": "CollateralPost",
  "tick": 43,
  "agent_id": "BANK_A",
  "amount": 500000,
  "reason": "strategic_posting",
  "posted_before": 0,
  "posted_after": 500000
}
```

### CollateralWithdraw

Collateral withdrawn.

```json
{
  "event_type": "CollateralWithdraw",
  "tick": 50,
  "agent_id": "BANK_A",
  "amount": 200000,
  "reason": "excess_liquidity"
}
```

### CollateralTimerWithdrawn

Auto-withdrawal via timer.

```json
{
  "event_type": "CollateralTimerWithdrawn",
  "tick": 53,
  "agent_id": "BANK_A",
  "amount": 100000,
  "original_tick": 43
}
```

---

## System Events

### EndOfDay

Day processing completed.

```json
{
  "event_type": "EndOfDay",
  "tick": 99,
  "day": 0,
  "queue2_size": 5,
  "unsettled_count": 3
}
```

### ScenarioEventExecuted

External event triggered.

```json
{
  "event_type": "ScenarioEventExecuted",
  "tick": 50,
  "event_type_name": "DirectTransfer",
  "details": {
    "from_agent": "EXTERNAL",
    "to_agent": "BANK_A",
    "amount": 1000000
  }
}
```

---

## Related Documents

- [08-event-system.md](./08-event-system.md) - Event architecture

---

*Next: [appendix-c-configuration-reference.md](./appendix-c-configuration-reference.md) - Config schema*
