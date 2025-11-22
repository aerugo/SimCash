# TARGET2 LSM Alignment Implementation Plan

**Created:** 2025-11-22
**Status:** Draft
**Author:** Claude Code Review

---

## Executive Summary

This plan addresses the remaining gaps between SimCash's LSM (Liquidity-Saving Mechanism) and TARGET2's implementation. A comprehensive review identified the following areas requiring implementation:

| Priority | Feature | Status |
|----------|---------|--------|
| High | Priority-based queuing | ✅ Already implemented (Phase 4 of priority-system-redesign) |
| **High** | **Bilateral/multilateral limits** | ❌ **Not implemented** |
| Medium | Algorithm sequencing | ❌ Not implemented |
| Medium | Entry disposition offsetting | ❌ Not implemented |

This plan focuses on the **remaining unimplemented features**.

---

## Context: LSM Review Findings

### What TARGET2 Has That SimCash Lacks

#### 1. Bilateral/Multilateral Limits (CRITICAL GAP)

TARGET2 allows participants to set limits on payment flows:

**Bilateral Limits:**
> "TARGET2 offers sender limits on outflows of liquidity to a given participant (bilateral limit)"

- Maximum exposure to a specific counterparty
- Prevents concentration risk
- Checked in Algorithm 1 ("all-or-nothing")

**Multilateral Limits:**
> "TARGET2 offers... to all TARGET2 participants (multilateral limit)"

- Maximum total outflow to all participants combined
- Overall liquidity cap
- Prevents excessive depletion

**Current SimCash behavior:**
- Only has `credit_limit` (overdraft limit)
- No per-counterparty exposure limits
- No total outflow caps

#### 2. Algorithm Sequencing

TARGET2 uses 5 algorithms that run in a specific sequence:

```
Algorithm 1 ("all-or-nothing")
    ↓ (if fails)
Algorithm 2 ("partial optimization")
    ↓ (if fails)
Algorithm 3 ("multiple bilateral pairs")
    ↓ (if succeeds, return to Algorithm 1)

Algorithm 4: Ancillary system settlement
Algorithm 5: Sub-account optimization (night-time)
```

**Key behaviors:**
- Algorithms cannot run simultaneously
- If Algorithm 2 fails, Algorithm 3 runs
- If Algorithm 2 succeeds, repeat Algorithm 1
- Clear state machine with defined transitions

**Current SimCash behavior:**
- Bilateral offsetting runs once per LSM pass
- Cycle detection runs after bilateral
- Up to 3 iterations per tick
- No formal algorithm state machine

#### 3. Entry Disposition Offsetting

TARGET2 performs offsetting checks **before** queuing:

> "An offsetting check determines whether the payee's payment orders at the front of the highly urgent or urgent queue are available to be offset against the payer's payment order."

**Extended offsetting check:**
> "If the offsetting check fails, an extended offsetting check may be applied, which determines whether offsetting payment orders are available in any of the payee's queues regardless of when they are placed."

**Current SimCash behavior:**
- Payments queue first (Queue 2)
- LSM runs afterward to find offsets
- No pre-queue offset detection

### What SimCash Already Has (Correctly Implemented)

1. **Full-value gross settlement** - Each payment settles at full value
2. **Unequal payment support** - Net position calculation is correct
3. **Bilateral offsetting** - Matches T2 Algorithm 3 behavior
4. **Two-phase commit** - Atomic all-or-nothing execution
5. **Conservation invariant** - Sum of net positions = 0
6. **Determinism** - Sorted collections throughout
7. **Priority-based queuing** - T2-style 3-level priority (implemented in priority-system-redesign)

---

## Implementation Plan

### Phase 1: Bilateral/Multilateral Limits (HIGH PRIORITY)

**Rationale:** This is the most significant gap for realistic simulation. Without limits, banks have unlimited exposure to counterparties, which doesn't match real-world risk management.

#### 1.1 Data Model Changes

##### Rust: Agent Limits Structure

**File:** `backend/src/models/agent.rs`

```rust
/// Agent limits for payment flow control (TARGET2-style)
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct AgentLimits {
    /// Maximum outflow to specific counterparties
    /// Key: counterparty agent ID, Value: maximum outflow amount (i64 cents)
    pub bilateral_limits: BTreeMap<String, i64>,

    /// Maximum total outflow to all participants (None = unlimited)
    pub multilateral_limit: Option<i64>,

    /// Current bilateral outflows (tracked for limit checking)
    /// Reset at start of each day
    #[serde(skip)]
    pub bilateral_outflows: BTreeMap<String, i64>,

    /// Current total outflow (tracked for limit checking)
    /// Reset at start of each day
    #[serde(skip)]
    pub total_outflow: i64,
}
```

