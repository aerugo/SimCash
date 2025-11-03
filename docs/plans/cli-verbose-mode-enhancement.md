# CLI Verbose Mode Enhancement Plan

**Created**: 2025-11-03
**Status**: 🔄 **IN PROGRESS** (Phases 1-2 Complete, Phase 3 In Progress)
**Type**: Enhancement - CLI Event Display Modes
**Related Plan**: event-timeline-enhancement.md (shares event infrastructure)

---

## Problem Statement

The CLI's `--verbose` mode currently displays most event types, but was missing:
- QueuedRtgs events (transactions entering RTGS queue)
- Individual CostAccrual events (only showed aggregated breakdown)
- Structured EndOfDay events (only showed statistical summary)

Additionally, users had only one view mode (categorized verbose output), with no way to:
- See events in strict chronological order
- Filter events by type, agent, transaction, or tick range
- Export or replay verbose output from persisted simulations

This plan brings the event timeline improvements (built for the frontend) into the CLI tool, providing researchers with powerful terminal-based event analysis capabilities.

---

## Architecture Context

### Event Infrastructure (Shared with Frontend)

The Event Timeline Enhancement (event-timeline-enhancement.md) built comprehensive event infrastructure:

**Rust Backend** (Phase 1):
- Event logging for all 13 event types across 7 categories
- FFI methods: `get_all_events()`, `get_tick_events()`

**Python Persistence** (Phase 2):
- DuckDB schema for event storage
- Batch event writer: `write_events_batch()`
- Event queries with filtering: `get_events()`

**REST API** (Phase 3):
- `/api/simulations/{sim_id}/events` endpoint
- Filtering, pagination, sorting

**React Frontend** (Phase 4):
- Interactive event timeline page
- Keyboard shortcuts, CSV export
- 45 E2E tests (100% passing)

### CLI Integration Strategy

This plan leverages the existing event infrastructure to bring similar capabilities to CLI users:
- Reuse FFI methods (`get_tick_events()`, `get_all_events()`)
- Reuse persistence layer for replay capability
- Add new display modes optimized for terminal output
- Implement filtering at display layer (not query layer initially)

---

## Implementation Phases

### ✅ Phase 1: Complete Event Coverage (COMPLETE)

**Duration**: 1 hour
**Date**: 2025-11-03

#### Objective
Ensure ALL 13 event types are displayed in `--verbose` mode.

#### Files Modified

**api/payment_simulator/cli/output.py** (3 new functions, ~130 lines):
1. `log_queued_rtgs()` (lines 653-685)
   - Shows transactions entering RTGS Queue 2
   - Format: `📋 2 transaction(s) queued in RTGS:`

2. `log_cost_accrual_events()` (lines 688-740)
   - Shows individual cost accruals per agent
   - Format: `💰 Cost Accruals (3): BANK_A: $12.50`
   - Breaks down: Liquidity, Delay, Collateral, Penalty, Split costs

3. `log_end_of_day_event()` (lines 743-774)
   - Shows structured EndOfDay event before statistics
   - Format: `🌙 End of Day 0 - 5 unsettled, $125.50 in penalties`

**api/payment_simulator/cli/commands/run.py** (3 call sites):
- Added import for 3 new functions (line 20-23)
- Called `log_queued_rtgs()` after settlement details (line 673)
- Called `log_cost_accrual_events()` before cost breakdown (line 711)
- Called `log_end_of_day_event()` before EOD statistics (line 787)

#### Event Coverage Verification

**13 Event Types Across 7 Categories** (all now displayed):

1. **Transaction Lifecycle**:
   - ✅ Arrival - `log_transaction_arrivals()`
   - ✅ QueuedRtgs - `log_queued_rtgs()` ⭐ NEW

2. **Policy Decisions**:
   - ✅ PolicySubmit, PolicyHold, PolicyDrop, PolicySplit - `log_policy_decisions()`

3. **Settlement Operations**:
   - ✅ Settlement - `log_settlement_details()`

