# SimCash Architecture Documentation Plan

**Version**: 1.0
**Created**: 2025-11-28
**Status**: Planning Phase

---

## Executive Summary

This document outlines a comprehensive plan to create technical architecture documentation for SimCash, a high-performance payment simulator modeling real-time settlement between banks. The documentation will consist of detailed Mermaid diagrams and technical reference documents organized in `docs/reference/architecture/`.

### Scope

- **19,445 lines of Rust** across 31 files (8 core modules)
- **34 Python source files** (6 major components)
- **50+ event types** in the event system
- **FFI boundary** via PyO3
- **Persistence layer** with DuckDB and StateProvider pattern

---

## Documentation Structure

```
docs/reference/architecture/
├── ARCHITECTURE_DOCUMENTATION_PLAN.md    ← This file (planning)
├── index.md                              ← Master index with navigation
├── 01-system-overview.md                 ← High-level architecture
├── 02-rust-core-engine.md                ← Rust backend deep dive
├── 03-python-api-layer.md                ← Python layer deep dive
├── 04-ffi-boundary.md                    ← PyO3 integration patterns
├── 05-domain-models.md                   ← Core data structures
├── 06-settlement-engines.md              ← RTGS + LSM algorithms
├── 07-policy-system.md                   ← Decision trees, DSL, evaluation
├── 08-event-system.md                    ← Event types and lifecycle
├── 09-persistence-layer.md               ← DuckDB, StateProvider, replay
├── 10-cli-architecture.md                ← Commands, execution engine
├── 11-tick-loop-anatomy.md               ← Detailed tick execution flow
├── 12-cost-model.md                      ← Cost types and calculations
├── appendix-a-module-reference.md        ← Complete module listing
├── appendix-b-event-catalog.md           ← All 50+ event types
└── appendix-c-configuration-reference.md ← Config schema documentation
```

---

## Phase 1: Foundation Documents (Priority: High)

### 1.1 Master Index (`index.md`)

**Purpose**: Navigation hub for all architecture documentation

**Contents**:
- Quick links to all documents
- Architecture overview diagram
- Reading order recommendations
- Cross-reference matrix

**Mermaid Diagrams**:
```
1. System Context Diagram (C4 Level 1)
   - External actors (Users, LLM Manager)
   - System boundary
   - External systems (DuckDB, Future: WebSocket clients)

2. Container Diagram (C4 Level 2)
   - CLI/API layer
   - Rust Core Engine
   - Python Orchestration
   - Database
```

---

### 1.2 System Overview (`01-system-overview.md`)

**Purpose**: High-level understanding of SimCash architecture

**Sections**:
1. **Design Philosophy**
   - Why Rust + Python hybrid
   - Performance vs. ergonomics trade-offs
   - FFI boundary minimization principles

2. **Three-Tier Architecture**
   - Python API/CLI (orchestration)
   - Rust Core Engine (simulation)
   - Persistence Layer (DuckDB)

3. **Key Architectural Decisions**
   - Money as i64 (integer cents)
   - Determinism via seeded RNG
   - StateProvider pattern for replay identity
   - Two-queue architecture (Q1 strategic, Q2 mechanical)

4. **System Invariants**
   - Balance conservation
   - Deterministic execution
   - FFI boundary safety

**Mermaid Diagrams**:
```
1. Three-Tier Architecture Diagram
   ┌─────────────────────────────────────────────┐
   │  Python Layer (CLI/API)                     │
   │  - Configuration validation                 │
   │  - Execution orchestration                  │
   │  - Output formatting                        │
   └────────────────┬────────────────────────────┘
                    │ FFI (PyO3)
   ┌────────────────▼────────────────────────────┐
   │  Rust Core Engine                           │
   │  - Tick loop execution                      │
   │  - Settlement engines                       │
   │  - Policy evaluation                        │
   │  - Event generation                         │
   └────────────────┬────────────────────────────┘
                    │ Persistence
   ┌────────────────▼────────────────────────────┐
   │  DuckDB (Persistence)                       │
   │  - Event timeline                           │
   │  - Transaction records                      │
   │  - Checkpoints                              │
   └─────────────────────────────────────────────┘

2. Data Flow Diagram (run command)
3. Request-Response Flow (API endpoints)
4. Replay vs Live Execution comparison
```