##### Agent Extensions

**File:** `backend/src/models/agent.rs`

```rust
impl Agent {
    /// Check if payment would exceed bilateral limit to counterparty
    pub fn would_exceed_bilateral_limit(&self, counterparty: &str, amount: i64) -> bool {
        if let Some(limit) = self.limits.bilateral_limits.get(counterparty) {
            let current = self.limits.bilateral_outflows.get(counterparty).copied().unwrap_or(0);
            current + amount > *limit
        } else {
            false // No limit set = unlimited
        }
    }

    /// Check if payment would exceed multilateral limit
    pub fn would_exceed_multilateral_limit(&self, amount: i64) -> bool {
        if let Some(limit) = self.limits.multilateral_limit {
            self.limits.total_outflow + amount > limit
        } else {
            false // No limit set = unlimited
        }
    }

    /// Check if payment would exceed ANY limit (bilateral OR multilateral)
    pub fn would_exceed_limits(&self, counterparty: &str, amount: i64) -> LimitCheckResult {
        if self.would_exceed_bilateral_limit(counterparty, amount) {
            LimitCheckResult::BilateralExceeded {
                counterparty: counterparty.to_string(),
                limit: self.limits.bilateral_limits.get(counterparty).copied().unwrap_or(0),
                current: self.limits.bilateral_outflows.get(counterparty).copied().unwrap_or(0),
                attempted: amount,
            }
        } else if self.would_exceed_multilateral_limit(amount) {
            LimitCheckResult::MultilateralExceeded {
                limit: self.limits.multilateral_limit.unwrap_or(0),
                current: self.limits.total_outflow,
                attempted: amount,
            }
        } else {
            LimitCheckResult::Ok
        }
    }

    /// Record an outflow (after successful settlement)
    pub fn record_outflow(&mut self, counterparty: &str, amount: i64) {
        *self.limits.bilateral_outflows.entry(counterparty.to_string()).or_insert(0) += amount;
        self.limits.total_outflow += amount;
    }

    /// Reset outflow tracking (called at start of each day)
    pub fn reset_outflow_tracking(&mut self) {
        self.limits.bilateral_outflows.clear();
        self.limits.total_outflow = 0;
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum LimitCheckResult {
    Ok,
    BilateralExceeded {
        counterparty: String,
        limit: i64,
        current: i64,
        attempted: i64,
    },
    MultilateralExceeded {
        limit: i64,
        current: i64,
        attempted: i64,
    },
}
```

#### 1.2 Configuration Schema

**File:** `api/payment_simulator/config/schemas.py`

```python
class AgentLimitsConfig(BaseModel):
    """Agent payment limits configuration (TARGET2-style)."""

    bilateral_limits: Optional[Dict[str, int]] = Field(
        default=None,
        description="Maximum outflow per counterparty in cents. Key is counterparty ID."
    )
    multilateral_limit: Optional[int] = Field(
        default=None,
        description="Maximum total outflow to all participants in cents."
    )

    class Config:
        extra = "forbid"

class AgentConfig(BaseModel):
    """Agent configuration."""
    # ... existing fields ...

    limits: Optional[AgentLimitsConfig] = Field(
        default=None,
        description="Payment flow limits (bilateral/multilateral)"
    )
```

#### 1.3 Integration with RTGS Settlement

**File:** `backend/src/settlement/rtgs.rs`

Modify `try_settle_immediate()` and `process_queue()` to check limits:

```rust
/// Check limits before settlement
fn check_settlement_limits(
    state: &SimulationState,
    sender_id: &str,
    receiver_id: &str,
    amount: i64,
) -> Result<(), SettlementError> {
    if let Some(sender) = state.get_agent(sender_id) {
        match sender.would_exceed_limits(receiver_id, amount) {
            LimitCheckResult::Ok => Ok(()),
            LimitCheckResult::BilateralExceeded { limit, current, attempted, .. } => {
                Err(SettlementError::BilateralLimitExceeded {
                    sender: sender_id.to_string(),
                    receiver: receiver_id.to_string(),
                    limit,
                    current,
                    attempted,
                })
            }
            LimitCheckResult::MultilateralExceeded { limit, current, attempted } => {
                Err(SettlementError::MultilateralLimitExceeded {
                    sender: sender_id.to_string(),
                    limit,
                    current,
                    attempted,
                })
            }
        }
    } else {
        Ok(()) // Agent not found - will fail on other checks
    }
}
```

#### 1.4 Integration with LSM

**File:** `backend/src/settlement/lsm.rs`

Modify `check_cycle_feasibility()` to include limit checks:

```rust
fn check_cycle_feasibility(
    state: &SimulationState,
    cycle: &Cycle,
    net_positions: &BTreeMap<String, i64>,
) -> Result<(), CycleFeasibilityError> {
    // Existing conservation check...

    // Existing liquidity check...

    // NEW: Check limits for each transaction in cycle
    for tx_id in &cycle.transactions {
        if let Some(tx) = state.get_transaction(tx_id) {
            let sender_id = tx.sender_id();
            let receiver_id = tx.receiver_id();
            let amount = tx.remaining_amount();

            if let Some(sender) = state.get_agent(sender_id) {
                if sender.would_exceed_bilateral_limit(receiver_id, amount) {
                    return Err(CycleFeasibilityError::BilateralLimitExceeded {
                        sender: sender_id.to_string(),
                        receiver: receiver_id.to_string(),
                    });
                }
                // Note: Multilateral limits need careful handling in cycles
                // since net positions are what matter, not gross flows
            }
        }
    }

    Ok(())
}
```

#### 1.5 TDD Test Specifications

**File:** `api/tests/integration/test_bilateral_multilateral_limits.py`

```python
"""
TDD Tests for Bilateral and Multilateral Limits

Test Strategy:
1. Write failing tests first
2. Implement minimal code to pass
3. Refactor while keeping tests green
"""

import pytest
from payment_simulator.backends.orchestrator import Orchestrator

class TestBilateralLimits:
    """Tests for bilateral (per-counterparty) limits."""

    def test_bilateral_limit_config_accepted(self):
        """Config with bilateral_limits is accepted without error."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {
                        "bilateral_limits": {
                            "BANK_B": 500_000,  # Max 500k to BANK_B
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_payment_within_bilateral_limit_settles(self):
        """Payment within bilateral limit settles immediately."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"bilateral_limits": {"BANK_B": 500_000}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Submit payment within limit (400k < 500k limit)
        orch.submit_transaction("BANK_A", "BANK_B", 400_000)
        orch.tick()

        # Should settle
        events = orch.get_tick_events(0)
        settlement_events = [e for e in events if "Settlement" in e.get("event_type", "")]
        assert len(settlement_events) == 1

    def test_payment_exceeding_bilateral_limit_queued(self):
        """Payment exceeding bilateral limit is queued, not settled."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"bilateral_limits": {"BANK_B": 500_000}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Submit payment exceeding limit (600k > 500k limit)
        orch.submit_transaction("BANK_A", "BANK_B", 600_000)
        orch.tick()

        # Should be queued, not settled
        assert orch.queue_size() == 1

    def test_cumulative_bilateral_limit_tracking(self):
        """Multiple payments cumulatively track toward bilateral limit."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"bilateral_limits": {"BANK_B": 500_000}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # First payment: 300k (within 500k limit)
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()
        assert orch.queue_size() == 0  # Settled

        # Second payment: 300k (cumulative 600k > 500k limit)
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()
        assert orch.queue_size() == 1  # Queued due to limit

    def test_bilateral_limit_per_counterparty(self):
        """Different counterparties have independent bilateral limits."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "limits": {
                        "bilateral_limits": {
                            "BANK_B": 500_000,
                            "BANK_C": 300_000,
                        }
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
                {"id": "BANK_C", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # 400k to B (within 500k limit) - settles
        orch.submit_transaction("BANK_A", "BANK_B", 400_000)
        # 400k to C (exceeds 300k limit) - queued
        orch.submit_transaction("BANK_A", "BANK_C", 400_000)

        orch.tick()

        assert orch.queue_size() == 1  # C payment queued
        # B payment should have settled
        balances = orch.get_balances()
        assert balances["BANK_A"] == 2_000_000 - 400_000  # Only B payment settled

    def test_bilateral_limit_resets_at_day_boundary(self):
        """Bilateral outflow tracking resets at start of new day."""
        config = {
            "seed": 12345,
            "ticks_per_day": 10,  # Short day for testing
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "limits": {"bilateral_limits": {"BANK_B": 500_000}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Day 0: Use up limit
        orch.submit_transaction("BANK_A", "BANK_B", 500_000)
        for _ in range(10):
            orch.tick()

        # Day 1: Limit should reset - new 500k available
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()

        # Should settle (limit reset)
        assert orch.queue_size() == 0


class TestMultilateralLimits:
    """Tests for multilateral (total outflow) limits."""

    def test_multilateral_limit_config_accepted(self):
        """Config with multilateral_limit is accepted without error."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"multilateral_limit": 800_000}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_payment_within_multilateral_limit_settles(self):
        """Payment within multilateral limit settles immediately."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"multilateral_limit": 800_000}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction("BANK_A", "BANK_B", 700_000)
        orch.tick()

        assert orch.queue_size() == 0

    def test_cumulative_multilateral_limit_across_counterparties(self):
        """Multilateral limit tracks total outflow across all counterparties."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "limits": {"multilateral_limit": 500_000}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
                {"id": "BANK_C", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # 300k to B - settles (300k < 500k)
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()
        assert orch.queue_size() == 0

        # 300k to C - queued (cumulative 600k > 500k)
        orch.submit_transaction("BANK_A", "BANK_C", 300_000)
        orch.tick()
        assert orch.queue_size() == 1


class TestCombinedLimits:
    """Tests for bilateral AND multilateral limits together."""

    def test_both_limits_applied(self):
        """Both bilateral and multilateral limits are checked."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "limits": {
                        "bilateral_limits": {"BANK_B": 400_000},
                        "multilateral_limit": 600_000,
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
                {"id": "BANK_C", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # 350k to B - settles (within both limits)
        orch.submit_transaction("BANK_A", "BANK_B", 350_000)
        orch.tick()
        assert orch.queue_size() == 0

        # 100k to B - queued (bilateral: 350k + 100k = 450k > 400k limit)
        orch.submit_transaction("BANK_A", "BANK_B", 100_000)
        orch.tick()
        assert orch.queue_size() == 1

    def test_multilateral_blocks_before_bilateral(self):
        """Multilateral limit can block payment even if bilateral allows it."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 2_000_000,
                    "limits": {
                        "bilateral_limits": {"BANK_B": 500_000, "BANK_C": 500_000},
                        "multilateral_limit": 400_000,  # Lower than bilateral
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
                {"id": "BANK_C", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # 300k to B - settles
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()

        # 200k to C - queued (within bilateral 500k, but multilateral 300+200=500 > 400)
        orch.submit_transaction("BANK_A", "BANK_C", 200_000)
        orch.tick()
        assert orch.queue_size() == 1


class TestLimitsInLSM:
    """Tests for limits interaction with LSM (bilateral offsetting/cycles)."""

    def test_bilateral_offset_respects_limits(self):
        """LSM bilateral offset respects bilateral limits."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": False},
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100_000,  # Low liquidity
                    "limits": {"bilateral_limits": {"BANK_B": 200_000}}
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 100_000,
                },
            ]
        }
        orch = Orchestrator.new(config)

        # Create offsetting payments
        # A→B 300k (exceeds A's 200k limit to B)
        # B→A 300k
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.submit_transaction("BANK_B", "BANK_A", 300_000)

        orch.tick()

        # Even though net is 0, A→B exceeds bilateral limit
        # This is a policy question - document expected behavior
        # Option 1: Block entire offset
        # Option 2: Allow offset since net exposure is 0
        # For T2 compliance, we check BEFORE offset, so should block
        assert orch.queue_size() == 2  # Both queued due to limit

    def test_cycle_settlement_respects_limits(self):
        """LSM cycle settlement respects bilateral limits."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": True},
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 50_000,
                    "limits": {"bilateral_limits": {"BANK_B": 200_000}}
                },
                {"id": "BANK_B", "opening_balance": 50_000},
                {"id": "BANK_C", "opening_balance": 50_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Create cycle: A→B→C→A
        # A→B 300k (exceeds limit)
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.submit_transaction("BANK_B", "BANK_C", 300_000)
        orch.submit_transaction("BANK_C", "BANK_A", 300_000)

        orch.tick()

        # Cycle should not settle due to A's bilateral limit to B
        assert orch.queue_size() == 3


class TestLimitEvents:
    """Tests for limit-related events."""

    def test_bilateral_limit_exceeded_event(self):
        """BilateralLimitExceeded event is emitted when limit blocks payment."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"bilateral_limits": {"BANK_B": 500_000}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction("BANK_A", "BANK_B", 600_000)
        orch.tick()

        events = orch.get_tick_events(0)
        limit_events = [e for e in events if e.get("event_type") == "BilateralLimitExceeded"]

        assert len(limit_events) == 1
        assert limit_events[0]["sender"] == "BANK_A"
        assert limit_events[0]["receiver"] == "BANK_B"
        assert limit_events[0]["limit"] == 500_000
        assert limit_events[0]["attempted"] == 600_000
```

