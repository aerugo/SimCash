# Day-Context Reasoning — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P5 — High
**Effort**: Medium
**Branch**: `feature/interactive-web-sandbox`

## Summary

When a user clicks a day in the Day Timeline, the right panel's "Latest Reasoning" section should show that day's reasoning, policies, and costs — not always the final/latest entry. Currently `reasoning_history[aid]` is indexed with `[history.length - 1]` regardless of `selectedDay`.

## Critical Invariants

- **INV-UI-4**: Selected day must control what reasoning is displayed
- **INV-UI-5**: Default (no selection) shows latest day's reasoning (current behavior)
- **INV-1**: Money is i64 — display as dollars in frontend

## Current State

In `GameView.tsx`, the "Latest Reasoning" section always shows `history[history.length - 1]` for each agent. The `selectedDay` state exists and controls the left panel's day costs/balances, but the right panel ignores it.

`reasoning_history` is `Record<string, GameOptimizationResult[]>` where index `i` corresponds to day `i`'s optimization result.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/GameView.tsx` | Modify | Index reasoning by `selectedDay` instead of always using latest |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Index reasoning display by selectedDay |
| 2 | Update section title and add visual indicator for historical vs current |
