# Remove Duplicate Launch Button — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P1 — Critical
**Effort**: Low
**Branch**: `feature/interactive-web-sandbox`

## Summary

The "AI Reasoning" toggle section and "Launch Simulation" button at the bottom of `HomeView.tsx` render on ALL tabs, including the Multi-Day Game tab. The Game tab has its own "Start Game" button and its own AI settings. The bottom section should only show on Presets and Custom Builder tabs.

## Critical Invariants

- **INV-UI-1**: Multi-Day Game tab must NOT show the single-run Launch Simulation button
- **INV-UI-2**: Presets and Custom Builder tabs must retain the Launch Simulation button and AI Reasoning toggle
- **INV-UI-3**: No backend changes — purely cosmetic fix

## Current State

In `HomeView.tsx`, the AI Reasoning section and Launch Simulation button are rendered unconditionally after the mode-specific content. The `mode` state variable (`'game' | 'preset' | 'custom'`) is available but not used to gate these elements.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/frontend/src/views/HomeView.tsx` | Modify | Wrap AI Reasoning + Launch button in `mode !== 'game'` conditional |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Conditionally render Launch section based on active tab |
