# Phase 1: Data Structures

**Status**: In Progress
**Started**: 2025-12-13
**Parent Plan**: `../development-plan.md`

## Objective

Define the core data types for bootstrap evaluation that preserve relative timing information and support deterministic resampling.

## Critical Invariants

These MUST be enforced in all data structures:

1. **INV-1: Money is integer cents** - All `amount` fields are `int`, never `float`
2. **INV-2: Immutability** - All records are frozen dataclasses for safety and hashability
3. **INV-3: Relative timing** - Offsets stored instead of absolute ticks where needed

## Data Types to Implement

### 1. TransactionRecord

**Purpose**: Store a historical transaction with relative timing offsets.

**Key Design Decision**: Store `deadline_offset` (relative) instead of `deadline_tick` (absolute). This enables correct remapping when arrival tick changes.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TransactionRecord:
    """Historical transaction record with relative timing offsets.

    This is the core data structure for bootstrap resampling. The key insight
    is storing RELATIVE timing (offsets from arrival) rather than ABSOLUTE
    ticks. When a transaction is resampled with a new arrival tick, the
    deadline maintains the same relative position.

    Example:
        Original: arrival=10, deadline=25 → deadline_offset=15
        Remapped to arrival=5 → deadline=5+15=20 (offset preserved)

    Attributes:
        tx_id: Unique transaction identifier.
        sender_id: ID of sending agent.
        receiver_id: ID of receiving agent.
        amount: Transaction amount in integer cents (INV-1).
        priority: Priority level (0-10, higher = more urgent).
        arrival_tick: Original tick when transaction arrived.
        deadline_offset: Ticks between arrival and deadline (deadline - arrival).
        settlement_offset: Ticks between arrival and settlement (if settled), None otherwise.
        is_divisible: Whether transaction can be split.
    """
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # INV-1: Integer cents
    priority: int
    arrival_tick: int
    deadline_offset: int  # deadline_tick - arrival_tick
    settlement_offset: int | None  # settlement_tick - arrival_tick, None if unsettled
    is_divisible: bool

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if not isinstance(self.amount, int):
            raise TypeError(f"amount must be int, got {type(self.amount).__name__}")
        if self.amount <= 0:
            raise ValueError(f"amount must be positive, got {self.amount}")
        if self.deadline_offset < 0:
            raise ValueError(f"deadline_offset must be non-negative, got {self.deadline_offset}")
        if self.settlement_offset is not None and self.settlement_offset < 0:
            raise ValueError(f"settlement_offset must be non-negative, got {self.settlement_offset}")

    @property
    def original_deadline_tick(self) -> int:
        """Compute original absolute deadline tick."""
        return self.arrival_tick + self.deadline_offset

    @property
    def was_settled(self) -> bool:
        """Check if transaction was settled in original simulation."""
        return self.settlement_offset is not None

    @classmethod
    def from_absolute_ticks(
        cls,
        tx_id: str,
        sender_id: str,
        receiver_id: str,
        amount: int,
        priority: int,
        arrival_tick: int,
        deadline_tick: int,
        settlement_tick: int | None,
        is_divisible: bool,
    ) -> "TransactionRecord":
        """Create record from absolute tick values (convenience constructor)."""
        deadline_offset = deadline_tick - arrival_tick
        settlement_offset = (
            settlement_tick - arrival_tick if settlement_tick is not None else None
        )
        return cls(
            tx_id=tx_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            priority=priority,
            arrival_tick=arrival_tick,
            deadline_offset=deadline_offset,
            settlement_offset=settlement_offset,
            is_divisible=is_divisible,
        )
