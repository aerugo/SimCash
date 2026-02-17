# Empty State Guidance — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P6 — Medium
**Effort**: Low
**Branch**: `feature/interactive-web-sandbox`

## Summary

Add placeholder text for Day 0 game state (before any days are simulated): "Ready to start. Click ▶ Next Day to simulate the first trading day. Each day, the AI agent will observe costs and propose improved policies."

## Critical Invariants

- **INV-UI-11**: Guidance shows only when `gameState.days.length === 0`

## Current State

When a game is first created, GameView shows the top bar, progress bar, and empty panels. No guidance on what to do next.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/GameView.tsx` | Modify | Add empty state message |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Add empty state guidance panel |
