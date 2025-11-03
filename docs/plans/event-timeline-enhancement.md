# Event Timeline Enhancement Plan

**Created**: 2025-11-03
**Status**: ✅ **COMPLETE** (Phases 1-4.5 implemented, Phase 4.6 deferred)
**Type**: Enhancement - Comprehensive Event Stream
**Parent Plan**: diagnostic-frontend.md
**Completed**: 2025-11-03
**Implementation Summary**: See [event-persistence-implementation-summary.md](../event-persistence-implementation-summary.md)

---

## Problem Statement

The current diagnostic frontend plan conflates two distinct concepts:
1. **System-wide Event Timeline** - comprehensive stream of ALL events (transactions, collateral, LSM operations, policy decisions)
2. **Transaction Lifecycle** - event history for a single transaction

The Events Endpoint specification needs to be enhanced to properly support a comprehensive event timeline that shows the full system activity, similar to CLI `--verbose` mode.

### Key Issues Identified
- Event types not fully specified
- Event schemas incomplete
- No clear strategy for event persistence vs. reconstruction
- Frontend components not designed for diverse event types
- Missing critical event categories (LSM, policy decisions, balance operations)
- Inconsistent event naming between frontend and backend (e.g., `Pledge` vs `CollateralPosted`)
- Balance events should be consolidated as sub-events rather than top-level events

---

## Event Type Taxonomy

Based on the game concept document, we need to support these event categories:

### 1. Transaction Lifecycle Events

| Event Type | When It Occurs | Key Fields |
|------------|----------------|------------|
| `TransactionArrival` | Transaction arrives at sender's Queue 1 | tx_id, sender_id, receiver_id, amount, priority, deadline_tick |
| `TransactionSubmitted` | Transaction submitted from Queue 1 to Queue 2 (RTGS) | tx_id, sender_id, receiver_id, submission_tick |
| `TransactionSettled` | Transaction successfully settled | tx_id, settlement_tick, settlement_method (rtgs/lsm_bilateral/lsm_cycle) |
| `TransactionDropped` | Transaction dropped (deadline passed, rejected) | tx_id, drop_tick, drop_reason |
| `TransactionSplit` | Large transaction split into N children | parent_tx_id, child_tx_ids[], split_count, split_reason |

### 2. Queue Events

| Event Type | When It Occurs | Key Fields |
|------------|----------------|------------|
| `Queue1Hold` | Policy decides to hold transaction in Queue 1 | tx_id, agent_id, hold_reason (insufficient_liquidity, waiting_for_inflow, strategic_delay) |
| `Queue1Release` | Policy decides to release transaction to RTGS | tx_id, agent_id, release_tick |
| `Queue2Queued` | Transaction enters RTGS central queue (awaiting liquidity) | tx_id, queue_tick, reason (insufficient_balance) |
| `Queue2Released` | Transaction released from Queue 2 (settled via liquidity or LSM) | tx_id, release_tick, release_method |

### 3. Balance Events (Embedded in Parent Events)

**Note:** Balance changes are NOT standalone events. They are embedded within the events that cause them (e.g., `TransactionSettled`, `CollateralPosted`).

This design groups cause and effect together, making the timeline cleaner and more intuitive for researchers tracing fund flows.

**Balance details are included in the `details` block of parent events:**
- `TransactionSettled` → includes `debit_details` and `credit_details`
- `CollateralPosted` → includes `balance_before` and `balance_after`
- `LSMCycleSettled` → includes balance changes for all participants

### 4. Liquidity Management Events

| Event Type | When It Occurs | Key Fields |
|------------|----------------|------------|
| `CollateralPosted` | Agent posts collateral for intraday credit | agent_id, amount, collateral_before, collateral_after, reason (strategic, forced) |
| `CollateralReleased` | Agent releases collateral | agent_id, amount, collateral_before, collateral_after |
| `OverdraftDrawn` | Agent draws on overdraft facility | agent_id, amount, overdraft_before, overdraft_after |
| `OverdraftRepaid` | Agent repays overdraft | agent_id, amount, overdraft_before, overdraft_after |
| `CreditLimitAdjusted` | Agent's credit limit changes | agent_id, old_limit, new_limit, reason |

### 5. LSM/Optimization Events

| Event Type | When It Occurs | Key Fields |
|------------|----------------|------------|
| `LSMBilateralOffset` | Bilateral offset applied between two agents | agent_a, agent_b, offset_amount, tx_ids_settled[], liquidity_saved |
| `LSMCycleDetected` | Multilateral cycle detected | cycle_agents[], cycle_amount, tx_ids_in_cycle[] |
| `LSMCycleSettled` | Multilateral cycle settled | cycle_id, agents[], amount_settled, liquidity_saved, tx_ids_settled[] |
| `LSMBatchSettled` | Batch optimization applied | batch_size, total_amount, liquidity_used, tx_ids_settled[] |

### 6. Policy Decision Events

| Event Type | When It Occurs | Key Fields |
|------------|----------------|------------|
| `PolicyEvaluation` | Policy evaluates transaction | tx_id, agent_id, decision (hold/submit/split), decision_reason, policy_name |
| `PolicySplitDecision` | Policy decides to split transaction | tx_id, agent_id, split_factor, split_reason |
| `PolicyLiquidityDecision` | Policy decides on liquidity action | agent_id, action (draw/post/wait), amount, reason |

### 7. System Events

| Event Type | When It Occurs | Key Fields |
|------------|----------------|------------|
| `TickStart` | New tick begins | tick, day, time_of_day |
| `ThroughputSignal` | System publishes throughput metrics | tick, throughput_rate, queue2_pressure, system_liquidity |
| `DayEnd` | Day closes | day, total_settled, total_dropped, avg_delay, total_cost |
| `DeadlineWarning` | Transaction approaching deadline | tx_id, ticks_remaining, urgency_level |