```

### 2. RemappedTransaction

**Purpose**: A transaction with a new arrival tick but preserved relative timing.

```python
@dataclass(frozen=True)
class RemappedTransaction:
    """Transaction remapped to a new arrival tick with preserved offsets.

    During bootstrap resampling, transactions are assigned new arrival ticks
    (uniformly distributed across the simulation day). The deadline maintains
    the same offset from the new arrival tick.

    Example:
        Original: arrival=10, deadline_offset=15 → deadline=25
        Remapped to new_arrival_tick=5 → deadline=5+15=20

    Attributes:
        original: The original TransactionRecord.
        new_arrival_tick: The remapped arrival tick.
    """
    original: TransactionRecord
    new_arrival_tick: int

    def __post_init__(self) -> None:
        """Validate that new arrival tick is non-negative."""
        if self.new_arrival_tick < 0:
            raise ValueError(f"new_arrival_tick must be non-negative, got {self.new_arrival_tick}")

    @property
    def deadline_tick(self) -> int:
        """Compute absolute deadline tick using preserved offset."""
        return self.new_arrival_tick + self.original.deadline_offset

    @property
    def tx_id(self) -> str:
        """Forward to original transaction ID."""
        return self.original.tx_id

    @property
    def sender_id(self) -> str:
        """Forward to original sender ID."""
        return self.original.sender_id

    @property
    def receiver_id(self) -> str:
        """Forward to original receiver ID."""
        return self.original.receiver_id

    @property
    def amount(self) -> int:
        """Forward to original amount (INV-1: integer cents)."""
        return self.original.amount

    @property
    def priority(self) -> int:
        """Forward to original priority."""
        return self.original.priority

    @property
    def is_divisible(self) -> bool:
        """Forward to original divisibility."""
        return self.original.is_divisible

    def to_scenario_event_dict(self) -> dict[str, str | int | bool]:
        """Convert to scenario_events dict for FFI config.

        Returns:
            Dict suitable for use in simulation config scenario_events.
        """
        return {
            "tx_id": self.tx_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "amount": self.amount,
            "priority": self.priority,
            "arrival_tick": self.new_arrival_tick,
            "deadline_tick": self.deadline_tick,
            "is_divisible": self.is_divisible,
        }
```

### 3. BootstrapSample

**Purpose**: A complete bootstrap sample ready for policy evaluation.

```python
@dataclass(frozen=True)
class BootstrapSample:
    """A complete bootstrap sample for policy evaluation.

    Contains all transactions needed to evaluate a policy in the 3-agent
    sandbox (AGENT, SINK, SOURCE):
    - outgoing_transactions: Payments AGENT needs to make (to SINK)
    - liquidity_beats: Payments AGENT receives (from SOURCE)

    The sample is fully deterministic given its seed.

    Attributes:
        sample_idx: Index of this sample (0 to num_samples-1).
        seed: Deterministic seed used to generate this sample (INV-2).
        outgoing_transactions: Transactions where agent is sender.
        liquidity_beats: Transactions where agent is receiver (incoming liquidity).
        source_agent_id: The agent this sample was created for.
    """
    sample_idx: int
    seed: int  # INV-2: Deterministic seed
    outgoing_transactions: tuple[RemappedTransaction, ...]
    liquidity_beats: tuple[RemappedTransaction, ...]
    source_agent_id: str

    def __post_init__(self) -> None:
        """Validate sample structure."""
        if self.sample_idx < 0:
            raise ValueError(f"sample_idx must be non-negative, got {self.sample_idx}")

    @property
    def num_outgoing(self) -> int:
        """Number of outgoing transactions."""
        return len(self.outgoing_transactions)

    @property
    def num_incoming(self) -> int:
        """Number of incoming liquidity beats."""
        return len(self.liquidity_beats)

    @property
    def total_outgoing_amount(self) -> int:
        """Total value of outgoing transactions (INV-1: integer cents)."""
        return sum(tx.amount for tx in self.outgoing_transactions)

    @property
    def total_incoming_amount(self) -> int:
        """Total value of incoming liquidity beats (INV-1: integer cents)."""
        return sum(tx.amount for tx in self.liquidity_beats)

    def get_scenario_events(self) -> list[dict[str, str | int | bool]]:
        """Convert all transactions to scenario_events format.

        Returns:
            List of scenario event dicts for FFI config.
        """
        events = []
        for tx in self.outgoing_transactions:
            events.append(tx.to_scenario_event_dict())
        for tx in self.liquidity_beats:
            events.append(tx.to_scenario_event_dict())
        # Sort by arrival tick for deterministic ordering
        events.sort(key=lambda e: (e["arrival_tick"], e["tx_id"]))
        return events
