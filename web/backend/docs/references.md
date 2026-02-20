# References & Reading

*Papers, documentation, and further resources*

## Primary References

- **Castro et al. (2025)**. *"AI agents for cash management in payment systems."* Bank of Canada Staff Working Paper 2025-35. [Paper ↗](https://www.bankofcanada.ca/2025/11/staff-working-paper-2025-35/)

  The foundational paper. Tests whether gen AI can perform intraday liquidity management in a wholesale payment system. SimCash replicates and extends their experiments.

- **Desai & Aldasoro (2025)**. *"AI agents for cash management in payment systems."* BIS Working Paper No. 1310. [Paper ↗](https://www.bis.org/publ/work1310.htm)

  BIS working paper on AI agents for cash management in payment systems. Explores the application of generative AI to intraday liquidity management in wholesale payment systems.

- **Korinek, A. (2025)**. *"AI Agents for Economic Research."* August 2025 update to *"Generative AI for Economic Research"* (JEL, 2023). [PDF ↗](https://www.aeaweb.org/content/file?id=23290)

  Demystifies AI agents for economists — covering autonomous LLM systems with planning, tool use, and multi-step task execution. Shows how to build research agents using "vibe coding" and frameworks like LangGraph. Directly relevant to SimCash's approach of using LLM agents as autonomous policy optimizers.

## Background Reading

- **ECB TARGET Services**. *T2 (formerly TARGET2) RTGS System.*

  The real-world system that SimCash's settlement mechanics are modeled on. T2 is the Eurosystem's RTGS system for large-value euro payments. SimCash implements T2-compliant liquidity-saving mechanisms.

- **Liquidity-Saving Mechanisms (LSM)**.

  Bilateral offsetting and multilateral cycle detection — the algorithms that let banks settle with less liquidity by netting mutual obligations.

## SimCash Documentation

- [GitHub Repository ↗](https://github.com/aerugo/SimCash) — Source code, README, and development guidelines
- [Reference Documentation ↗](https://github.com/aerugo/SimCash/tree/main/docs/reference) — 80+ pages covering CLI, experiments, AI cash management, policy DSL
- [Game Concept Document ↗](https://github.com/aerugo/SimCash/blob/main/docs/game_concept_doc.md) — The "why" behind the simulation

## Key Concepts Glossary

| Term | Definition |
|------|-----------|
| `RTGS` | Real-Time Gross Settlement — each payment settles individually in real time |
| `LSM` | Liquidity-Saving Mechanism — bilateral/multilateral netting to reduce liquidity needs |
| `initial_liquidity_fraction` | The key parameter: what fraction of the pool to commit (0.0–1.0) |
| `Bootstrap` | Statistical resampling to compare policies across multiple samples |
| `Paired comparison` | Evaluating both policies on identical samples to cancel noise |
| `Nash equilibrium` | Strategy profile where no player gains from unilateral deviation |
| `Pareto efficiency` | No player can be made better off without making another worse off |
| `Free-riding` | Exploiting others' liquidity commitment while minimizing your own |
