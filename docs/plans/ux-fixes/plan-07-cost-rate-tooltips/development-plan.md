# Cost Rate Tooltips — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P3 — Medium
**Effort**: Low
**Branch**: `feature/interactive-web-sandbox`

## Summary

Add hover tooltips to cost rate badges (💰, ⏱, ⚠️) on scenario cards in the Game tab explaining what each parameter means in plain language.

## Critical Invariants

- **INV-UI-10**: Tooltips must be accurate to SimCash cost mechanics

## Current State

Scenario cards in `HomeView.tsx` show cost rates as bare numbers: `💰 333 bps`, `⏱ 0.2/¢/tick`, `⚠️ $500`. No explanation of what these mean.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/HomeView.tsx` | Modify | Add title attributes or tooltip components to cost badges |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Add tooltips to cost rate badges |