```

## File Location

Create: `api/payment_simulator/ai_cash_mgmt/bootstrap/models.py`

## TDD Test Plan

### Test File: `api/tests/unit/ai_cash_mgmt/bootstrap/test_models.py`

Write tests FIRST (Red phase), then implement to make them pass (Green phase).

#### 1. TransactionRecord Tests

```python
class TestTransactionRecord:
    """Tests for TransactionRecord dataclass."""

    def test_creates_with_valid_data(self) -> None:
        """TransactionRecord can be created with valid data."""
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,  # $1000.00
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=5,
            is_divisible=True,
        )
        assert record.tx_id == "TX001"
        assert record.amount == 100_000
        assert record.deadline_offset == 15

    def test_amount_must_be_int(self) -> None:
        """TransactionRecord raises TypeError if amount is not int."""
        with pytest.raises(TypeError, match="amount must be int"):
            TransactionRecord(
                tx_id="TX001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=1000.00,  # Float - INVALID
                priority=5,
                arrival_tick=10,
                deadline_offset=15,
                settlement_offset=None,
                is_divisible=True,
            )

    def test_amount_must_be_positive(self) -> None:
        """TransactionRecord raises ValueError if amount <= 0."""
        with pytest.raises(ValueError, match="amount must be positive"):
            TransactionRecord(
                tx_id="TX001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=0,
                priority=5,
                arrival_tick=10,
                deadline_offset=15,
                settlement_offset=None,
                is_divisible=True,
            )

    def test_deadline_offset_non_negative(self) -> None:
        """TransactionRecord raises ValueError if deadline_offset < 0."""
        with pytest.raises(ValueError, match="deadline_offset must be non-negative"):
            TransactionRecord(
                tx_id="TX001",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100_000,
                priority=5,
                arrival_tick=10,
                deadline_offset=-5,
                settlement_offset=None,
                is_divisible=True,
            )

    def test_original_deadline_tick_computed_correctly(self) -> None:
        """original_deadline_tick = arrival_tick + deadline_offset."""
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        assert record.original_deadline_tick == 25  # 10 + 15

    def test_was_settled_true_when_settlement_offset_present(self) -> None:
        """was_settled is True when settlement_offset is not None."""
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=5,
            is_divisible=True,
        )
        assert record.was_settled is True

    def test_was_settled_false_when_settlement_offset_none(self) -> None:
        """was_settled is False when settlement_offset is None."""
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        assert record.was_settled is False

    def test_from_absolute_ticks_computes_offsets(self) -> None:
        """from_absolute_ticks correctly computes offsets."""
        record = TransactionRecord.from_absolute_ticks(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_tick=25,
            settlement_tick=15,
            is_divisible=True,
        )
        assert record.deadline_offset == 15  # 25 - 10
        assert record.settlement_offset == 5  # 15 - 10

    def test_is_frozen_immutable(self) -> None:
        """TransactionRecord is immutable (frozen dataclass)."""
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        with pytest.raises(FrozenInstanceError):
            record.amount = 200_000  # Should raise

    def test_is_hashable(self) -> None:
        """TransactionRecord is hashable (can be used in sets/dicts)."""
        record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        # Should not raise
        hash(record)
        {record}  # Can add to set
