# Extended Policy Evaluation Stats - Test Matrix

This document defines all combinations that MUST be tested to ensure complete coverage.

## Dimensions

### 1. Evaluation Mode
- **Deterministic**: Single scenario, N=1
- **Bootstrap**: Multiple resampled scenarios, N>1 (typically 50)

### 2. Metric Types
- **settlement_rate**: Float 0.0-1.0
- **avg_delay**: Float (ticks)
- **cost_breakdown**: Dict with 4 cost components
- **cost_std_dev**: Int cents (bootstrap only)
- **confidence_interval_95**: [lower, upper] in cents (bootstrap only)

### 3. Granularity
- **Total**: System-wide aggregate
- **Per-agent**: Individual agent metrics

### 4. Agent Count
- **Single agent**: One optimized agent
- **Multi-agent**: Multiple optimized agents (2-3)

---

## Complete Test Matrix

### A. Deterministic Mode - Total Metrics

| Test ID | Metric | Expected Type | Expected Value Constraints |
|---------|--------|---------------|---------------------------|
| DT-01 | `settlement_rate` | `float` | 0.0 ≤ x ≤ 1.0 |
| DT-02 | `avg_delay` | `float` | x ≥ 0.0 |
| DT-03 | `cost_breakdown.delay_cost` | `int` | x ≥ 0 |
| DT-04 | `cost_breakdown.overdraft_cost` | `int` | x ≥ 0 |
| DT-05 | `cost_breakdown.deadline_penalty` | `int` | x ≥ 0 |
| DT-06 | `cost_breakdown.eod_penalty` | `int` | x ≥ 0 |
| DT-07 | `cost_breakdown` sum | `int` | Equals or approximates `new_cost` |
| DT-08 | `cost_std_dev` | `None` | Must be None (N=1) |
| DT-09 | `confidence_interval_95` | `None` | Must be None (N=1) |

### B. Deterministic Mode - Per-Agent Metrics (Single Agent)

| Test ID | Metric | Expected Type | Expected Value Constraints |
|---------|--------|---------------|---------------------------|
| DA-01 | `agent_stats["AGENT"].cost` | `int` | x ≥ 0, equals per-agent cost |
| DA-02 | `agent_stats["AGENT"].settlement_rate` | `float` | 0.0 ≤ x ≤ 1.0 |
| DA-03 | `agent_stats["AGENT"].avg_delay` | `float` | x ≥ 0.0 |
| DA-04 | `agent_stats["AGENT"].cost_breakdown.delay_cost` | `int` | x ≥ 0 |
| DA-05 | `agent_stats["AGENT"].cost_breakdown.overdraft_cost` | `int` | x ≥ 0 |
| DA-06 | `agent_stats["AGENT"].cost_breakdown.deadline_penalty` | `int` | x ≥ 0 |
| DA-07 | `agent_stats["AGENT"].cost_breakdown.eod_penalty` | `int` | x ≥ 0 |
| DA-08 | `agent_stats["AGENT"].std_dev` | `None` | Must be None (N=1) |
| DA-09 | `agent_stats["AGENT"].ci_95_lower` | `None` | Must be None (N=1) |
| DA-10 | `agent_stats["AGENT"].ci_95_upper` | `None` | Must be None (N=1) |

### C. Deterministic Mode - Per-Agent Metrics (Multi-Agent: 3 agents)

| Test ID | Metric | Expected |
|---------|--------|----------|
| DM-01 | `agent_stats` has all 3 agents | Keys: BANK_A, BANK_B, BANK_C |
| DM-02 | Each agent has `cost` | All 3 present, type int |
| DM-03 | Each agent has `settlement_rate` | All 3 present, type float |
| DM-04 | Each agent has `avg_delay` | All 3 present, type float |
| DM-05 | Each agent has `cost_breakdown` | All 3 present, type dict |
| DM-06 | Sum of agent costs | Approximates total cost |
| DM-07 | Each agent `std_dev` | All None (N=1) |
| DM-08 | Each agent `ci_95_lower` | All None (N=1) |

