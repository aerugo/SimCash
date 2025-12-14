# Phase 5: Integration Tests

## Overview

End-to-end tests validating the full CLI flow with real database operations.

**Status**: In Progress
**Start Date**: 2025-12-14

---

## Goals

1. Create realistic test fixtures with populated database
2. Test full CLI command invocation
3. Verify JSON output structure matches expected format
4. Test persistence and query round-trip

---

## TDD Steps

### Step 5.1: Create Integration Test File

Create `api/tests/experiments/integration/test_policy_evolution_integration.py`

**Test Cases**:
1. `test_full_evolution_extraction_round_trip` - Save iterations, extract evolution
2. `test_evolution_with_complex_policies` - Nested policy trees
3. `test_evolution_preserves_iteration_order` - Order guarantee
4. `test_evolution_diff_content` - Verify diff text is meaningful
5. `test_llm_data_extraction_complete` - Full LLM data round-trip

### Step 5.2: Run Full Test Suite

Ensure all analysis module tests pass together.

---

## Completion Criteria

- [ ] All integration tests pass
- [ ] Full test suite passes (`pytest tests/experiments/analysis/` + `pytest tests/experiments/cli/test_policy_evolution_command.py`)
- [ ] Test coverage meets requirements
