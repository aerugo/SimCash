# Iterative Alignment: Castro Initial Liquidity Game

## Goal

Make the policy optimization find the Nash equilibrium for the Castro 2-period Initial Liquidity Game using GPT-5.2 with high reasoning.

**Expected Optimal Outcome (from Castro et al. 2025, Section 6.3):**
- Bank A: Post 0 initial liquidity (ℓ₀^A = 0)
- Bank B: Post 0.20 of collateral capacity (ℓ₀^B = 20000 cents)

**Why this is optimal:**
- Bank B must send 15000 at tick 0 (deadline 1) and 5000 at tick 1 (deadline 2) = 20000 total
- Bank B sends 15000 to Bank A in tick 0 → A receives it (available tick 1 with deferred crediting)
- Bank A's only payment is 15000 at tick 1 to Bank B with deadline 2
- Bank A can use the 15000 received from B to cover its outgoing payment
- Therefore: B posts 20000 (its total outgoing), A posts 0 (uses incoming from B)

## Current State

**Experiment file**: `experiments/castro/experiments/exp1.yaml`
**Scenario file**: `experiments/castro/configs/exp1_2period.yaml`
**Paper reference**: `experiments/castro/papers/castro_et_al.md`

## Gap Analysis

### 1. Excessive Policy Constraint Fields (CRITICAL)

The current `exp1.yaml` allows many fields irrelevant to the simple 2-period game:

**Currently allowed but irrelevant:**
- `queue1_total_value` - No queue dynamics in 2-period game
- `outgoing_queue_size` - Ditto
- `priority` - All transactions have same priority
- `effective_liquidity` - Confuses with balance+collateral

**Should focus on:**
- `system_tick_in_day` - Distinguish t=0 from t=1
- `balance` - Current settlement account balance
- `remaining_collateral_capacity` - For collateral posting decisions
- `max_collateral_capacity` - Total collateral available
- `posted_collateral` - Already posted
- `ticks_to_deadline` - For payment release decisions

### 2. Parameter Simplification Needed

The Castro game has essentially ONE decision: what fraction x₀ ∈ [0,1] of collateral to post at t=0.

**Current parameters (too many):**
- `initial_liquidity_fraction` - Relevant
- `urgency_threshold` - Not needed (fixed payments, fixed deadlines)
- `liquidity_buffer` - Not needed

**Should simplify to just:**
- `initial_liquidity_fraction` - The only decision variable

### 3. Castro Mode Context Not Active

The system prompt builder has Castro mode but it's not being used effectively. Need to:
1. Enable `castro_mode: true` in experiment config
2. Simplify the system prompt to focus on the one-shot liquidity decision

### 4. Cost Rate Calibration

The paper uses abstract rates: r_c = 0.1, r_d = 0.2, r_b = 0.4 (r_c < r_d < r_b)

Current config has:
- `collateral_cost_per_tick_bps: 500` (5% per tick)
- `delay_cost_per_tick_per_cent: 0.1`
- `eod_penalty_per_transaction: 100000`

Need to verify the relationship holds and costs are properly incentivized.

### 5. LLM Prompt Clarity

The LLM needs to understand:
1. This is a ONE-SHOT game at t=0
2. The strategic_collateral_tree MUST post collateral at t=0
3. The payment_tree should always release (no strategic delay)
4. The goal is to minimize total cost

## Development Plan

### Phase 1: Minimal Field Set (TDD)
- Create tests that verify optimal Nash equilibrium
- Reduce `allowed_fields` to only those needed
- Reduce `allowed_parameters` to just `initial_liquidity_fraction`
- Run experiment, document results

### Phase 2: Castro-Specific System Prompt
- Enable and enhance Castro mode in prompt builder
- Add clear explanation of the one-shot liquidity decision
- Include the mathematical model from the paper
- Run experiment, document results

### Phase 3: Seed Policy Optimization
- Create optimal seed policies that match paper structure
- Test that seed policies achieve expected costs
- Verify convergence behavior

### Phase 4: Cost Rate Validation
- Verify cost rates satisfy r_c < r_d < r_b
- Add tests for cost calculations
- Ensure LLM sees cost structure clearly

### Phase 5: Full Integration Testing
- Run full experiment with GPT-5.2 high reasoning
- Compare results to expected Nash equilibrium
- Document any remaining gaps

## Success Criteria

1. **Primary**: Bank A converges to 0 initial liquidity, Bank B to 20000
2. **Secondary**: Total cost approaches theoretical minimum (R_A = 0, R_B = collateral_cost * 20000)
3. **Convergence**: Stable within 10 iterations

## Files to Modify

1. `experiments/castro/experiments/exp1.yaml` - Simplify constraints
2. `experiments/castro/configs/exp1_2period.yaml` - Verify cost rates
3. `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` - Enhance Castro mode
4. `api/tests/ai_cash_mgmt/integration/test_castro_equilibrium.py` - New test file

## Tracking

- **Work Notes**: `docs/plans/iterative-alignment/work_notes.md`
- **Phase Plans**: `docs/plans/iterative-alignment/phases/phase_X.md`
