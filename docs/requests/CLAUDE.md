# AI Agent Request Format Guide

This directory is where AI-agents can put requests for features or documentation.
Each request should be a markdown file with a clear title and description of the request.

## File Naming

Use kebab-case names that describe the feature or change:
- `implement-real-bootstrap-evaluation.md`
- `scenario-config-builder.md`
- `add-policy-evolution-cli.md`

## Request Structure

A well-structured request helps the implementing agent understand the context, requirements, and acceptance criteria clearly.

```markdown
# Feature Request: <Title>

**Date**: <YYYY-MM-DD>
**Priority**: <High|Medium|Low>
**Affects**: <Components, modules, or systems affected>

## Summary

<1-3 sentence description of what is being requested and why>

## Problem Statement

<Describe the current state and why it's problematic>

### Current Behavior

<What happens now - include code snippets if helpful>

```python
# Example of current problematic code
def current_approach():
    # This has issues because...
```

### Why This Is a Problem

<Explain the impact: bugs caused, maintenance burden, correctness issues, etc.>

## Proposed Solution

<Describe the desired end state>

### Design Goals

1. <Goal 1>
2. <Goal 2>
3. <Goal 3>

### Proposed API / Interface

```python
# Example of proposed solution
class ProposedSolution:
    """Docstring explaining the solution."""

    def proposed_method(self, arg: Type) -> ReturnType:
        """What this method should do."""
        ...
```

### Usage Example

```python
# Show how the solution would be used
solution = ProposedSolution()
result = solution.proposed_method(input)
```

## Implementation Notes

<Any specific implementation details, constraints, or considerations>

### Invariants to Respect

<Reference relevant invariants from docs/reference/patterns-and-conventions.md>

- **INV-X**: <How it applies>
- **INV-Y**: <How it applies>

### Related Components

| Component | Impact |
|-----------|--------|
| `path/to/file.py` | <What changes needed> |
| `path/to/other.py` | <What changes needed> |

### Migration Path (if applicable)

1. Phase 1: <description>
2. Phase 2: <description>
3. Phase 3: <description>

## Acceptance Criteria

- [ ] <Specific, testable criterion>
- [ ] <Specific, testable criterion>
- [ ] <Specific, testable criterion>
- [ ] Tests verify <behavior>
- [ ] Documentation updated for <component>

## Testing Requirements

<Describe what tests should be written>

1. **Unit tests**: <what they verify>
2. **Integration tests**: <what they verify>
3. **Identity/invariant tests**: <what invariants they enforce>

## Related Documentation

- `docs/reference/<relevant-doc>.md` - <what it covers>
- `docs/legacy/<relevant-doc>.md` - <what it covers>

## Related Code

- `path/to/relevant/file.py` - <why it's relevant>
- `path/to/other/file.py` - <why it's relevant>

## Notes

<Any additional context, historical information, or considerations>
```

---

## Request Categories

### Feature Requests

New functionality to be added. Include:
- Clear problem statement
- Proposed solution with API examples
- Acceptance criteria

### Bug Fix Requests

Issues that need to be corrected. Include:
- Steps to reproduce
- Expected vs actual behavior
- Root cause analysis (if known)

### Refactoring Requests

Code improvements without behavior change. Include:
- Current state and why it's problematic
- Proposed improvement
- Migration path if breaking changes

### Documentation Requests

Documentation to be added or updated. Include:
- What needs documenting
- Where it should live
- Outline of content

---

## Examples of Good Requests

### Example 1: Clear Problem + Solution

From `scenario-config-builder.md`:

```markdown
## Problem Statement

The codebase currently has **multiple parallel helper methods** that extract 
agent configuration from scenario YAML files. This pattern is error-prone because:

1. **Easy to forget parameters**: When adding a new agent property, developers 
   must remember to add extraction logic in multiple places
2. **No single source of truth**: The same extraction logic is duplicated
3. **Silent failures**: Missing parameters cause subtle bugs

### The Bug This Pattern Caused

When `liquidity_pool` was added to the scenario config schema, the extraction 
was added to the main simulation path but **not** to the bootstrap evaluation path.
```

