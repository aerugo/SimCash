# TARGET2 LSM Alignment - Detailed TDD Implementation Plans

**Created:** 2025-11-22
**Status:** Draft
**Parent Document:** `target2-lsm-alignment-plan.md`

---

## Overview

This document provides **detailed TDD implementation plans** for each phase of the TARGET2 LSM alignment. Each phase follows strict TDD principles and ensures:

1. **Event Persistence**: All events stored in `simulation_events` table
2. **CLI Verbose Output**: All events displayed via `display_tick_verbose_output()`
3. **Replay Identity**: Run output == Replay output (byte-for-byte where applicable)
4. **E2E Tests**: Full integration tests covering persistence → display → replay

---

## Critical Invariants (Apply to ALL Phases)

### 1. Event Persistence Pattern

Every new event type MUST follow this pattern:

```rust
// 1. Define event in backend/src/models/event.rs
Event::NewEventType {
    tick: usize,
    // Include ALL fields needed for display
    // Don't store IDs only - store full display data
    field1: Type1,
    field2: Type2,
}

// 2. Serialize in backend/src/ffi/orchestrator.rs
Event::NewEventType { tick, field1, field2 } => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "NewEventType".into());
    dict.insert("tick".to_string(), tick.into());
    dict.insert("field1".to_string(), field1.into());
    dict.insert("field2".to_string(), field2.into());
    dict
}
```

### 2. CLI Verbose Output Pattern

Every event MUST have display logic in `display_tick_verbose_output()`:

```python
# api/payment_simulator/cli/execution/display.py

def display_tick_verbose_output(provider: StateProvider, tick: int, events: list[dict]):
    # ... existing code ...

    for event in events:
        if event["event_type"] == "NewEventType":
            log_new_event_type(event)

def log_new_event_type(event: dict):
    """Display NewEventType in verbose output."""
    console.print(f"[cyan]Event:[/cyan] {event['field1']}")
    console.print(f"  Field2: {event['field2']}")
```

### 3. Replay Identity Pattern

The display function receives events **identically** from both:
- **Run mode**: Events from FFI (`orch.get_tick_events(tick)`)
- **Replay mode**: Events from database (`get_simulation_events(sim_id, tick)`)

**NEVER** reconstruct events manually in replay. Events are self-contained.

### 4. StateProvider Extensions

If new state queries are needed, extend BOTH providers:

```python
# StateProvider Protocol
class StateProvider(Protocol):
    def new_query_method(self, arg: Type) -> ReturnType:
        ...

# OrchestratorStateProvider (live)
class OrchestratorStateProvider:
    def new_query_method(self, arg: Type) -> ReturnType:
        return self.orchestrator.new_ffi_method(arg)

# DatabaseStateProvider (replay)
class DatabaseStateProvider:
    def new_query_method(self, arg: Type) -> ReturnType:
        # Query from tick_agent_states or simulation_events
        return self._query_database(arg)
```

---

## Phase 0: Dual Priority System

### TDD Step 0.1: RtgsPriority Enum

**Test First:**
```python
# api/tests/integration/test_dual_priority_system.py

class TestRtgsPriorityEnum:
    """TDD Step 0.1: RtgsPriority enum exists and has correct values."""

    def test_rtgs_priority_values_exist(self):
        """RtgsPriority enum should have HighlyUrgent=0, Urgent=1, Normal=2."""
        # This test will FAIL until we implement the enum
        from payment_simulator._core import RtgsPriority

        assert RtgsPriority.HighlyUrgent.value == 0
        assert RtgsPriority.Urgent.value == 1
        assert RtgsPriority.Normal.value == 2

    def test_rtgs_priority_default_is_normal(self):
        """Default RtgsPriority should be Normal."""
        from payment_simulator._core import RtgsPriority

        assert RtgsPriority.default() == RtgsPriority.Normal
```

**Implementation:**
```rust
// backend/src/models/transaction.rs

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[derive(serde::Serialize, serde::Deserialize)]
#[pyclass]
pub enum RtgsPriority {
    HighlyUrgent = 0,
    Urgent = 1,
    Normal = 2,
}

impl Default for RtgsPriority {
    fn default() -> Self {
        RtgsPriority::Normal
    }
}

// Expose to Python via PyO3
#[pymethods]
impl RtgsPriority {
    #[staticmethod]
    fn default() -> Self {
        RtgsPriority::Normal
    }
}
```

**Verify:** Run test, should pass.

---

### TDD Step 0.2: Transaction RTGS Priority Fields