---

### Phase 2: Algorithm Sequencing (MEDIUM PRIORITY)

**Rationale:** TARGET2's algorithm sequencing provides a formal state machine for settlement optimization. While SimCash's current iterative approach works, explicit algorithm sequencing would better model T2 behavior and provide clearer semantics.

#### 2.1 Algorithm State Machine Design

```rust
/// TARGET2-style algorithm state machine
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SettlementAlgorithm {
    /// All-or-nothing check (limits, liquidity)
    Algorithm1,
    /// Partial optimization attempt
    Algorithm2,
    /// Multiple bilateral pair matching
    Algorithm3,
    /// Ancillary system settlement (future)
    Algorithm4,
    /// Sub-account optimization (future)
    Algorithm5,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AlgorithmResult {
    Success,
    Failure,
    NoProgress,
}

pub struct AlgorithmSequencer {
    current: SettlementAlgorithm,
    iteration_count: usize,
    max_iterations: usize,
}

impl AlgorithmSequencer {
    pub fn new() -> Self {
        Self {
            current: SettlementAlgorithm::Algorithm1,
            iteration_count: 0,
            max_iterations: 10,
        }
    }

    /// Get next algorithm based on current result
    pub fn next(&mut self, result: AlgorithmResult) -> Option<SettlementAlgorithm> {
        if self.iteration_count >= self.max_iterations {
            return None;
        }
        self.iteration_count += 1;

        match (self.current, result) {
            // Algorithm 1 success -> repeat Algorithm 1
            (SettlementAlgorithm::Algorithm1, AlgorithmResult::Success) => {
                Some(SettlementAlgorithm::Algorithm1)
            }
            // Algorithm 1 failure -> try Algorithm 2
            (SettlementAlgorithm::Algorithm1, AlgorithmResult::Failure) => {
                self.current = SettlementAlgorithm::Algorithm2;
                Some(SettlementAlgorithm::Algorithm2)
            }
            // Algorithm 2 success -> back to Algorithm 1
            (SettlementAlgorithm::Algorithm2, AlgorithmResult::Success) => {
                self.current = SettlementAlgorithm::Algorithm1;
                Some(SettlementAlgorithm::Algorithm1)
            }
            // Algorithm 2 failure -> try Algorithm 3
            (SettlementAlgorithm::Algorithm2, AlgorithmResult::Failure) => {
                self.current = SettlementAlgorithm::Algorithm3;
                Some(SettlementAlgorithm::Algorithm3)
            }
            // Algorithm 3 success -> back to Algorithm 1
            (SettlementAlgorithm::Algorithm3, AlgorithmResult::Success) => {
                self.current = SettlementAlgorithm::Algorithm1;
                Some(SettlementAlgorithm::Algorithm1)
            }
            // No progress anywhere -> stop
            (_, AlgorithmResult::NoProgress) => None,
            // Algorithm 3 failure -> stop
            (SettlementAlgorithm::Algorithm3, AlgorithmResult::Failure) => None,
            // Future algorithms
            _ => None,
        }
    }
}
```