This is effective because it:
- States the problem clearly
- Explains why it matters
- Gives a concrete example of harm caused

### Example 2: Detailed Acceptance Criteria

From `implement-real-bootstrap-evaluation.md`:

```markdown
## Acceptance Criteria

1. [ ] Initial simulation produces `initial_simulation_output` for LLM context
2. [ ] `TransactionSampler.collect_transactions()` is called after initial simulation
3. [ ] Bootstrap samples use `TransactionSampler.create_samples()` with `method="bootstrap"`
4. [ ] Each bootstrap evaluation uses resampled transactions (not parametric generation)
5. [ ] LLM prompt includes all three event streams
6. [ ] Deterministic scenarios (exp1) continue to work correctly
7. [ ] Tests verify bootstrap is resampling, not regenerating
```

This is effective because each criterion is:
- Specific and testable
- Verifiable by looking at code or running tests
- Independent (can check each one separately)

### Example 3: Clear Before/After

From `scenario-config-builder.md`:

```markdown
### Usage After Migration

```python
# Before (fragile)
evaluator = BootstrapPolicyEvaluator(
    opening_balance=self._get_agent_opening_balance(agent_id),
    credit_limit=self._get_agent_credit_limit(agent_id),
    max_collateral_capacity=self._get_agent_max_collateral_capacity(agent_id),
    liquidity_pool=self._get_agent_liquidity_pool(agent_id),
)

# After (single extraction, can't forget fields)
config = self._scenario_builder.extract_agent_config(agent_id)
evaluator = BootstrapPolicyEvaluator(
    opening_balance=config.opening_balance,
    credit_limit=config.credit_limit,
    max_collateral_capacity=config.max_collateral_capacity,
    liquidity_pool=config.liquidity_pool,
)
```
```

This is effective because:
- Shows concrete code, not abstract description
- Makes the improvement immediately obvious
- Implementer knows exactly what to build

---

## Anti-Patterns to Avoid

### Too Vague

❌ Bad:
```markdown
## Summary
Make the bootstrap evaluation better.

## Acceptance Criteria
- [ ] It works correctly
```

✅ Good:
```markdown
## Summary
Implement actual bootstrap resampling (with replacement from historical data) 
instead of parametric Monte Carlo simulation for policy evaluation.

## Acceptance Criteria
- [ ] Bootstrap samples use `TransactionSampler.create_samples()` with `method="bootstrap"`
- [ ] Each bootstrap evaluation uses resampled transactions (not parametric generation)
```

### No Problem Statement

❌ Bad:
```markdown
## Proposed Solution
Add a ScenarioConfigBuilder class.
```

✅ Good:
```markdown
## Problem Statement
The codebase has 4 separate helper methods that extract agent config, 
leading to bugs when new fields are added to one path but not others.

## Proposed Solution
Add a ScenarioConfigBuilder class that provides a single extraction point.
```

### Missing Context

❌ Bad:
```markdown
## Summary
Fix the bootstrap bug.
```

✅ Good:
```markdown
## Summary
Fix bootstrap evaluation ignoring `liquidity_pool` parameter (commit `c06a880`).

## Related Code
- `api/payment_simulator/experiments/runner/optimization.py` - Missing extraction
- `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` - Receives None
```

---

## Checklist Before Submitting a Request

- [ ] Summary clearly states what and why
- [ ] Problem statement explains current state and its issues
- [ ] Proposed solution includes concrete API/interface examples
- [ ] Acceptance criteria are specific and testable
- [ ] Related files and documentation are referenced
- [ ] Invariants from `patterns-and-conventions.md` are noted if applicable
- [ ] Priority is set appropriately