**Test First:**
```python
class TestTransactionRtgsPriorityFields:
    """TDD Step 0.2: Transaction has rtgs_priority and rtgs_submission_tick."""

    def test_transaction_has_rtgs_priority_field(self):
        """Transaction details should include rtgs_priority field."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 100_000)
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert "rtgs_priority" in details
        assert details["rtgs_priority"] == "Normal"  # Default

    def test_transaction_has_rtgs_submission_tick_field(self):
        """Transaction details should include rtgs_submission_tick."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 100_000)
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert "rtgs_submission_tick" in details
        assert details["rtgs_submission_tick"] == 0  # Submitted on tick 0

    def test_rtgs_priority_none_before_submission(self):
        """rtgs_priority should be None before submission to RTGS."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Hold"},  # Don't auto-submit
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 100_000)

        # Before tick - still in Queue 1
        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] is None
        assert details["rtgs_submission_tick"] is None
```

**Implementation:**
```rust
// backend/src/models/transaction.rs

pub struct Transaction {
    // ... existing fields ...

    /// RTGS declared priority - set when submitted to Queue 2
    rtgs_priority: Option<RtgsPriority>,

    /// Tick when submitted to RTGS Queue 2
    rtgs_submission_tick: Option<usize>,
}

impl Transaction {
    pub fn rtgs_priority(&self) -> Option<RtgsPriority> {
        self.rtgs_priority
    }

    pub fn rtgs_submission_tick(&self) -> Option<usize> {
        self.rtgs_submission_tick
    }

    pub fn set_rtgs_priority(&mut self, priority: RtgsPriority, tick: usize) {
        self.rtgs_priority = Some(priority);
        self.rtgs_submission_tick = Some(tick);
    }

    pub fn clear_rtgs_priority(&mut self) {
        self.rtgs_priority = None;
        self.rtgs_submission_tick = None;
    }
}

// Update FFI serialization
// backend/src/ffi/orchestrator.rs
fn get_transaction_details(&self, tx_id: &str) -> Option<HashMap<String, PyObject>> {
    // ... existing code ...
    dict.insert("rtgs_priority".to_string(),
        tx.rtgs_priority().map(|p| p.to_string()).into());
    dict.insert("rtgs_submission_tick".to_string(),
        tx.rtgs_submission_tick().into());
    // ...
}
```

---

### TDD Step 0.3: Submit with RTGS Priority

**Test First:**
```python
class TestSubmitWithRtgsPriority:
    """TDD Step 0.3: Submit action can specify RTGS priority."""

    def test_submit_transaction_with_rtgs_priority_ffi(self):
        """FFI method to submit with explicit RTGS priority."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # New FFI method with rtgs_priority parameter
        tx_id = orch.submit_transaction_with_rtgs_priority(
            sender="BANK_A",
            receiver="BANK_B",
            amount=100_000,
            deadline_tick=50,
            priority=5,  # Internal priority
            divisible=False,
            rtgs_priority="Urgent"  # NEW: RTGS priority
        )
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["priority"] == 5  # Internal priority unchanged
        assert details["rtgs_priority"] == "Urgent"  # RTGS priority set

    def test_policy_submit_action_with_rtgs_priority(self):
        """Policy Submit action can specify rtgs_priority."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low - forces Queue 2
                    "policy": {
                        "type": "Json",
                        "rules": [
                            {
                                "condition": {"field": "priority", "op": ">=", "value": 8},
                                "action": {"type": "Submit", "rtgs_priority": "Urgent"}
                            },
                            {
                                "condition": {"op": "default"},
                                "action": {"type": "Submit", "rtgs_priority": "Normal"}
                            }
                        ]
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # High internal priority -> Urgent RTGS
        tx1 = orch.submit_transaction("BANK_A", "BANK_B", 1000, priority=9)
        # Low internal priority -> Normal RTGS
        tx2 = orch.submit_transaction("BANK_A", "BANK_B", 1000, priority=3)

        orch.tick()

        details1 = orch.get_transaction_details(tx1)
        details2 = orch.get_transaction_details(tx2)

        assert details1["rtgs_priority"] == "Urgent"
        assert details2["rtgs_priority"] == "Normal"
```

**Implementation:**
```rust
// backend/src/ffi/orchestrator.rs

#[pymethods]
impl Orchestrator {
    /// Submit transaction with explicit RTGS priority
    #[pyo3(signature = (sender, receiver, amount, deadline_tick=None, priority=5, divisible=false, rtgs_priority=None))]
    pub fn submit_transaction_with_rtgs_priority(
        &mut self,
        sender: &str,
        receiver: &str,
        amount: i64,
        deadline_tick: Option<usize>,
        priority: u8,
        divisible: bool,
        rtgs_priority: Option<&str>,
    ) -> PyResult<String> {
        let rtgs_priority = rtgs_priority
            .map(|s| RtgsPriority::from_str(s))
            .transpose()?
            .unwrap_or(RtgsPriority::Normal);

        // Create transaction with rtgs_priority set
        // ...
    }
}

// backend/src/policy/actions.rs
#[derive(Debug, Clone, serde::Deserialize)]
pub struct SubmitAction {
    #[serde(default)]
    pub rtgs_priority: Option<String>,  // "Urgent" or "Normal"
}
```