---

## Phase 2: Core Component Deep Dives (Priority: High)

### 2.1 Rust Core Engine (`02-rust-core-engine.md`)

**Purpose**: Complete documentation of Rust backend

**Sections**:
1. **Module Organization**
   - `lib.rs` - Entry point and exports
   - `core/` - Time management
   - `models/` - Domain types
   - `orchestrator/` - Main simulation loop
   - `settlement/` - RTGS + LSM
   - `rng/` - Deterministic RNG
   - `policy/` - Decision tree evaluation
   - `arrivals/` - Transaction generation
   - `events/` - Scenario events
   - `ffi/` - PyO3 boundary

2. **Module Dependency Graph**
3. **Public API Surface**
4. **Error Handling Patterns**
5. **Performance Characteristics**

**Mermaid Diagrams**:
```
1. Module Dependency Graph (flowchart)
   lib.rs → orchestrator → [settlement, policy, arrivals, models]
   orchestrator → models → [agent, transaction, state, event]
   settlement → [rtgs, lsm] → models
   lsm → [graph, pair_index]

2. Orchestrator Structure (class diagram)
   Orchestrator
   ├── state: SimulationState
   ├── rng: RngManager
   ├── time: TimeManager
   ├── policies: HashMap<String, Policy>
   ├── arrival_generators: HashMap<String, ArrivalGenerator>
   └── config: OrchestratorConfig

3. Data Structure Relationships (ER diagram)
   Agent ──1:N── Transaction (as sender)
   Agent ──1:N── Transaction (as receiver)
   Transaction ──0:1── Transaction (parent)
   SimulationState ──1:N── Agent
   SimulationState ──1:N── Transaction
   SimulationState ──1:N── Event
```

---

### 2.2 Python API Layer (`03-python-api-layer.md`)

**Purpose**: Complete documentation of Python layer

**Sections**:
1. **Package Structure**
   - `cli/` - Command-line interface
   - `config/` - Configuration management
   - `persistence/` - Database layer
   - `api/` - FastAPI endpoints
   - `_core.py` - FFI shim

2. **CLI Command Architecture**
   - `run` command flow
   - `replay` command flow
   - `checkpoint` commands
   - `db` management commands

3. **Execution Engine (Template Method Pattern)**
   - SimulationRunner
   - OutputStrategy implementations
   - PersistenceManager

4. **StateProvider Pattern**
   - OrchestratorStateProvider (live)
   - DatabaseStateProvider (replay)

**Mermaid Diagrams**:
```
1. Package Dependency Graph
2. CLI Command Flow (sequence diagram)
3. Template Method Pattern Structure
4. StateProvider Protocol diagram
5. Execution Pipeline (run command)
```

---

### 2.3 FFI Boundary (`04-ffi-boundary.md`)

**Purpose**: Document PyO3 integration patterns

**Sections**:
1. **FFI Design Principles**
   - Minimal crossing frequency
   - Simple types only (primitives, dicts, lists)
   - Validation at boundary
   - Rust owns state, Python gets snapshots

2. **Type Conversions**
   - Python dict → Rust structs
   - Rust structs → Python dicts
   - Event serialization patterns

3. **Error Propagation**
   - SimulationError enum
   - Python exception mapping
   - Graceful failure handling

4. **Performance Considerations**
   - Batch operations
   - Avoiding tight loops
   - Memory ownership

**Mermaid Diagrams**:
```
1. FFI Boundary Crossing Points
2. Type Conversion Flow
3. Error Propagation Chain
4. Data Ownership Model
```

---

## Phase 3: Domain Models (Priority: High)

### 3.1 Domain Models (`05-domain-models.md`)

**Purpose**: Document core data structures

**Sections**:
1. **Agent (Bank)**
   - Identity and core state
   - Queue management
   - Liquidity management
   - Budget control
   - TARGET2 limits

2. **Transaction**
   - Identification
   - Amount tracking
   - Temporal properties
   - Priority system (dual)
   - Splitting support