```

#### 2. RemappedTransaction Tests

```python
class TestRemappedTransaction:
    """Tests for RemappedTransaction dataclass."""

    def test_creates_with_valid_data(self) -> None:
        """RemappedTransaction can be created with valid data."""
        original = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        remapped = RemappedTransaction(original=original, new_arrival_tick=5)
        assert remapped.new_arrival_tick == 5

    def test_deadline_tick_uses_preserved_offset(self) -> None:
        """deadline_tick = new_arrival_tick + original.deadline_offset."""
        original = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,  # Original deadline was tick 25
            settlement_offset=None,
            is_divisible=True,
        )
        remapped = RemappedTransaction(original=original, new_arrival_tick=5)
        # New deadline should be 5 + 15 = 20 (offset preserved)
        assert remapped.deadline_tick == 20

    def test_forwards_properties_from_original(self) -> None:
        """RemappedTransaction forwards properties from original."""
        original = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=7,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=False,
        )
        remapped = RemappedTransaction(original=original, new_arrival_tick=5)
        assert remapped.tx_id == "TX001"
        assert remapped.sender_id == "BANK_A"
        assert remapped.receiver_id == "BANK_B"
        assert remapped.amount == 100_000
        assert remapped.priority == 7
        assert remapped.is_divisible is False

    def test_to_scenario_event_dict_correct_format(self) -> None:
        """to_scenario_event_dict returns FFI-compatible dict."""
        original = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        remapped = RemappedTransaction(original=original, new_arrival_tick=5)
        event_dict = remapped.to_scenario_event_dict()

        assert event_dict["tx_id"] == "TX001"
        assert event_dict["sender_id"] == "BANK_A"
        assert event_dict["receiver_id"] == "BANK_B"
        assert event_dict["amount"] == 100_000
        assert event_dict["priority"] == 5
        assert event_dict["arrival_tick"] == 5  # NEW arrival tick
        assert event_dict["deadline_tick"] == 20  # 5 + 15
        assert event_dict["is_divisible"] is True

    def test_new_arrival_tick_must_be_non_negative(self) -> None:
        """RemappedTransaction raises ValueError if new_arrival_tick < 0."""
        original = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        with pytest.raises(ValueError, match="new_arrival_tick must be non-negative"):
            RemappedTransaction(original=original, new_arrival_tick=-1)