---

## Event Schema Design

Each event follows this base structure:

```json
{
  "event_id": "evt_uuid",
  "simulation_id": "sim_uuid",
  "tick": 42,
  "day": 0,
  "event_type": "TransactionSettled",
  "timestamp": "2025-11-03T10:30:00Z",
  "details": { /* type-specific fields */ }
}
```

### Example Events

#### TransactionSettled Event (with Embedded Balance Changes)
```json
{
  "event_id": "evt_001",
  "simulation_id": "sim_abc",
  "tick": 42,
  "day": 0,
  "event_type": "TransactionSettled",
  "timestamp": "2025-11-03T10:30:00Z",
  "details": {
    "tx_id": "tx_123",
    "sender_id": "BANK_A",
    "receiver_id": "BANK_B",
    "amount": 100000,
    "settlement_method": "lsm_cycle",
    "settlement_delay_ticks": 15,
    "delay_cost": 150,
    "cycle_id": "cycle_xyz",
    "debit_details": {
      "agent_id": "BANK_A",
      "amount": 100000,
      "balance_before": 500000,
      "balance_after": 400000
    },
    "credit_details": {
      "agent_id": "BANK_B",
      "amount": 100000,
      "balance_before": 200000,
      "balance_after": 300000
    }
  }
}
```

**Note:** Balance changes are embedded within the settlement event, grouping cause and effect together for cleaner timeline visualization.

#### CollateralPosted Event
```json
{
  "event_id": "evt_002",
  "simulation_id": "sim_abc",
  "tick": 35,
  "day": 0,
  "event_type": "CollateralPosted",
  "timestamp": "2025-11-03T10:29:45Z",
  "details": {
    "agent_id": "BANK_A",
    "amount": 500000,
    "collateral_before": 0,
    "collateral_after": 500000,
    "balance_before": 4500000,
    "reason": "strategic",
    "triggered_by_tx": "tx_123"
  }
}
```

#### LSMCycleSettled Event
```json
{
  "event_id": "evt_003",
  "simulation_id": "sim_abc",
  "tick": 42,
  "day": 0,
  "event_type": "LSMCycleSettled",
  "timestamp": "2025-11-03T10:30:00Z",
  "details": {
    "cycle_id": "cycle_xyz",
    "cycle_agents": ["BANK_A", "BANK_B", "BANK_C", "BANK_D"],
    "amount_settled": 50000,
    "liquidity_saved": 150000,
    "tx_ids_settled": ["tx_123", "tx_456", "tx_789", "tx_012"],
    "cycle_path": "BANK_A→BANK_B→BANK_C→BANK_D→BANK_A"
  }
}
```

#### PolicyEvaluation Event
```json
{
  "event_id": "evt_004",
  "simulation_id": "sim_abc",
  "tick": 11,
  "day": 0,
  "event_type": "PolicyEvaluation",
  "timestamp": "2025-11-03T10:30:01Z",
  "details": {
    "tx_id": "tx_123",
    "agent_id": "BANK_A",
    "decision": "hold",
    "decision_reason": "insufficient_liquidity",
    "policy_name": "adaptive_liquidity_manager",
    "queue1_depth": 15,
    "available_balance": 3000000,
    "required_amount": 100000
  }
}
```

---

## Implementation Strategy

### Option 1: Persist Events During Simulation (RECOMMENDED)

**Approach:** Add a `simulation_events` table that captures all events as they occur during simulation execution.

**Advantages:**
- ✅ Fast queries (direct table read)
- ✅ Complete event history preserved
- ✅ Easy filtering and pagination
- ✅ Supports real-time streaming (future feature)
- ✅ No complex query reconstruction logic

**Disadvantages:**
- ❌ Requires backend changes
- ❌ Increases storage requirements (~10-20% more DB space)
- ❌ Needs careful performance optimization (batch writes)

**Database Schema:**
```sql
CREATE TABLE simulation_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_id UUID NOT NULL REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    tick INTEGER NOT NULL,
    day INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    details JSONB NOT NULL,
    
    -- Indexed fields for fast filtering
    agent_id VARCHAR(50),  -- NULL for system events
    tx_id VARCHAR(100),     -- NULL for non-tx events
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT check_tick_positive CHECK (tick >= 0),
    CONSTRAINT check_day_positive CHECK (day >= 0)
);

-- Indexes for common query patterns
CREATE INDEX idx_sim_events_sim_tick ON simulation_events(simulation_id, tick);
CREATE INDEX idx_sim_events_sim_agent ON simulation_events(simulation_id, agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_sim_events_sim_tx ON simulation_events(simulation_id, tx_id) WHERE tx_id IS NOT NULL;
CREATE INDEX idx_sim_events_sim_type ON simulation_events(simulation_id, event_type);
CREATE INDEX idx_sim_events_sim_day ON simulation_events(simulation_id, day);

-- Composite index for common filters
CREATE INDEX idx_sim_events_composite ON simulation_events(simulation_id, tick, event_type);
```

**Backend Changes Required:**
1. Define event types and schemas in Rust
2. Create `EventEmitter` trait
3. Instrument key points in simulation:
   - Transaction arrivals → `TransactionArrival`
   - Policy decisions → `PolicyEvaluation`, `Queue1Hold`, `Queue1Release`
   - Submissions → `TransactionSubmitted`, `Queue2Queued`
   - Settlement operations → `TransactionSettled`, `BalanceDebited`, `BalanceCredited`
   - Collateral operations → `CollateralPosted`, `CollateralReleased`
   - LSM operations → `LSMBilateralOffset`, `LSMCycleSettled`
   - System ticks → `TickStart`, `ThroughputSignal`