3. **SimulationState**
   - Agent registry
   - Transaction registry
   - RTGS queue (Queue 2)
   - Event log

4. **TimeManager**
   - Tick tracking
   - Day boundaries
   - EOD detection

**Mermaid Diagrams**:
```
1. Agent State Diagram
   [Initial] → Active
   Active: balance operations
   Active: queue operations
   Active: collateral operations
   Active → [EOD Reset]

2. Transaction State Machine
   [Created] → Pending
   Pending → PartiallySettled
   Pending → Settled
   Pending → Overdue
   PartiallySettled → Settled
   Overdue → Settled (with penalty)

3. Entity Relationship Diagram
4. Transaction Lifecycle Flowchart
```

---

### 3.2 Settlement Engines (`06-settlement-engines.md`)

**Purpose**: Document RTGS and LSM algorithms

**Sections**:
1. **RTGS Settlement**
   - Immediate settlement flow
   - Queue 2 management
   - Liquidity checking
   - Atomic execution

2. **LSM Algorithms**
   - Algorithm 1: FIFO queue processing
   - Algorithm 2: Bilateral offsetting
   - Algorithm 3: Multilateral cycle detection

3. **Graph-Based Cycle Detection**
   - AggregatedGraph structure
   - Vertex indexing (lexicographic)
   - Cycle enumeration algorithm
   - Deterministic ordering

4. **TARGET2 Alignment**
   - Bilateral/multilateral limits
   - Algorithm sequencing
   - Entry disposition offsetting

**Mermaid Diagrams**:
```
1. RTGS Settlement Flow
   Submit → Check Liquidity → [Sufficient?]
   Yes → Debit/Credit → Settled
   No → Queue → Retry Loop

2. LSM Algorithm Sequence
   FIFO Processing → Bilateral Scan → Multilateral Search
   ↓                 ↓                 ↓
   Settle OK         Find Pairs        Find Cycles
   ↓                 ↓                 ↓
   Next Queue Item   Net Settlement    Atomic Settlement

3. Cycle Detection Visualization
   A ──$100──→ B
   ↑           ↓
   └──$80─ C ←$120─┘

4. Bilateral Offset Diagram
5. Graph Construction Flow
```

---

## Phase 4: Policy & Events (Priority: Medium)

### 4.1 Policy System (`07-policy-system.md`)

**Purpose**: Document decision tree policies

**Sections**:
1. **Policy Architecture**
   - CashManagerPolicy trait
   - ReleaseDecision enum
   - Policy evaluation timing

2. **Decision Tree DSL**
   - JSON schema
   - Expression language
   - Available fields (50+)
   - Operators

3. **Policy Evaluation Points**
   - bank_tree (Step 1.75)
   - strategic_collateral_tree (Step 2)
   - payment_tree (Step 3)
   - end_of_tick_collateral_tree (Step 8)

4. **Available Actions**
   - Release, Hold, Split, Reprioritize, Drop
   - PostCollateral, WithdrawCollateral
   - SetReleaseBudget, SetState, AddState

**Mermaid Diagrams**:
```
1. Policy Evaluation Flow
2. Decision Tree Structure
3. Field Access Hierarchy
4. Action Execution Flow
```

---

### 4.2 Event System (`08-event-system.md`)

**Purpose**: Document all event types

**Sections**:
1. **Event Architecture**
   - Event enum (50+ variants)
   - EventLog structure
   - Event lifecycle

2. **Event Categories**
   - Arrival events
   - Policy events
   - Settlement events
   - LSM events
   - Cost events
   - Collateral events
   - EOD events

3. **Event Persistence**
   - Serialization via FFI
   - Storage in simulation_events
   - Replay reconstruction

4. **Event Catalog**
   - Complete listing
   - Fields per event
   - Generation conditions

**Mermaid Diagrams**:
```
1. Event Flow (generation to storage)
2. Event Category Hierarchy
3. Event Timeline (typical tick)
```

---

## Phase 5: Execution & Persistence (Priority: Medium)

### 5.1 Persistence Layer (`09-persistence-layer.md`)

**Purpose**: Document DuckDB integration

