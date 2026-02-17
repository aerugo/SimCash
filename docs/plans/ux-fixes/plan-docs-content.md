# Docs Content Plan

**Status**: In Progress
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Current State

The docs section is built with 11 pages across 3 categories. **7 guide pages have full content.** 3 blog posts are stubbed with "coming soon" + topic outlines. The reference page is complete.

## Content To Write

### Priority 1: Blog Posts (high impact, makes the sandbox feel like a real research tool)

#### Blog 1: "Do LLM Agents Converge?"
- **Status**: Stubbed with topic outline
- **Content needed**:
  - Convergence trajectories from all 3 experiments (pull data from paper.tex)
  - Comparison table: Exp1 (10.3 iters), Exp2 (49 iters/budget), Exp3 (7 iters)
  - Visualization: fraction trajectory charts (could embed images from paper_generator/output/charts/)
  - Analysis: why Exp2 never formally converges (bootstrap acceptance criteria are strict)
  - Comparison with Castro's REINFORCE training curves
  - Interactive element: link to sandbox to try it yourself
- **Effort**: Medium (content exists in paper.tex, needs rewriting for blog format)

#### Blog 2: "Coordination Failures in Symmetric Games"
- **Status**: Stubbed
- **Content needed**:
  - Define coordination failure and Pareto dominance simply
  - Walk through Exp3 results: symmetric setup → asymmetric outcome
  - The "early mover" effect with concrete numbers from paper
  - Contrast with Exp2 where bootstrap prevents free-riding
  - Why this matters for real RTGS systems
  - Open question: can prompt engineering prevent this?
- **Effort**: Medium

#### Blog 3: "Bootstrap Evaluation: Why and How"
- **Status**: Stubbed
- **Content needed**:
  - The problem: single comparison unreliable (concrete example with variance numbers)
  - Paired comparison explained with simple diagram
  - 3-agent sandbox architecture (SOURCE → AGENT → SINK) with diagram
  - Settlement timing as sufficient statistic (the formal argument, simplified)
  - Risk-adjusted acceptance criteria (3 conditions)
  - Known limitations (CV overestimation, frozen bilateral feedback)
  - When to use: bootstrap vs deterministic-temporal vs deterministic-pairwise
- **Effort**: High (most technical content, needs clear diagrams/explanations)

### Priority 2: Additional Guide Pages

#### Guide: "Parameter Tuning"
- **Add new page** to Guides section
- Content: recommended ranges for all parameters, how they interact, what happens at extremes
- Include: `liquidity_cost_per_tick_bps`, `delay_cost_per_tick_per_cent`, `deadline_penalty`, `eod_penalty_per_transaction`, `liquidity_pool`, `ticks_per_day`
- Tie each parameter to observable behavior in the sandbox
- **Effort**: Low-Medium

#### Guide: "Reading the Results"
- **Add new page** to Guides section
- Content: how to interpret the game view — cost charts, fraction trajectories, reasoning panels, bootstrap stats
- Walk through a typical 10-day game run annotating what to look for
- When to know convergence happened vs stuck vs diverging
- **Effort**: Medium

### Priority 3: Reference Expansion

#### Reference: "Policy DSL Reference"
- **Add new page** to Reference section
- Full documentation of the JSON policy tree format
- Context fields available (60+), operators, actions
- Example policies from simple to complex
- **Effort**: Medium (content exists in docs/reference/policy/)

#### Reference: "Scenario YAML Format"
- **Add new page** to Reference section
- Complete YAML schema for scenarios
- All agent config fields, cost config, arrival config
- Example: how to build a custom 5-bank scenario with stochastic arrivals
- **Effort**: Low (content exists in docs/reference/orchestrator/)

#### Reference: "API Reference"
- **Add new page** to Reference section
- Document all REST and WebSocket endpoints
- Request/response formats
- Example curl commands
- **Effort**: Medium

### Priority 4: Interactive Elements

#### Embedded Charts
- Add chart images from `paper_generator/output/charts/` to blog posts
- Could also render live charts using recharts (same library as game view)
- **Effort**: Medium per blog post

#### "Try It" Links
- Each blog post should link to the sandbox with a recommended scenario
- E.g., "Coordination Failures" → link to start Exp3-style game
- **Effort**: Low (just add links/buttons)

## Implementation Notes

- All content lives in `web/frontend/src/views/DocsView.tsx` (single file for now)
- As content grows, consider splitting into separate files per page
- Blog posts should eventually support markdown rendering (e.g., react-markdown) for easier authoring
- Images could be served from `web/frontend/public/docs/` directory
- Consider adding a table of contents within long pages

## Execution Order

1. ✅ Build docs skeleton with all pages
2. Write Blog 1 (Convergence) — most data readily available from paper
3. Write Blog 3 (Bootstrap) — most educational value
4. Write Blog 2 (Coordination Failures) — depends on 1 and 3 conceptually
5. Add "Parameter Tuning" guide
6. Add "Reading the Results" guide
7. Add reference pages as needed
8. Add embedded charts and "Try It" links