#### 2.2 Algorithm Implementation Mapping

| T2 Algorithm | SimCash Mapping | Implementation |
|--------------|-----------------|----------------|
| Algorithm 1 | Limit/liquidity check + immediate settlement | `try_settle_immediate()` with limits |
| Algorithm 2 | Partial optimization (future) | New: try splitting payments |
| Algorithm 3 | Bilateral offsetting | `bilateral_offset()` |
| Algorithm 4 | Ancillary systems | Out of scope |
| Algorithm 5 | Sub-accounts | Out of scope |

#### 2.3 TDD Test Specifications

**File:** `api/tests/integration/test_algorithm_sequencing.py`

```python
"""
TDD Tests for T2-style Algorithm Sequencing
"""

import pytest
from payment_simulator.backends.orchestrator import Orchestrator

class TestAlgorithmSequencing:
    """Tests for T2-style algorithm sequencing."""

    def test_algorithm_sequencing_config_accepted(self):
        """Config with algorithm_sequencing enabled is accepted."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {
                "algorithm_sequencing": True,  # Enable T2-style sequencing
            },
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_algorithm1_success_repeats(self):
        """After Algorithm 1 success, Algorithm 1 runs again."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"algorithm_sequencing": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Submit two payments that can both settle immediately
        orch.submit_transaction("BANK_A", "BANK_B", 100_000)
        orch.submit_transaction("BANK_A", "BANK_B", 100_000)

        orch.tick()

        # Both should settle via Algorithm 1 (no need for Algorithm 2/3)
        events = orch.get_tick_events(0)
        alg_events = [e for e in events if "algorithm" in e.get("event_type", "").lower()]

        # Should see Algorithm 1 events only
        alg1_events = [e for e in alg_events if e.get("algorithm") == 1]
        assert len(alg1_events) >= 2

    def test_algorithm1_failure_triggers_algorithm2(self):
        """Algorithm 1 failure leads to Algorithm 2."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"algorithm_sequencing": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},  # Low liquidity
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Payment that A can't afford immediately
        orch.submit_transaction("BANK_A", "BANK_B", 500_000)

        orch.tick()

        events = orch.get_tick_events(0)
        alg_events = [e for e in events if "algorithm" in e.get("event_type", "").lower()]

        # Should see Algorithm 1 failure, then Algorithm 2 attempt
        algorithms_run = [e.get("algorithm") for e in alg_events]
        assert 1 in algorithms_run  # Algorithm 1 was attempted
        assert 2 in algorithms_run  # Algorithm 2 followed

    def test_algorithm3_bilateral_offsetting(self):
        """Algorithm 3 runs bilateral offsetting when Algorithm 2 fails."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"algorithm_sequencing": True},
            "lsm_config": {"enable_bilateral": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},
                {"id": "BANK_B", "opening_balance": 100_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Create bilateral offset opportunity
        orch.submit_transaction("BANK_A", "BANK_B", 500_000)
        orch.submit_transaction("BANK_B", "BANK_A", 500_000)

        orch.tick()

        # Both should settle via Algorithm 3 (bilateral offset)
        assert orch.queue_size() == 0

        events = orch.get_tick_events(0)
        bilateral_events = [e for e in events if "bilateral" in e.get("event_type", "").lower()]
        assert len(bilateral_events) > 0


class TestAlgorithmEvents:
    """Tests for algorithm execution events."""

    def test_algorithm_execution_events_emitted(self):
        """Each algorithm execution emits an event."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"algorithm_sequencing": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction("BANK_A", "BANK_B", 100_000)
        orch.tick()

        events = orch.get_tick_events(0)
        alg_events = [e for e in events if e.get("event_type") == "AlgorithmExecution"]

        assert len(alg_events) >= 1
        event = alg_events[0]
        assert "algorithm" in event
        assert "result" in event
        assert "duration_ns" in event  # Optional: timing
```