```

#### 3. BootstrapSample Tests

```python
class TestBootstrapSample:
    """Tests for BootstrapSample dataclass."""

    @pytest.fixture
    def sample_transactions(self) -> tuple[RemappedTransaction, RemappedTransaction]:
        """Create sample transactions for testing."""
        outgoing_record = TransactionRecord(
            tx_id="TX001",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100_000,
            priority=5,
            arrival_tick=10,
            deadline_offset=15,
            settlement_offset=None,
            is_divisible=True,
        )
        incoming_record = TransactionRecord(
            tx_id="TX002",
            sender_id="BANK_B",
            receiver_id="BANK_A",
            amount=50_000,
            priority=3,
            arrival_tick=5,
            deadline_offset=20,
            settlement_offset=None,
            is_divisible=True,
        )
        return (
            RemappedTransaction(original=outgoing_record, new_arrival_tick=5),
            RemappedTransaction(original=incoming_record, new_arrival_tick=10),
        )

    def test_creates_with_valid_data(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """BootstrapSample can be created with valid data."""
        outgoing, incoming = sample_transactions
        sample = BootstrapSample(
            sample_idx=0,
            seed=12345,
            outgoing_transactions=(outgoing,),
            liquidity_beats=(incoming,),
            source_agent_id="BANK_A",
        )
        assert sample.sample_idx == 0
        assert sample.seed == 12345
        assert sample.source_agent_id == "BANK_A"

    def test_num_outgoing_counts_correctly(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """num_outgoing returns correct count."""
        outgoing, incoming = sample_transactions
        sample = BootstrapSample(
            sample_idx=0,
            seed=12345,
            outgoing_transactions=(outgoing,),
            liquidity_beats=(incoming,),
            source_agent_id="BANK_A",
        )
        assert sample.num_outgoing == 1
        assert sample.num_incoming == 1

    def test_total_outgoing_amount_sums_correctly(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """total_outgoing_amount sums all outgoing transaction amounts."""
        outgoing, incoming = sample_transactions
        sample = BootstrapSample(
            sample_idx=0,
            seed=12345,
            outgoing_transactions=(outgoing,),
            liquidity_beats=(incoming,),
            source_agent_id="BANK_A",
        )
        assert sample.total_outgoing_amount == 100_000
        assert sample.total_incoming_amount == 50_000

    def test_get_scenario_events_includes_all_transactions(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """get_scenario_events includes both outgoing and incoming."""
        outgoing, incoming = sample_transactions
        sample = BootstrapSample(
            sample_idx=0,
            seed=12345,
            outgoing_transactions=(outgoing,),
            liquidity_beats=(incoming,),
            source_agent_id="BANK_A",
        )
        events = sample.get_scenario_events()
        assert len(events) == 2
        tx_ids = {e["tx_id"] for e in events}
        assert tx_ids == {"TX001", "TX002"}

    def test_get_scenario_events_sorted_by_arrival_tick(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """get_scenario_events returns events sorted by arrival_tick."""
        outgoing, incoming = sample_transactions
        # outgoing has new_arrival_tick=5, incoming has new_arrival_tick=10
        sample = BootstrapSample(
            sample_idx=0,
            seed=12345,
            outgoing_transactions=(outgoing,),
            liquidity_beats=(incoming,),
            source_agent_id="BANK_A",
        )
        events = sample.get_scenario_events()
        assert events[0]["arrival_tick"] <= events[1]["arrival_tick"]

    def test_sample_idx_must_be_non_negative(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """BootstrapSample raises ValueError if sample_idx < 0."""
        outgoing, incoming = sample_transactions
        with pytest.raises(ValueError, match="sample_idx must be non-negative"):
            BootstrapSample(
                sample_idx=-1,
                seed=12345,
                outgoing_transactions=(outgoing,),
                liquidity_beats=(incoming,),
                source_agent_id="BANK_A",
            )

    def test_is_immutable(
        self, sample_transactions: tuple[RemappedTransaction, RemappedTransaction]
    ) -> None:
        """BootstrapSample is immutable (frozen dataclass)."""
        outgoing, incoming = sample_transactions
        sample = BootstrapSample(
            sample_idx=0,
            seed=12345,
            outgoing_transactions=(outgoing,),
            liquidity_beats=(incoming,),
            source_agent_id="BANK_A",
        )
        with pytest.raises(FrozenInstanceError):
            sample.seed = 99999  # Should raise
```

## Implementation Steps

### Step 1: Create Test File (RED)

1. Create directory: `api/tests/unit/ai_cash_mgmt/bootstrap/`
2. Create `__init__.py` files as needed
3. Create `test_models.py` with all tests above
4. Run tests - they should all FAIL (Red phase)

```bash
cd api
.venv/bin/python -m pytest tests/unit/ai_cash_mgmt/bootstrap/test_models.py -v
```

### Step 2: Create Models Module (GREEN)

1. Create `api/payment_simulator/ai_cash_mgmt/bootstrap/models.py`
2. Implement `TransactionRecord`, `RemappedTransaction`, `BootstrapSample`
3. Run tests - they should all PASS (Green phase)

### Step 3: Type Check and Lint (REFACTOR)

```bash
cd api
.venv/bin/python -m mypy payment_simulator/ai_cash_mgmt/bootstrap/models.py
.venv/bin/python -m ruff check payment_simulator/ai_cash_mgmt/bootstrap/models.py
.venv/bin/python -m ruff format payment_simulator/ai_cash_mgmt/bootstrap/models.py
```

### Step 4: Verify All Tests Pass

```bash
cd api
.venv/bin/python -m pytest tests/unit/ai_cash_mgmt/bootstrap/test_models.py -v
```

## Acceptance Criteria

- [ ] All tests pass
- [ ] mypy passes with no errors
- [ ] ruff passes with no errors
- [ ] TransactionRecord enforces int amount (INV-1)
- [ ] All dataclasses are frozen (immutable)
- [ ] RemappedTransaction preserves deadline_offset
- [ ] BootstrapSample generates valid scenario_events

## Definition of Done

Phase 1 is complete when:
1. All acceptance criteria are met
2. Code is committed to feature branch
3. Work notes updated with completion status

---

*Created: 2025-12-13*
*Last updated: 2025-12-13*