4. Buffer events and batch-write to database
5. Test performance impact

**Performance Considerations:**
- Batch insert events every N ticks (e.g., every 10 ticks)
- Use prepared statements
- Consider async writes if simulation performance degrades
- Target: < 5% performance impact on simulation execution

**Estimated Effort:** 
- Backend (Rust): 3-4 days
- Database migration: 0.5 day
- Performance testing: 0.5 day
- **Total: 4-5 days**

### Option 2: Reconstruct Events from Existing Tables (NOT RECOMMENDED)

**Approach:** Query transactions, collateral_events, lsm_cycles, and policy_snapshots tables and reconstruct timeline.

**Advantages:**
- ✅ No changes to simulation engine
- ✅ Works with existing data

**Disadvantages:**
- ❌ Complex queries (UNION across multiple tables)
- ❌ Slower performance (multiple table joins)
- ❌ Incomplete event history (missing policy decisions, queue events)
- ❌ Harder to maintain and extend
- ❌ Cannot support real-time streaming
- ❌ Inconsistent event ordering

**Decision:** NOT recommended for production. Could be used as temporary interim solution during backend development.

---

## Updated API Endpoint Specification

### API Design Decisions

**Separate Summary Endpoint:** To avoid slowing down paginated event requests with aggregation queries, metadata is retrieved from a separate, cacheable endpoint:
- `GET /api/simulations/{sim_id}/events` - Returns paginated events only
- `GET /api/simulations/{sim_id}/events/summary` - Returns metadata (total counts, event type distribution)

**Comprehensive Agent Filtering:** The `agent_id` parameter performs deep search across both top-level `agent_id` field AND JSONB `details` fields (sender_id, receiver_id, cycle_agents arrays), ensuring all events involving an agent are found.

**Event Expansion:** The `expand=all` parameter enables the API to group related events (e.g., balance changes under settlement events), simplifying frontend logic and improving UX.

### Enhanced Events Endpoint

```
GET /api/simulations/{sim_id}/events
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tick` | integer | No | - | Exact tick filter |
| `tick_min` | integer | No | - | Minimum tick (inclusive) |
| `tick_max` | integer | No | - | Maximum tick (inclusive) |
| `day` | integer | No | - | Filter by specific day |
| `agent_id` | string | No | - | Filter by agent (comprehensive search: top-level agent_id OR within JSONB details fields like sender_id, receiver_id, cycle_agents) |
| `tx_id` | string | No | - | Filter by transaction ID |
| `event_type` | string | No | - | Filter by event type (comma-separated for multiple) |
| `event_category` | string | No | - | Filter by category: transaction, queue, balance, liquidity, lsm, policy, system |
| `expand` | string | No | - | Expand sub-events: `all` returns primary events with nested sub_events array populated |
| `limit` | integer | No | 100 | Number of events per page (max: 1000) |
| `offset` | integer | No | 0 | Pagination offset |
| `sort` | string | No | tick_asc | Sort order: tick_asc, tick_desc |

**Response Schema:**
```json
{
  "events": [
    {
      "event_id": "evt_uuid",
      "simulation_id": "sim_uuid",
      "tick": 42,
      "day": 0,
      "event_type": "TransactionSettled",
      "timestamp": "2025-11-03T10:30:00Z",
      "details": {
        // Event-type-specific fields
      }
    }
  ],
  "total": 15420,
  "limit": 100,
  "offset": 0,
  "filters": {
    "tick_min": null,
    "tick_max": null,
    "agent_id": null,
    "event_type": null,
    "event_category": null
  },
  "simulation_summary": {
    "total_ticks": 500,
    "total_days": 5,
    "event_type_counts": {
      "TransactionArrival": 5420,
      "TransactionSettled": 5200,
      "CollateralPosted": 250
      // ... etc
    }
  }
}
```

**Example Requests:**

```bash
# Get all events for tick 42
GET /api/simulations/abc123/events?tick=42

# Get events in tick range 40-50
GET /api/simulations/abc123/events?tick_min=40&tick_max=50

# Get all events involving BANK_A
GET /api/simulations/abc123/events?agent_id=BANK_A

# Get all LSM events
GET /api/simulations/abc123/events?event_category=lsm

# Get specific event types
GET /api/simulations/abc123/events?event_type=TransactionSettled,TransactionDropped

# Get events for specific transaction
GET /api/simulations/abc123/events?tx_id=tx_123

# Paginated results
GET /api/simulations/abc123/events?limit=50&offset=100
```

**Error Responses:**

```json
// 404 - Simulation not found
{
  "error": "SimulationNotFound",
  "message": "Simulation with id 'abc123' not found"
}

// 400 - Invalid parameters
{
  "error": "InvalidParameters",
  "message": "tick_min cannot be greater than tick_max"
}
```

---

## Frontend Component Architecture

### Component Hierarchy

```
EventTimelinePage
├── EventFilters
│   ├── TickRangeSlider
│   ├── AgentSelector
│   ├── EventCategorySelector
│   ├── EventTypeSelector
│   └── TransactionSearchInput
├── EventStats (summary bar)
├── EventList (virtualized)
│   └── EventCard (polymorphic by type)
│       ├── TransactionArrivalCard
│       ├── TransactionSettledCard
│       ├── CollateralPostedCard
│       ├── LSMCycleSettledCard
│       ├── PolicyEvaluationCard
│       └── ... (one per event type)
└── EventPagination
```

### EventCard Component Design

