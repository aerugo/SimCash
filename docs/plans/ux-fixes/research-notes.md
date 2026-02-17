# Research Notes — SimCash Web Sandbox

Compiled 2026-02-17 from reference docs, papers, and experiment configs.

## 1. SimCash Architecture

### Core Engine (Rust)
- Discrete-time simulation: ticks as atomic time units
- Banks hold balances in settlement accounts
- Transactions arrive with amounts, counterparties, and deadlines
- RTGS settlement with immediate finality
- Two-queue architecture: internal bank queues (strategic) + RTGS central queue (mechanical)
- T2-compliant LSM: bilateral offsetting, multilateral cycle detection
- **Performance**: 1,000+ ticks/sec, 200+ agent scale

### Cost Function
Five cost types (only 3 used in paper experiments):
1. **Liquidity opportunity cost** (`liquidity_cost_per_tick_bps`): Proportional to allocated reserves per tick
2. **Delay penalty** (`delay_cost_per_tick_per_cent`): Per tick per cent of unsettled payment
3. **Deadline penalty** (`deadline_penalty`): Incurred when transactions become overdue
4. **End-of-day penalty** (`eod_penalty_per_transaction`): Large cost for unsettled transactions at day end
5. **Overdraft cost** (`overdraft_bps_per_tick`): Fee for negative balance (not used in paper experiments)

**Key constraint**: r_c < r_d < r_b (liquidity cost < delay cost < penalty cost)

### Policy Trees
- JSON decision trees with 60+ context fields
- Key parameter: `initial_liquidity_fraction` (0.0–1.0)
- Payment tree actions: Release, Hold
- Bank tree actions: PostCollateral, HoldCollateral, NoAction
- Enters engine via `InlineJson` policy config type

### Determinism
- All randomness via xorshift64* seeded RNG
- Same seed = identical results (INV-2)
- Money is always i64 integer cents (INV-1)

## 2. Experiment Framework

### YAML-Driven Configuration
- No Python code required — everything in YAML
- `ExperimentConfig.from_yaml()` loads config
- `GenericExperimentRunner` executes

### Evaluation Modes
1. **Bootstrap** (default): Paired comparison with bootstrap resampling on 3-agent sandbox
2. **Deterministic-Pairwise**: Compare old vs new policy on same seed within iteration
3. **Deterministic-Temporal**: Compare cost across iterations (more efficient, 1 sim/iteration)

### Convergence Detection
- `max_iterations`: Hard cap (default 50)
- `stability_threshold`: Cost stability % (default 5%)
- `stability_window`: Consecutive stable iterations (default 5)
- `improvement_threshold`: Minimum improvement % (default 1%)
- In practice: convergence when policies stop being accepted for stability_window iterations

### Experiment 2 (Paper Config)
- 12 ticks per day
- Poisson arrivals (λ=2.0/tick), LogNormal amounts (μ=10k, σ=5k)
- 2 banks (BANK_A, BANK_B), symmetric setup
- Liquidity pool: 1,000,000 cents ($10,000) per bank
- Bootstrap mode with 50 samples
- 50 iterations max
- Expected equilibrium: both agents in 10–30% range
- **Paper results**: A≈8.5%, B≈6.3% (our replication: A≈8.8%, B≈5.2%)

### Experiment 1 (Deterministic, 2-period)
- 2 ticks, asymmetric payments
- Deterministic-temporal mode
- Expected: A=0%, B=20% (free-rider equilibrium)
- Paper: A=0.1%, B=17% — matches prediction

### Experiment 3 (Symmetric, 3-period)
- 3 ticks, symmetric payments (P^A = P^B = [0.2, 0.2, 0])
- Deterministic-temporal mode
- Expected: symmetric ~20%
- Paper: coordination failures observed (one agent exploits the other)

## 3. AI Cash Management System

### PolicyOptimizer
- Builds 50k+ token prompts with 7 sections:
  1. Header (agent ID, iteration)
  2. Current State (performance metrics, policy params)
  3. Cost Analysis (breakdown by type, rates)
  4. Optimization Guidance (actionable recommendations)
  5. Simulation Output (best/worst seed event traces)
  6. Iteration History (full trajectory)
  7. Parameter Trajectories
  8. Final Instructions
- Retry logic with constraint validation feedback
- Per-agent context — strict information isolation

### ConstraintValidator
- Validates LLM output against `ScenarioConstraints`
- `allowed_parameters`: name, type, min/max
- `allowed_fields`: context fields available to policy tree
- `allowed_actions`: valid actions per tree type

### Bootstrap Evaluation (3-Agent Sandbox)
- SOURCE → AGENT → SINK architecture
- Eliminates inter-agent confounding
- Preserves `settlement_offset` (sufficient statistic for liquidity environment)
- Paired comparison: same N samples for both old and new policy
- Acceptance: mean improvement + CI doesn't cross zero + CV < 0.5

