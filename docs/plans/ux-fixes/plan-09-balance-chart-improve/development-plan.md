# Balance Chart Improvements — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P8 — Low
**Effort**: Low
**Branch**: `feature/interactive-web-sandbox`

## Summary

Improve MiniBalanceChart: increase height from 80px to 160px, add Y-axis labels (dollar amounts), add a color legend, make the SVG responsive.

## Critical Invariants

- **INV-1**: Money is i64 — display as dollars

## Current State

`MiniBalanceChart` in `GameView.tsx` is an 80px-tall SVG with no axis labels, no legend, and minimal padding (5px all sides). Lines are drawn but unidentifiable without color context.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/GameView.tsx` | Modify | Improve MiniBalanceChart component |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Enhance MiniBalanceChart with labels, legend, and responsive sizing |