```typescript
// src/components/events/EventCard.tsx
import { SimulationEvent } from '@/types/events';
import { TransactionArrivalCard } from './cards/TransactionArrivalCard';
import { CollateralPostedCard } from './cards/CollateralPostedCard';
import { LSMCycleSettledCard } from './cards/LSMCycleSettledCard';
// ... import all card types

interface EventCardProps {
  event: SimulationEvent;
  onTransactionClick?: (txId: string) => void;
  onAgentClick?: (agentId: string) => void;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export function EventCard({ 
  event, 
  onTransactionClick, 
  onAgentClick,
  isExpanded = false,
  onToggleExpand
}: EventCardProps) {
  // Render based on event_type
  const CardComponent = getCardComponent(event.event_type);
  
  return (
    <div className="event-card" data-event-type={event.event_type}>
      <CardComponent
        event={event}
        onTransactionClick={onTransactionClick}
        onAgentClick={onAgentClick}
        isExpanded={isExpanded}
        onToggleExpand={onToggleExpand}
      />
    </div>
  );
}

function getCardComponent(eventType: string) {
  switch (eventType) {
    case 'TransactionArrival':
      return TransactionArrivalCard;
    case 'TransactionSettled':
      return TransactionSettledCard;
    case 'CollateralPosted':
      return CollateralPostedCard;
    case 'LSMCycleSettled':
      return LSMCycleSettledCard;
    case 'PolicyEvaluation':
      return PolicyEvaluationCard;
    // ... etc
    default:
      return GenericEventCard;
  }
}
```

### EventFilters Component

```typescript
// src/components/events/EventFilters.tsx
interface EventFiltersProps {
  filters: EventFilters;
  onFiltersChange: (filters: EventFilters) => void;
  simulationMetadata: {
    totalTicks: number;
    totalDays: number;
    agents: string[];
  };
}

interface EventFilters {
  tickMin?: number;
  tickMax?: number;
  day?: number;
  agentId?: string;
  txId?: string;
  eventCategory?: 'transaction' | 'queue' | 'balance' | 'liquidity' | 'lsm' | 'policy' | 'system' | 'all';
  eventType?: string;
}

export function EventFilters({ filters, onFiltersChange, simulationMetadata }: EventFiltersProps) {
  return (
    <div className="event-filters">
      <TickRangeSlider
        min={0}
        max={simulationMetadata.totalTicks}
        value={[filters.tickMin || 0, filters.tickMax || simulationMetadata.totalTicks]}
        onChange={([min, max]) => onFiltersChange({ ...filters, tickMin: min, tickMax: max })}
      />
      
      <Select
        label="Event Category"
        value={filters.eventCategory || 'all'}
        onChange={(category) => onFiltersChange({ ...filters, eventCategory: category })}
        options={[
          { value: 'all', label: 'All Events' },
          { value: 'transaction', label: 'Transactions' },
          { value: 'liquidity', label: 'Liquidity' },
          { value: 'lsm', label: 'LSM Operations' },
          { value: 'policy', label: 'Policy Decisions' },
          { value: 'system', label: 'System Events' }
        ]}
      />
      
      <Select
        label="Agent"
        value={filters.agentId || 'all'}
        onChange={(agentId) => onFiltersChange({ ...filters, agentId })}
        options={[
          { value: 'all', label: 'All Agents' },
          ...simulationMetadata.agents.map(a => ({ value: a, label: a }))
        ]}
      />
      
      <Input
        label="Transaction ID"
        placeholder="Search by tx_id..."
        value={filters.txId || ''}
        onChange={(txId) => onFiltersChange({ ...filters, txId })}
      />
    </div>
  );
}
```

### Event Timeline Page Layout

```
┌─────────────────────────────────────────────────────────┐
│  Event Timeline - Simulation abc123                      │
├─────────────────────────────────────────────────────────┤
│  Filters:                                                │
│  [Tick Range: 0━━━━━━━━●━━━━━━━500]                     │
│  [Category: All ▼] [Agent: All ▼] [TX: _______]        │
│                                                          │
│  📊 15,420 events | 🔄 5,420 transactions | 💰 250 LSM  │
│  [Export CSV]                                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ Tick 10 · Day 0 · 10:30:00 ──────────────────────┐ │
│  │ 🔵 TransactionArrival                              │ │
│  │    tx_123: BANK_A → BANK_B  $1,000.00             │ │
│  │    Priority: 8  Deadline: Tick 50                 │ │
│  │    [View Transaction →]                            │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Tick 11 · Day 0 · 10:30:01 ──────────────────────┐ │
│  │ 🟡 PolicyEvaluation                                │ │
│  │    BANK_A evaluated tx_123 → HOLD                  │ │
│  │    Reason: Insufficient liquidity                  │ │
│  │    Policy: adaptive_liquidity_manager              │ │
│  │    Queue depth: 15  Available: $30,000.00         │ │
│  │    [View Agent →] [View Transaction →]            │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Tick 15 · Day 0 · 10:30:05 ──────────────────────┐ │
│  │ 💰 CollateralPosted                                │ │
│  │    BANK_A posted $5,000.00 collateral              │ │
│  │    Before: $0.00 → After: $5,000.00               │ │
│  │    Reason: Strategic positioning                   │ │
│  │    Triggered by: tx_123                            │ │
│  │    [View Agent →]                                  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ Tick 25 · Day 0 · 10:30:15 ──────────────────────┐ │
│  │ ⚙️  LSMCycleSettled                                 │ │
│  │    4-agent cycle: BANK_A→BANK_B→BANK_C→BANK_D→A   │ │
│  │    Amount: $50,000  Liquidity saved: $150,000     │ │
│  │    Transactions: tx_123, tx_456, tx_789, tx_012   │ │
│  │    [+ Show 4 events] ▼                             │ │
│  │    ├─ ✅ TransactionSettled: tx_123                │ │
│  │    ├─ 📤 BalanceDebited: BANK_A -$1,000.00        │ │
│  │    ├─ 📥 BalanceCredited: BANK_B +$1,000.00       │ │
│  │    └─ ... (show all)                               │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  [Load More...]  Page 1 of 155                          │
└─────────────────────────────────────────────────────────┘
```

