# Discussion & Conclusion

## Interpreting the Complexity Threshold

The central finding of this campaign — that LLM optimization helps below ~4 banks and hurts above ~5 — demands explanation. We propose three interacting mechanisms.

### 1. The Tragedy of the Commons

Intraday liquidity in an RTGS system is a **common-pool resource**. When Bank A commits funds to the settlement process, those funds become available not just for A's own payments but — through the circular flow of interbank obligations — for the entire system. A well-funded system settles efficiently; a liquidity-starved system gridlocks.

Each LLM agent, tasked with minimizing its bank's costs, discovers the individually rational strategy: reduce the initial liquidity fraction, hold cash, and wait for incoming payments from others before releasing outgoing ones. In a 2-bank system, this strategy is self-limiting — if your only counterparty is also holding back, your incoming payments dry up and the feedback is immediate. The state space is small enough for the LLM to reason about this equilibrium.

In a 5+ bank system, the feedback loops are diffuse. Bank A's decision to hold liquidity doesn't immediately affect Bank A's incoming flow — it affects Banks B, C, D, and E, who in turn affect each other and eventually A, but through a chain too long for the LLM to trace within a single policy decision. Each agent sees only that holding back slightly reduces its own costs, never perceiving the system-wide damage.

This is Hardin (1968) in silico. The shared resource is intraday liquidity. The rational herders are LLM agents. The overgrazed commons is the settlement system.

### 2. Objective Misspecification

The tragedy is amplified by a design choice in SimCash's optimization framework. The `is_better_than()` function that evaluates candidate policies compares **cost only**. A candidate policy that settles 60% of payments at lower cost will be preferred over one that settles 95% at higher cost.

This is not a bug — it's a faithful representation of a real failure mode. If you give an AI agent a cost-minimization objective in a payment system, it **will** free-ride on others' liquidity, because free-riding is cheaper. The optimization target and the social objective are misaligned, and the LLM optimizes exactly what it's told to optimize.

The v0.2 experiment series tested whether this could be corrected through prompt engineering:

- **C1 (information only)**: Telling the LLM about settlement rates had **zero effect**. The agent acknowledged the information and continued optimizing for cost.
- **C2 (settlement floor constraint)**: Imposing a hard minimum settlement rate of 80% was the **most effective single intervention**, achieving 100% settlement under Flash while maintaining significant cost reduction.
- **C3 (strategy guidance)**: Describing available policy tools (decision tree branches, timing strategies) helped Flash achieve 100% settlement.
- **C4 (full composition)**: Combining all interventions. Flash achieved 100% settlement with the lowest cost of any condition.

The pattern is unambiguous: **constraints beat information**. Agents respond to binding requirements, not to awareness of consequences. This mirrors a fundamental insight from mechanism design theory — incentive compatibility requires constraints on the action space, not just information about payoffs (Myerson, 1981).

But here's the critical limitation: these prompt improvements worked on the simple Castro Exp2 scenario (2 banks). When we applied the full C4 prompt toolkit to complex scenarios, the results were statistically indistinguishable from v0.1:

| Scenario | v0.1 Flash SR | C4-full Flash SR | Baseline SR |
|----------|--------------|-----------------|-------------|
| Periodic Shocks | 70.3% | 70.4% | 76.6% |
| Large Network | 56.9% | 58.3% | 58.8% |
| Lehman Month | 73.5%* | 59.4% | 68.7% |

The complexity threshold is not a prompt engineering problem. It is a **multi-agent coordination problem** that cannot be solved by improving individual agent behavior.

### 3. The Smart Free-Rider Effect

Perhaps the most counterintuitive finding is that **Pro consistently produces worse collective outcomes than Flash** on complex scenarios:

| Scenario | Flash SR | Pro SR | Baseline SR |
|----------|----------|--------|-------------|
| Large Network | 56.4% | 55.6% | 58.8% |
| Lehman Month | 58.6% | 57.1% | 68.7% |

On cost, Pro also performs worse (higher total system cost) than Flash in 5 of 6 comparable scenarios, and the gap widens on complex scenarios.

We interpret this as follows: Pro's superior reasoning capability makes it a **more effective free-rider**. Where Flash might settle on a moderately aggressive liquidity fraction through pattern matching, Pro can reason about payment timing, anticipate incoming flows, and identify more sophisticated opportunities to delay payments while waiting for counterparty liquidity. Each individual strategy is locally rational — and collectively, the system suffers more because every agent is more effectively extracting from the common pool.

This has a direct analogy in game theory. In a prisoner's dilemma, a "smarter" player who better understands the payoff matrix is not more likely to cooperate — they are more certain to defect. Model capability, without coordination mechanisms, amplifies the coordination failure.

The one exception is `2b_stress`, where Pro outperforms Flash (68,086 cost vs. 164,585; 90% SR vs. 82%). Under stress conditions with only 2 banks, Pro's careful reasoning produces more conservative policies that better navigate payment pressure. This suggests the threshold for the smart free-rider effect is the same complexity threshold: below it, reasoning helps; above it, reasoning enables more effective defection.

## Strategy Poverty

Examining the policy trees produced by all three models across all experiments reveals a striking pattern: **LLMs are parameter optimizers, not strategy architects**.

Of the 11 available policy actions (Release, Delay, Hold, Split, RequestLiquidity, NoAction, plus conditional branches based on queue depth, balance, urgency, time), models consistently use only 5. The bank-level decision tree is universally set to NoAction — no model ever learned to request additional liquidity or adjust reserves during the day.

The primary lever every model discovers is the **initial liquidity fraction** — how much cash to put into the system at the start. Models tune this parameter aggressively (Flash tends toward moderate values around 0.05–0.25; GLM and Pro push toward 0.00–0.05) but rarely construct meaningful conditional logic in the payment decision tree.

