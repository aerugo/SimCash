# Q1 2026 Experiment Campaign: The Complexity Threshold

## Research Question

Can large language models (LLMs) optimize payment coordination in real-time gross settlement (RTGS) systems? And if so, where do they fail?

The SimCash platform provides a controlled simulation environment for testing whether AI agents can reduce liquidity costs in interbank payment networks by optimizing when to release, delay, or split payments. This paper reports results from a systematic experiment campaign conducted in Q1 2026, spanning **132 experiments** across **3 LLM models** and **10 scenarios** of varying complexity.

## Models Tested

| Model | Description | Provider |
|-------|-------------|----------|
| **Flash** | Gemini 2.0 Flash | Google |
| **Pro** | Gemini 2.0 Pro | Google |
| **GLM** | GLM-4-Flash | Zhipu AI |

## Scenarios

| Scenario | Banks | Complexity | Description |
|----------|-------|------------|-------------|
| [`2b_3t`](https://simcash-487714.web.app/experiment/5c59f15f) | 2 | Simple | 2 banks, 3 payment types |
| [`2b_stress`](https://simcash-487714.web.app/experiment/a36fe08d) | 2 | Simple | 2 banks under stress conditions |
| [`3b_6t`](https://simcash-487714.web.app/experiment/c2994509) | 3 | Medium | 3 banks, 6 payment types |
| [`4b_8t`](https://simcash-487714.web.app/experiment/73e5990a) | 4 | Medium | 4 banks, 8 payment types |
| [`castro_exp2`](https://simcash-487714.web.app/experiment/17bdd52c) | 2 | Medium | Castro replication experiment |
| [`lynx_day`](https://simcash-487714.web.app/experiment/9eaf71b4) | 2 | Simple | Lynx-calibrated day scenario |
| [`liquidity_squeeze`](https://simcash-487714.web.app/experiment/8a46d6e0) | 2 | Stress | Liquidity squeeze conditions |
| [`periodic_shocks`](https://simcash-487714.web.app/experiment/747025f3) | 5+ | Complex | Periodic liquidity shocks, 25 days |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | 6+ | Complex | Large interbank network, 25 days |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | 5+ | Complex | Lehman-crisis calibrated month |

## Experiment Design

Each scenario was run with:
- **Baseline**: Default policies (no LLM optimization)
- **3 models × 3 runs** (r1, r2, r3): To capture variance in LLM behavior
- **v0.2 prompt variants** (castro_exp2 only): Testing improved prompts with compositional strategies (c1-info, c2-floor, c3-guidance, c4-composition)

Simple scenarios run for **10 simulated days**; complex scenarios run for **25 days**.

### Cumulative Settlement Rate

Our primary metric is the **cumulative settlement rate** — the fraction of all arrived payments that were successfully settled across the entire simulation:

$$\text{Cumulative SR} = \frac{\sum_{\text{all days}} \text{total\_settled}}{\sum_{\text{all days}} \text{total\_arrived}}$$

This differs from per-day settlement rates as it captures the full picture across multi-day runs where unsettled payments may carry over.