### Frontend Implementation Details

**URL State Management:**
Filter criteria (tick range, agent, event type, etc.) are stored in URL query parameters using React Router's `useSearchParams` hook. This enables:
- Shareable links to specific filtered views (critical for researchers)
- Browser back/forward navigation through filter states
- Bookmarkable event timeline views

**Pagination Strategy:**
Standard pagination (vs. infinite scroll) is used for the event timeline because:
- Provides stable, referenceable context ("see page 5 of results")
- Enables precise navigation to specific result ranges
- Better suited for research/analysis workflows
- Allows users to bookmark specific pages of results

**View Density Toggle:**
A "Compact View" toggle switches between:
- **Default View**: Spacious cards with full details, optimized for readability
- **Compact View**: Dense table layout showing more events per screen, optimized for scanning large datasets

**Loading States:**
Skeleton loaders (using shadcn/ui Skeleton component) are used instead of generic "Loading..." text. Skeleton loaders:
- Mimic the final layout of event cards
- Provide visual feedback of content structure
- Make the application feel faster and more polished
- Reduce perceived loading time

**Data Scope:**
This event timeline feature applies **only to simulations run after implementation**. No backfilling of event data for older simulations will be performed. The architecture allows for future backfilling if needed, but it is out of scope for initial release.

**Deprecation Notice:**
The current `/events` endpoint in `api/payment_simulator/api/main.py` that reconstructs events on-the-fly will be **deprecated and removed** once the new persistence-based system is implemented and verified. A migration period with both endpoints available may be considered.

---

## Implementation Phases

### Phase 1: Backend Event Infrastructure ⭐ PRIORITY

**Goal:** Add event persistence to simulation engine

**Tasks:**

#### 1.1: Define Event Types in Rust
**File:** `backend/src/models/events.rs`

```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationEvent {
    pub event_id: Uuid,
    pub simulation_id: Uuid,
    pub tick: u32,
    pub day: u32,
    pub event_type: EventType,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub details: serde_json::Value,
    pub agent_id: Option<String>,
    pub tx_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum EventType {
    TransactionArrival,
    TransactionSubmitted,
    TransactionSettled,
    TransactionDropped,
    CollateralPosted,
    LSMCycleSettled,
    PolicyEvaluation,
    // ... etc
}
```

#### 1.2: Create Database Migration
**File:** `api/migrations/003_add_simulation_events.sql`

```sql
CREATE TABLE simulation_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_id UUID NOT NULL REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    tick INTEGER NOT NULL,
    day INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    details JSONB NOT NULL,
    agent_id VARCHAR(50),
    tx_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT check_tick_positive CHECK (tick >= 0),
    CONSTRAINT check_day_positive CHECK (day >= 0)
);

CREATE INDEX idx_sim_events_sim_tick ON simulation_events(simulation_id, tick);
CREATE INDEX idx_sim_events_sim_agent ON simulation_events(simulation_id, agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_sim_events_sim_tx ON simulation_events(simulation_id, tx_id) WHERE tx_id IS NOT NULL;
CREATE INDEX idx_sim_events_sim_type ON simulation_events(simulation_id, event_type);
CREATE INDEX idx_sim_events_sim_day ON simulation_events(simulation_id, day);
CREATE INDEX idx_sim_events_composite ON simulation_events(simulation_id, tick, event_type);
```

#### 1.3: Implement EventEmitter Trait
**File:** `backend/src/orchestrator/event_emitter.rs`

```rust
pub trait EventEmitter {
    fn emit_transaction_arrival(&mut self, tx: &Transaction, tick: u32, day: u32);
    fn emit_transaction_submitted(&mut self, tx_id: &str, agent_id: &str, tick: u32, day: u32);
    fn emit_transaction_settled(&mut self, tx: &Transaction, method: SettlementMethod, tick: u32, day: u32);
    fn emit_collateral_posted(&mut self, agent_id: &str, amount: i64, tick: u32, day: u32);
    fn emit_lsm_cycle_settled(&mut self, cycle: &LSMCycle, tick: u32, day: u32);
    fn emit_policy_evaluation(&mut self, tx_id: &str, agent_id: &str, decision: &PolicyDecision, tick: u32, day: u32);
}
```

#### 1.4: Instrument Key Points
Locations to add event emission:
- `backend/src/arrivals/generator.rs` → TransactionArrival
- `backend/src/policy/engine.rs` → PolicyEvaluation
- `backend/src/orchestrator/mod.rs` → TransactionSubmitted, queue events
- `backend/src/settlement/engine.rs` → TransactionSettled, balance events
- `backend/src/models/agent.rs` → CollateralPosted, collateral events
- `backend/src/settlement/lsm.rs` → LSM events

#### 1.5: Add Batch Event Writer
**File:** `api/payment_simulator/persistence/event_writer.rs`