---

### Phase 3: Entry Disposition Offsetting (MEDIUM PRIORITY)

**Rationale:** TARGET2 checks for offsetting opportunities BEFORE queuing a payment. This can prevent unnecessary queuing and improve settlement speed.

#### 3.1 Design

```rust
/// Entry disposition with offsetting check
/// Called before a payment is queued to see if it can offset immediately
pub fn entry_disposition_with_offsetting(
    state: &mut SimulationState,
    tx_id: &str,
    tick: usize,
) -> EntryDispositionResult {
    let tx = match state.get_transaction(tx_id) {
        Some(tx) => tx,
        None => return EntryDispositionResult::TransactionNotFound,
    };

    let sender = tx.sender_id().to_string();
    let receiver = tx.receiver_id().to_string();
    let amount = tx.remaining_amount();

    // Step 1: Try immediate settlement (existing logic)
    if try_settle_immediate(state, tx_id, tick).is_ok() {
        return EntryDispositionResult::SettledImmediate;
    }

    // Step 2: Offsetting check - look for payment in opposite direction
    // Check receiver's queue for payments to sender
    let offset_candidates = find_offsetting_payments(state, &receiver, &sender, amount);

    if !offset_candidates.is_empty() {
        // Found potential offset - try bilateral settlement
        if try_bilateral_offset_pair(state, tx_id, &offset_candidates, tick).is_ok() {
            return EntryDispositionResult::SettledViaOffset;
        }
    }

    // Step 3: Extended offsetting check (look in any queue position)
    if state.config.extended_offsetting_enabled {
        let extended_candidates = find_all_offsetting_payments(state, &receiver, &sender);
        if !extended_candidates.is_empty() {
            // FIFO bypass rules: only if liquidity increases
            if would_increase_liquidity(state, tx_id, &extended_candidates) {
                if try_bilateral_offset_pair(state, tx_id, &extended_candidates, tick).is_ok() {
                    return EntryDispositionResult::SettledViaExtendedOffset;
                }
            }
        }
    }

    // Step 4: Queue the payment
    EntryDispositionResult::Queued
}

#[derive(Debug, Clone, PartialEq)]
pub enum EntryDispositionResult {
    SettledImmediate,
    SettledViaOffset,
    SettledViaExtendedOffset,
    Queued,
    TransactionNotFound,
    LimitExceeded,
}
```

#### 3.2 TDD Test Specifications

**File:** `api/tests/integration/test_entry_disposition_offsetting.py`