**Sections**:
1. **Database Schema**
   - Pydantic models as source of truth
   - Table definitions
   - Index strategy

2. **Event Storage**
   - simulation_events table
   - JSONB details column
   - Unified event timeline

3. **StateProvider Pattern**
   - Protocol definition
   - OrchestratorStateProvider
   - DatabaseStateProvider
   - Replay identity guarantee

4. **Checkpoint System**
   - State serialization
   - Save/load flow
   - Resume semantics

**Mermaid Diagrams**:
```
1. Database Schema (ER diagram)
2. StateProvider Pattern
   display_tick_verbose_output(provider)
       ↓
   ┌─────────┴─────────┐
   ↓                   ↓
   OrchestratorSP      DatabaseSP
   (FFI queries)       (SQL queries)

3. Persistence Pipeline
4. Checkpoint Flow
```

---

### 5.2 CLI Architecture (`10-cli-architecture.md`)

**Purpose**: Document command-line interface

**Sections**:
1. **Command Structure**
   - Typer application
   - Command registration
   - Option/argument handling

2. **Execution Engine**
   - SimulationRunner (template method)
   - OutputStrategy implementations
   - PersistenceManager

3. **Output Modes**
   - Normal (JSON summary)
   - Verbose (rich logs)
   - Stream (JSONL)
   - Event stream (filtered)

4. **Event Filtering**
   - EventFilter class
   - Filter predicates
   - CLI argument parsing

**Mermaid Diagrams**:
```
1. CLI Command Tree
   payment-sim
   ├── run <config>
   ├── replay <db>
   ├── checkpoint
   │   ├── save
   │   ├── load
   │   ├── list
   │   └── delete
   └── db
       ├── init
       ├── validate
       ├── migrate
       └── schema

2. Execution Pipeline (sequence diagram)
3. OutputStrategy Selection Flow
4. Event Filter Evaluation
```

---

## Phase 6: Detailed Flows (Priority: Medium)

### 6.1 Tick Loop Anatomy (`11-tick-loop-anatomy.md`)

**Purpose**: Document the 9-step tick execution

**Sections**:
1. **Step-by-Step Breakdown**
   - Step 1: Advance time
   - Step 2: Check EOD
   - Step 3: Generate arrivals
   - Step 4: Entry disposition offsetting
   - Step 5: Policy evaluation
   - Step 6: RTGS processing
   - Step 7: LSM optimization
   - Step 8: Cost accrual
   - Step 9: Event logging

2. **State Changes per Step**
3. **Event Generation per Step**
4. **Performance Characteristics**

**Mermaid Diagrams**:
```
1. Complete Tick Flow (detailed flowchart)
2. State Mutation Timeline
3. Event Generation Timeline
```

---

### 6.2 Cost Model (`12-cost-model.md`)

**Purpose**: Document cost calculations

**Sections**:
1. **Cost Types**
   - Liquidity costs (overdraft)
   - Collateral costs
   - Delay costs (Queue 1)
   - Split friction
   - Deadline penalties

2. **Cost Calculation Formulas**
3. **Cost Accumulation**
4. **Cost Reporting**

**Mermaid Diagrams**:
```
1. Cost Accrual Flow
2. Cost Type Hierarchy
3. Cost Reporting Pipeline
```

---

## Phase 7: Reference Appendices (Priority: Low)

### 7.1 Module Reference (`appendix-a-module-reference.md`)

**Contents**:
- Complete Rust module listing (31 files)
- Complete Python module listing (34 files)
- Key types per module
- Public API per module

---

### 7.2 Event Catalog (`appendix-b-event-catalog.md`)

**Contents**:
- All 50+ event types
- Fields per event
- Generation conditions
- Example payloads

---

### 7.3 Configuration Reference (`appendix-c-configuration-reference.md`)

**Contents**:
- SimulationConfig schema
- AgentConfig fields
- ArrivalConfig options
- PolicyConfig variants
- CostRates parameters

---

## Implementation Notes

### Mermaid Diagram Guidelines

1. **Flowcharts**: Use for processes and decision flows
   ```mermaid
   flowchart TD
       A[Start] --> B{Decision}
       B -->|Yes| C[Action 1]
       B -->|No| D[Action 2]
   ```

