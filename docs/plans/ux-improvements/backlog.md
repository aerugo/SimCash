# SimCash UX Improvements Backlog

**Source:** UX Review — Central Banker Persona (2026-02-18)
**Priority:** P0 = critical, P1 = important, P2 = nice-to-have
**Effort:** S = <1h, M = 1-4h, L = 4-8h

---

## Authentication & Onboarding

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 1 | Add `VITE_AUTH_DISABLED` env var to skip Firebase auth in frontend | P0 | S | F1.1 |
| 2 | Create pre-auth landing page with value proposition, features, screenshots | P1 | M | F1.2 |
| 3 | Replace "Access restricted" text with welcoming CTA + contact info | P2 | S | F1.3 |

## Navigation & Information Architecture

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 4 | Consolidate 13 tabs into 3-4 top-level sections with sub-navigation | P1 | L | F2.1 |
| 5 | Rename "Setup" tab to "Home" or "Start" | P2 | S | F2.2 |
| 6 | Add breadcrumb navigation in library detail views | P2 | S | F2.3 |

## Home/Setup View

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 7 | Simplify launch modes — default to Multi-Day Game, hide others behind "Advanced" | P1 | M | F3.1 |
| 8 | Rename "Mock Mode" to "Simulated AI" with clearer description of behavior | P2 | S | F3.2 |
| 9 | Make "How It Works" non-dismissible for first-time users (show at least once per session) | P2 | S | F3.4 |

## Scenario Library

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 10 | Rewrite developer-focused scenario descriptions to be research-focused | P2 | M | F4.2 |
| 11 | Add text search to scenario library | P2 | M | F4.3 |
| 12 | Add tooltip/explanation for "LLM Strategy Depth" (Simple/Standard/Full) | P1 | S | F4.4 |

## Policy Library

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 13 | Build visual decision tree renderer (SVG boxes + arrows) | P1 | L | F5.3 |
| 14 | Add policy comparison view (side-by-side two policies) | P2 | L | F5.2 |

## Create/Editor Views

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 15 | Add syntax highlighting to YAML/JSON editors (CodeMirror or Monaco) | P2 | M | F6.2 |
| 16 | Build visual policy tree builder (drag-and-drop nodes) | P2 | L | F6.3 |

## Game View

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 17 | Add tooltips/explanations for bootstrap statistics (Δ, CV, CI, n) | P1 | S | F7.3 |
| 18 | Add hover tooltips to custom SVG balance charts | P2 | M | F7.4 |
| 19 | Unify chart library — use Recharts everywhere or custom SVG everywhere | P2 | M | F7.5 |
| 20 | Add data export (CSV/JSON/PDF) for game results and charts | P1 | L | F7.6 |
| 21 | Add speed control for auto-run (pause between days option) | P2 | S | F7.7 |

## Documentation

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 22 | Move docs from hardcoded TSX to Markdown files served by backend | P1 | L | F8.2 |
| 23 | Add prominent BIS paper comparison tables to blog posts | P2 | M | F8.3 |
| 24 | Add API documentation page (or link to FastAPI /docs) | P2 | S | F8.4 |

## Auditability & Trust

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 25 | Build payment lifecycle trace view (click payment → see full journey) | P1 | L | F9.2 |
| 26 | Add "re-run day with same seed" button | P2 | S | F9.3 |
| 27 | Add formal validation section to docs (BIS Table 3 comparison, analytical verification) | P1 | M | F9.4 |

## Technical Issues

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 28 | Add exponential backoff + max retries to WebSocket reconnection | P2 | S | F10.2 |
| 29 | Fix unused `detailLoading` state in ScenarioLibraryView (show spinner) | P2 | S | F10.4 |

## Missing Features

| # | Task | Priority | Effort | Finding |
|---|------|----------|--------|---------|
| 30 | ~~Build batch experiment runner~~ → moved to parking lot | — | — | F11.1 |
| 31 | ~~Scenario comparison view~~ → moved to parking lot | — | — | F11.3 |
| 32 | ~~Add game state annotation/note-taking feature~~ | ✅ DONE | M | F11.5 |
| 33 | ~~"Research Mode" toggle~~ | ✅ DONE | M | — |

---

## Summary by Priority

- **P0 (Critical):** 1 task — Auth bypass
- **P1 (Important):** 11 tasks — Landing page, navigation, strategy depth labels, tree renderer, bootstrap stats, data export, docs to markdown, payment tracing, validation results
- **P2 (Nice-to-have):** 21 tasks — Various polish items

## Summary by Effort

- **S (<1h):** 12 tasks
- **M (1-4h):** 11 tasks
- **L (4-8h):** 10 tasks