---

### TDD Step 0.4: RtgsSubmission Event

**Test First:**
```python
class TestRtgsSubmissionEvent:
    """TDD Step 0.4: RtgsSubmission event emitted and persisted."""

    def test_rtgs_submission_event_emitted(self):
        """RtgsSubmission event should be emitted when tx enters Queue 2."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 100_000, rtgs_priority="Urgent"
        )
        orch.tick()

        events = orch.get_tick_events(0)
        submission_events = [e for e in events if e["event_type"] == "RtgsSubmission"]

        assert len(submission_events) == 1
        event = submission_events[0]

        # Verify ALL required fields for replay identity
        assert event["tick"] == 0
        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["receiver"] == "BANK_B"
        assert event["amount"] == 100_000
        assert event["internal_priority"] == 5  # default
        assert event["rtgs_priority"] == "Urgent"

    def test_rtgs_submission_event_persisted(self, temp_db):
        """RtgsSubmission event should be persisted to database."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        tx_id = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 100_000, rtgs_priority="Urgent"
        )
        orch.tick()

        # Persist events
        events = orch.get_tick_events(0)
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()

        sim_id = "test_sim"
        persist_tick_events(db_manager, sim_id, 0, events)

        # Retrieve and verify
        retrieved_events = get_simulation_events(temp_db, sim_id, tick=0)
        submission_events = [e for e in retrieved_events if e["event_type"] == "RtgsSubmission"]

        assert len(submission_events) == 1
        assert submission_events[0]["rtgs_priority"] == "Urgent"
```

**Implementation:**
```rust
// backend/src/models/event.rs

pub enum Event {
    // ... existing variants ...

    RtgsSubmission {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        internal_priority: u8,
        rtgs_priority: RtgsPriority,
    },
}

// backend/src/ffi/orchestrator.rs - serialization
Event::RtgsSubmission { tick, tx_id, sender, receiver, amount, internal_priority, rtgs_priority } => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "RtgsSubmission".into());
    dict.insert("tick".to_string(), tick.into());
    dict.insert("tx_id".to_string(), tx_id.into());
    dict.insert("sender".to_string(), sender.into());
    dict.insert("receiver".to_string(), receiver.into());
    dict.insert("amount".to_string(), amount.into());
    dict.insert("internal_priority".to_string(), internal_priority.into());
    dict.insert("rtgs_priority".to_string(), rtgs_priority.to_string().into());
    dict
}
```

---

### TDD Step 0.5: CLI Verbose Output for RtgsSubmission

**Test First:**
```python
class TestRtgsSubmissionVerboseOutput:
    """TDD Step 0.5: RtgsSubmission displayed in verbose output."""

    def test_rtgs_submission_displayed_in_verbose(self, capsys):
        """RtgsSubmission should appear in verbose output."""
        events = [{
            "event_type": "RtgsSubmission",
            "tick": 0,
            "tx_id": "TX-001",
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 100000,
            "internal_priority": 7,
            "rtgs_priority": "Urgent",
        }]

        # Create mock provider
        provider = MockStateProvider()

        display_tick_verbose_output(provider, tick=0, events=events)

        captured = capsys.readouterr()
        assert "RTGS Submission" in captured.out
        assert "TX-001" in captured.out
        assert "BANK_A" in captured.out
        assert "BANK_B" in captured.out
        assert "$1,000.00" in captured.out  # 100000 cents
        assert "Urgent" in captured.out
        assert "internal: 7" in captured.out
```

**Implementation:**
```python
# api/payment_simulator/cli/execution/display.py

def display_tick_verbose_output(provider: StateProvider, tick: int, events: list[dict]):
    # ... existing code ...

    for event in events:
        event_type = event.get("event_type", "")

        if event_type == "RtgsSubmission":
            log_rtgs_submission_event(event)
        # ... other event types ...

def log_rtgs_submission_event(event: dict):
    """Display RtgsSubmission event in verbose output."""
    console.print(f"[green]RTGS Submission:[/green] {event['tx_id']}")
    console.print(f"  {event['sender']} → {event['receiver']}")
    console.print(f"  Amount: ${event['amount']/100:,.2f}")
    console.print(f"  RTGS Priority: [bold]{event['rtgs_priority']}[/bold] (internal: {event['internal_priority']})")
```