2. **Sequence Diagrams**: Use for component interactions
   ```mermaid
   sequenceDiagram
       Python->>Rust: tick()
       Rust->>Rust: process_arrivals()
       Rust-->>Python: TickResult
   ```

3. **Class Diagrams**: Use for data structures
   ```mermaid
   classDiagram
       class Agent {
           +id: String
           +balance: i64
           +debit(amount)
           +credit(amount)
       }
   ```

4. **ER Diagrams**: Use for relationships
   ```mermaid
   erDiagram
       AGENT ||--o{ TRANSACTION : sends
       AGENT ||--o{ TRANSACTION : receives
   ```

5. **State Diagrams**: Use for lifecycles
   ```mermaid
   stateDiagram-v2
       [*] --> Pending
       Pending --> Settled
       Pending --> Overdue
   ```

### Cross-Reference Format

Use markdown links between documents:
```markdown
See [Settlement Engines](./06-settlement-engines.md#rtgs-settlement) for details.
```

### Code Examples

Include code snippets from actual codebase:
```markdown
**Source**: `backend/src/models/agent.rs:15-30`
```

---

## Work Estimation

| Document | Complexity | Est. Time | Priority |
|----------|------------|-----------|----------|
| index.md | Low | 2h | High |
| 01-system-overview.md | Medium | 4h | High |
| 02-rust-core-engine.md | High | 8h | High |
| 03-python-api-layer.md | High | 6h | High |
| 04-ffi-boundary.md | Medium | 4h | High |
| 05-domain-models.md | High | 6h | High |
| 06-settlement-engines.md | High | 6h | High |
| 07-policy-system.md | Medium | 4h | Medium |
| 08-event-system.md | High | 6h | Medium |
| 09-persistence-layer.md | Medium | 4h | Medium |
| 10-cli-architecture.md | Medium | 4h | Medium |
| 11-tick-loop-anatomy.md | Medium | 3h | Medium |
| 12-cost-model.md | Low | 2h | Medium |
| appendix-a | Low | 2h | Low |
| appendix-b | Medium | 3h | Low |
| appendix-c | Low | 2h | Low |

**Total Estimated Time**: ~66 hours

---

## Document Creation Order

### Phase 1 (Foundation) - Start Here
1. `index.md` - Navigation hub
2. `01-system-overview.md` - High-level context

### Phase 2 (Core Components)
3. `02-rust-core-engine.md` - Backend deep dive
4. `03-python-api-layer.md` - Frontend deep dive
5. `04-ffi-boundary.md` - Integration patterns

### Phase 3 (Domain)
6. `05-domain-models.md` - Data structures
7. `06-settlement-engines.md` - RTGS + LSM

### Phase 4 (Behavior)
8. `07-policy-system.md` - Decision logic
9. `08-event-system.md` - Event architecture

### Phase 5 (Operations)
10. `09-persistence-layer.md` - Data storage
11. `10-cli-architecture.md` - CLI design
12. `11-tick-loop-anatomy.md` - Execution flow
13. `12-cost-model.md` - Cost calculations

### Phase 6 (Reference)
14. `appendix-a-module-reference.md`
15. `appendix-b-event-catalog.md`
16. `appendix-c-configuration-reference.md`

---

## Quality Checklist

Each document must include:
- [ ] Overview section with purpose
- [ ] At least 2 Mermaid diagrams
- [ ] Cross-references to related documents
- [ ] Code examples with file locations
- [ ] Consistent terminology (from glossary)
- [ ] Last updated date

---

## Glossary (Use Consistently)

| Term | Definition |
|------|------------|
| **Tick** | Smallest discrete time unit |
| **Day** | Collection of ticks (business day) |
| **Agent** | Participating bank |
| **Queue 1** | Internal bank queue (strategic) |
| **Queue 2** | RTGS central queue (mechanical) |
| **RTGS** | Real-Time Gross Settlement |
| **LSM** | Liquidity-Saving Mechanism |
| **FFI** | Foreign Function Interface (PyO3) |
| **StateProvider** | Abstraction for data access |

---

*This plan will be updated as documentation progresses.*