### D. Bootstrap Mode - Total Metrics

| Test ID | Metric | Expected Type | Expected Value Constraints |
|---------|--------|---------------|---------------------------|
| BT-01 | `settlement_rate` | `float` | 0.0 ≤ x ≤ 1.0 (mean or representative) |
| BT-02 | `avg_delay` | `float` | x ≥ 0.0 (mean or representative) |
| BT-03 | `cost_breakdown.delay_cost` | `int` | x ≥ 0 |
| BT-04 | `cost_breakdown.overdraft_cost` | `int` | x ≥ 0 |
| BT-05 | `cost_breakdown.deadline_penalty` | `int` | x ≥ 0 |
| BT-06 | `cost_breakdown.eod_penalty` | `int` | x ≥ 0 |
| BT-07 | `cost_breakdown` sum | `int` | Approximates `new_cost` |
| BT-08 | `cost_std_dev` | `int` | x ≥ 0 |
| BT-09 | `confidence_interval_95[0]` (lower) | `int` | lower ≤ mean |
| BT-10 | `confidence_interval_95[1]` (upper) | `int` | upper ≥ mean |
| BT-11 | CI width | `int` | upper - lower > 0 |
| BT-12 | CI contains mean | bool | lower ≤ mean_new_cost ≤ upper |

### E. Bootstrap Mode - Per-Agent Metrics (Single Agent)

| Test ID | Metric | Expected Type | Expected Value Constraints |
|---------|--------|---------------|---------------------------|
| BA-01 | `agent_stats["AGENT"].cost` | `int` | Mean cost for agent |
| BA-02 | `agent_stats["AGENT"].settlement_rate` | `float` | 0.0 ≤ x ≤ 1.0 |
| BA-03 | `agent_stats["AGENT"].avg_delay` | `float` | x ≥ 0.0 |
| BA-04 | `agent_stats["AGENT"].cost_breakdown` | `dict` | All 4 components present |
| BA-05 | `agent_stats["AGENT"].std_dev` | `int` | x ≥ 0 |
| BA-06 | `agent_stats["AGENT"].ci_95_lower` | `int` | lower ≤ mean |
| BA-07 | `agent_stats["AGENT"].ci_95_upper` | `int` | upper ≥ mean |
| BA-08 | Per-agent CI contains mean | bool | lower ≤ agent.cost ≤ upper |

### F. Bootstrap Mode - Per-Agent Metrics (Multi-Agent: 3 agents)

| Test ID | Metric | Expected |
|---------|--------|----------|
| BM-01 | `agent_stats` has all 3 agents | Keys: BANK_A, BANK_B, BANK_C |
| BM-02 | Each agent has `cost` | All 3 present, type int |
| BM-03 | Each agent has `settlement_rate` | All 3 present, type float |
| BM-04 | Each agent has `avg_delay` | All 3 present, type float |
| BM-05 | Each agent has `cost_breakdown` | All 3 present, 4 components each |
| BM-06 | Each agent has `std_dev` | All 3 present, type int, ≥ 0 |
| BM-07 | Each agent has `ci_95_lower` | All 3 present, type int |
| BM-08 | Each agent has `ci_95_upper` | All 3 present, type int |
| BM-09 | Sum of agent mean costs | Approximates total mean cost |

---

## Persistence Round-Trip Tests

For each record type, verify persistence → retrieval preserves all data:

| Test ID | Scenario | Verification |
|---------|----------|--------------|
| PR-01 | Deterministic single-agent | All fields survive round-trip |
| PR-02 | Deterministic multi-agent | All fields survive round-trip |
| PR-03 | Bootstrap single-agent | All fields survive round-trip |
| PR-04 | Bootstrap multi-agent | All fields survive round-trip |
| PR-05 | JSON nested dicts | cost_breakdown structure preserved |
| PR-06 | JSON nested in agent_stats | Each agent's cost_breakdown preserved |
| PR-07 | Null handling | None values stored and retrieved as None |
| PR-08 | Empty agent_stats | {} stored and retrieved correctly |

