# Documentation Expansion — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 2 (Tiers 1-2), Wave 3 (Tiers 3-4), Wave 4 (Tier 5)

## Goal

Expand in-app documentation from the current 720-line single-focus page to a comprehensive reference covering all of SimCash's capabilities: scenarios, policies, optimization, and research guides. Structured in 5 tiers of progressive depth.

## Web Invariants

- **WEB-INV-6**: Dark Mode Only — docs styled consistently

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/views/docs/` | Directory for doc section components |
| `web/frontend/src/views/docs/CoreConceptsDocs.tsx` | Tier 1: RTGS, queuing, cost model, game theory |
| `web/frontend/src/views/docs/ScenarioDocs.tsx` | Tier 2: Scenario config, payment generation, events |
| `web/frontend/src/views/docs/PolicyDocs.tsx` | Tier 3: Policy trees, actions, fields, patterns |
| `web/frontend/src/views/docs/OptimizationDocs.tsx` | Tier 4: LLM loop, constraints, bootstrap, convergence |
| `web/frontend/src/views/docs/ResearchGuides.tsx` | Tier 5: Step-by-step experiment guides |
| `web/frontend/src/components/DocsSidebar.tsx` | Navigable sidebar for docs |
| `web/frontend/src/components/CodeBlock.tsx` | Syntax-highlighted code block (YAML/JSON) |

### Modified
| File | Changes |
|------|---------|
| `web/frontend/src/views/DocsView.tsx` | Restructure as docs shell with sidebar + content area |

## Tiers & Content

### Tier 1: Core Concepts (Wave 2)

Expand existing content:

1. **What is SimCash** — broaden beyond "2 banks tuning a fraction" to "research platform for RTGS payment system coordination"
2. **RTGS Systems** — TARGET2, Fedwire, RIX-RTGS context
3. **The Two Queues** — Queue 1 (strategic, bank-side) vs Queue 2 (mechanical, central bank)
4. **Settlement Mechanics** — immediate settlement, LSM algorithms (FIFO, bilateral, multilateral)
5. **Cost Model** — ALL 7 cost types with formulas:
   - Overdraft (bps × |negative_balance| × tick_fraction)
   - Collateral (bps × posted × tick_fraction)
   - Delay (penalty × ticks_held, Queue 1 only)
   - Deadline penalty (fixed, one-time)
   - Overdue delay (penalty × 5× multiplier)
   - Split friction (cost × (parts - 1))
   - End-of-day penalty (penalty × remaining/original)
6. **The Coordination Game** — Prisoner's Dilemma / Stag Hunt framing, when each applies

### Tier 2: Scenarios (Wave 2)

1. **What is a Scenario** — YAML config defining the experiment
2. **Scenario Parameters Reference** — all top-level config fields
3. **Payment Generation** — deterministic, Poisson, LogNormal, custom events
4. **Custom Events** — 7 event types with examples:
   - DirectTransfer, CollateralAdjustment, GlobalArrivalRateChange
   - AgentArrivalRateChange, CounterpartyWeightChange, DeadlineWindowChange
   - OneTime vs Repeating scheduling
5. **Settlement System Config** — FIFO, priority mode, LSM modes, algorithm sequencing
6. **Agent Configuration** — per-agent policies, arrival rates, credit limits
7. **Scenario Design Guide** — "How to create a crisis scenario" with worked example

### Tier 3: Policies (Wave 3)

1. **What is a Policy Tree** — JSON decision tree DSL overview
2. **The 4 Tree Types** — when each is evaluated, what it controls
3. **Actions Reference** — all 16 actions organized by tree type
4. **Context Fields Reference** — all 140+ fields organized by category (agent, transaction, system, collateral, time, LSM, cost)
5. **Expression System** — comparisons, arithmetic, parameters
6. **State Registers** — cross-tick memory, max 10, daily reset
7. **Policy Design Patterns**:
   - "The Cautious Banker" — hold until balance is safe
   - "The Aggressive Market Maker" — release everything, manage overdraft
   - "The Deadline Driver" — priority-based timing
   - "The Budget Controller" — bank_tree sets limits, payment_tree obeys
   - "The Crisis Manager" — collateral-aware with state registers
8. **Policy Cookbook** — copy-paste JSON examples for common patterns

### Tier 4: LLM Optimization (Wave 3)

1. **How Optimization Works** — the day-by-day loop
2. **Constraint Configuration** — simple/standard/full presets, what each allows
3. **Bootstrap Evaluation** — paired comparison, statistical significance
4. **Multi-Agent Isolation** — why agents can't see each other
5. **Convergence** — what it means, when to expect it, how to diagnose stuck optimization
6. **Tuning Guide** — max iterations, eval samples, optimization interval, temperature

### Tier 5: Research Guides (Wave 4)

1. **"Replicating Castro et al."** — step-by-step with expected results
2. **"Designing a Stress Test"** — crisis events + policy resilience evaluation
3. **"Exploring LSM Effectiveness"** — bilateral vs multilateral, with/without scenarios
4. **"Finding Nash Equilibria"** — multi-agent convergence, temporal mode
5. **"Building a Custom Experiment"** — scenario + policy + optimization end-to-end

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Restructure DocsView as shell + sidebar (Wave 2) | 2h | tsc + build |
| 2 | Tier 1: Core Concepts content (Wave 2) | 3h | tsc + build |
| 3 | Tier 2: Scenarios content (Wave 2) | 3h | tsc + build |
| 4 | Tier 3: Policies content (Wave 3) | 4h | tsc + build |
| 5 | Tier 4: Optimization content (Wave 3) | 3h | tsc + build |
| 6 | Tier 5: Research Guides (Wave 4) | 4h | tsc + build |

## Phase 1: Docs Shell Restructure

Replace monolithic DocsView with:
```
┌────────────┬──────────────────────────────────────┐
│ Sidebar    │ Content Area                          │
│            │                                       │
│ Core       │  [Selected section renders here]     │
│  ├ What is │                                       │
│  ├ RTGS    │                                       │
│  ├ Queues  │                                       │
│  └ Costs   │                                       │
│            │                                       │
│ Scenarios  │                                       │
│  ├ Config  │                                       │
│  ├ Events  │                                       │
│  └ Design  │                                       │
│            │                                       │
│ Policies   │                                       │
│  ├ Trees   │                                       │
│  ├ Actions │                                       │
│  └ Patterns│                                       │
│            │                                       │
│ ...        │                                       │
└────────────┴──────────────────────────────────────┘
```

Sidebar: collapsible sections, highlights active item, scrolls content area.

**CodeBlock.tsx**: Reusable component for YAML/JSON examples with syntax highlighting (use `prism-react-renderer` or similar lightweight library).

## Content Principles

1. **Accuracy first** — all formulas, rates, and examples verified against engine source
2. **Code examples for everything** — YAML for scenarios, JSON for policies, never just prose
3. **No false claims** — don't say "Castro uses REINFORCE" or "default cost rate is 83 bps" (it varies by experiment)
4. **Progressive depth** — each section starts with a one-paragraph summary, then details
5. **Cross-references** — link between related sections ("see Policy Design Patterns for examples using this field")
6. **Searchable** — add text search across all docs content

### UI Test Protocol

```
Protocol: W2-Docs (Wave 2, Tiers 1-2)

