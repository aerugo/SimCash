# Discussion & Conclusion

## The Complexity Threshold

The most striking finding of this campaign is the existence of a **complexity threshold** at approximately 4-5 banks, beyond which LLM optimization becomes counterproductive. Below this threshold, LLMs achieve dramatic cost reductions (up to 86%). Above it, they actively increase costs and reduce settlement rates.

This threshold likely emerges from the interaction between:
1. **Information overload**: With 5+ banks, the state space becomes too large for the LLM to reason about effectively within a single policy decision
2. **Coordination failure**: Each agent optimizes individually without explicit coordination mechanisms, leading to emergent conflicts
3. **Temporal compounding**: In 25-day runs, small per-day errors compound into large cumulative effects

## Tragedy of the Commons

The complex scenario results exhibit a classic **tragedy of the commons** pattern. Each LLM agent, acting rationally to minimize its own bank's costs, creates externalities that harm the system:

- **Delayed payments** reduce the agent's own holding costs but starve other banks of incoming liquidity
- **Strategic timing** by one agent disrupts the payment flow that others depend on
- **Free-riding on liquidity** is individually optimal but collectively disastrous

The "smart free-rider effect" (Pro performing worse than Flash) further supports this interpretation: a more capable reasoner is better at identifying free-riding opportunities, but this sophistication is precisely what makes the system worse.

## Implications for RTGS Design

### 1. LLM Optimization Has a Role — But a Limited One
For small interbank networks (2-4 participants), LLM-optimized policies can deliver substantial cost savings. Central banks or clearing houses overseeing small bilateral or trilateral arrangements could benefit from AI-assisted liquidity management.

### 2. Complex Systems Need Mechanism Design, Not Just Smarter Agents
The failure mode in complex scenarios isn't that the LLMs are "too dumb" — it's that individual optimization without coordination mechanisms produces bad collective outcomes. Solutions should focus on:
- **Incentive alignment**: Penalty structures that make free-riding costly
- **Information sharing**: Giving agents visibility into system-wide liquidity states
- **Centralized coordination layers**: Hybrid approaches where a central agent coordinates individual optimizers

### 3. Model Capability ≠ System Performance
The Pro-worse-than-Flash finding challenges the assumption that "better models → better outcomes" in multi-agent systems. In adversarial or coordination-dependent settings, more capable agents can produce worse equilibria.

## Limitations

- **Single prompt version**: v0.2 prompt variants were only tested on castro_exp2; the threshold may shift with better prompting
- **No communication**: Agents cannot communicate or negotiate; adding communication channels might shift the threshold
- **Fixed scenarios**: Real RTGS systems have dynamic participant sets and evolving payment patterns
- **GLM data issues**: Pre-bugfix GLM data for complex scenarios was excluded, limiting three-way model comparisons for the most interesting cases

## Future Work

1. **Breaking the threshold**: Can prompt engineering, agent communication, or hybrid centralized/decentralized architectures push the threshold higher?
2. **Mechanism design experiments**: Test penalty structures and information sharing regimes
3. **Larger model evaluation**: Test with GPT-4o, Claude, and other frontier models
4. **Real-world calibration**: Validate against actual RTGS transaction data

## Conclusion

LLMs can optimize payment coordination — but only in simple networks. The Q1 2026 campaign establishes a clear **complexity threshold** at ~4-5 banks, beyond which individual LLM optimization produces a tragedy of the commons. Breaking this threshold is the central challenge for AI-assisted RTGS systems, and will likely require mechanism design innovations rather than simply scaling model capability.