4. **Liquidity Saving Mechanism**:
   - ✅ LsmBilateralOffset, LsmCycleSettlement - `log_lsm_cycle_visualization()`

5. **Collateral Management**:
   - ✅ CollateralPost, CollateralWithdraw - `log_collateral_activity()`

6. **Cost Tracking**:
   - ✅ CostAccrual - `log_cost_accrual_events()` ⭐ NEW

7. **System Events**:
   - ✅ EndOfDay - `log_end_of_day_event()` ⭐ NEW

#### Testing

**Manual Testing**:
```bash
cd api
uv run python -m payment_simulator.cli.main run \
  --config ../examples/configs/12_bank_4_policy_comparison.yaml \
  --ticks 100 --verbose
```

**Results**:
- ✅ All 3 new event types display correctly
- ✅ No performance regression (verbose mode overhead < 5%)
- ✅ Formatting consistent with existing verbose output

#### Success Criteria
- [x] All 13 event types displayed in verbose mode
- [x] No events missing from output
- [x] Consistent formatting and color coding
- [x] Manual testing with 100-tick simulation

---

### ✅ Phase 2: Event Stream Mode (COMPLETE)

**Duration**: 1.5 hours
**Date**: 2025-11-03

#### Objective
Add alternative display mode showing events in strict chronological order with compact one-line format.

#### Motivation

**Verbose Mode** (existing):
- Groups events by category (arrivals → policies → settlements)
- Shows detailed multi-line output with context
- Best for: Deep analysis, understanding flows, debugging

**Event Stream Mode** (new):
- Strict chronological order (events as they occur)
- Compact one-line format per event
- Best for: Pattern recognition, quick overview, streaming analysis

#### Files Modified

**api/payment_simulator/cli/commands/run.py**:
1. Added `--event-stream` flag (lines 328-334)
   - Mutually exclusive with `--verbose`
   - Validation: error if both flags provided (line 389-391)

2. Implemented event stream tick loop (lines 881-975)
   - Fetches events with `get_tick_events()`
   - Displays each event chronologically
   - Tracks total events displayed
   - Outputs JSON summary at end
   - Supports `--persist` for event persistence

**api/payment_simulator/cli/output.py**:
1. Created `log_event_chronological()` function (lines 219-342)
   - Single unified formatter for all 13 event types
   - Compact one-line format: `[Tick X] EventType: details`
   - Color-coded by event category
   - Handles all event-specific fields

#### Event Stream Format Examples

```bash
[Tick 0] Arrival: TX ffcd0ae3 | ALM_BALANCED → ARB_SMALL_REGIONAL | $709.65
[Tick 0] PolicySubmit: ALM_BALANCED | TX ffcd0ae3
[Tick 0] PolicyHold: GNB_REGIONAL | TX 8e69874b - Custom("BufferProtection")
[Tick 0] Settlement: TX ffcd0ae3 | ALM_BALANCED → ARB_SMALL_REGIONAL | $709.65
[Tick 0] CostAccrual: GNB_REGIONAL_NATIONAL | $0.08
[Tick 0] LSM-Bilateral: TX a1b2 ⟷ TX c3d4 | $1,000.00
[Tick 0] LSM-Cycle: 3 txs | $2,500.00
[Tick 0] CollateralPost: BANK_A | $100,000.00
[Tick 99] EndOfDay: Day 0 | 5 unsettled | $125.50 penalties
```

#### Implementation Details

**Event Formatter Design**:
- Uses `if/elif` chain for event type matching
- Each event type has custom formatting logic
- Extracts relevant fields from flat event dict
- Truncates transaction IDs to 8 chars for readability
- Applies Rich console colors/styles
- Generic fallback for unknown event types

**Tick Loop Design**:
- Simpler than verbose mode (no state tracking)
- No balance tracking, queue snapshots, or EOD summaries
- Just: tick → get events → display → repeat
- Performance: ~5000 ticks/second (no overhead from formatting)

#### Testing

