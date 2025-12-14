# Optimizer Prompt Improvements - Development Plan

## Overview

This plan addresses three critical issues in the LLM policy optimization prompt generation:

1. **Agent Isolation Violation** - Events from other agents leak into prompts
2. **Poor Event Formatting** - Simple text format instead of rich CLI-style output
3. **Section Hierarchy** - Initial simulation buried inside best seed section

## Guiding Principles

- **Strict TDD**: Write failing tests FIRST, then implement fixes
- **Agent Isolation is CRITICAL**: This is a security/correctness invariant
- **Replay Identity**: Event formatting should be consistent with CLI output
- **Incremental Commits**: Small, focused changes with clear commit messages

---

## Phase 1: Agent Isolation (CRITICAL)

### Problem Statement

The `filter_events_for_agent()` function exists but is NEVER CALLED in the optimization flow. This allows BANK_A's LLM to see BANK_B's outgoing transactions, violating the critical isolation invariant.

### TDD Test Cases

#### Test 1.1: Prompt Must Not Contain Other Agent's Outgoing Transactions

```python
def test_prompt_excludes_other_agents_outgoing_transactions():
    """CRITICAL: Agent X's prompt must NEVER contain Agent Y's outgoing transactions."""
    # Setup: Create events where BANK_A sends to BANK_B, and BANK_B sends to BANK_A
    events = [
        {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B", "tx_id": "tx_a_to_b"},
        {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_A", "tx_id": "tx_b_to_a"},
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_A", "receiver": "BANK_B", "tx_id": "tx_a_to_b"},
        {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A", "tx_id": "tx_b_to_a"},
    ]

    # Generate prompt for BANK_A
    prompt = build_prompt_for_agent("BANK_A", events)

    # BANK_A should see:
    # - tx_a_to_b (outgoing from BANK_A)
    # - tx_b_to_a (incoming to BANK_A)
    assert "tx_a_to_b" in prompt  # BANK_A's outgoing
    assert "tx_b_to_a" in prompt  # BANK_A's incoming

    # Generate prompt for BANK_B
    prompt_b = build_prompt_for_agent("BANK_B", events)

    # BANK_B should see:
    # - tx_b_to_a (outgoing from BANK_B)
    # - tx_a_to_b (incoming to BANK_B)
    # But BANK_B should NOT see BANK_A as a sender in outgoing context
    # (they see it as receiver of their incoming)
```

#### Test 1.2: Best Seed Output Must Be Filtered

```python
def test_best_seed_output_filtered_by_agent():
    """Best seed output in prompt must only contain agent's own events."""
    # Setup: EnrichedBootstrapContextBuilder with multi-agent events
    # Assert: format_event_trace_for_llm() output only contains target agent's events
```

#### Test 1.3: Worst Seed Output Must Be Filtered

```python
def test_worst_seed_output_filtered_by_agent():
    """Worst seed output in prompt must only contain agent's own events."""
    # Similar to Test 1.2
```

#### Test 1.4: Initial Simulation Output Must Be Filtered

```python
def test_initial_simulation_output_filtered_by_agent():
    """Initial simulation output must only contain agent's own events."""
    # Bootstrap LLM context must also be filtered
```

### Implementation Steps

1. **Write failing tests** in `api/tests/unit/test_agent_isolation_prompt.py`
2. **Modify `EnrichedBootstrapContextBuilder`** to accept `agent_id` and filter events
3. **Modify `optimization.py`** to pass agent_id for filtering
4. **Verify tests pass**

### Files to Modify

- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`
- `api/payment_simulator/experiments/runner/optimization.py`
- `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py` (already has filter logic)

---

## Phase 2: Section Hierarchy Restructuring

### Problem Statement

Initial simulation data is nested inside `<best_seed_output>` tags, making it appear as secondary information when it should be the primary reference.

### TDD Test Cases

#### Test 2.1: Initial Simulation Must Be Separate Section

```python
def test_initial_simulation_is_separate_section():
    """Initial simulation must NOT be inside best_seed_output tags."""
    prompt = build_single_agent_context(...)

    # Initial simulation should be its own section
    assert "## INITIAL SIMULATION" in prompt or "### Initial Simulation" in prompt

    # It should NOT be inside best_seed_output XML tags
    best_seed_start = prompt.find("<best_seed_output>")
    best_seed_end = prompt.find("</best_seed_output>")
    if best_seed_start != -1 and best_seed_end != -1:
        best_seed_content = prompt[best_seed_start:best_seed_end]
        assert "INITIAL SIMULATION" not in best_seed_content
```

#### Test 2.2: Initial Simulation Must Appear Before Bootstrap Samples

```python
def test_initial_simulation_appears_first():
    """Initial simulation section must appear before bootstrap samples."""
    prompt = build_single_agent_context(...)

    initial_pos = prompt.find("Initial Simulation")
    best_seed_pos = prompt.find("Best Performing Seed")
    worst_seed_pos = prompt.find("Worst Performing Seed")

    assert initial_pos < best_seed_pos
    assert initial_pos < worst_seed_pos