```python
"""
TDD Tests for Entry Disposition Offsetting

Entry disposition offsetting checks for offsetting payments BEFORE queuing.
This can prevent unnecessary queuing and improve settlement latency.
"""

import pytest
from payment_simulator.backends.orchestrator import Orchestrator

class TestBasicEntryDispositionOffsettin:
    """Basic entry disposition offsetting tests."""

    def test_entry_offsetting_config_accepted(self):
        """Config with entry_disposition_offsetting is accepted."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {
                "entry_disposition_offsetting": True,
            },
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},
                {"id": "BANK_B", "opening_balance": 100_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_incoming_payment_offsets_at_entry(self):
        """Payment arriving when opposite direction queued triggers offset."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"entry_disposition_offsetting": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},  # Low liquidity
                {"id": "BANK_B", "opening_balance": 100_000},
            ]
        }
        orch = Orchestrator.new(config)

        # A→B 500k (can't settle immediately, queued)
        orch.submit_transaction("BANK_A", "BANK_B", 500_000)
        orch.tick()
        assert orch.queue_size() == 1

        # B→A 500k (should trigger offset at entry disposition)
        orch.submit_transaction("BANK_B", "BANK_A", 500_000)
        orch.tick()

        # Both should settle via entry disposition offsetting
        assert orch.queue_size() == 0

    def test_partial_offset_at_entry(self):
        """Entry disposition handles partial offsets."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"entry_disposition_offsetting": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},
                {"id": "BANK_B", "opening_balance": 300_000},  # Can cover net
            ]
        }
        orch = Orchestrator.new(config)

        # A→B 500k (queued)
        orch.submit_transaction("BANK_A", "BANK_B", 500_000)
        orch.tick()

        # B→A 300k (triggers offset, net 200k B→A flows)
        orch.submit_transaction("BANK_B", "BANK_A", 300_000)
        orch.tick()

        # Both should settle (B has 300k, net flow is 200k A→B which A can cover via offset)
        assert orch.queue_size() == 0


class TestExtendedOffsettingCheck:
    """Tests for extended offsetting (look in any queue position)."""

    def test_extended_offsetting_config(self):
        """Extended offsetting can be enabled separately."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {
                "entry_disposition_offsetting": True,
                "extended_offsetting": True,  # Look beyond front of queue
            },
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},
                {"id": "BANK_B", "opening_balance": 100_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_extended_offsetting_finds_deep_queue_match(self):
        """Extended offsetting finds matches anywhere in queue."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {
                "entry_disposition_offsetting": True,
                "extended_offsetting": True,
            },
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 50_000},
                {"id": "BANK_B", "opening_balance": 50_000},
                {"id": "BANK_C", "opening_balance": 50_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Queue up several payments from B
        orch.submit_transaction("BANK_B", "BANK_C", 200_000)  # First in B's queue
        orch.submit_transaction("BANK_B", "BANK_A", 300_000)  # Second in B's queue
        orch.tick()

        # Now A→B arrives - should find B→A even though it's not at front
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()

        # A→B and B→A should offset (extended offsetting found B→A)
        # B→C should remain queued
        assert orch.queue_size() == 1


class TestEntryDispositionEvents:
    """Tests for entry disposition events."""

    def test_entry_disposition_offset_event(self):
        """EntryDispositionOffset event emitted when offset occurs."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "rtgs_config": {"entry_disposition_offsetting": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100_000},
                {"id": "BANK_B", "opening_balance": 100_000},
            ]
        }
        orch = Orchestrator.new(config)

        orch.submit_transaction("BANK_A", "BANK_B", 500_000)
        orch.tick()
        orch.submit_transaction("BANK_B", "BANK_A", 500_000)
        orch.tick()

        events = orch.get_tick_events(1)
        offset_events = [e for e in events if e.get("event_type") == "EntryDispositionOffset"]

        assert len(offset_events) == 1
        event = offset_events[0]
        assert "incoming_tx" in event
        assert "offset_tx" in event
        assert "offset_amount" in event
```

---

## Implementation Order and Dependencies

```
Phase 1: Bilateral/Multilateral Limits
    │
    ├─► 1.1 AgentLimits data model (Rust)
    ├─► 1.2 Config schema (Python)
    ├─► 1.3 RTGS integration (check limits before settlement)
    ├─► 1.4 LSM integration (check limits in cycle feasibility)
    ├─► 1.5 Events (LimitExceeded events)
    └─► 1.6 Tests (14 integration tests)

Phase 2: Algorithm Sequencing (depends on Phase 1)
    │
    ├─► 2.1 AlgorithmSequencer state machine
    ├─► 2.2 Integration with tick loop
    ├─► 2.3 Algorithm execution events
    └─► 2.4 Tests (8 integration tests)

Phase 3: Entry Disposition Offsetting (can parallel with Phase 2)
    │
    ├─► 3.1 entry_disposition_with_offsetting() function
    ├─► 3.2 Extended offsetting check
    ├─► 3.3 FIFO bypass rules
    └─► 3.4 Tests (8 integration tests)
```

---

## Files to Modify/Create

### Phase 1: Bilateral/Multilateral Limits