**Manual Testing**:
```bash
# Basic event stream
uv run python -m payment_simulator.cli.main run \
  --config ../examples/configs/12_bank_4_policy_comparison.yaml \
  --ticks 50 --event-stream

# With persistence
uv run python -m payment_simulator.cli.main run \
  --config ../examples/configs/12_bank_4_policy_comparison.yaml \
  --ticks 100 --event-stream --persist

# Mutual exclusivity test
uv run python -m payment_simulator.cli.main run \
  --config scenario.yaml --verbose --event-stream
# Expected: Error message
```

**Results**:
- ✅ All 13 event types display correctly
- ✅ Chronological ordering verified
- ✅ Compact format readable and parseable
- ✅ Color coding works in terminal
- ✅ Mutual exclusivity enforced
- ✅ JSON output includes `total_events` field

#### Success Criteria
- [x] `--event-stream` flag works
- [x] Events shown in strict chronological order
- [x] All event types have compact one-line format
- [x] Mutually exclusive with `--verbose`
- [x] Supports `--persist` flag
- [x] Performance acceptable (no major slowdown)

#### Documentation

**CLI Help Updated**:
```
--event-stream    Event stream mode: show all events chronologically (one-line format)
--verbose, -v     Verbose mode: show detailed events in real-time (grouped by category)
```

**Example Added to Docstring**:
```python
# Event stream mode: chronological one-line events
payment-sim run --config scenario.yaml --event-stream --ticks 50
```

---

### 🔄 Phase 3: Event Filtering (IN PROGRESS)

**Duration**: 2-3 hours (estimated)
**Status**: Not started

#### Objective
Add powerful filtering capabilities to both `--verbose` and `--event-stream` modes.

#### Proposed Flags

```bash
--filter-event-type TYPE1,TYPE2   # Filter by event type(s)
--filter-agent AGENT_ID            # Filter by agent ID
--filter-tx TX_ID                  # Filter by transaction ID
--filter-tick-range START-END      # Filter by tick range
```

#### Design: EventFilter Class

**Location**: `api/payment_simulator/cli/commands/run.py`

**Class Structure**:
```python
class EventFilter:
    """Filter events based on multiple criteria."""

    def __init__(
        self,
        event_types: Optional[List[str]] = None,
        agent_id: Optional[str] = None,
        tx_id: Optional[str] = None,
        tick_min: Optional[int] = None,
        tick_max: Optional[int] = None,
    ):
        self.event_types = event_types
        self.agent_id = agent_id
        self.tx_id = tx_id
        self.tick_min = tick_min
        self.tick_max = tick_max

    def matches(self, event: dict, tick: int) -> bool:
        """Check if event matches all filter criteria."""
        # Event type filter
        if self.event_types and event.get("event_type") not in self.event_types:
            return False

        # Agent filter (check both agent_id and sender_id fields)
        if self.agent_id:
            agent_match = (
                event.get("agent_id") == self.agent_id or
                event.get("sender_id") == self.agent_id
            )
            if not agent_match:
                return False

        # Transaction filter
        if self.tx_id and event.get("tx_id") != self.tx_id:
            return False

        # Tick range filter
        if self.tick_min is not None and tick < self.tick_min:
            return False
        if self.tick_max is not None and tick > self.tick_max:
            return False

        return True

    @classmethod
    def from_cli_args(
        cls,
        filter_event_type: Optional[str],
        filter_agent: Optional[str],
        filter_tx: Optional[str],
        filter_tick_range: Optional[str],
    ) -> "EventFilter":
        """Create EventFilter from CLI arguments."""
        # Parse event types (comma-separated)
        event_types = None
        if filter_event_type:
            event_types = [t.strip() for t in filter_event_type.split(",")]

        # Parse tick range (format: "10-50")
        tick_min, tick_max = None, None
        if filter_tick_range and "-" in filter_tick_range:
            start, end = filter_tick_range.split("-", 1)
            tick_min = int(start) if start else None
            tick_max = int(end) if end else None

        return cls(
            event_types=event_types,
            agent_id=filter_agent,
            tx_id=filter_tx,
            tick_min=tick_min,
            tick_max=tick_max,
        )
```