### Risk-Adjusted Acceptance Criteria (Paper)
1. Mean improvement (μ_new < μ_old via paired comparison)
2. Statistical significance (95% CI for delta doesn't cross zero)
3. Variance guard (CV < 0.5)

## 4. LLM Integration

### Provider Config
- Format: `"provider:model"` (e.g., `"openai:gpt-5.2"`, `"anthropic:claude-sonnet-4-5"`)
- pydantic-ai for structured output
- Streaming: `run_stream()` + `stream_text(delta=True)`
- Temperature: 0.0 for experiments (0.5 in paper)
- Max retries: 3
- Timeout: 120s

### Paper LLM Config
- Model: `openai:gpt-5.2`
- Reasoning effort: `high`
- Reasoning summary: `detailed`
- Temperature: 0.5
- Max iterations: 50 per pass
- 3 passes (independent runs) per experiment

## 5. Key Paper Findings

### Convergence Behavior
- Exp1: Mean 10.3 iterations to convergence (100% rate)
- Exp2: 49 iterations (budget termination, 100% — never formally converged)
- Exp3: Mean 7.0 iterations (100% rate)

### Critical Insight: Stability ≠ Optimality
- In deterministic games: agents converge to **coordination failures** (Pareto-dominated)
- Free-rider determined by early aggressive moves
- Stochastic environments (bootstrap evaluation) produced **near-symmetric** allocations without coordination collapse

### Information Isolation
- Each agent sees ONLY own costs, events, policy history
- No counterparty balances, policies, or costs visible
- Only signal about counterparty: incoming payment timing
- Enforced by `filter_events_for_agent()` function

## 6. BIS Working Paper 1310 (Castro et al. 2025)

**Title**: "AI agents for cash management in payment systems"
**Published**: 26 November 2025

### Summary
- Tests whether gen AI (ChatGPT reasoning model) can perform intraday liquidity management
- Simulates payment scenarios with liquidity shocks and competing priorities
- Even without domain-specific training, AI replicates key prudential cash-management practices
- Maintains precautionary liquidity buffers, prioritizes urgent payments
- Balances trade-offs between liquidity costs and settlement delays
- Suggests routine cash-management tasks could be automated using general-purpose LLMs

### Relevance to SimCash
- SimCash builds on this work by implementing a full simulator with iterative optimization
- Goes beyond single-scenario testing to multi-day convergence games
- Uses policy trees (not just text recommendations) fed into actual engine
- Bootstrap evaluation for statistical rigor

## 7. Korinek Paper (AEA, August 2025)

**Title**: "AI Agents for Economic Research"
**Author**: Anton Korinek
**Published**: August 2025 update to "Generative AI for Economic Research" (JEL 61(4))

### Key Themes
1. **From Chatbots to Agents**: Three paradigms — traditional LLMs (System 1), reasoning models (System 2), agentic systems (planning + tools + multi-step)
2. **Deep Research Agents**: Multi-agent architectures that decompose tasks, spawn specialized agents, process hundreds of sources
3. **Vibe Coding**: Programming through natural language (Claude Code, released Feb 2025)
4. **Democratizing Technical Implementation**: Economists can build tools without traditional coding
5. **Building Custom Agents**: Using frameworks like LangGraph

### Relevance to SimCash
- SimCash is exactly the kind of "AI agent for economic research" Korinek describes
- Our LLM agents are autonomous policy optimizers with planning (multi-iteration), tool use (simulation engine), and adaptive strategies
- The paper validates our approach: using LLMs as semi-autonomous research assistants for economic analysis
- Korinek notes agents "struggle to identify frontier-defining papers" — similar limitation to our finding that agents converge but not always optimally

## 8. Web Sandbox Implications

### For Onboarding (Plan 3) ✅ DONE
- Explain RTGS, game loop, `initial_liquidity_fraction`, cost tradeoffs
- Use simple language: "banks decide how much cash to keep ready"
- Mention the r_c < r_d < r_b constraint naturally
- Reference Castro et al. and the idea that AI can learn these strategies

### For Custom Scenario Game Mode (Plan 4) ✅ DONE
- Config must match `SimulationConfig.from_dict()` expected structure
- Key fields: `simulation` (ticks_per_day, num_days, rng_seed), `cost_rates`, `agents`, `payment_schedule`
- Agents need `opening_balance`, `unsecured_cap`, `liquidity_pool`

### Parameter Ranges for Custom Scenarios
- `initial_liquidity_fraction`: 0.0–1.0 (optimal typically 5–30%)
- `liquidity_cost_per_tick_bps`: 50–1000 (paper uses 83)
- `delay_cost_per_tick_per_cent`: 0.1–5.0 (paper uses 0.2)
- `deadline_penalty`: 10000–500000 cents (paper uses 50000)
- `eod_penalty_per_transaction`: 50000–500000 cents (paper uses 100000)
- `liquidity_pool`: 100000–10000000 cents per bank
- `ticks_per_day`: 2–20 (paper exp2 uses 12)
- `num_agents`: 2–5

### For Future Scenarios
- Stochastic arrivals need `arrival_config` on agents (rate_per_tick, amount distribution, counterparty weights, deadline range)
- LSM features available but not tested in paper experiments
- Scenario events (liquidity shocks) possible but not in current web sandbox