```python
class EventWriter:
    def __init__(self, connection):
        self.connection = connection
        self.buffer = []
        self.batch_size = 1000
    
    def add_event(self, event: SimulationEvent):
        self.buffer.append(event)
        if len(self.buffer) >= self.batch_size:
            self.flush()
    
    def flush(self):
        if not self.buffer:
            return
        
        # Batch insert
        cursor = self.connection.cursor()
        cursor.executemany(
            """
            INSERT INTO simulation_events 
            (simulation_id, tick, day, event_type, details, agent_id, tx_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [(e.simulation_id, e.tick, e.day, e.event_type, 
              json.dumps(e.details), e.agent_id, e.tx_id) 
             for e in self.buffer]
        )
        self.connection.commit()
        self.buffer.clear()
```

**Estimated Time:** 3-4 days

**Acceptance Criteria:**
- ✅ All event types defined in Rust
- ✅ Database migration created and tested
- ✅ EventEmitter trait implemented
- ✅ All key simulation points instrumented
- ✅ Batch event writer implemented
- ✅ Events persisted to database during simulation
- ✅ Performance impact < 5%
- ✅ Integration tests pass

---

### Phase 2: API Endpoint Implementation

**Goal:** Implement enhanced events endpoint with filtering and pagination

**Tasks:**

#### 2.1: Create API Route
**File:** `api/payment_simulator/api/routes/events.py`

```python
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from uuid import UUID

router = APIRouter()

@router.get("/simulations/{sim_id}/events")
async def get_simulation_events(
    sim_id: UUID,
    tick: Optional[int] = None,
    tick_min: Optional[int] = None,
    tick_max: Optional[int] = None,
    day: Optional[int] = None,
    agent_id: Optional[str] = None,
    tx_id: Optional[str] = None,
    event_type: Optional[str] = None,
    event_category: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query("tick_asc", regex="^(tick_asc|tick_desc)$")
):
    """
    Get paginated, filterable event timeline for a simulation.
    """
    # Implementation
    pass
```

#### 2.2: Implement Query Logic
**File:** `api/payment_simulator/persistence/event_queries.py`

```python
from typing import Optional, List, Dict, Any
from uuid import UUID

def get_events(
    connection,
    simulation_id: UUID,
    tick: Optional[int] = None,
    tick_min: Optional[int] = None,
    tick_max: Optional[int] = None,
    day: Optional[int] = None,
    agent_id: Optional[str] = None,
    tx_id: Optional[str] = None,
    event_type: Optional[str] = None,
    event_category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "tick_asc"
) -> Dict[str, Any]:
    """
    Query simulation events with filters and pagination.
    """
    # Build dynamic query
    query = """
        SELECT event_id, simulation_id, tick, day, event_type, 
               event_timestamp, details, agent_id, tx_id
        FROM simulation_events
        WHERE simulation_id = %s
    """
    params = [simulation_id]
    
    # Add filters
    if tick is not None:
        query += " AND tick = %s"
        params.append(tick)
    if tick_min is not None:
        query += " AND tick >= %s"
        params.append(tick_min)
    if tick_max is not None:
        query += " AND tick <= %s"
        params.append(tick_max)
    # ... etc
    
    # Add sorting and pagination
    order = "ASC" if sort == "tick_asc" else "DESC"
    query += f" ORDER BY tick {order}, event_timestamp {order}"
    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    # Execute query
    cursor = connection.cursor()
    cursor.execute(query, params)
    events = cursor.fetchall()
    
    # Get total count
    count_query = "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = %s"
    cursor.execute(count_query, [simulation_id])
    total = cursor.fetchone()[0]
    
    return {
        "events": [format_event(e) for e in events],
        "total": total,
        "limit": limit,
        "offset": offset
    }
```

#### 2.3: Write Integration Tests
**File:** `api/tests/integration/test_event_timeline_api.py`

```python
def test_get_events_basic(client, sample_simulation_with_events):
    response = client.get(f"/simulations/{sample_simulation_with_events.id}/events")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert data["total"] > 0

def test_get_events_with_tick_filter(client, sample_simulation_with_events):
    response = client.get(
        f"/simulations/{sample_simulation_with_events.id}/events",
        params={"tick": 10}
    )
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        assert event["tick"] == 10

def test_get_events_with_agent_filter(client, sample_simulation_with_events):
    response = client.get(
        f"/simulations/{sample_simulation_with_events.id}/events",
        params={"agent_id": "BANK_A"}
    )
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        assert event.get("agent_id") == "BANK_A" or "BANK_A" in str(event["details"])
```

**Estimated Time:** 1-2 days

**Acceptance Criteria:**
- ✅ API endpoint implemented
- ✅ All query filters work correctly
- ✅ Pagination works correctly
- ✅ Response includes event counts by type
- ✅ Error handling (404, 400) implemented
- ✅ Integration tests pass
- ✅ API documentation updated

---

### Phase 3: Frontend Event Timeline Page

**Goal:** Build comprehensive event timeline UI with filtering and navigation

**Tasks:**

#### 3.1: Create Event Type Definitions
**File:** `frontend/diagnostic/src/types/events.ts`

```typescript
export interface SimulationEvent {
  event_id: string;
  simulation_id: string;
  tick: number;
  day: number;
  event_type: EventType;
  timestamp: string;
  details: Record<string, any>;
  agent_id?: string;
  tx_id?: string;
}

export type EventType = 
  | 'TransactionArrival'
  | 'TransactionSubmitted'
  | 'TransactionSettled'
  | 'TransactionDropped'
  | 'CollateralPosted'
  | 'LSMCycleSettled'
  | 'PolicyEvaluation'
  // ... etc

export type EventCategory = 
  | 'transaction'
  | 'queue'
  | 'balance'
  | 'liquidity'
  | 'lsm'
  | 'policy'
  | 'system'
  | 'all';
```