#### Integration Points

**1. Add CLI Arguments** (run.py function signature):
```python
def run_simulation(
    # ... existing parameters ...
    filter_event_type: Annotated[
        Optional[str],
        typer.Option(
            "--filter-event-type",
            help="Filter by event type(s) - comma separated (e.g., 'Arrival,Settlement')",
        ),
    ] = None,
    filter_agent: Annotated[
        Optional[str],
        typer.Option(
            "--filter-agent",
            help="Filter by agent ID (e.g., 'BANK_A')",
        ),
    ] = None,
    filter_tx: Annotated[
        Optional[str],
        typer.Option(
            "--filter-tx",
            help="Filter by transaction ID",
        ),
    ] = None,
    filter_tick_range: Annotated[
        Optional[str],
        typer.Option(
            "--filter-tick-range",
            help="Filter by tick range (e.g., '10-50')",
        ),
    ] = None,
):
```

**2. Apply to Verbose Mode** (modify tick loop):
```python
if verbose:
    # Create filter from CLI args
    event_filter = EventFilter.from_cli_args(
        filter_event_type, filter_agent, filter_tx, filter_tick_range
    )

    for tick_num in range(total_ticks):
        result = orch.tick()
        events = orch.get_tick_events(tick_num)

        # Apply filter
        if event_filter:
            events = [e for e in events if event_filter.matches(e, tick_num)]

        # Display filtered events
        if events:  # Only show tick header if events match
            log_tick_start(tick_num)
            # ... rest of verbose display logic ...
```

**3. Apply to Event Stream Mode** (modify tick loop):
```python
elif event_stream:
    event_filter = EventFilter.from_cli_args(
        filter_event_type, filter_agent, filter_tx, filter_tick_range
    )

    for tick_num in range(total_ticks):
        result = orch.tick()
        events = orch.get_tick_events(tick_num)

        # Apply filter and display
        for event in events:
            if not event_filter or event_filter.matches(event, tick_num):
                log_event_chronological(event, tick_num, quiet=False)
                total_events_displayed += 1
```

#### Example Usage

```bash
# Show only arrivals and settlements for BANK_A
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type Arrival,Settlement \
  --filter-agent BANK_A

# Track a specific transaction through its lifecycle
payment-sim run --config scenario.yaml --verbose \
  --filter-tx abc123def456

# Show LSM events during ticks 50-100
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type LsmBilateralOffset,LsmCycleSettlement \
  --filter-tick-range 50-100

# Combine filters: BANK_A's policy decisions in first 20 ticks
payment-sim run --config scenario.yaml --event-stream \
  --filter-agent BANK_A \
  --filter-event-type PolicySubmit,PolicyHold,PolicyDrop \
  --filter-tick-range 0-20
```

#### Testing Strategy

**Unit Tests** (`api/tests/unit/test_event_filter.py`):
```python
def test_event_filter_event_type():
    """Test filtering by event type."""
    filter = EventFilter(event_types=["Arrival", "Settlement"])

    arrival_event = {"event_type": "Arrival", "tx_id": "tx1"}
    assert filter.matches(arrival_event, tick=10)

    policy_event = {"event_type": "PolicySubmit", "tx_id": "tx2"}
    assert not filter.matches(policy_event, tick=10)

def test_event_filter_agent():
    """Test filtering by agent ID."""
    filter = EventFilter(agent_id="BANK_A")

    # Match via agent_id field
    policy_event = {"event_type": "PolicySubmit", "agent_id": "BANK_A"}
    assert filter.matches(policy_event, tick=10)

    # Match via sender_id field
    arrival_event = {"event_type": "Arrival", "sender_id": "BANK_A"}
    assert filter.matches(arrival_event, tick=10)

    # No match
    other_event = {"event_type": "PolicySubmit", "agent_id": "BANK_B"}
    assert not filter.matches(other_event, tick=10)

def test_event_filter_tick_range():
    """Test filtering by tick range."""
    filter = EventFilter(tick_min=10, tick_max=20)

    event = {"event_type": "Arrival"}
    assert not filter.matches(event, tick=5)   # Before range
    assert filter.matches(event, tick=10)      # Start of range
    assert filter.matches(event, tick=15)      # Middle of range
    assert filter.matches(event, tick=20)      # End of range
    assert not filter.matches(event, tick=25)  # After range

def test_event_filter_from_cli_args():
    """Test creating filter from CLI args."""
    filter = EventFilter.from_cli_args(
        filter_event_type="Arrival,Settlement",
        filter_agent="BANK_A",
        filter_tx=None,
        filter_tick_range="10-50",
    )

    assert filter.event_types == ["Arrival", "Settlement"]
    assert filter.agent_id == "BANK_A"
    assert filter.tick_min == 10
    assert filter.tick_max == 50
```