| File | Change |
|------|--------|
| `backend/src/models/agent.rs` | Add `AgentLimits`, limit checking methods |
| `backend/src/models/mod.rs` | Export new types |
| `backend/src/settlement/rtgs.rs` | Check limits in `try_settle_immediate()` |
| `backend/src/settlement/lsm.rs` | Check limits in `check_cycle_feasibility()` |
| `backend/src/models/event.rs` | Add `LimitExceeded` events |
| `backend/src/ffi/types.rs` | Add limit config parsing |
| `api/payment_simulator/config/schemas.py` | Add `AgentLimitsConfig` |
| `api/tests/integration/test_bilateral_multilateral_limits.py` | **NEW** - 14 tests |

### Phase 2: Algorithm Sequencing

| File | Change |
|------|--------|
| `backend/src/settlement/mod.rs` | Add `algorithm.rs` module |
| `backend/src/settlement/algorithm.rs` | **NEW** - `AlgorithmSequencer` |
| `backend/src/orchestrator/engine.rs` | Integrate sequencer into tick loop |
| `backend/src/models/event.rs` | Add `AlgorithmExecution` event |
| `backend/src/ffi/types.rs` | Add `algorithm_sequencing` config |
| `api/tests/integration/test_algorithm_sequencing.py` | **NEW** - 8 tests |

### Phase 3: Entry Disposition Offsetting

| File | Change |
|------|--------|
| `backend/src/settlement/rtgs.rs` | Add `entry_disposition_with_offsetting()` |
| `backend/src/orchestrator/engine.rs` | Use entry disposition in tick loop |
| `backend/src/models/event.rs` | Add `EntryDispositionOffset` event |
| `backend/src/ffi/types.rs` | Add `entry_disposition_offsetting` config |
| `api/tests/integration/test_entry_disposition_offsetting.py` | **NEW** - 8 tests |

---

## TDD Workflow

For each phase, follow this strict TDD process:

### Step 1: Write Failing Tests

```bash
# Create test file with all tests
# Tests should fail because feature doesn't exist yet

cd api
.venv/bin/python -m pytest tests/integration/test_bilateral_multilateral_limits.py -v

# Expected: All tests FAIL (feature not implemented)
```

### Step 2: Implement Minimal Code

```bash
# Implement just enough to pass tests
# Start with data structures, then logic

cd backend
cargo test --no-default-features

cd ../api
uv sync --extra dev --reinstall-package payment-simulator
.venv/bin/python -m pytest tests/integration/test_bilateral_multilateral_limits.py -v

# Expected: Tests pass one by one as you implement
```

### Step 3: Refactor

```bash
# Clean up code while keeping tests green
# Add documentation, optimize as needed

.venv/bin/python -m pytest tests/integration/ -v

# Expected: All tests still pass
```

### Step 4: Integration Verification

```bash
# Verify no regressions in existing tests

.venv/bin/python -m pytest tests/ -v

# Expected: All tests pass (new + existing)
```

---

## Success Criteria

### Phase 1: Bilateral/Multilateral Limits
- [ ] All 14 integration tests pass
- [ ] Config with limits is accepted
- [ ] Payments exceeding limits are queued
- [ ] Limits reset at day boundaries
- [ ] LSM respects limits in cycle settlement
- [ ] LimitExceeded events are emitted

### Phase 2: Algorithm Sequencing
- [ ] All 8 integration tests pass
- [ ] Algorithm state machine follows T2 rules
- [ ] AlgorithmExecution events are emitted
- [ ] Backward compatible (disabled by default)

### Phase 3: Entry Disposition Offsetting
- [ ] All 8 integration tests pass
- [ ] Offset check occurs before queuing
- [ ] Extended offsetting respects FIFO rules
- [ ] EntryDispositionOffset events are emitted
- [ ] Backward compatible (disabled by default)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing behavior | All features are opt-in via config flags |
| Performance impact | Limit checks are O(1); sequencing adds minimal overhead |
| Complexity for users | Sensible defaults; comprehensive documentation |
| Determinism issues | Use BTreeMap for all limit tracking |

---

## References

- [ECB TARGET2 Technical Specifications](https://www.bank.lv/images/stories/pielikumi/tiesibuakti/maksajumu_sistemas/Appendix11_eng.pdf)
- [ECB Economic Bulletin - Liquidity usage in TARGET2](https://www.ecb.europa.eu/press/economic-bulletin/articles/2021/html/ecb.ebart202103_03~2e159cbd38.en.html)
- [BIS CPMI - New developments in large-value payment systems](https://www.bis.org/cpmi/publ/d67.pdf)
- Existing implementation: `backend/src/settlement/lsm.rs`
- Priority system: `docs/plans/priority-system-redesign.md`
