# Onboarding Explainer — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P3 — High
**Effort**: Medium
**Branch**: `feature/interactive-web-sandbox`

## Summary

Add a collapsible "How It Works" explainer section at the top of the Setup page (HomeView). Covers: (1) what RTGS simulation means, (2) the game loop, (3) key parameter `initial_liquidity_fraction`, (4) cost tradeoffs. Helps first-time users understand what they're looking at.

## Critical Invariants

- **INV-UI-6**: Explainer must be collapsible (don't force-scroll returning users)
- **INV-UI-7**: Content must be accurate to SimCash mechanics (i64 money, cost ordering r_c < r_d < r_b)

## Current State

`HomeView.tsx` has a header with title and subtitle but no educational content. Users land on the page with no context about what RTGS means or how the simulation works.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/HomeView.tsx` | Modify | Add collapsible HowItWorks component |
| `web/frontend/src/components/HowItWorks.tsx` | Create | Reusable explainer component |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Create HowItWorks component with collapsible content |
| 2 | Integrate into HomeView and add localStorage persistence for collapse state |