---

### TDD Step 0.6: Replay Identity for RtgsSubmission

**Test First (E2E):**
```python
class TestRtgsSubmissionReplayIdentity:
    """TDD Step 0.6: RtgsSubmission replay produces identical output."""

    def test_rtgs_submission_replay_identity(self, temp_db, capsys):
        """Run and replay should produce identical RtgsSubmission output."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }

        # === RUN MODE ===
        orch = Orchestrator.new(config)
        orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 100_000, rtgs_priority="Urgent"
        )
        orch.tick()

        # Capture run output
        run_events = orch.get_tick_events(0)
        run_provider = OrchestratorStateProvider(orch)

        run_output = io.StringIO()
        with redirect_stdout(run_output):
            display_tick_verbose_output(run_provider, 0, run_events)
        run_text = run_output.getvalue()

        # Persist to database
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()
        sim_id = "test_sim"
        persist_simulation(db_manager, sim_id, config, orch)

        # === REPLAY MODE ===
        replay_events = get_simulation_events(temp_db, sim_id, tick=0)
        replay_provider = DatabaseStateProvider(temp_db, sim_id, tick=0)

        replay_output = io.StringIO()
        with redirect_stdout(replay_output):
            display_tick_verbose_output(replay_provider, 0, replay_events)
        replay_text = replay_output.getvalue()

        # === IDENTITY CHECK ===
        # Remove timing info (Duration:) before comparison
        run_lines = [l for l in run_text.split('\n') if not l.startswith('Duration:')]
        replay_lines = [l for l in replay_text.split('\n') if not l.startswith('Duration:')]

        assert run_lines == replay_lines, \
            f"Replay diverged from run:\nRun:\n{run_text}\n\nReplay:\n{replay_text}"
```

---

### TDD Step 0.7: Withdrawal from RTGS

**Test First:**
```python
class TestWithdrawFromRtgs:
    """TDD Step 0.7: Withdrawal from RTGS Queue 2."""

    def test_withdraw_removes_from_queue2(self):
        """Withdrawal should remove transaction from Queue 2."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},  # Low - forces Queue 2
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000)
        orch.tick()

        assert orch.queue_size() == 1
        assert tx_id in orch.get_queue2_contents()

        # Withdraw
        result = orch.withdraw_from_rtgs(tx_id)

        assert result["success"] == True
        assert orch.queue_size() == 0
        assert tx_id not in orch.get_queue2_contents()

    def test_withdraw_returns_to_queue1(self):
        """Withdrawn transaction should return to sender's Queue 1."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 1000)
        orch.tick()

        orch.withdraw_from_rtgs(tx_id)

        queue1 = orch.get_agent_queue1_contents("BANK_A")
        assert tx_id in queue1

    def test_withdraw_clears_rtgs_priority(self):
        """Withdrawal should clear rtgs_priority and rtgs_submission_tick."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Urgent"
        )
        orch.tick()

        details_before = orch.get_transaction_details(tx_id)
        assert details_before["rtgs_priority"] == "Urgent"
        assert details_before["rtgs_submission_tick"] == 0

        orch.withdraw_from_rtgs(tx_id)

        details_after = orch.get_transaction_details(tx_id)
        assert details_after["rtgs_priority"] is None
        assert details_after["rtgs_submission_tick"] is None

    def test_withdraw_emits_event(self):
        """Withdrawal should emit RtgsWithdrawal event."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Urgent"
        )
        orch.tick()  # Tick 0: submission

        orch.withdraw_from_rtgs(tx_id)
        orch.tick()  # Tick 1: withdrawal processed

        events = orch.get_tick_events(1)
        withdrawal_events = [e for e in events if e["event_type"] == "RtgsWithdrawal"]

        assert len(withdrawal_events) == 1
        event = withdrawal_events[0]

        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["original_rtgs_priority"] == "Urgent"
        assert event["ticks_in_queue"] == 1
        assert event["reason"] == "AgentRequest"
```

---

### TDD Step 0.8: Resubmission with New Priority