1. Navigate to Docs
2. VERIFY: Sidebar shows at least "Core Concepts" and "Scenarios" sections
3. Click "Cost Model"
4. VERIFY: All 7 cost types listed with formulas
5. Click "Custom Events"
6. VERIFY: All 7 event types documented with examples
7. Click a YAML code example
8. VERIFY: Syntax highlighted, copyable

Protocol: W3-Docs (Wave 3, Tiers 3-4)

1. Navigate to Docs → Policies → Actions Reference
2. VERIFY: All 16 actions listed with descriptions
3. Navigate to Context Fields
4. VERIFY: Fields organized by category, at least 50 listed
5. Navigate to Policy Patterns
6. VERIFY: At least 3 named patterns with JSON examples
7. Navigate to Optimization → Bootstrap Evaluation
8. VERIFY: Paired comparison explained with formula

Protocol: W4-Docs (Wave 4, Tier 5)

1. Navigate to Docs → Research Guides
2. VERIFY: At least 3 guides listed
3. Open "Replicating Castro et al."
4. VERIFY: Step-by-step instructions with expected results
5. VERIFY: Code examples (YAML configs) are present

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] Docs restructured with navigable sidebar
- [ ] All 5 tiers populated with accurate content
- [ ] All 7 cost types documented with formulas
- [ ] All 16 actions documented with descriptions
- [ ] All 7 event types documented with examples
- [ ] At least 5 policy design patterns with JSON examples
- [ ] At least 3 research guides with step-by-step instructions
- [ ] Code examples are syntax-highlighted and accurate
- [ ] No factual errors (verified against engine source)
