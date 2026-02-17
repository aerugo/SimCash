# Hide Mock Label — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P9 — Low
**Effort**: Trivial
**Branch**: `feature/interactive-web-sandbox`

## Summary

Change the inline "mock" text in the reasoning display from plain text to a subtle debug badge (small gray pill with tooltip on hover).

## Critical Invariants

- **INV-UI-12**: Mock indicator must still be present (for debugging), just less prominent

## Current State

In `GameView.tsx`, reasoning entries show `{latest.mock && <span className="text-[10px] text-slate-600">mock</span>}` as plain inline text. This looks like part of the data rather than a debug indicator.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/GameView.tsx` | Modify | Restyle mock indicator |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Restyle mock label to subtle pill badge |