**Test First:**
```python
class TestResubmitToRtgs:
    """TDD Step 0.8: Resubmission to RTGS with new priority."""

    def test_resubmit_changes_rtgs_priority(self):
        """Resubmission should change RTGS priority."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Normal"
        )
        orch.tick()

        orch.withdraw_from_rtgs(tx_id)
        orch.resubmit_to_rtgs(tx_id, rtgs_priority="Urgent")
        orch.tick()

        details = orch.get_transaction_details(tx_id)
        assert details["rtgs_priority"] == "Urgent"

    def test_resubmit_loses_fifo_position(self):
        """Resubmission should move transaction to back of priority band."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # Submit three Normal transactions
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Normal"
        )
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Normal"
        )
        tx3 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Normal"
        )
        orch.tick()  # Tick 0

        # Queue should be FIFO: tx1, tx2, tx3
        queue = orch.get_queue2_contents()
        assert queue == [tx1, tx2, tx3]

        # Withdraw tx1 and resubmit (same priority)
        orch.withdraw_from_rtgs(tx1)
        orch.resubmit_to_rtgs(tx1, rtgs_priority="Normal")
        orch.tick()  # Tick 1

        # tx1 should now be LAST (lost FIFO position)
        queue = orch.get_queue2_contents()
        assert queue == [tx2, tx3, tx1]

    def test_resubmit_emits_event(self):
        """Resubmission should emit RtgsResubmission event."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        tx_id = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, rtgs_priority="Normal"
        )
        orch.tick()

        orch.withdraw_from_rtgs(tx_id)
        orch.resubmit_to_rtgs(tx_id, rtgs_priority="Urgent")
        orch.tick()

        events = orch.get_tick_events(1)
        resubmit_events = [e for e in events if e["event_type"] == "RtgsResubmission"]

        assert len(resubmit_events) == 1
        event = resubmit_events[0]

        assert event["tx_id"] == tx_id
        assert event["sender"] == "BANK_A"
        assert event["old_rtgs_priority"] == "Normal"
        assert event["new_rtgs_priority"] == "Urgent"
```

---

### TDD Step 0.9: Queue 2 Ordering by RTGS Priority

**Test First:**
```python
class TestQueue2RtgsPriorityOrdering:
    """TDD Step 0.9: Queue 2 ordered by rtgs_priority, then submission tick."""

    def test_queue2_orders_by_rtgs_priority_not_internal(self):
        """Queue 2 should order by RTGS priority, not internal priority."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # High internal (9), Normal RTGS
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, priority=9, rtgs_priority="Normal"
        )
        # Low internal (2), Urgent RTGS
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, priority=2, rtgs_priority="Urgent"
        )

        orch.tick()

        queue = orch.get_queue2_contents()

        # Urgent (tx2) should be BEFORE Normal (tx1), despite lower internal priority
        assert queue[0] == tx2  # Urgent first
        assert queue[1] == tx1  # Normal second

    def test_queue2_fifo_within_same_rtgs_priority(self):
        """Within same RTGS priority band, FIFO by submission tick."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        # All Normal RTGS, different internal priorities
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, priority=3, rtgs_priority="Normal"
        )
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, priority=9, rtgs_priority="Normal"
        )
        tx3 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_B", 1000, priority=5, rtgs_priority="Normal"
        )

        orch.tick()

        queue = orch.get_queue2_contents()

        # All Normal, so FIFO order preserved
        assert queue == [tx1, tx2, tx3]
```

---

### TDD Step 0.10: Full E2E Replay Identity Test

**Test First:**
```python
class TestPhase0FullReplayIdentity:
    """TDD Step 0.10: Complete E2E replay identity for Phase 0."""

    def test_complete_dual_priority_replay_identity(self, temp_db):
        """Full E2E test: run with all Phase 0 features, replay must match."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "priority_mode": True,
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 100},
                {"id": "BANK_C", "opening_balance": 1_000_000},
            ]
        }

        # === RUN MODE ===
        orch = Orchestrator.new(config)

        # Various operations
        tx1 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_C", 1000, priority=5, rtgs_priority="Normal"
        )
        tx2 = orch.submit_transaction_with_rtgs_priority(
            "BANK_B", "BANK_C", 1000, priority=8, rtgs_priority="Urgent"
        )
        orch.tick()  # Tick 0

        # Withdraw and resubmit tx1 as Urgent
        orch.withdraw_from_rtgs(tx1)
        orch.resubmit_to_rtgs(tx1, rtgs_priority="Urgent")
        orch.tick()  # Tick 1

        # More transactions
        tx3 = orch.submit_transaction_with_rtgs_priority(
            "BANK_A", "BANK_C", 500, rtgs_priority="Normal"
        )
        orch.tick()  # Tick 2

        # Capture ALL events from run
        all_run_events = []
        for tick in range(3):
            events = orch.get_tick_events(tick)
            all_run_events.append((tick, events))

        # Persist to database
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()
        sim_id = "test_sim"

        for tick, events in all_run_events:
            persist_tick_events(db_manager, sim_id, tick, events)
        persist_tick_agent_states(db_manager, sim_id, orch)

        # === REPLAY MODE ===
        # For each tick, compare run events vs replay events
        for tick, run_events in all_run_events:
            replay_events = get_simulation_events(temp_db, sim_id, tick=tick)

            # Sort both for comparison (events may be in different order)
            run_sorted = sorted(run_events, key=lambda e: (e["event_type"], str(e)))
            replay_sorted = sorted(replay_events, key=lambda e: (e["event_type"], str(e)))

            assert len(run_sorted) == len(replay_sorted), \
                f"Tick {tick}: Event count mismatch"

            for run_evt, replay_evt in zip(run_sorted, replay_sorted):
                assert run_evt == replay_evt, \
                    f"Tick {tick}: Event mismatch\nRun: {run_evt}\nReplay: {replay_evt}"

        # === DISPLAY IDENTITY ===
        for tick, run_events in all_run_events:
            run_provider = OrchestratorStateProvider(orch)
            replay_provider = DatabaseStateProvider(temp_db, sim_id, tick)
            replay_events = get_simulation_events(temp_db, sim_id, tick=tick)

            run_output = capture_display_output(run_provider, tick, run_events)
            replay_output = capture_display_output(replay_provider, tick, replay_events)

            # Remove timing lines
            run_lines = filter_timing_lines(run_output)
            replay_lines = filter_timing_lines(replay_output)

            assert run_lines == replay_lines, \
                f"Tick {tick}: Display output diverged"
```