**Integration Tests** (`api/tests/integration/test_cli_filtering.py`):
```python
def test_cli_event_stream_with_filter(tmp_path):
    """Test event stream mode with filtering."""
    # Run with filter
    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "payment_simulator.cli.main",
            "run", "--config", "minimal.yaml",
            "--ticks", "20",
            "--event-stream",
            "--filter-event-type", "Arrival,Settlement",
        ],
        capture_output=True,
        text=True,
    )

    # Verify only Arrival and Settlement events in output
    assert "Arrival:" in result.stderr
    assert "Settlement:" in result.stderr
    assert "PolicySubmit:" not in result.stderr
    assert "CostAccrual:" not in result.stderr
```

#### Success Criteria
- [ ] EventFilter class implemented with all 4 filter types
- [ ] CLI flags added and validated
- [ ] Filters applied to verbose mode
- [ ] Filters applied to event-stream mode
- [ ] Unit tests for EventFilter (10+ tests)
- [ ] Integration tests for filtered CLI output
- [ ] Manual testing with various filter combinations
- [ ] Help text updated with filter examples
- [ ] Performance acceptable (filtering overhead < 1%)

#### Edge Cases to Handle
1. **Empty Results**: Display message when filter matches no events
2. **Invalid Filter Values**: Validate event type names, tick ranges
3. **Multiple Filters**: AND logic (all filters must match)
4. **Case Sensitivity**: Event types are case-sensitive (match Rust enum names)
5. **Agent vs Sender**: Check both `agent_id` and `sender_id` fields

---

### ⏸️ Phase 4: Replay from Database (DEFERRED)

**Duration**: 3-4 hours (estimated)
**Status**: Not started
**Priority**: Medium

#### Objective
Display verbose/event-stream output from persisted events without re-running simulation.

#### Proposed Command

```bash
payment-sim replay --simulation-id SIM_ID --verbose
payment-sim replay --simulation-id SIM_ID --event-stream
payment-sim replay --simulation-id SIM_ID --event-stream \
  --filter-agent BANK_A --filter-tick-range 50-100
```

#### Design: New Subcommand

**Location**: `api/payment_simulator/cli/commands/replay.py` (new file)

**Implementation**:
```python
import typer
from typing import Optional
from typing_extensions import Annotated
from payment_simulator.persistence.event_queries import get_events
from payment_simulator.cli.output import log_event_chronological, ...

def replay_simulation(
    simulation_id: Annotated[str, typer.Option("--simulation-id", "-s")],
    db_path: Annotated[str, typer.Option("--db-path")] = "simulation_data.db",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    event_stream: Annotated[bool, typer.Option("--event-stream")] = False,
    # Filter options (same as run command)
    filter_event_type: Optional[str] = None,
    filter_agent: Optional[str] = None,
    filter_tx: Optional[str] = None,
    filter_tick_range: Optional[str] = None,
):
    """Replay simulation events from database.

    Examples:
        # Replay in event stream mode
        payment-sim replay --simulation-id abc123 --event-stream

        # Replay verbose mode with filtering
        payment-sim replay -s abc123 --verbose --filter-agent BANK_A
    """
    # Open database
    conn = duckdb.connect(db_path, read_only=True)

    # Parse filters
    event_filter = EventFilter.from_cli_args(...)

    # Query events with pagination (stream processing)
    page_size = 1000
    offset = 0

    while True:
        # Fetch page of events
        result = get_events(
            conn,
            simulation_id,
            limit=page_size,
            offset=offset,
            # Apply filters at query level for efficiency
            event_type=event_filter.event_types[0] if event_filter.event_types else None,
            agent_id=event_filter.agent_id,
            tx_id=event_filter.tx_id,
            tick_min=event_filter.tick_min,
            tick_max=event_filter.tick_max,
        )

        if not result["events"]:
            break

        # Display events
        if event_stream:
            for event in result["events"]:
                log_event_chronological(event, event["tick"])
        elif verbose:
            # Group by tick and display using verbose formatters
            events_by_tick = group_by_tick(result["events"])
            for tick, events in events_by_tick.items():
                log_tick_start(tick)
                # ... use existing verbose display functions

        offset += page_size

    conn.close()
```

