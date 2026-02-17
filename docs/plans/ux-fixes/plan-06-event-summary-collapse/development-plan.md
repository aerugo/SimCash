# Event Summary & Collapse — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P7 — Medium
**Effort**: Low
**Branch**: `feature/interactive-web-sandbox`

## Summary

Replace the raw event dump (up to 251 events) in GameView with a compact summary line (e.g., "45 arrivals, 45 settlements, 12 cost accruals...") and a collapsible "Show all events" detail view.

## Critical Invariants

- **INV-UI-9**: Event data must remain accessible (just collapsed, not removed)

## Current State

`GameView.tsx` renders `day.events.slice(0, 100)` in a scrollable div with "... and N more" for overflow. No summary or categorization.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/GameView.tsx` | Modify | Replace raw event list with summary + collapsible detail |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Add event categorization summary and collapsible detail |