---

## Phase 1: Bilateral/Multilateral Limits

### TDD Step 1.1: AgentLimits Data Structure

**Test First:**
```python
class TestAgentLimitsConfig:
    """TDD Step 1.1: AgentLimits configuration accepted."""

    def test_bilateral_limits_config_accepted(self):
        """Config with bilateral_limits should be accepted."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {
                        "bilateral_limits": {"BANK_B": 500_000}
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_multilateral_limit_config_accepted(self):
        """Config with multilateral_limit should be accepted."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {
                        "multilateral_limit": 800_000
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None

    def test_get_agent_limits(self):
        """Should be able to query agent's limits."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {
                        "bilateral_limits": {"BANK_B": 500_000, "BANK_C": 300_000},
                        "multilateral_limit": 700_000
                    }
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
                {"id": "BANK_C", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)

        limits = orch.get_agent_limits("BANK_A")

        assert limits["bilateral_limits"]["BANK_B"] == 500_000
        assert limits["bilateral_limits"]["BANK_C"] == 300_000
        assert limits["multilateral_limit"] == 700_000
```

---

### TDD Step 1.2: Bilateral Limit Enforcement

**Test First:**
```python
class TestBilateralLimitEnforcement:
    """TDD Step 1.2: Bilateral limits block settlements."""

    def test_payment_within_bilateral_limit_settles(self):
        """Payment within limit should settle."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 400_000)
        orch.tick()

        # Should settle (400k < 500k limit)
        details = orch.get_transaction_details(tx_id)
        assert details["status"] == "settled"

    def test_payment_exceeding_bilateral_limit_queued(self):
        """Payment exceeding limit should be queued."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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

        tx_id = orch.submit_transaction("BANK_A", "BANK_B", 600_000)
        orch.tick()

        # Should be queued (600k > 500k limit)
        assert orch.queue_size() == 1

    def test_bilateral_limit_exceeded_event(self):
        """BilateralLimitExceeded event should be emitted."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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
        limit_events = [e for e in events if e["event_type"] == "BilateralLimitExceeded"]

        assert len(limit_events) == 1
        event = limit_events[0]

        # All fields for replay identity
        assert event["sender"] == "BANK_A"
        assert event["receiver"] == "BANK_B"
        assert event["limit"] == 500_000
        assert event["attempted"] == 600_000
        assert event["current_outflow"] == 0
```

---

### TDD Step 1.3: Cumulative Bilateral Tracking

**Test First:**
```python
class TestCumulativeBilateralTracking:
    """TDD Step 1.3: Bilateral limits track cumulative outflow."""

    def test_cumulative_bilateral_outflow_tracked(self):
        """Multiple payments should cumulatively track toward limit."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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
        tx1 = orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()
        assert orch.queue_size() == 0  # Settled

        # Second payment: 300k (cumulative 600k > 500k limit)
        tx2 = orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()
        assert orch.queue_size() == 1  # Queued due to limit

        # Check event shows current outflow
        events = orch.get_tick_events(1)
        limit_events = [e for e in events if e["event_type"] == "BilateralLimitExceeded"]
        assert limit_events[0]["current_outflow"] == 300_000

    def test_bilateral_outflow_resets_at_day_boundary(self):
        """Bilateral outflow tracking should reset at new day."""
        config = {
            "ticks_per_day": 10,  # Short day
            "rng_seed": 42,
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

        # Now at Day 1, tick 0
        assert orch.current_day() == 1

        # Limit should have reset - new 500k available
        tx = orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.tick()

        details = orch.get_transaction_details(tx)
        assert details["status"] == "settled"
```