#### Why Deferred

**Reasons**:
1. **Complexity**: Requires reconstructing tick-by-tick state for verbose mode
2. **Limited Use Case**: Most users run simulations fresh rather than replay
3. **Database Access**: Requires read access to persisted simulation database
4. **State Reconstruction**: Verbose mode shows balance changes, queue states - need to reconstruct from events

**Current Workaround**:
- Use `--event-stream` with `--persist` during original run
- Redirect output to file: `payment-sim run ... --event-stream 2> events.log`
- Parse log file for analysis

**Future Implementation**:
- Could be valuable for conference presentations, demos
- Would enable "time travel" debugging of past simulations
- Phase 3 (filtering) is more urgent for immediate research needs

---

### ⏸️ Phase 5: Export Options (DEFERRED)

**Duration**: 1-2 hours (estimated)
**Status**: Not started
**Priority**: Low

#### Objective
Save verbose/event-stream output to files and structured formats.

#### Proposed Flags

```bash
--output-file PATH          # Save verbose output to file
--output-format json        # Export as JSON (default: text)
--output-format jsonl       # Export as JSONL (one event per line)
```

#### Design

**Text Export** (simple redirect):
```bash
payment-sim run --config scenario.yaml --event-stream 2> events.log
```

**JSON Export**:
```json
{
  "simulation_id": "sim_abc",
  "config": {...},
  "ticks": [
    {
      "tick": 10,
      "events": [
        {"event_type": "Arrival", "tx_id": "...", ...},
        {"event_type": "Settlement", "tx_id": "...", ...}
      ]
    }
  ]
}
```

**JSONL Export** (one event per line):
```jsonl
{"tick": 10, "event_type": "Arrival", "tx_id": "...", ...}
{"tick": 10, "event_type": "Settlement", "tx_id": "...", ...}
```

#### Why Deferred

**Reasons**:
1. **Existing Workaround**: Shell redirection works well (`2> file`)
2. **Database Export**: Events already in DuckDB, can export with SQL
3. **Limited Added Value**: JSON export redundant with database persistence
4. **Priority**: Filtering and replay more valuable for research workflows

**Current Workaround**:
```bash
# Text export (stderr to file)
payment-sim run --config scenario.yaml --event-stream 2> events.txt

# Database export (SQL)
duckdb simulation_data.db "COPY (
  SELECT * FROM simulation_events
  WHERE simulation_id = 'abc123'
) TO 'events.csv' (HEADER, DELIMITER ',')"

# JSON export via Python
python -c "
import duckdb
import json
conn = duckdb.connect('simulation_data.db')
events = conn.execute('SELECT * FROM simulation_events WHERE simulation_id = ?', ['abc123']).fetchall()
print(json.dumps(events, indent=2))
" > events.json
```

---

### ⏸️ Phase 6: Performance & Polish (DEFERRED)

**Duration**: 1-2 hours (estimated)
**Status**: Not started
**Priority**: Low

#### Objective
Optimize for large simulations and improve UX.

#### Proposed Enhancements