#### 3.2: Create API Hook
**File:** `frontend/diagnostic/src/hooks/useEvents.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchEvents } from '@/api/events';

export function useEvents(
  simulationId: string,
  filters: EventFilters,
  options?: UseQueryOptions
) {
  return useQuery({
    queryKey: ['events', simulationId, filters],
    queryFn: () => fetchEvents(simulationId, filters),
    ...options
  });
}
```

#### 3.3: Implement EventCard Components
Create individual card components for each event type:
- `TransactionArrivalCard.tsx`
- `TransactionSettledCard.tsx`
- `CollateralPostedCard.tsx`
- `LSMCycleSettledCard.tsx`
- `PolicyEvaluationCard.tsx`
- etc.

Each component should render event-specific information clearly and provide navigation links.

#### 3.4: Implement EventFilters Component
**File:** `frontend/diagnostic/src/components/events/EventFilters.tsx`

With interactive controls for:
- Tick range slider
- Event category dropdown
- Agent selector
- Transaction ID search
- Clear filters button

#### 3.5: Implement EventTimelinePage
**File:** `frontend/diagnostic/src/pages/EventTimelinePage.tsx`

Main page component that:
- Manages filter state
- Fetches events using useEvents hook
- Renders EventFilters component
- Renders virtualized EventList
- Handles pagination
- Updates URL query params on filter change

#### 3.6: Add Route
**File:** `frontend/diagnostic/src/App.tsx`

```typescript
<Route path="/simulations/:simId/events" element={<EventTimelinePage />} />
```

**Estimated Time:** 3-4 days

**Acceptance Criteria:**
- ✅ EventTimelinePage renders correctly
- ✅ All event types display properly
- ✅ Filters work and update results
- ✅ Pagination works smoothly
- ✅ Links to transactions/agents work
- ✅ Virtualized scrolling performs well
- ✅ URL query params sync with filters
- ✅ Component tests pass

---

### Phase 4: Polish & Testing

**Goal:** Refine UX, add features, and ensure quality

**Tasks:**

#### 4.1: Event Type Legend
Add legend/help overlay explaining each event type with icons and descriptions.

#### 4.2: Color Coding
Apply consistent color scheme by event category:
- 🔵 Blue: Transaction events
- 🟡 Yellow: Queue events
- 💰 Green: Balance/liquidity events
- ⚙️ Purple: LSM operations
- 🟠 Orange: Policy decisions
- ⚪ Gray: System events

#### 4.3: Export to CSV
Implement CSV export functionality for filtered events.

#### 4.4: Keyboard Shortcuts
Add keyboard navigation:
- `j/k`: Navigate up/down through events
- `/`: Focus search/filter
- `Esc`: Clear filters

#### 4.5: E2E Tests
**File:** `frontend/diagnostic/tests/e2e/event-timeline.spec.ts`

```typescript
test('filters events by tick range', async ({ page }) => {
  await page.goto('/simulations/test-sim/events');
  
  // Set tick range
  await page.locator('[data-testid="tick-range-min"]').fill('10');
  await page.locator('[data-testid="tick-range-max"]').fill('50');
  
  // Verify filtered results
  const events = page.locator('[data-testid="event-card"]');
  const count = await events.count();
  
  for (let i = 0; i < count; i++) {
    const tick = await events.nth(i).getAttribute('data-tick');
    expect(Number(tick)).toBeGreaterThanOrEqual(10);
    expect(Number(tick)).toBeLessThanOrEqual(50);
  }
});

test('navigates to transaction detail from event', async ({ page }) => {
  await page.goto('/simulations/test-sim/events');
  
  // Click first transaction link
  await page.locator('[data-testid="event-card"]')
    .first()
    .locator('[data-testid="tx-link"]')
    .click();
  
  // Verify navigation
  await expect(page).toHaveURL(/\/transactions\//);
});
```

#### 4.6: Performance Testing
Test with large simulations (100K+ events):
- Ensure pagination handles large datasets
- Verify virtualized scrolling performance
- Check filter query performance
- Optimize if needed

**Estimated Time:** 2-3 days

**Acceptance Criteria:**
- ✅ Event legend/help available
- ✅ Consistent color coding applied
- ✅ CSV export works correctly
- ✅ Keyboard shortcuts functional
- ✅ E2E tests pass
- ✅ Performance acceptable with 100K+ events
- ✅ No console errors
- ✅ Responsive on mobile

---

## Success Metrics

### Completeness
- ✅ All 20+ event types from taxonomy captured and displayed
- ✅ Event timeline shows comprehensive system activity
- ✅ Policy decisions, LSM operations, and queue events visible
- ✅ Balance changes tracked for all agents

### Performance
- ✅ Event timeline loads < 1 second for typical simulations
- ✅ Filters apply < 500ms
- ✅ Smooth scrolling with 1000+ events displayed
- ✅ Database queries < 500ms (95th percentile)
- ✅ Simulation performance impact < 5%

### Usability
- ✅ Users can trace transaction lifecycle through event stream
- ✅ Users can filter to find specific events quickly
- ✅ Event descriptions are human-readable and informative
- ✅ Navigation to related entities (tx, agent) works seamlessly
- ✅ Visual distinction between event types clear

### Correctness
- ✅ Event ordering matches simulation tick order
- ✅ All events have complete, accurate information
- ✅ Filtering produces correct results
- ✅ Pagination doesn't skip or duplicate events

---

## Testing Strategy

### Backend Tests
1. **Unit tests** for event emission logic
2. **Integration tests** for event persistence
3. **API tests** for event endpoint filtering/pagination
4. **Performance tests** for batch inserts

### Frontend Tests
1. **Component tests** for each EventCard type
2. **Integration tests** for EventFilters behavior
3. **E2E tests** for complete user flows
4. **Visual regression tests** for event rendering