---

### TDD Step 1.4: Multilateral Limit Enforcement

**Test First:**
```python
class TestMultilateralLimitEnforcement:
    """TDD Step 1.4: Multilateral limits block settlements."""

    def test_multilateral_limit_tracks_total_outflow(self):
        """Multilateral limit should track total outflow to all counterparties."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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

        # 300k to C - queued (cumulative 600k > 500k multilateral)
        orch.submit_transaction("BANK_A", "BANK_C", 300_000)
        orch.tick()
        assert orch.queue_size() == 1

        events = orch.get_tick_events(1)
        limit_events = [e for e in events if e["event_type"] == "MultilateralLimitExceeded"]
        assert len(limit_events) == 1
```

---

### TDD Step 1.5: Limits in LSM

**Test First:**
```python
class TestLimitsInLsm:
    """TDD Step 1.5: LSM respects limits in cycle settlement."""

    def test_lsm_bilateral_offset_respects_limits(self):
        """LSM bilateral offset should check limits."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "lsm_config": {"enable_bilateral": True, "enable_cycles": False},
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 100,  # Low liquidity
                    "limits": {"bilateral_limits": {"BANK_B": 200_000}}
                },
                {"id": "BANK_B", "opening_balance": 100},
            ]
        }
        orch = Orchestrator.new(config)

        # A→B 300k (exceeds A's 200k bilateral limit to B)
        # B→A 300k
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.submit_transaction("BANK_B", "BANK_A", 300_000)
        orch.tick()

        # Should NOT offset due to bilateral limit
        assert orch.queue_size() == 2

    def test_lsm_cycle_respects_limits(self):
        """LSM cycle settlement should check limits for each leg."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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

        # Cycle: A→B (300k, exceeds limit), B→C (300k), C→A (300k)
        orch.submit_transaction("BANK_A", "BANK_B", 300_000)
        orch.submit_transaction("BANK_B", "BANK_C", 300_000)
        orch.submit_transaction("BANK_C", "BANK_A", 300_000)
        orch.tick()

        # Cycle should NOT settle due to A's bilateral limit to B
        assert orch.queue_size() == 3
```

---

### TDD Step 1.6: Limits E2E Replay Identity

**Test First:**
```python
class TestLimitsReplayIdentity:
    """TDD Step 1.6: Limits events replay correctly."""

    def test_bilateral_limit_exceeded_replay_identity(self, temp_db):
        """BilateralLimitExceeded event should replay identically."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "limits": {"bilateral_limits": {"BANK_B": 500_000}}
                },
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }

        # Run
        orch = Orchestrator.new(config)
        orch.submit_transaction("BANK_A", "BANK_B", 600_000)
        orch.tick()

        run_events = orch.get_tick_events(0)

        # Persist
        db_manager = DatabaseManager(temp_db)
        db_manager.initialize_schema()
        sim_id = "test_sim"
        persist_tick_events(db_manager, sim_id, 0, run_events)

        # Replay
        replay_events = get_simulation_events(temp_db, sim_id, tick=0)

        # Compare limit events
        run_limit = [e for e in run_events if e["event_type"] == "BilateralLimitExceeded"]
        replay_limit = [e for e in replay_events if e["event_type"] == "BilateralLimitExceeded"]

        assert run_limit == replay_limit
```

---

## Phase 2: Algorithm Sequencing

### TDD Step 2.1: Algorithm Sequencing Config

**Test First:**
```python
class TestAlgorithmSequencingConfig:
    """TDD Step 2.1: Algorithm sequencing configuration."""

    def test_algorithm_sequencing_config_accepted(self):
        """Config with algorithm_sequencing should be accepted."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "rtgs_config": {"algorithm_sequencing": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 1_000_000},
                {"id": "BANK_B", "opening_balance": 1_000_000},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None
```

### TDD Step 2.2: Algorithm Execution Events

**Test First:**
```python
class TestAlgorithmExecutionEvents:
    """TDD Step 2.2: Algorithm execution events emitted."""

    def test_algorithm_execution_event_emitted(self):
        """AlgorithmExecution event should be emitted for each algorithm run."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
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
        alg_events = [e for e in events if e["event_type"] == "AlgorithmExecution"]

        assert len(alg_events) >= 1
        event = alg_events[0]

        assert "algorithm" in event  # 1, 2, or 3
        assert "result" in event  # "Success", "Failure", "NoProgress"
        assert "settlements" in event  # Number of settlements
        assert "duration_ns" in event  # Execution time
```

---

## Phase 3: Entry Disposition Offsetting