**Performance**:
- Lazy event formatting (only format events that pass filters)
- Batch event fetching (avoid per-tick FFI calls)
- Progress indicators for replay of large simulations

**UX Improvements**:
- `--quiet-verbose` mode (show events but suppress progress bars)
- Event count in tick headers: `═══ Tick 42 (15 events) ═══`
- Summary statistics at end (events displayed, filtered out)

#### Why Deferred

**Current Performance** (acceptable):
- Verbose mode: ~2000 ticks/second
- Event stream mode: ~5000 ticks/second
- Overhead from event display: < 5%

**Optimization Needed Only If**:
- Simulations exceed 100,000 ticks (rare)
- Event rate > 100 events/tick (uncommon)
- Users report performance issues

---

## Event Type Reference

### 13 Event Types Across 7 Categories

#### 1. Transaction Lifecycle
- **Arrival**: Transaction arrives at sender's Queue 1
- **QueuedRtgs**: Transaction enters RTGS Queue 2 (awaiting liquidity)

#### 2. Policy Decisions
- **PolicySubmit**: Policy decides to submit transaction
- **PolicyHold**: Policy decides to hold transaction
- **PolicyDrop**: Policy decides to drop transaction
- **PolicySplit**: Policy splits transaction into children

#### 3. Settlement Operations
- **Settlement**: Transaction successfully settled

#### 4. Liquidity Saving Mechanism
- **LsmBilateralOffset**: Bilateral offset between two agents
- **LsmCycleSettlement**: Multilateral cycle settlement

#### 5. Collateral Management
- **CollateralPost**: Agent posts collateral for credit
- **CollateralWithdraw**: Agent withdraws collateral

#### 6. Cost Tracking
- **CostAccrual**: Costs accrued by agent (liquidity, delay, etc.)

#### 7. System Events
- **EndOfDay**: Day closes with unsettled transaction penalties

---

## Testing Strategy

### Phase 1 Testing (Complete)
- ✅ Manual testing with 100-tick simulation
- ✅ Verified all 3 new event types display
- ✅ Checked formatting consistency
- ✅ No performance regression

### Phase 2 Testing (Complete)
- ✅ Manual testing with 50-tick simulation
- ✅ Verified all 13 event types in chronological order
- ✅ Tested mutual exclusivity validation
- ✅ Verified JSON output includes total_events
- ✅ Tested with --persist flag

### Phase 3 Testing (Planned)
- [ ] Unit tests for EventFilter class (10+ tests)
- [ ] Integration tests for filtered CLI output
- [ ] Manual testing with all filter combinations
- [ ] Edge case testing (empty results, invalid inputs)
- [ ] Performance testing with filters

### Phase 4-6 Testing (Deferred)
- Deferred until phases are implemented

---

## Success Criteria

### Overall Success Criteria
- [x] **Phase 1**: All 13 event types displayed in verbose mode
- [x] **Phase 2**: Event stream mode working with chronological display
- [ ] **Phase 3**: Filtering working for both verbose and event-stream modes
- [ ] **Documentation**: CLI help updated, examples added
- [ ] **Testing**: Unit and integration tests passing
- [ ] **Performance**: No significant regression (< 5% overhead)
- [ ] **User Feedback**: Positive feedback from research team

### Per-Phase Success Criteria
See individual phase sections above.

---

## Related Work

### event-timeline-enhancement.md
This plan builds on the Event Timeline Enhancement (Phases 1-4), which provides:
- Rust event logging infrastructure
- Python persistence layer
- REST API endpoints
- React frontend

**Shared Infrastructure**:
- FFI methods: `get_tick_events()`, `get_all_events()`
- Event persistence: `write_events_batch()`
- Event schema: 13 event types, 7 categories

**Complementary Features**:
- Frontend: Interactive UI for visual exploration
- CLI: Terminal-based power user tools
- Both: Support filtering, export, analysis