This suggests that the bootstrap evaluation framework, while effective at selecting parameters, may not provide sufficient signal for structural strategy innovation. The evaluation compares aggregate cost between two complete policies — it does not decompose which aspects of a policy contributed to improvement. Without this decomposition, the LLM has no guidance for exploring qualitatively different strategies.

## Implications for RTGS Operations

### 1. AI-Assisted Liquidity Management Has a Domain

Our results do not argue against AI in payment systems — they argue for understanding where it works. For small bilateral or trilateral clearing arrangements, LLM-optimized policies deliver genuine value: 55–86% cost reduction with maintained settlement. Central banks overseeing small-participant systems, correspondent banking arrangements, or specialized clearing houses could benefit from AI-assisted liquidity management.

### 2. Multi-Agent Deployment Requires Mechanism Design

Deploying independent AI optimizers for each bank in a large RTGS system would, based on our results, degrade system performance. This is not a capability limitation that will be solved by better models — it is a structural coordination problem.

Solutions from mechanism design theory are directly applicable:
- **Throughput guidelines** (minimum settlement fractions by time of day) — already used in Lynx and other systems — function as the real-world equivalent of our C2 settlement floor constraint
- **Penalty structures** that make liquidity hoarding costly would internalize the externality
- **Centralized coordination layers** where a system-level agent allocates optimization budgets across individual banks could preserve the benefits of AI optimization while preventing the tragedy of the commons
- **Communication protocols** between agents (absent in our experiments) might enable cooperative equilibria, though the mechanism design challenge of preventing strategic misrepresentation remains

### 3. The Evaluation Metric Matters

Our finding that the `is_better_than()` cost-only comparison drives free-riding behavior has direct implications for any deployed system. The objective function given to an AI agent in critical infrastructure is not just a technical choice — it is a **policy choice** with systemic consequences. An AI agent optimizing for the wrong metric in a real RTGS system would produce the same dynamics we observe in simulation: individual cost savings at the expense of system-wide settlement quality.

### 4. Model Capability Is Not the Bottleneck

The smart free-rider effect and the failure of v0.2 prompts on complex scenarios both point to the same conclusion: the binding constraint on AI-assisted payment coordination is not model intelligence but **coordination architecture**. Investing in better models without investing in coordination mechanisms will not improve outcomes — and may worsen them.

## Limitations

Several limitations constrain the generalizability of our findings:

- **No agent communication**: Real banks communicate, negotiate, and have reputations. Our agents are isolated optimizers with no ability to signal, commit, or bargain. Adding communication channels might shift the threshold.

- **Prompt variants tested on simple scenarios only**: The v0.2 conditions (C1–C4) were systematically tested on Castro Exp2 (2 banks) and applied to complex scenarios in only the C4-full configuration. A complete factorial design across all scenarios would strengthen claims about prompt ineffectiveness at scale.

- **Three models from two providers**: Testing GPT-4o, Claude, and open-weight models (Llama, Qwen) would establish whether the threshold is model-universal or architecture-dependent.

- **Static scenarios**: Real RTGS systems have time-varying participant sets, evolving payment patterns, and adaptive human operators. Our scenarios are fixed.

- **GLM exclusion on complex scenarios**: A pre-bugfix data integrity issue required excluding GLM results for complex scenarios, limiting three-way model comparisons where they matter most.

- **Deterministic simulation with stochastic optimization**: SimCash uses a fixed seed (42) for reproducibility, meaning all variance comes from LLM stochasticity. Real payment systems have additional sources of variance.

## Future Work

1. **Breaking the threshold**: Can agent communication, cooperative learning, or hybrid centralized/decentralized architectures push the complexity threshold higher? The mechanism design literature suggests that appropriate information structures and penalty schemes can align incentives in common-pool resource problems — testing these in SimCash is a natural next step.

2. **Objective function design**: Testing multi-objective optimization (cost + settlement rate) and Pareto-frontier approaches to policy evaluation, replacing the current cost-only `is_better_than()`.

3. **Broader model evaluation**: Testing GPT-4o, Claude Sonnet/Opus, and open-weight models to determine whether the complexity threshold and smart free-rider effect are universal properties of LLM-based multi-agent optimization or specific to particular model architectures.

4. **Real-world calibration**: Validating scenario parameters against actual Lynx transaction data and testing whether the threshold shifts with realistic payment distributions.

5. **Dynamic scenarios**: Introducing time-varying participation, stochastic payment generation, and adaptive opponent modeling to move closer to real operational conditions.

## Conclusion

Large language models can optimize payment coordination — but only in simple networks.

This campaign establishes a clear **complexity threshold** at approximately 4–5 banks, beyond which individual LLM optimization produces a computational tragedy of the commons. The mechanism is classical: rational agents competing for a shared resource (intraday liquidity) without coordination mechanisms extract more value than the system can sustain. That general-purpose LLMs, without any game-theoretic training, naturally converge to this outcome validates decades of theory on common-pool resource dilemmas.

The **smart free-rider effect** — where more capable models produce worse collective outcomes — challenges the assumption that AI progress automatically translates to better system performance. In strategic settings, capability without coordination is not just useless but actively harmful.

Our prompt engineering experiments reveal that **constraints outperform information** in guiding AI agent behavior, independently rediscovering the rationale for throughput guidelines and minimum settlement requirements used in real RTGS systems. But these per-agent improvements cannot break the complexity threshold, because the threshold is a property of the multi-agent system, not of individual agent quality.

The path forward for AI-assisted RTGS operations is not better models but better mechanisms: coordination architectures that channel individual AI optimization toward collective efficiency. The central challenge is not making the agents smarter — it is making the game they play one where smart play and good outcomes align.
