# Game Completion Summary — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P10 — Medium
**Effort**: Low
**Branch**: `feature/interactive-web-sandbox`

## Summary

Add a summary panel when game completes (`gameState.is_complete === true`) showing: final fractions per agent, cost reduction from Day 1 to final day, system efficiency improvement, and whether agents appear to have reached equilibrium (fraction changes < threshold).

## Critical Invariants

- **INV-1**: Money is i64 — costs in cents, display as dollars
- **INV-UI-8**: Summary only shows when `is_complete` is true

## Current State

`GameView.tsx` shows a small "COMPLETE" badge when the game finishes. No summary analysis is provided. All the data needed (fraction_history, cost_history, days) is already in `gameState`.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/GameView.tsx` | Modify | Add CompletionSummary component |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Add CompletionSummary panel to GameView |