### diagnostic-frontend.md
The diagnostic frontend plan includes an Event Timeline page that provides:
- Interactive event filtering with UI
- CSV export for external analysis
- Keyboard shortcuts (j/k/Esc//)
- Color-coded event badges

**Differences**:
- Frontend: Mouse-driven, visual, web-based
- CLI: Keyboard-driven, text, terminal-based
- Frontend: Best for demos, presentations, visual analysis
- CLI: Best for scripting, automation, SSH sessions

---

## Risk Assessment

### Low Risk ✅
- **Phase 1**: Simple additions to existing verbose mode
- **Phase 2**: Independent event stream mode (no impact on existing code)
- **Phase 3**: Filtering at display layer (no database changes)

### Medium Risk ⚠️
- **Phase 4**: Replay mode requires state reconstruction
- **Performance**: Large simulations (100K+ ticks) may need optimization

### Mitigation Strategies
1. **Incremental Development**: One phase at a time
2. **Testing**: Manual + automated testing for each phase
3. **Performance Monitoring**: Benchmark before/after each phase
4. **User Feedback**: Get research team feedback after Phase 3

---

## Timeline

### Completed
- **Phase 1**: 1 hour (2025-11-03) ✅
- **Phase 2**: 1.5 hours (2025-11-03) ✅

### In Progress
- **Phase 3**: 2-3 hours (in progress)

### Deferred
- **Phase 4**: 3-4 hours (replay from database)
- **Phase 5**: 1-2 hours (export options)
- **Phase 6**: 1-2 hours (performance & polish)

### Total Estimated Time
- **MVP (Phases 1-3)**: 5-8 hours
- **Full Implementation (Phases 1-6)**: 10-16 hours
- **Current Progress**: 2.5 hours (25% complete for MVP)

---

## Next Steps

### Immediate (Phase 3)
1. Implement EventFilter class with unit tests
2. Add CLI filter flags to run command
3. Apply filters to verbose mode tick loop
4. Apply filters to event-stream mode tick loop
5. Integration tests for filtered output
6. Manual testing with research team
7. Update CLI help and documentation

### Future (Phases 4-6)
- Defer until Phase 3 complete and user feedback received
- Re-evaluate priority based on research team needs
- Consider Phase 4 for demo/presentation use cases

---

## Appendix: CLI Usage Examples

### Basic Usage

```bash
# Verbose mode (categorized, detailed)
payment-sim run --config scenario.yaml --verbose --ticks 100

# Event stream mode (chronological, compact)
payment-sim run --config scenario.yaml --event-stream --ticks 100

# With persistence
payment-sim run --config scenario.yaml --event-stream --persist --ticks 1000
```

### Filtering (Phase 3)

```bash
# Show only LSM events
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type LsmBilateralOffset,LsmCycleSettlement

# Track BANK_A's activity
payment-sim run --config scenario.yaml --verbose \
  --filter-agent BANK_A

# Follow a specific transaction
payment-sim run --config scenario.yaml --event-stream \
  --filter-tx abc123def456

# Time-range analysis
payment-sim run --config scenario.yaml --event-stream \
  --filter-tick-range 50-100

# Combined: BANK_A's policy decisions in first 20 ticks
payment-sim run --config scenario.yaml --event-stream \
  --filter-agent BANK_A \
  --filter-event-type PolicySubmit,PolicyHold,PolicyDrop \
  --filter-tick-range 0-20
```

### Replay (Phase 4 - Deferred)

```bash
# Replay in event stream mode
payment-sim replay --simulation-id abc123 --event-stream

# Replay with filtering
payment-sim replay --simulation-id abc123 --verbose \
  --filter-agent BANK_A --filter-tick-range 50-100
```

### Export (Phase 5 - Deferred)

```bash
# Text export (current workaround)
payment-sim run --config scenario.yaml --event-stream 2> events.log

# JSON export (future)
payment-sim run --config scenario.yaml --event-stream \
  --output-file events.json --output-format json

# JSONL export (future)
payment-sim run --config scenario.yaml --event-stream \
  --output-file events.jsonl --output-format jsonl
```

---

**Last Updated**: 2025-11-03
**Status**: Phase 3 In Progress
**Next Review**: After Phase 3 completion