```

### Implementation Steps

1. **Write failing tests** in `api/tests/unit/test_prompt_structure.py`
2. **Modify `SingleAgentContextBuilder._build_simulation_output_section()`** to:
   - Add dedicated initial simulation section
   - Keep best/worst seed as secondary sections
3. **Modify `optimization.py`** to pass initial simulation separately (not combined)
4. **Verify tests pass**

### Files to Modify

- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py`
- `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` (add initial_simulation_output field)
- `api/payment_simulator/experiments/runner/optimization.py`

---

## Phase 3: Event Formatting Improvement

### Problem Statement

Event logs use simple text format that's hard to read. Should use CLI-style verbose formatting for consistency.

### TDD Test Cases

#### Test 3.1: Settlement Events Must Show Balance Changes

```python
def test_settlement_events_show_balance_changes():
    """Settlement events should show balance before/after like CLI does."""
    events = [{"event_type": "RtgsImmediateSettlement", ...}]
    formatted = format_events_for_prompt(events, "BANK_A")

    assert "Balance:" in formatted or "→" in formatted
```

#### Test 3.2: Events Must Be Grouped By Tick

```python
def test_events_grouped_by_tick():
    """Events should be grouped by tick with clear headers."""
    # Already implemented in format_filtered_output(), verify it's used
```

#### Test 3.3: Currency Formatting Must Be Consistent

```python
def test_currency_formatting_consistent():
    """All amounts must be formatted as $X,XXX.XX."""
    formatted = format_events_for_prompt(events, "BANK_A")

    # Should not have raw cents like "amount=12345"
    assert not re.search(r"amount=\d{5,}", formatted)
    # Should have dollar formatting
    assert "$" in formatted
```

### Implementation Steps

1. **Write failing tests** in `api/tests/unit/test_event_formatting.py`
2. **Update `_format_single_event()`** in `event_filter.py` to match CLI style
3. **Consider creating `format_events_for_llm_prompt()`** that produces plain-text CLI-style output
4. **Verify tests pass**

### Files to Modify

- `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py`

---

## Implementation Order

### Sprint 1: Agent Isolation (CRITICAL - Do First)

1. [ ] Write `test_agent_isolation_prompt.py` with failing tests
2. [ ] Add `agent_id` parameter to `EnrichedBootstrapContextBuilder.format_event_trace_for_llm()`
3. [ ] Call `filter_events_for_agent()` before formatting
4. [ ] Update `optimization.py` to use filtered outputs
5. [ ] Verify all isolation tests pass
6. [ ] Commit: "fix: enforce agent isolation in optimizer prompts"

### Sprint 2: Section Hierarchy

1. [ ] Write `test_prompt_structure.py` with failing tests
2. [ ] Add `initial_simulation_output` to `SingleAgentContext`
3. [ ] Restructure `_build_simulation_output_section()`
4. [ ] Update `optimization.py` to pass initial simulation separately
5. [ ] Verify structure tests pass
6. [ ] Commit: "refactor: restructure prompt sections for clarity"

### Sprint 3: Event Formatting

1. [ ] Write `test_event_formatting.py` with failing tests
2. [ ] Update `_format_single_event()` for better readability
3. [ ] Ensure tick grouping is used consistently
4. [ ] Verify formatting tests pass
5. [ ] Commit: "improve: enhance event formatting in optimizer prompts"

---

## Success Criteria

### Phase 1 Complete When:
- [ ] All agent isolation tests pass
- [ ] Manual verification: Run experiment, check audit output shows only agent's own transactions

### Phase 2 Complete When:
- [ ] Initial simulation appears as separate, prominent section
- [ ] Best/worst seed are clearly marked as "bootstrap samples"

### Phase 3 Complete When:
- [ ] Event formatting is readable and consistent with CLI output
- [ ] Currency amounts properly formatted
- [ ] Events grouped by tick

---

## Risk Mitigation

1. **Regression Risk**: Run full test suite after each phase
2. **Token Limit Risk**: Filtering reduces event count, but verify prompts don't exceed limits
3. **LLM Quality Risk**: Better formatted prompts should improve LLM output quality

---

## Appendix: Key Code Locations

| Component | File | Function/Class |
|-----------|------|----------------|
| Event Filter | `ai_cash_mgmt/prompts/event_filter.py` | `filter_events_for_agent()` |
| Context Builder | `ai_cash_mgmt/bootstrap/context_builder.py` | `EnrichedBootstrapContextBuilder` |
| Prompt Builder | `ai_cash_mgmt/prompts/single_agent_context.py` | `SingleAgentContextBuilder` |
| Optimization Loop | `experiments/runner/optimization.py` | `_optimize_agent()` |
| CLI Verbose Output | `cli/execution/display.py` | `display_tick_verbose_output()` |
