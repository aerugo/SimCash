# Pretty LLM Event Formatting - Development Plan

**Status**: Pending
**Created**: 2024-12-19
**Branch**: claude/simcash-paper-proposal-PbmtC

## Summary

Unify event formatting so LLM prompts receive the same pretty-formatted output as `payment-sim run --verbose` and `payment-sim replay --verbose`, eliminating the current divergence where terminal output is rich and structured while LLM context uses simple `[tick N] EventType: details` format.

## Critical Invariants to Respect

- **INV-5**: Replay Identity - The same display functions must work for both live and replay modes
- **INV-11**: Agent Isolation - Event filtering must still apply (agents only see their own events)

## Current State Analysis

### The Problem

Two separate formatting paths exist:

1. **Terminal output** (`cli/output.py` + `cli/execution/display.py`):
   - Rich tables, colored output, structured sections
   - Uses `display_tick_verbose_output()` as single source of truth
   - Outputs to stderr via Rich Console

2. **LLM context** (`experiments/runner/optimization.py`):
   - Simple `[tick N] EventType: field=value` format
   - Uses `_format_events_for_llm()` method
   - Returns plain string

### Current Event Format for LLM
```
[tick 0] Arrival: tx_id=84a647b5-3c54-4ba9-b315-aaddb5315ae0, amount=$150.00, sender_id=BANK_B
[tick 1] RtgsSubmission: tx_id=84a647b5-3c54-4ba9-b315-aaddb5315ae0, amount=$150.00
```

### Desired Event Format for LLM
```
═══ Tick 0 ═══
📥 2 transaction(s) arrived
  BANK_B → BANK_A: $150.00 (tx: 84a6..., deadline: tick 2)
  BANK_A → BANK_B: $150.00 (tx: 59f6..., deadline: tick 2)

──────────────────────────────────────────────────────────────────────

═══ Tick 1 ═══
✓ 2 settlement(s)
  [RTGS] BANK_B → BANK_A: $150.00
  [RTGS] BANK_A → BANK_B: $150.00
```

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `cli/output.py` | Functions print to stderr console | Add optional `console` parameter to key functions |
| `cli/execution/display.py` | `display_tick_verbose_output()` uses module console | Add `console` parameter, default to module console |
| `experiments/runner/optimization.py` | `_format_events_for_llm()` produces simple format | Replace with call to new capture function |
| `ai_cash_mgmt/bootstrap/context_builder.py` | `_format_events()` produces simple format | Replace with call to new capture function |

## Solution Design

Use Rich's built-in recording capability to capture pretty output as plain text:

```
┌─────────────────────────────────────────────────────────────────┐
│                    format_events_as_text()                       │
│  (New function in cli/output.py or new module)                  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  StringIO buffer + Console(file=buffer, no_color=True)          │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Existing output functions with console= parameter              │
│  (log_transaction_arrivals, log_settlement_details, etc.)       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  buffer.getvalue() → plain text string                          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Thread console parameter through existing functions**: Rather than duplicating formatting logic, we add an optional `console` parameter that defaults to the existing stderr console. This ensures any future improvements to terminal output automatically appear in LLM context.

2. **Create a StateProvider adapter for bootstrap events**: The pretty output functions expect a `StateProvider` interface. We'll create a lightweight adapter that wraps `BootstrapEvent` lists to satisfy this interface.

3. **Strip ANSI codes**: Use `Console(no_color=True)` to get plain text without escape codes.

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Add console parameter to output functions | Functions work with custom console | 3 tests |
| 2 | Create text capture wrapper function | Captures output as string | 2 tests |
| 3 | Create BootstrapEvent StateProvider adapter | Adapter satisfies protocol | 3 tests |
| 4 | Integrate into optimization.py and context_builder.py | End-to-end formatting works | 2 tests |

## Phase 1: Add Console Parameter

**Goal**: Make output functions accept an optional console parameter

### Deliverables
1. Modified `cli/output.py` key functions with `console` parameter
2. Modified `cli/execution/display.py` with `console` parameter

### TDD Approach
1. Write test that passes custom console to output function
2. Modify functions to accept parameter
3. Verify default behavior unchanged

### Success Criteria
- [ ] `log_transaction_arrivals(provider, events, console=custom)` works
- [ ] `log_settlement_details(provider, events, tick, count, console=custom)` works
- [ ] `display_tick_verbose_output(..., console=custom)` works
- [ ] Default behavior (no console param) unchanged

## Phase 2: Text Capture Wrapper

**Goal**: Create function to capture formatted output as string

### Deliverables
1. New function `format_events_as_text()` in `cli/output.py`

### Implementation
```python
def format_events_as_text(
    provider: StateProvider,
    events: list[dict[str, Any]],
    tick: int,
    agent_ids: list[str],
) -> str:
    """Format events as plain text using same logic as verbose terminal output.

    This function captures the output of display_tick_verbose_output() as a string,
    ensuring LLM prompts see exactly the same formatting as terminal users.
    """
    from io import StringIO
    buffer = StringIO()
    text_console = Console(file=buffer, force_terminal=False, no_color=True)

    display_tick_verbose_output(
        provider=provider,
        events=events,
        tick_num=tick,
        agent_ids=agent_ids,
        prev_balances={},
        num_arrivals=count_arrivals(events),
        num_settlements=count_settlements(events),
        num_lsm_releases=count_lsm(events),
        console=text_console,
    )

    return buffer.getvalue()
```

### Success Criteria
- [ ] Returns non-empty string for valid events
- [ ] Output matches terminal output structure (sections, headers)
- [ ] No ANSI escape codes in output

## Phase 3: BootstrapEvent StateProvider Adapter

**Goal**: Create adapter to use BootstrapEvent lists with StateProvider-expecting functions

### Deliverables
1. New class `BootstrapEventStateProvider` implementing `StateProvider` protocol

### Implementation
```python
class BootstrapEventStateProvider:
    """StateProvider adapter for BootstrapEvent lists.

    Provides minimal StateProvider implementation for formatting bootstrap
    events. Only implements methods needed by output formatting functions.
    """

    def __init__(self, events: list[BootstrapEvent], agent_id: str) -> None:
        self._events = events
        self._agent_id = agent_id
        self._event_dicts = [self._to_dict(e) for e in events]

    def get_agent_balance(self, agent_id: str) -> int:
        # Extract from events or return 0
        ...

    def get_queue1_size(self, agent_id: str) -> int:
        return 0  # Not tracked in bootstrap events

    # ... other required methods with sensible defaults
```

### Success Criteria
- [ ] Satisfies StateProvider protocol
- [ ] Works with `format_events_as_text()`
- [ ] Filters events by agent (respects INV-11)

## Phase 4: Integration

**Goal**: Replace simple formatting with pretty formatting in optimization code

### Deliverables
1. Modified `optimization.py._format_events_for_llm()` to use new function
2. Modified `context_builder.py.format_event_trace_for_llm()` to use new function

### Success Criteria
- [ ] LLM prompts show pretty-formatted events
- [ ] Agent isolation still enforced
- [ ] Experiment audit shows formatted output

## Testing Strategy

### Unit Tests
- Console parameter threading: verify custom console receives output
- Text capture: verify string output matches expectations
- Adapter: verify protocol compliance

### Integration Tests
- End-to-end: run experiment, verify audit shows pretty output
- Replay identity: ensure no regression in replay output

## Documentation Updates

After implementation is complete:
- [ ] Update `docs/reference/ai_cash_mgmt/optimizer-prompt.md` to reflect new format
- [ ] Add note about format unification to `docs/reference/patterns-and-conventions.md`

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | Add console parameters |
| Phase 2 | Pending | Create capture function |
| Phase 3 | Pending | StateProvider adapter |
| Phase 4 | Pending | Integration |