### Data Validation Tests
1. Verify events match CLI `--verbose` output
2. Verify event counts match transaction/collateral table counts
3. Verify event ordering is consistent
4. Verify no events are lost or duplicated

---

## Risk Mitigation

### Risk 1: Performance Impact on Simulation
**Mitigation:**
- Batch event writes (every 10 ticks)
- Use async writes if needed
- Benchmark before/after
- Make event persistence optional via flag

### Risk 2: Large Database Growth
**Mitigation:**
- Estimate: 500 ticks × 100 txs × 5 events/tx = 250K events
- At ~1KB per event = 250MB per simulation
- Add cleanup for old simulations
- Consider compression for archived simulations

### Risk 3: Complex Event Reconstruction
**Mitigation:**
- Persist events directly (chosen approach)
- Avoid reconstruction complexity
- If reconstruction needed, implement incrementally

### Risk 4: Frontend Performance with Large Event Lists
**Mitigation:**
- Use virtualized scrolling (react-window)
- Server-side pagination only
- Aggressive page size limit (max 1000)
- Consider infinite scroll vs traditional pagination

---

## Timeline Summary

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1 | Backend event infrastructure | 3-4 days |
| Phase 2 | API endpoint implementation | 1-2 days |
| Phase 3 | Frontend event timeline page | 3-4 days |
| Phase 4 | Polish and testing | 2-3 days |
| **Total** | | **9-13 days** |

*With one developer working full-time*

---

## Dependencies

### Required Before Implementation
- ✅ Diagnostic frontend plan approved
- ✅ Event taxonomy reviewed and approved
- ✅ Database access patterns understood

### Required During Implementation
- PostgreSQL database for testing
- Sample simulations with diverse event types
- Design mockups for event cards (optional but helpful)

### Parallel Work Opportunities
- Backend (Phase 1) and API (Phase 2) can be done by one developer
- Frontend (Phase 3) can start once API is ready
- Polish (Phase 4) can be done while backend work continues for other features

---

## Future Enhancements (Post-MVP)

### 1. Real-Time Event Streaming
- WebSocket support for live event stream
- Live simulation monitoring
- Pause/resume controls

### 2. Event Playback & Animation
- Animated timeline showing events as they occurred
- Speed controls (1x, 2x, 10x)
- Visual representation of money flowing between agents

### 3. Event Correlation & Analysis
- Highlight related events (e.g., all events for a transaction)
- Show causality chains (event A caused event B)
- Statistical analysis of event patterns

### 4. Advanced Filtering
- Complex queries (AND/OR logic)
- Saved filter presets
- Filter by custom event attributes

### 5. Event Annotations
- Allow users to add notes to events
- Highlight important events
- Share annotated timelines

---

## Appendix A: Event Category Mapping

| Event Type | Category | Icon | Color |
|------------|----------|------|-------|
| TransactionArrival | transaction | 🔵 | Blue |
| TransactionSubmitted | transaction | 📤 | Blue |
| TransactionSettled | transaction | ✅ | Blue |
| TransactionDropped | transaction | ❌ | Blue |
| TransactionSplit | transaction | ✂️ | Blue |
| Queue1Hold | queue | 🟡 | Yellow |
| Queue1Release | queue | 🚀 | Yellow |
| Queue2Queued | queue | ⏸️ | Yellow |
| Queue2Released | queue | ▶️ | Yellow |
| BalanceDebited | balance | 📤 | Green |
| BalanceCredited | balance | 📥 | Green |
| CollateralPosted | liquidity | 💰 | Green |
| CollateralReleased | liquidity | 💸 | Green |
| OverdraftDrawn | liquidity | 📉 | Green |
| OverdraftRepaid | liquidity | 📈 | Green |
| LSMBilateralOffset | lsm | ⚙️ | Purple |
| LSMCycleSettled | lsm | 🔄 | Purple |
| LSMBatchSettled | lsm | 📦 | Purple |
| PolicyEvaluation | policy | 🤔 | Orange |
| PolicySplitDecision | policy | ✂️ | Orange |
| TickStart | system | ⏰ | Gray |
| ThroughputSignal | system | 📊 | Gray |
| DayEnd | system | 🌙 | Gray |

---

## Appendix B: Example Event Sequence

Here's how the events you described would appear in the system:

```
Tick 10:  🔵 TransactionArrival    tx123 arrives to BANK_A for BANK_B ($10,000)
Tick 11:  🟡 PolicyEvaluation      BANK_A evaluated tx123 to HOLD (insufficient liquidity)
Tick 15:  💰 CollateralPosted      BANK_A posted $50,000 collateral
Tick 20:  🚀 Queue1Release         BANK_A released tx123 from Queue 1
Tick 20:  📤 TransactionSubmitted  tx123 submitted by BANK_A to RTGS
Tick 25:  ✅ TransactionSettled    tx123 settled via RTGS
Tick 25:  📤 BalanceDebited        BANK_A debited $10,000 (balance: $90,000)
Tick 25:  📥 BalanceCredited       BANK_B credited $10,000 (balance: $110,000)
```

Each event shows:
- Tick number and icon
- Event type in readable format
- Key details relevant to that event type
- Links to view related transaction or agent

---

## Next Steps

1. ✅ **Review this plan** - Ensure event taxonomy is complete and approved
2. ⏸️ **Prioritize phases** - Decide if all phases needed immediately or if phased rollout preferred
3. 🚀 **Begin Phase 1** - Start with backend event infrastructure (highest priority)
4. 📊 **Track progress** - Use implementation phases as milestones

**Ready to begin implementation!** 🎉