### TDD Step 3.1: Entry Disposition Config

**Test First:**
```python
class TestEntryDispositionConfig:
    """TDD Step 3.1: Entry disposition offsetting configuration."""

    def test_entry_disposition_config_accepted(self):
        """Config with entry_disposition_offsetting should be accepted."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "rtgs_config": {"entry_disposition_offsetting": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 100},
            ]
        }
        orch = Orchestrator.new(config)
        assert orch is not None
```

### TDD Step 3.2: Entry Disposition Offset

**Test First:**
```python
class TestEntryDispositionOffset:
    """TDD Step 3.2: Entry disposition triggers offset at submission."""

    def test_entry_disposition_finds_offset(self):
        """Incoming payment should offset queued opposite payment at entry."""
        config = {
            "ticks_per_day": 100,
            "rng_seed": 42,
            "rtgs_config": {"entry_disposition_offsetting": True},
            "agent_configs": [
                {"id": "BANK_A", "opening_balance": 100},
                {"id": "BANK_B", "opening_balance": 100},
            ]
        }
        orch = Orchestrator.new(config)

        # A→B queued (insufficient liquidity)
        orch.submit_transaction("BANK_A", "BANK_B", 500_000)
        orch.tick()
        assert orch.queue_size() == 1

        # B→A arrives - should trigger offset at entry
        orch.submit_transaction("BANK_B", "BANK_A", 500_000)
        orch.tick()

        # Both should have settled via entry disposition offset
        assert orch.queue_size() == 0

        events = orch.get_tick_events(1)
        offset_events = [e for e in events if e["event_type"] == "EntryDispositionOffset"]
        assert len(offset_events) == 1
```

---

## StateProvider Extensions

For each phase, extend StateProvider if new queries are needed:

```python
# api/payment_simulator/cli/execution/state_provider.py

class StateProvider(Protocol):
    # Phase 0: RTGS Priority
    def get_transaction_rtgs_priority(self, tx_id: str) -> str | None:
        """Get transaction's RTGS priority."""
        ...

    # Phase 1: Limits
    def get_agent_limits(self, agent_id: str) -> dict:
        """Get agent's bilateral and multilateral limits."""
        ...

    def get_agent_current_outflows(self, agent_id: str) -> dict:
        """Get agent's current bilateral outflows and total outflow."""
        ...

# Implement in BOTH OrchestratorStateProvider AND DatabaseStateProvider
```

---

## Test Execution Order

```bash
# Phase 0: Run tests in order
pytest tests/integration/test_dual_priority_system.py::TestRtgsPriorityEnum -v
pytest tests/integration/test_dual_priority_system.py::TestTransactionRtgsPriorityFields -v
pytest tests/integration/test_dual_priority_system.py::TestSubmitWithRtgsPriority -v
pytest tests/integration/test_dual_priority_system.py::TestRtgsSubmissionEvent -v
pytest tests/integration/test_dual_priority_system.py::TestRtgsSubmissionVerboseOutput -v
pytest tests/integration/test_dual_priority_system.py::TestRtgsSubmissionReplayIdentity -v
pytest tests/integration/test_dual_priority_system.py::TestWithdrawFromRtgs -v
pytest tests/integration/test_dual_priority_system.py::TestResubmitToRtgs -v
pytest tests/integration/test_dual_priority_system.py::TestQueue2RtgsPriorityOrdering -v
pytest tests/integration/test_dual_priority_system.py::TestPhase0FullReplayIdentity -v

# Phase 1: After Phase 0 passes
pytest tests/integration/test_bilateral_multilateral_limits.py -v

# Phase 2: After Phase 1 passes
pytest tests/integration/test_algorithm_sequencing.py -v

# Phase 3: After Phase 1 passes (can parallel with Phase 2)
pytest tests/integration/test_entry_disposition_offsetting.py -v

# Full regression
pytest tests/ -v
```

---

## Checklist Per Feature

For EVERY new event type:

- [ ] Event defined in `backend/src/models/event.rs`
- [ ] Event serialized in `backend/src/ffi/orchestrator.rs`
- [ ] Event includes ALL fields needed for display (no ID-only fields)
- [ ] Display function in `api/payment_simulator/cli/execution/display.py`
- [ ] Persistence test (event stored and retrieved correctly)
- [ ] Display test (event appears in verbose output)
- [ ] Replay identity test (run == replay)
- [ ] E2E test (full workflow)

For EVERY new StateProvider query:

- [ ] Protocol method added to `StateProvider`
- [ ] Implemented in `OrchestratorStateProvider` (FFI)
- [ ] Implemented in `DatabaseStateProvider` (SQL)
- [ ] Contract test verifying both implementations agree