---

## Edge Case Tests

| Test ID | Scenario | Expected Behavior |
|---------|----------|-------------------|
| EC-01 | N=1 bootstrap (treated as deterministic) | std_dev=None, CI=None |
| EC-02 | N=2 bootstrap | std_dev computed, CI very wide |
| EC-03 | All transactions settled | settlement_rate = 1.0 |
| EC-04 | No transactions settled | settlement_rate = 0.0 |
| EC-05 | No transactions arrived | settlement_rate = 1.0 (by convention) |
| EC-06 | Zero cost | cost_breakdown all zeros, std_dev=0 |
| EC-07 | Agent not in some samples | Handled gracefully |
| EC-08 | Very large costs | No overflow (i64) |

---

## Cross-Validation Tests

| Test ID | Validation | Description |
|---------|------------|-------------|
| CV-01 | Total vs sum of per-agent costs | Should be approximately equal |
| CV-02 | cost_breakdown sum vs new_cost | Should be approximately equal |
| CV-03 | Determinism | Same seed produces identical stats |
| CV-04 | CI covers true mean | With 95% probability over many runs |

---

## Test Implementation Checklist

### Phase 1 Tests (Schema)
- [ ] All field types validated (DT-*, DA-*, BT-*, BA-*)
- [ ] Round-trip tests (PR-01 through PR-08)
- [ ] Null handling (EC-01, PR-07)

### Phase 2 Tests (Capture)
- [ ] Deterministic total metrics (DT-01 through DT-09)
- [ ] Deterministic per-agent single (DA-01 through DA-10)
- [ ] Deterministic per-agent multi (DM-01 through DM-08)
- [ ] Bootstrap total metrics (BT-01 through BT-12)
- [ ] Bootstrap per-agent single (BA-01 through BA-08)
- [ ] Bootstrap per-agent multi (BM-01 through BM-09)

### Phase 3 Tests (Statistics)
- [ ] Std dev computation (BT-08, BA-05, BM-06)
- [ ] CI computation (BT-09 through BT-12, BA-06 through BA-08, BM-07, BM-08)
- [ ] Edge cases (EC-01 through EC-08)

### Phase 4 Tests (Integration)
- [ ] Cross-validation (CV-01 through CV-04)
- [ ] End-to-end persistence (PR-01 through PR-04)

---

## Expected `agent_stats` Structure

```json
{
  "BANK_A": {
    "cost": 8000,
    "settlement_rate": 0.95,
    "avg_delay": 5.2,
    "cost_breakdown": {
      "delay_cost": 3000,
      "overdraft_cost": 4500,
      "deadline_penalty": 500,
      "eod_penalty": 0
    },
    "std_dev": 450,           // Bootstrap only, null for deterministic
    "ci_95_lower": 7100,      // Bootstrap only, null for deterministic
    "ci_95_upper": 8900       // Bootstrap only, null for deterministic
  },
  "BANK_B": {
    // Same structure
  }
}
```

---

## Expected `cost_breakdown` Structure (Total)

```json
{
  "delay_cost": 5000,
  "overdraft_cost": 8000,
  "deadline_penalty": 1000,
  "eod_penalty": 0
}
```

---

## Summary: Total Test Count by Phase

| Phase | Test Category | Test Count |
|-------|---------------|------------|
| 1 | Schema & Round-trip | 18 tests |
| 2 | Deterministic capture | 27 tests |
| 2 | Bootstrap capture | 29 tests |
| 3 | Statistics computation | 12 tests |
| 4 | Integration & Cross-validation | 8 tests |
| **Total** | | **94 tests** |

This comprehensive matrix ensures every combination of evaluation mode × metric type × granularity is explicitly tested.
